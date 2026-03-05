"""
Brunetti Online trilingual Beowulf fetcher and parser.

Fetches the interlinear-glossed dual-language (OE + Modern English) edition from
giuseppebrunetti.eu, parses every gloss entry, assigns half-lines using
caesura-based word counting, and can write the result as CSV.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from assets import get_asset_path
from beowulf_mcp.db import BeoDB, _quote_identifier
from logging_config import get_logger
from text.numbering import FITT_BOUNDARIES

logger = get_logger()

# URL of the trilingual Beowulf page
BRUNETTI_ONLINE_URL = (
    "https://www.giuseppebrunetti.eu/Brunetti/OE/Trilingual-Beowulf/"
    "index.php?lingua=eng"
)

# DuckDB table name
TABLE_NAME = "brunetti"

# CSV output columns
CSV_COLUMNS = [
    "line_id",
    "half_line",
    "token_offset",
    "oe_line",
    "lemma",
    "pos",
    "parse",
    "syntax",
    "gloss_en",
    "gloss_it",
    "pos_description",
]

# Regex for extracting line blocks from the raw HTML.
# Each line has: <span class="nverso">NNNN</span> ... OE text ... <BR>
# followed by <span class="glosse"> ... </span>
_LINE_RE = re.compile(
    r'<span class="nverso">(\d+)</span>(.*?)<BR>',
    re.DOTALL,
)
_GLOSSE_RE = re.compile(
    r'<span class="glosse">(.*?)</span>',
    re.DOTALL,
)

# Regex for individual gloss entries within a glosse block.
# Format: <b>lemma</b> <a title="DESC">CODES </a> <i>English</i> ... / <i>Italian</i>
_GLOSS_ENTRY_RE = re.compile(
    r"<b>(.*?)</b>\s*<a\s+title=\"([^\"]*)\">([^<]*)</a>\s*<i>(.*?)</i>"
    r"\s*(?:&nbsp;)*\s*/\s*<i>(.*?)</i>",
)

# Regex for parsing the POS code string: "pos[-syntax] [parse]"
# pos = letters only, syntax = non-space after hyphen, parse = rest after space
_CODE_RE = re.compile(r"^([a-zA-Z]+)(?:-(\S+))?\s*(.*)$")


def _clean_oe_text(raw: str) -> str:
    """Clean OE text from HTML: decode entities, normalise whitespace."""
    t = raw.replace("&nbsp;", " ").replace("\xa0", " ")
    t = re.sub(r" {3,}", "    ", t)  # caesura → 4 spaces
    return t.strip()


def _count_real_words(text: str) -> int:
    """Count real OE words, skipping dashes, brackets, and lacunae."""
    text = re.sub(r"\[.*?\]", "", text)
    return sum(1 for w in text.split() if re.search(r"[a-zA-ZæþðÆÞÐ]", w))


def _parse_pos_code(codes: str) -> Dict[str, str]:
    """
    Parse a POS code string like 'v-a p3s' or 'np gp' or 'e'.

    Returns dict with keys: pos, parse, syntax.
    """
    codes = codes.strip()
    if not codes:
        return {"pos": "", "parse": "", "syntax": ""}

    m = _CODE_RE.match(codes)
    if not m:
        return {"pos": codes, "parse": "", "syntax": ""}

    return {
        "pos": m.group(1),
        "syntax": m.group(2) or "",
        "parse": m.group(3).strip(),
    }


def parse_glosses(glosse_html: str) -> List[Dict[str, str]]:
    """
    Parse a single glosse block into a list of gloss entries.

    Each entry has keys: lemma, pos, parse, syntax, gloss_en, gloss_it,
    pos_description.
    """
    entries: List[Dict[str, str]] = []
    for m in _GLOSS_ENTRY_RE.finditer(glosse_html):
        lemma = m.group(1).strip()
        pos_description = m.group(2).strip()
        codes = m.group(3)
        gloss_en = m.group(4).strip()
        gloss_it = m.group(5).strip()

        parsed_codes = _parse_pos_code(codes)
        entries.append(
            {
                "lemma": lemma,
                "pos": parsed_codes["pos"],
                "parse": parsed_codes["parse"],
                "syntax": parsed_codes["syntax"],
                "gloss_en": gloss_en,
                "gloss_it": gloss_it,
                "pos_description": pos_description,
            }
        )
    return entries


def parse(html: str) -> List[Dict[str, Any]]:
    """
    Parse the full Brunetti online HTML page.

    Extracts all 3182 lines with their OE text and interlinear glosses, assigns
    half-line (a/b) values using caesura-based word counting

    Args:
        html: Raw HTML content of the trilingual Beowulf page.

    Returns:
        List of token-level dicts (one per gloss entry) with CSV_COLUMNS keys.
    """

    # Extract line-level data
    oe_matches = _LINE_RE.findall(html)
    glosse_matches = _GLOSSE_RE.findall(html)

    if len(oe_matches) != len(glosse_matches):
        logger.warning(
            "Line/gloss count mismatch",
            oe_lines=len(oe_matches),
            glosse_blocks=len(glosse_matches),
        )

    rows: List[Dict[str, Any]] = []
    for (line_id, oe_raw), glosse_html in zip(oe_matches, glosse_matches):
        oe_line = _clean_oe_text(oe_raw)
        glosses = parse_glosses(glosse_html)

        if not glosses:
            continue

        parts = re.split(r"    ", oe_line, maxsplit=1)
        a_count = _count_real_words(parts[0]) if len(parts) == 2 else len(glosses)

        # Cap a_count to actual gloss count
        a_count = min(a_count, len(glosses))

        a_offset = 0
        b_offset = 0
        for i, gloss in enumerate(glosses):
            if i < a_count:
                half = "a"
                a_offset += 1
                offset = a_offset
            else:
                half = "b"
                b_offset += 1
                offset = b_offset

            rows.append(
                {
                    "line_id": line_id,
                    "half_line": half,
                    "token_offset": offset,
                    "oe_line": oe_line,
                    "lemma": gloss["lemma"],
                    "pos": gloss["pos"],
                    "parse": gloss["parse"],
                    "syntax": gloss["syntax"],
                    "gloss_en": gloss["gloss_en"],
                    "gloss_it": gloss["gloss_it"],
                    "pos_description": gloss["pos_description"],
                }
            )

    return rows


class Brunetti:
    """Interface to the Brunetti online trilingual Beowulf backed by DuckDB."""

    def __init__(self, db: Optional[BeoDB] = None) -> None:
        self._db = db or BeoDB()

    def __enter__(self) -> "Brunetti":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self._db.close()

    def load_from_html(self, html: str, force: bool = False) -> int:
        """
        Parse HTML and load into DuckDB.

        Args:
            html: Raw HTML content of the Brunetti trilingual page.
            force: If True, drop and recreate the table.

        Returns:
            Number of rows loaded.
        """
        if self._db.table_exists(TABLE_NAME):
            if not force:
                logger.info("brunetti table already exists, skipping load")
                return self._db.count(TABLE_NAME)
            logger.info("Dropping existing brunetti table")
            self._db.drop_table(TABLE_NAME)

        logger.info("Parsing Brunetti online HTML")
        rows = parse(html)

        self._db.conn.execute(
            f"""
            CREATE TABLE {TABLE_NAME} (
                line_id VARCHAR,
                half_line VARCHAR,
                token_offset INTEGER,
                oe_line VARCHAR,
                lemma VARCHAR,
                pos VARCHAR,
                parse VARCHAR,
                syntax VARCHAR,
                gloss_en VARCHAR,
                gloss_it VARCHAR,
                pos_description VARCHAR
            )
        """
        )

        for row in rows:
            self._db.conn.execute(
                f"INSERT INTO {TABLE_NAME} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [row[col] for col in CSV_COLUMNS],
            )

        row_count = self._db.count(TABLE_NAME)
        logger.info("Loaded Brunetti online", row_count=row_count)
        return row_count

    def load(self, url: str = BRUNETTI_ONLINE_URL, force: bool = False) -> int:
        """
        Fetch HTML from URL and load into DuckDB.

        Args:
            url: URL to fetch. Defaults to the Brunetti trilingual page.
            force: If True, drop and recreate the table.

        Returns:
            Number of rows loaded.
        """
        if self._db.table_exists(TABLE_NAME) and not force:
            logger.info("brunetti table already exists, skipping load")
            return self._db.count(TABLE_NAME)

        logger.info("Fetching Brunetti online HTML", url=url)
        response = requests.get(url, timeout=60)
        response.encoding = "utf-8"
        response.raise_for_status()
        return self.load_from_html(response.text, force=force)

    def count(self) -> int:
        """Return the number of token rows in the table."""
        return self._db.count(TABLE_NAME)

    def get_line(self, line_id: str) -> List[dict]:
        """Get all glosses for a line. line_id is zero-padded (e.g. '0001')."""
        cols = ", ".join(CSV_COLUMNS)
        result = self._db.conn.execute(
            f"SELECT {cols} FROM {TABLE_NAME} WHERE line_id = ? "
            f"ORDER BY half_line, token_offset",
            [line_id],
        ).fetchall()
        return [dict(zip(CSV_COLUMNS, row)) for row in result]

    def get_by_line(self, line_id: str) -> List[dict]:
        """Get all tokens for a line. Alias for get_line()."""
        return self.get_line(line_id)

    def get_lines(self, start: int = 1, end: Optional[int] = None) -> List[dict]:
        """Get all glosses for a range of lines."""
        cols = ", ".join(CSV_COLUMNS)
        start_id = str(start).zfill(4)
        if end is None:
            result = self._db.conn.execute(
                f"SELECT {cols} FROM {TABLE_NAME} WHERE line_id >= ? "
                f"ORDER BY line_id, half_line, token_offset",
                [start_id],
            ).fetchall()
        else:
            end_id = str(end).zfill(4)
            result = self._db.conn.execute(
                f"SELECT {cols} FROM {TABLE_NAME} "
                f"WHERE line_id >= ? AND line_id <= ? "
                f"ORDER BY line_id, half_line, token_offset",
                [start_id, end_id],
            ).fetchall()
        return [dict(zip(CSV_COLUMNS, row)) for row in result]

    def get_by_fitt(self, fitt_id: str) -> List[dict]:
        """
        Get all tokens for a given fitt using FITT_BOUNDARIES line ranges.

        Args:
            fitt_id: The fitt number as a zero-padded string (e.g. '01').

        Returns:
            List of token rows for that fitt.
        """
        fitt_num = int(fitt_id)
        if fitt_num < 0 or fitt_num >= len(FITT_BOUNDARIES):
            return []
        start_line, end_line, _ = FITT_BOUNDARIES[fitt_num]
        return self.get_lines(start_line, end_line)

    def lookup(self, lemma: str, oper: str = "=") -> List[dict]:
        """
        Look up tokens by lemma.

        Args:
            lemma: The Old English lemma to look up.
            oper: SQL operator to use for matching (i.e., '=' or 'LIKE')

        Returns:
            List of matching token rows as dictionaries.
        """
        if oper.upper() not in ["=", "LIKE"]:
            raise ValueError(f"Invalid operator: {oper}")

        cols = ", ".join(CSV_COLUMNS)
        lemma_col = _quote_identifier("lemma")
        result = self._db.conn.execute(
            f"SELECT {cols} FROM {TABLE_NAME} WHERE {lemma_col} {oper.upper()} ? "
            f"ORDER BY line_id, half_line, token_offset",
            [lemma],
        ).fetchall()
        return [dict(zip(CSV_COLUMNS, row)) for row in result]

    def lookup_like(self, pattern: str) -> List[dict]:
        """Look up lemmas matching a SQL LIKE pattern."""
        return self.lookup(pattern, oper="LIKE")

    def search(self, term: str, column: Optional[str] = None) -> List[dict]:
        """
        Search for a term in the gloss data (case-insensitive).

        Args:
            term: Search term.
            column: Restrict to a specific column, or None for all text columns.
        """
        cols = ", ".join(CSV_COLUMNS)
        searchable = ["lemma", "gloss_en", "gloss_it", "oe_line"]

        if column and column in CSV_COLUMNS:
            where = f"LOWER({column}) LIKE LOWER(?)"
            params = [f"%{term}%"]
        else:
            clauses = [f"LOWER({c}) LIKE LOWER(?)" for c in searchable]
            where = " OR ".join(clauses)
            params = [f"%{term}%"] * len(searchable)

        result = self._db.conn.execute(
            f"SELECT {cols} FROM {TABLE_NAME} WHERE {where} "
            f"ORDER BY line_id, half_line, token_offset",
            params,
        ).fetchall()
        return [dict(zip(CSV_COLUMNS, row)) for row in result]

    def write_csv(self, output_path: Optional[Path] = None) -> Path:
        """
        Write the loaded data to a CSV file.

        Args:
            output_path: Where to write. Defaults to output/brunetti.csv.

        Returns:
            The path written to.
        """
        if output_path is None:
            output_path = Path("output") / "brunetti.csv"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        cols = ", ".join(CSV_COLUMNS)
        result = self._db.conn.execute(
            f"SELECT {cols} FROM {TABLE_NAME} "
            f"ORDER BY line_id, half_line, token_offset"
        ).fetchall()

        rows = [dict(zip(CSV_COLUMNS, row)) for row in result]

        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

        logger.info("Wrote CSV", path=str(output_path), rows=len(rows))
        return output_path

    @property
    def db(self) -> BeoDB:
        return self._db


# Module-level convenience functions
_default_brunetti: Optional[Brunetti] = None


def get_brunetti() -> Brunetti:
    """Get the default Brunetti instance."""
    global _default_brunetti
    if _default_brunetti is None:
        _default_brunetti = Brunetti()
    return _default_brunetti


def load(url: str = BRUNETTI_ONLINE_URL, force: bool = False) -> int:
    """Fetch and load the Brunetti online data into DuckDB."""
    return get_brunetti().load(url, force)


def lookup(lemma: str) -> List[dict]:
    """Look up tokens by lemma in the Brunetti data."""
    return get_brunetti().lookup(lemma)


def lookup_like(pattern: str) -> List[dict]:
    """Look up lemmas matching a SQL LIKE pattern."""
    return get_brunetti().lookup_like(pattern)


def search(term: str, column: Optional[str] = None) -> List[dict]:
    """Search for a term in the Brunetti data."""
    return get_brunetti().search(term, column)


def get_line(line_id: str) -> List[dict]:
    """Get all glosses for a line by line_id."""
    return get_brunetti().get_line(line_id)


def get_by_line(line_id: str) -> List[dict]:
    """Get all tokens for a line number."""
    return get_brunetti().get_by_line(line_id)


def get_by_fitt(fitt_id: str) -> List[dict]:
    """Get all tokens for a fitt."""
    return get_brunetti().get_by_fitt(fitt_id)


def get_lines(start: int = 1, end: Optional[int] = None) -> List[dict]:
    """Get all glosses for a range of lines."""
    return get_brunetti().get_lines(start, end)


def write_csv(output_path: Optional[Path] = None) -> Path:
    """Write loaded data to CSV."""
    return get_brunetti().write_csv(output_path)
