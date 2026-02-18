"""
Beowulf text processing module for heorot.dk data.

This module handles parsing of the heorot.dk HTML format and persistence to DuckDB.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup, Tag

from db import BeoDB
from logging_config import get_logger

# URL of our Beowulf text (messy HTML)
HEOROT_URL = "https://heorot.dk/beowulf-rede-text.html"

# Table name for this source
TABLE_NAME = "heorot"

logger = get_logger()


def normalize_text(text: str) -> str:
    """
    Normalize text by converting line breaks to spaces and collapsing whitespace.

    Args:
        text: Raw text from HTML parsing

    Returns:
        Normalized text with consistent spacing
    """
    # Convert HTML entities to spaces (like &nbsp;)
    text = text.replace("&nbsp;", " ")

    # Convert line breaks and other whitespace to single spaces
    text = re.sub(r"\s+", " ", text)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


def parse(html: str) -> List[Dict[str, Any]]:
    """
    Parse HTML content and extract Beowulf text lines.

    Args:
        html: HTML content to parse

    Returns:
        List of dictionaries containing line data with 'line', 'OE', and 'ME' keys
    """
    current_line_number = 0
    soup = BeautifulSoup(html, "html.parser")

    # Extract table or divs containing the two columns
    # Use natural 1-based numbering in the array of lines
    lines: List[Dict[str, Any]] = [{"line": 0, "OE": "", "ME": ""}]

    tables = soup.find_all("table", class_="c15")

    if len(tables) > 0:
        for table in tables:
            if isinstance(table, Tag):
                table_rows = table.find_all("tr")
            else:
                continue
            last_oe = None

            for row in table_rows:
                if not isinstance(row, Tag):
                    continue
                note_divs = row.find_all("div")
                if len(note_divs) > 0:
                    for note_div in note_divs:
                        if note_div.get("class") != [
                            "c35"
                        ]:  # malformation at line 1066 of the Heorot HTML
                            note_div.decompose()

                # Find all span elements with class 'c7' in this row
                columns = row.find_all("span", class_="c7")

                if len(columns) >= 2:
                    if len(columns) > 2:
                        logger.debug(
                            "long row found",
                            line=current_line_number + 1,
                            cols=len(columns),
                        )

                    # Take first and last span with class 'c7' to ensure we get OE and ME
                    oe_text = columns[0]
                    me_text = columns[-1]

                    if oe_text == last_oe:  # skip dupes
                        continue
                    else:
                        last_oe = oe_text

                    # Remove <a> tags
                    for tag in oe_text.find_all("a"):
                        tag.unwrap()
                    for tag in me_text.find_all("a"):
                        tag.unwrap()

                    current_line_number += 1

                    # Get raw text and normalize it
                    oe_raw = oe_text.get_text(strip=False)
                    me_raw = me_text.get_text(strip=False)

                    # Normalize the text to handle line breaks and whitespace
                    oe_normalized = normalize_text(oe_raw)
                    me_normalized = normalize_text(me_raw)

                    # Handle the special case of '--' which should be preserved as space
                    oe_final = oe_normalized.replace("--", " ")
                    me_final = me_normalized.replace("--", " ")

                    lines.append(
                        {"line": current_line_number, "OE": oe_final, "ME": me_final}
                    )

    return lines


class Heorot:
    """Interface to the Beowulf text from heorot.dk backed by DuckDB."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """
        Initialize the Heorot interface.

        Args:
            db_path: Path to the DuckDB database file. Defaults to beodb.duckdb
                    in the assets directory.
        """
        self._db = BeoDB(db_path)

    def __enter__(self) -> "Heorot":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self._db.close()

    def load_from_html(self, html: str, force: bool = False) -> int:
        """
        Load Beowulf text from HTML into DuckDB.

        Args:
            html: HTML content to parse.
            force: If True, drop and recreate the table even if it exists.

        Returns:
            Number of lines loaded.
        """
        if self._db.table_exists(TABLE_NAME):
            if not force:
                logger.info("heorot table already exists, skipping load")
                return self._db.count(TABLE_NAME)
            logger.info("Dropping existing heorot table")
            self._db.drop_table(TABLE_NAME)

        logger.info("Parsing HTML and loading into DuckDB")

        # Parse the HTML
        lines = parse(html)

        # Create the table
        self._db.conn.execute(
            f"""
            CREATE TABLE {TABLE_NAME} (
                line INTEGER PRIMARY KEY,
                oe VARCHAR,
                me VARCHAR
            )
        """
        )

        # Insert all lines
        for line_data in lines:
            self._db.conn.execute(
                f"INSERT INTO {TABLE_NAME} (line, oe, me) VALUES (?, ?, ?)",
                [line_data["line"], line_data["OE"], line_data["ME"]],
            )

        row_count = self._db.count(TABLE_NAME)
        logger.info("Loaded Beowulf text", row_count=row_count)
        return row_count

    def load_from_url(self, url: str = HEOROT_URL, force: bool = False) -> int:
        """
        Fetch HTML from URL and load into DuckDB.

        Args:
            url: URL to fetch HTML from. Defaults to HEOROT_URL.
            force: If True, drop and recreate the table even if it exists.

        Returns:
            Number of lines loaded.
        """
        if self._db.table_exists(TABLE_NAME) and not force:
            logger.info("heorot table already exists, skipping load")
            return self._db.count(TABLE_NAME)

        logger.info("Fetching HTML from URL", url=url)
        response = requests.get(url)
        response.raise_for_status()

        return self.load_from_html(response.text, force=force)

    def count(self) -> int:
        """Return the number of lines in the table."""
        return self._db.count(TABLE_NAME)

    def get_line(self, line_number: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific line by number.

        Args:
            line_number: The line number to retrieve.

        Returns:
            Dictionary with line, oe, and me keys, or None if not found.
        """
        result = self._db.conn.execute(
            f"SELECT line, oe, me FROM {TABLE_NAME} WHERE line = ?", [line_number]
        ).fetchone()

        if result:
            return {"line": result[0], "OE": result[1], "ME": result[2]}
        return None

    def get_lines(
        self, start: int = 1, end: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get a range of lines.

        Args:
            start: Starting line number (inclusive).
            end: Ending line number (inclusive). If None, returns all lines from start.

        Returns:
            List of dictionaries with line, OE, and ME keys.
        """
        if end is None:
            result = self._db.conn.execute(
                f"SELECT line, oe, me FROM {TABLE_NAME} WHERE line >= ? ORDER BY line",
                [start],
            ).fetchall()
        else:
            result = self._db.conn.execute(
                f"SELECT line, oe, me FROM {TABLE_NAME} WHERE line >= ? AND line <= ? ORDER BY line",
                [start, end],
            ).fetchall()

        return [{"line": row[0], "OE": row[1], "ME": row[2]} for row in result]

    def search_oe(self, term: str) -> List[Dict[str, Any]]:
        """
        Search for a term in Old English text.

        Args:
            term: The term to search for (case-insensitive contains).

        Returns:
            List of matching lines.
        """
        result = self._db.conn.execute(
            f"SELECT line, oe, me FROM {TABLE_NAME} WHERE LOWER(oe) LIKE LOWER(?) ORDER BY line",
            [f"%{term}%"],
        ).fetchall()

        return [{"line": row[0], "OE": row[1], "ME": row[2]} for row in result]

    def search_me(self, term: str) -> List[Dict[str, Any]]:
        """
        Search for a term in Modern English text.

        Args:
            term: The term to search for (case-insensitive contains).

        Returns:
            List of matching lines.
        """
        result = self._db.conn.execute(
            f"SELECT line, oe, me FROM {TABLE_NAME} WHERE LOWER(me) LIKE LOWER(?) ORDER BY line",
            [f"%{term}%"],
        ).fetchall()

        return [{"line": row[0], "OE": row[1], "ME": row[2]} for row in result]

    def search(self, term: str) -> List[Dict[str, Any]]:
        """
        Search for a term in both Old English and Modern English text.

        Args:
            term: The term to search for (case-insensitive contains).

        Returns:
            List of matching lines.
        """
        result = self._db.conn.execute(
            f"""SELECT line, oe, me FROM {TABLE_NAME}
               WHERE LOWER(oe) LIKE LOWER(?) OR LOWER(me) LIKE LOWER(?)
               ORDER BY line""",
            [f"%{term}%", f"%{term}%"],
        ).fetchall()

        return [{"line": row[0], "OE": row[1], "ME": row[2]} for row in result]

    @property
    def db(self):
        return self._db


# Module-level convenience functions
_default_heorot: Optional[Heorot] = None


def get_heorot() -> Heorot:
    """Get the default Heorot instance."""
    global _default_heorot
    if _default_heorot is None:
        _default_heorot = Heorot()
    return _default_heorot


def load(url: str = HEOROT_URL, force: bool = False) -> int:
    """Load the Beowulf text from URL into DuckDB."""
    return get_heorot().load_from_url(url, force)


def get_line(line_number: int) -> Optional[Dict[str, Any]]:
    """Get a specific line by number."""
    return get_heorot().get_line(line_number)


def get_lines(start: int = 1, end: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get a range of lines."""
    return get_heorot().get_lines(start, end)


def search(term: str) -> List[Dict[str, Any]]:
    """Search for a term in both OE and ME text."""
    return get_heorot().search(term)
