"""Bosworth-Toller abbreviations interface backed by DuckDB."""

import re
import xml.etree.ElementTree as ET
from typing import List, Optional

from assets import get_asset_path
from beowulf_mcp.db import BeoDB
from logging_config import get_logger

logger = get_logger()

# XML abbv content from https://www.germanic-lexicon-project.org/texts/oe_bosworthtoller_about.html
BT_ABBREVIATIONS_XML = "bt_abbreviations.xml"

# Table name for this source
TABLE_NAME = "abbreviations"


class Abbreviations:
    """Interface to the Bosworth-Toller abbreviations."""

    def __init__(self, db: Optional[BeoDB] = None) -> None:
        """
        Initialize the abbreviations interface.

        Args:
            db: BeoDB instance. Defaults to BeoDB() using the configured DB_PATH.
        """
        self._db = db or BeoDB()

    def __enter__(self) -> "Abbreviations":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self._db.close()

    def load_from_xml(self, force: bool = False) -> int:
        """
        Load the Bosworth-Toller abbreviations from XML into DuckDB.

        Args:
            force: If True, drop and recreate the table even if it exists.

        Returns:
            Number of abbreviations loaded.
        """
        if self._db.table_exists(TABLE_NAME):
            if not force:
                logger.info("abbreviations table already exists, skipping load")
                return self._db.count(TABLE_NAME)
            logger.info("Dropping existing abbreviations table")
            self._db.drop_table(TABLE_NAME)

        xml_path = get_asset_path(BT_ABBREVIATIONS_XML)
        logger.info("Loading abbreviations from XML", xml_path=str(xml_path))

        # Parse the XML
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Create the table
        self._db.conn.execute(
            f"""
            CREATE TABLE {TABLE_NAME} (
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

            self._db.conn.execute(
                f"INSERT INTO {TABLE_NAME} VALUES (?, ?, ?)",
                [abbrev, expansion, desc],
            )

        row_count = self._db.count(TABLE_NAME)
        schema = self._db.get_schema(TABLE_NAME)
        logger.info("Loaded abbreviations", row_count=row_count, schema=schema)
        return row_count

    def lookup(self, abbrev: str) -> List[dict]:
        """
        Look up an abbreviation.

        Args:
            abbrev: The abbreviation to look up (e.g., 'Beo. Th.')

        Returns:
            List of matching abbreviation entries.
        """
        result = self._db.conn.execute(
            f"SELECT * FROM {TABLE_NAME} WHERE abbreviation LIKE ?", [f"%{abbrev}%"]
        ).fetchall()
        return [
            {"abbreviation": row[0], "expansion": row[1], "description": row[2]}
            for row in result
        ]


# Module-level convenience functions
_default_abbr_instance: Optional[Abbreviations] = None


def get_abbreviations() -> Abbreviations:
    """Get the default Abbreviations instance."""
    global _default_abbr_instance
    if _default_abbr_instance is None:
        _default_abbr_instance = Abbreviations()
    return _default_abbr_instance


def lookup(pattern: str) -> List[dict]:
    """Look up abbreviations."""
    return get_abbreviations().lookup(pattern)


def load(force: bool = False) -> int:
    """Load the abbreviations from XML into DuckDB."""
    return get_abbreviations().load_from_xml(force)
