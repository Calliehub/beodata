"""Battle of Brunanburh source from sacred-texts.com, backed by DuckDB."""

import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from assets import read_asset_text
from beowulf_mcp.db import BeoDB
from logging_config import get_logger

logger = get_logger()

# Asset filename
BRUNANBURH_ASSET = "brunanburh.html"

# Table name for this source
TABLE_NAME = "brunanburh"


def parse(html: str) -> List[Dict[str, Any]]:
    """
    Parse the sacred-texts.com Brunanburh HTML and extract OE verse lines.

    The HTML uses <dl>/<dt>/<dd> structure where <dt> elements hold line numbers
    (every 5th line) and <dd> elements hold verse lines separated by <br> tags.

    Args:
        html: Raw HTML content.

    Returns:
        List of dicts with 'line' (int) and 'oe' (str) keys.
    """
    soup = BeautifulSoup(html, "html.parser")
    dl = soup.find("dl")
    if not dl or not isinstance(dl, Tag):
        logger.error("No <dl> element found in Brunanburh HTML")
        return []

    lines: List[Dict[str, Any]] = []
    current_line = 0

    # Walk through <dt>/<dd> pairs
    for child in dl.children:
        if not isinstance(child, Tag):
            continue

        if child.name == "dt":
            # <dt> holds the starting line number for the next <dd> block.
            # The very first <dt> is empty, meaning line 1.
            dt_text = child.get_text(strip=True)
            if dt_text:
                current_line = int(dt_text)
            else:
                current_line = 1

        elif child.name == "dd":
            # Split the <dd> content on <br> tags to get individual verse lines.
            inner_html = child.decode_contents()
            parts = re.split(r"<br\s*/?>", inner_html)

            for part in parts:
                text = BeautifulSoup(part, "html.parser").get_text()
                # Normalise: nbsp → space, collapse multi-space runs to 4 (caesura)
                text = text.replace("\xa0", " ")
                text = re.sub(r" {2,}", "    ", text)
                text = text.strip()
                if not text:
                    continue

                lines.append({"line": current_line, "oe": text})
                current_line += 1

    return lines


class Brunanburh:
    """Interface to the Battle of Brunanburh text backed by DuckDB."""

    def __init__(self, db: Optional[BeoDB] = None) -> None:
        self._db = db or BeoDB()

    def __enter__(self) -> "Brunanburh":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self._db.close()

    def load(self, force: bool = False) -> int:
        """
        Load Brunanburh text from the asset HTML into DuckDB.

        Args:
            force: If True, drop and recreate the table even if it exists.

        Returns:
            Number of rows loaded.
        """
        if self._db.table_exists(TABLE_NAME):
            if not force:
                logger.info("brunanburh table already exists, skipping load")
                return self._db.count(TABLE_NAME)
            logger.info("Dropping existing brunanburh table")
            self._db.drop_table(TABLE_NAME)

        html = read_asset_text(BRUNANBURH_ASSET)
        logger.info("Parsing Brunanburh HTML")

        lines = parse(html)

        self._db.conn.execute(
            f"""
            CREATE TABLE {TABLE_NAME} (
                line INTEGER PRIMARY KEY,
                oe VARCHAR
            )
        """
        )

        for line_data in lines:
            self._db.conn.execute(
                f"INSERT INTO {TABLE_NAME} (line, oe) VALUES (?, ?)",
                [line_data["line"], line_data["oe"]],
            )

        row_count = self._db.count(TABLE_NAME)
        schema = self._db.get_schema(TABLE_NAME)
        logger.info("Loaded Brunanburh", row_count=row_count, schema=schema)
        return row_count

    def count(self) -> int:
        """Return the number of lines in the table."""
        return self._db.count(TABLE_NAME)

    def get_line(self, line_number: int) -> Optional[dict]:
        """Get a specific line by number."""
        result = self._db.conn.execute(
            f"SELECT line, oe FROM {TABLE_NAME} WHERE line = ?", [line_number]
        ).fetchone()

        if result:
            return {"line": result[0], "oe": result[1]}
        return None

    def get_lines(self, start: int = 1, end: Optional[int] = None) -> List[dict]:
        """Get a range of lines."""
        if end is None:
            result = self._db.conn.execute(
                f"SELECT line, oe FROM {TABLE_NAME} WHERE line >= ? ORDER BY line",
                [start],
            ).fetchall()
        else:
            result = self._db.conn.execute(
                f"SELECT line, oe FROM {TABLE_NAME} WHERE line >= ? AND line <= ? ORDER BY line",
                [start, end],
            ).fetchall()

        return [{"line": row[0], "oe": row[1]} for row in result]

    def search(self, term: str) -> List[dict]:
        """Search for a term in the Old English text (case-insensitive)."""
        result = self._db.conn.execute(
            f"SELECT line, oe FROM {TABLE_NAME} WHERE LOWER(oe) LIKE LOWER(?) ORDER BY line",
            [f"%{term}%"],
        ).fetchall()

        return [{"line": row[0], "oe": row[1]} for row in result]

    @property
    def db(self) -> BeoDB:
        return self._db


# Module-level convenience functions
_default_brunanburh: Optional[Brunanburh] = None


def get_brunanburh() -> Brunanburh:
    """Get the default Brunanburh instance."""
    global _default_brunanburh
    if _default_brunanburh is None:
        _default_brunanburh = Brunanburh()
    return _default_brunanburh


def load(force: bool = False) -> int:
    """Load the Brunanburh text into DuckDB."""
    return get_brunanburh().load(force)


def get_line(line_number: int) -> Optional[dict]:
    """Get a specific line by number."""
    return get_brunanburh().get_line(line_number)


def get_lines(start: int = 1, end: Optional[int] = None) -> List[dict]:
    """Get a range of lines."""
    return get_brunanburh().get_lines(start, end)


def search(term: str) -> List[dict]:
    """Search for a term in the Old English text."""
    return get_brunanburh().search(term)
