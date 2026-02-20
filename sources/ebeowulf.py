"""eBeowulf edition interface backed by DuckDB."""

import re
from typing import List, Optional

from assets import get_asset_path
from beowulf_mcp.db import BeoDB
from logging_config import get_logger

logger = get_logger()

# Asset filename
EBEOWULF_ASSET = "ebeowulf.txt"

# Table name for this source
TABLE_NAME = "ebeowulf"


def parse_line(raw: str) -> Optional[dict]:
    """
    Parse a single line from the eBeowulf text file.

    Expected format: "<line_number> <OE text>"

    Args:
        raw: A raw line from the text file.

    Returns:
        Dict with 'line' (int) and 'oe' (str) keys, or None if unparseable.
    """
    raw = raw.rstrip("\n")
    if not raw.strip():
        return None

    match = re.match(r"^(\d+)\s+(.*)$", raw)
    if not match:
        return None

    return {"line": int(match.group(1)), "oe": match.group(2)}


class EBeowulf:
    """Interface to the eBeowulf edition."""

    def __init__(self, db: Optional[BeoDB] = None) -> None:
        """
        Initialize the eBeowulf interface.

        Args:
            db: BeoDB instance. Defaults to BeoDB() using the configured DB_PATH.
        """
        self._db = db or BeoDB()

    def __enter__(self) -> "EBeowulf":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self._db.close()

    def load_from_txt(self, force: bool = False) -> int:
        """
        Load eBeowulf text from the asset file into DuckDB.

        Args:
            force: If True, drop and recreate the table even if it exists.

        Returns:
            Number of rows loaded.
        """
        if self._db.table_exists(TABLE_NAME):
            if not force:
                logger.info("ebeowulf table already exists, skipping load")
                return self._db.count(TABLE_NAME)
            logger.info("Dropping existing ebeowulf table")
            self._db.drop_table(TABLE_NAME)

        txt_path = get_asset_path(EBEOWULF_ASSET)
        logger.info("Loading eBeowulf from TXT", txt_path=str(txt_path))

        # Create the table
        self._db.conn.execute(
            f"""
            CREATE TABLE {TABLE_NAME} (
                line INTEGER PRIMARY KEY,
                oe VARCHAR
            )
        """
        )

        # Parse and insert lines
        with open(txt_path, encoding="utf-8") as f:
            for raw_line in f:
                parsed = parse_line(raw_line)
                if parsed:
                    self._db.conn.execute(
                        f"INSERT INTO {TABLE_NAME} (line, oe) VALUES (?, ?)",
                        [parsed["line"], parsed["oe"]],
                    )

        row_count = self._db.count(TABLE_NAME)
        schema = self._db.get_schema(TABLE_NAME)
        logger.info("Loaded eBeowulf", row_count=row_count, schema=schema)
        return row_count

    def count(self) -> int:
        """Return the number of lines in the table."""
        return self._db.count(TABLE_NAME)

    def get_line(self, line_number: int) -> Optional[dict]:
        """
        Get a specific line by number.

        Args:
            line_number: The line number to retrieve.

        Returns:
            Dictionary with 'line' and 'oe' keys, or None if not found.
        """
        result = self._db.conn.execute(
            f"SELECT line, oe FROM {TABLE_NAME} WHERE line = ?", [line_number]
        ).fetchone()

        if result:
            return {"line": result[0], "oe": result[1]}
        return None

    def get_lines(self, start: int = 1, end: Optional[int] = None) -> List[dict]:
        """
        Get a range of lines.

        Args:
            start: Starting line number (inclusive).
            end: Ending line number (inclusive). If None, returns all from start.

        Returns:
            List of dictionaries with 'line' and 'oe' keys.
        """
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
        """
        Search for a term in the Old English text.

        Args:
            term: The term to search for (case-insensitive contains).

        Returns:
            List of matching lines.
        """
        result = self._db.conn.execute(
            f"SELECT line, oe FROM {TABLE_NAME} WHERE LOWER(oe) LIKE LOWER(?) ORDER BY line",
            [f"%{term}%"],
        ).fetchall()

        return [{"line": row[0], "oe": row[1]} for row in result]

    @property
    def db(self) -> BeoDB:
        return self._db


# Module-level convenience functions
_default_ebeowulf: Optional[EBeowulf] = None


def get_ebeowulf() -> EBeowulf:
    """Get the default EBeowulf instance."""
    global _default_ebeowulf
    if _default_ebeowulf is None:
        _default_ebeowulf = EBeowulf()
    return _default_ebeowulf


def load(force: bool = False) -> int:
    """Load the eBeowulf text into DuckDB."""
    return get_ebeowulf().load_from_txt(force)


def get_line(line_number: int) -> Optional[dict]:
    """Get a specific line by number."""
    return get_ebeowulf().get_line(line_number)


def get_lines(start: int = 1, end: Optional[int] = None) -> List[dict]:
    """Get a range of lines."""
    return get_ebeowulf().get_lines(start, end)


def search(term: str) -> List[dict]:
    """Search for a term in the Old English text."""
    return get_ebeowulf().search(term)
