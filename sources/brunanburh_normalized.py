"""Battle of Brunanburh (CLASP normalized edition) backed by DuckDB."""

import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from assets import read_asset_text
from beowulf_mcp.db import BeoDB
from logging_config import get_logger

logger = get_logger()

# Asset filename
BRUNANBURH_NORMALIZED_ASSET = "brunanburh_normalized.html"

# Table name for this source
TABLE_NAME = "brunanburh_normalized"


def _extract_span_text(span: Tag) -> str:
    """
    Extract verse text from a corepoem or normed span.

    Words live in <a> tags; the caesura is <span class="caesura">||</span>.
    Words are joined with spaces, the caesura becomes 4 spaces.
    """
    parts: List[str] = []
    for child in span.children:
        if isinstance(child, Tag):
            if child.name == "a":
                parts.append(child.get_text(strip=True))
            elif "caesura" in (child.get("class") or []):
                parts.append("||")
        # ignore NavigableStrings (whitespace noise between tags)

    # Join words with spaces, then replace the caesura marker with 4 spaces
    text = " ".join(parts)
    text = re.sub(r"\s*\|\|\s*", "    ", text)
    return text.strip()


def parse(html: str) -> List[Dict[str, Any]]:
    """
    Parse the CLASP Brunanburh normalized HTML.

    Each <tr> in the withrefs table holds one verse line with a corepoem span
    (original OE) and a normed span (normalized OE with macrons and punctuation).

    Args:
        html: Raw HTML content.

    Returns:
        List of dicts with 'line' (int), 'oe' (str), and 'normed' (str) keys.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="withrefs")
    if not table or not isinstance(table, Tag):
        logger.error("No <table class='withrefs'> found in CLASP HTML")
        return []

    lines: List[Dict[str, Any]] = []

    for row in table.find_all("tr"):
        if not isinstance(row, Tag):
            continue

        td_line = row.find("td", class_="line")
        if not td_line or not isinstance(td_line, Tag):
            continue

        line_id = td_line.get("id")
        if not line_id:
            continue
        line_number = int(line_id)

        corepoem = td_line.find("span", class_="corepoem")
        normed = td_line.find("span", class_="normed")

        oe_text = _extract_span_text(corepoem) if isinstance(corepoem, Tag) else ""
        normed_text = _extract_span_text(normed) if isinstance(normed, Tag) else ""

        lines.append({"line": line_number, "oe": oe_text, "normed": normed_text})

    return lines


class BrunanburhNormalized:
    """Interface to the CLASP normalized Brunanburh text backed by DuckDB."""

    def __init__(self, db: Optional[BeoDB] = None) -> None:
        self._db = db or BeoDB()

    def __enter__(self) -> "BrunanburhNormalized":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self._db.close()

    def load(self, force: bool = False) -> int:
        """
        Load CLASP Brunanburh text from the asset HTML into DuckDB.

        Args:
            force: If True, drop and recreate the table even if it exists.

        Returns:
            Number of rows loaded.
        """
        if self._db.table_exists(TABLE_NAME):
            if not force:
                logger.info("brunanburh_normalized table already exists, skipping load")
                return self._db.count(TABLE_NAME)
            logger.info("Dropping existing brunanburh_normalized table")
            self._db.drop_table(TABLE_NAME)

        html = read_asset_text(BRUNANBURH_NORMALIZED_ASSET)
        logger.info("Parsing CLASP Brunanburh normalized HTML")

        lines = parse(html)

        self._db.conn.execute(
            f"""
            CREATE TABLE {TABLE_NAME} (
                line INTEGER PRIMARY KEY,
                oe VARCHAR,
                normed VARCHAR
            )
        """
        )

        for line_data in lines:
            self._db.conn.execute(
                f"INSERT INTO {TABLE_NAME} (line, oe, normed) VALUES (?, ?, ?)",
                [line_data["line"], line_data["oe"], line_data["normed"]],
            )

        row_count = self._db.count(TABLE_NAME)
        schema = self._db.get_schema(TABLE_NAME)
        logger.info("Loaded Brunanburh normalized", row_count=row_count, schema=schema)
        return row_count

    def count(self) -> int:
        """Return the number of lines in the table."""
        return self._db.count(TABLE_NAME)

    def get_line(self, line_number: int) -> Optional[dict]:
        """Get a specific line by number."""
        result = self._db.conn.execute(
            f"SELECT line, oe, normed FROM {TABLE_NAME} WHERE line = ?", [line_number]
        ).fetchone()

        if result:
            return {"line": result[0], "oe": result[1], "normed": result[2]}
        return None

    def get_lines(self, start: int = 1, end: Optional[int] = None) -> List[dict]:
        """Get a range of lines."""
        if end is None:
            result = self._db.conn.execute(
                f"SELECT line, oe, normed FROM {TABLE_NAME} WHERE line >= ? ORDER BY line",
                [start],
            ).fetchall()
        else:
            result = self._db.conn.execute(
                f"SELECT line, oe, normed FROM {TABLE_NAME} WHERE line >= ? AND line <= ? ORDER BY line",
                [start, end],
            ).fetchall()

        return [{"line": row[0], "oe": row[1], "normed": row[2]} for row in result]

    def search(self, term: str) -> List[dict]:
        """Search for a term in OE or normalized text (case-insensitive)."""
        result = self._db.conn.execute(
            f"""SELECT line, oe, normed FROM {TABLE_NAME}
               WHERE LOWER(oe) LIKE LOWER(?) OR LOWER(normed) LIKE LOWER(?)
               ORDER BY line""",
            [f"%{term}%", f"%{term}%"],
        ).fetchall()

        return [{"line": row[0], "oe": row[1], "normed": row[2]} for row in result]

    def search_oe(self, term: str) -> List[dict]:
        """Search for a term in the original OE text (case-insensitive)."""
        result = self._db.conn.execute(
            f"SELECT line, oe, normed FROM {TABLE_NAME} WHERE LOWER(oe) LIKE LOWER(?) ORDER BY line",
            [f"%{term}%"],
        ).fetchall()

        return [{"line": row[0], "oe": row[1], "normed": row[2]} for row in result]

    def search_normed(self, term: str) -> List[dict]:
        """Search for a term in the normalized text (case-insensitive)."""
        result = self._db.conn.execute(
            f"SELECT line, oe, normed FROM {TABLE_NAME} WHERE LOWER(normed) LIKE LOWER(?) ORDER BY line",
            [f"%{term}%"],
        ).fetchall()

        return [{"line": row[0], "oe": row[1], "normed": row[2]} for row in result]

    @property
    def db(self) -> BeoDB:
        return self._db


# Module-level convenience functions
_default_instance: Optional[BrunanburhNormalized] = None


def get_brunanburh_normalized() -> BrunanburhNormalized:
    """Get the default BrunanburhNormalized instance."""
    global _default_instance
    if _default_instance is None:
        _default_instance = BrunanburhNormalized()
    return _default_instance


def load(force: bool = False) -> int:
    """Load the CLASP Brunanburh normalized text into DuckDB."""
    return get_brunanburh_normalized().load(force)


def get_line(line_number: int) -> Optional[dict]:
    """Get a specific line by number."""
    return get_brunanburh_normalized().get_line(line_number)


def get_lines(start: int = 1, end: Optional[int] = None) -> List[dict]:
    """Get a range of lines."""
    return get_brunanburh_normalized().get_lines(start, end)


def search(term: str) -> List[dict]:
    """Search for a term in OE or normalized text."""
    return get_brunanburh_normalized().search(term)
