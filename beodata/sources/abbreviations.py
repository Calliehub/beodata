"""Bosworth-Toller abbreviations interface backed by DuckDB."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, List, Optional

import duckdb

from beodata.assets import get_asset_path
from beodata.logging_config import get_logger

logger = get_logger()

# Default database path (in assets directory)
DEFAULT_DB_PATH = Path(__file__).parent.parent / "assets" / "beodb.duckdb"

# XML abbv content from https://www.germanic-lexicon-project.org/texts/oe_bosworthtoller_about.html
BT_ABBREVIATIONS_XML = "bt_abbreviations.xml"


class Abbreviations:
    """Interface to the Bosworth-Toller abbreviations."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """
        Initialize the abbreviations interface.

        Args:
            db_path: Path to the DuckDB database file. Defaults to beodb.duckdb
                    in the assets directory.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._conn: Optional[duckdb.DuckDBPyConnection] = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = duckdb.connect(str(self.db_path))
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Abbreviations":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def table_exists(self) -> bool:
        """Check if the abbreviations table exists."""
        result = self.conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'abbreviations'"
        ).fetchone()
        return result is not None and result[0] > 0

    def _get_schema(self) -> dict[str, str]:
        """Get the schema of the abbreviations table as {column_name: data_type}."""
        result = self.conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'abbreviations' ORDER BY ordinal_position"
        ).fetchall()
        return {row[0]: row[1] for row in result}

    def load_from_xml(self, force: bool = False) -> int:
        """
        Load the Bosworth-Toller abbreviations from XML into DuckDB.

        Args:
            force: If True, drop and recreate the table even if it exists.

        Returns:
            Number of abbreviations loaded.
        """
        if self.table_exists():
            if not force:
                logger.info("abbreviations table already exists, skipping load")
                return self.count()
            logger.info("Dropping existing abbreviations table")
            self.conn.execute("DROP TABLE abbreviations")

        xml_path = get_asset_path(BT_ABBREVIATIONS_XML)
        logger.info("Loading abbreviations from XML", xml_path=str(xml_path))

        # Parse the XML
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Create the table
        self.conn.execute(
            """
            CREATE TABLE abbreviations (
                abbreviation VARCHAR,
                expansion VARCHAR,
                description VARCHAR
            )
        """
        )

        # Extract and insert abbreviations
        for source in root.findall("source"):
            spellout = source.find("spellout")
            heading = source.find("heading")
            body = source.find("body")

            abbrev = (
                spellout.text.strip() if spellout is not None and spellout.text else ""
            )
            expansion = (
                heading.text.strip() if heading is not None and heading.text else ""
            )
            desc = body.text.strip() if body is not None and body.text else ""

            # Clean up whitespace in description
            desc = re.sub(r"\s+", " ", desc)

            self.conn.execute(
                "INSERT INTO abbreviations VALUES (?, ?, ?)", [abbrev, expansion, desc]
            )

        row_count = self.count()
        schema = self._get_schema()
        logger.info("Loaded abbreviations", row_count=row_count, schema=schema)
        return row_count

    def count(self) -> int:
        """Return the number of abbreviations."""
        result = self.conn.execute("SELECT COUNT(*) FROM abbreviations").fetchone()
        return result[0] if result else 0

    def lookup(self, abbrev: str) -> List[dict]:
        """
        Look up an abbreviation.

        Args:
            abbrev: The abbreviation to look up (e.g., 'Beo. Th.')

        Returns:
            List of matching abbreviation entries.
        """
        result = self.conn.execute(
            "SELECT * FROM abbreviations WHERE abbreviation LIKE ?", [f"%{abbrev}%"]
        ).fetchall()
        return [
            {"abbreviation": row[0], "expansion": row[1], "description": row[2]}
            for row in result
        ]


# Module-level convenience functions
_default_abbr: Optional[Abbreviations] = None


def get_abbreviations() -> Abbreviations:
    """Get the default Abbreviations instance."""
    global _default_abbr
    if _default_abbr is None:
        _default_abbr = Abbreviations()
    return _default_abbr


def lookup(pattern: str) -> List[dict]:
    """Look up abbreviations."""
    return get_abbreviations().lookup(pattern)


def load(force: bool = False) -> int:
    """Load the abbreviations from XML into DuckDB."""
    return get_abbreviations().load_from_xml(force)
