"""Bosworth-Toller Old English Dictionary interface backed by DuckDB."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, List, Optional

import duckdb

from beodata.assets import get_asset_path
from beodata.logging_config import get_logger

# Regex to strip HTML tags
_HTML_TAG_RE = re.compile(r"<[^>]+>")

logger = get_logger()


def _quote_identifier(name: str) -> str:
    """Safely quote a SQL identifier to prevent injection."""
    # Double any internal double quotes, then wrap in double quotes
    return '"' + name.replace('"', '""') + '"'


# Default database path (in assets directory)
DEFAULT_DB_PATH = Path(__file__).parent / "assets" / "beodb.duckdb"

# Asset filenames
BT_CSV_ASSET = "oe_bt.csv"
BT_ABBREVIATIONS_XML = "bt_abbreviations.xml"


class BosworthToller:
    """Interface to the Bosworth-Toller Old English Dictionary."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """
        Initialize the dictionary interface.

        Args:
            db_path: Path to the DuckDB database file. Defaults to beodb.duckdb
                    in the project root.
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

    def __enter__(self) -> "BosworthToller":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def table_exists(self) -> bool:
        """Check if the bosworth table exists."""
        result = self.conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'bosworth'"
        ).fetchone()
        return result is not None and result[0] > 0

    def load_from_csv(self, force: bool = False) -> int:
        """
        Load the Bosworth-Toller dictionary from CSV into DuckDB.

        Args:
            force: If True, drop and recreate the table even if it exists.

        Returns:
            Number of rows loaded.
        """
        if self.table_exists():
            if not force:
                logger.info("bosworth table already exists, skipping load")
                return self.count()
            logger.info("Dropping existing bosworth table")
            self.conn.execute("DROP TABLE bosworth")

        csv_path = get_asset_path(BT_CSV_ASSET)
        logger.info("Loading Bosworth-Toller from CSV", csv_path=str(csv_path))

        # Load CSV with @ delimiter, no header row, explicit column names and types
        self.conn.execute(
            f"""
            CREATE TABLE bosworth AS
            SELECT * FROM read_csv(
                '{csv_path}',
                header=false,
                delim='@',
                columns={{'headword': 'VARCHAR', 'definition': 'VARCHAR', 'references': 'VARCHAR'}}
            )
        """
        )

        # Strip HTML tags from the headword (first column)
        columns = self.get_columns()
        if columns:
            first_col = _quote_identifier(columns[0])
            self.conn.execute(
                f"""
                UPDATE bosworth
                SET {first_col} = regexp_replace({first_col}, '<[^>]+>', '', 'g')
            """
            )

        # Add cleaned_definition column with HTML stripped (for searching)
        self.conn.execute(
            """
            ALTER TABLE bosworth ADD COLUMN cleaned_definition VARCHAR
        """
        )
        self.conn.execute(
            """
            UPDATE bosworth
            SET cleaned_definition = regexp_replace(definition, '<[^>]+>', '', 'g')
        """
        )

        row_count = self.count()
        schema = self._get_schema()
        logger.info(
            "Loaded Bosworth-Toller dictionary", row_count=row_count, schema=schema
        )
        return row_count

    def _get_schema(self, table_name: str = "bosworth") -> dict[str, str]:
        """Get the schema of a table as {column_name: data_type}."""
        result = self.conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            f"WHERE table_name = '{table_name}' ORDER BY ordinal_position"
        ).fetchall()
        return {row[0]: row[1] for row in result}

    def abbreviations_table_exists(self) -> bool:
        """Check if the abbreviations table exists."""
        result = self.conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'abbreviations'"
        ).fetchone()
        return result is not None and result[0] > 0

    def load_abbreviations(self, force: bool = False) -> int:
        """
        Load the Bosworth-Toller abbreviations from XML into DuckDB.

        Args:
            force: If True, drop and recreate the table even if it exists.

        Returns:
            Number of abbreviations loaded.
        """
        if self.abbreviations_table_exists():
            if not force:
                logger.info("abbreviations table already exists, skipping load")
                return self.abbreviations_count()
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

        row_count = self.abbreviations_count()
        schema = self._get_schema("abbreviations")
        logger.info("Loaded abbreviations", row_count=row_count, schema=schema)
        return row_count

    def abbreviations_count(self) -> int:
        """Return the number of abbreviations."""
        result = self.conn.execute("SELECT COUNT(*) FROM abbreviations").fetchone()
        return result[0] if result else 0

    def lookup_abbreviation(self, abbrev: str) -> List[dict]:
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

    def count(self) -> int:
        """Return the number of entries in the dictionary."""
        result = self.conn.execute("SELECT COUNT(*) FROM bosworth").fetchone()
        return result[0] if result else 0

    def get_columns(self) -> List[str]:
        """Get the column names of the bosworth table."""
        result = self.conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'bosworth' ORDER BY ordinal_position"
        ).fetchall()
        return [row[0] for row in result]

    def lookup(self, word: str) -> List[dict]:
        """
        Look up a word in the dictionary by the first column (headword).

        Args:
            word: The Old English word to look up.

        Returns:
            List of matching dictionary entries as dictionaries.
        """
        columns = self.get_columns()
        if not columns:
            return []

        first_col = _quote_identifier(columns[0])
        result = self.conn.execute(
            f"SELECT * FROM bosworth WHERE {first_col} = ?", [word]
        ).fetchall()

        return [dict(zip(columns, row)) for row in result]

    def lookup_like(self, pattern: str) -> List[dict]:
        """
        Look up words matching a SQL LIKE pattern.

        Args:
            pattern: SQL LIKE pattern (e.g., 'burg%' for words starting with 'burg').

        Returns:
            List of matching dictionary entries as dictionaries.
        """
        columns = self.get_columns()
        if not columns:
            return []

        first_col = _quote_identifier(columns[0])
        result = self.conn.execute(
            f"SELECT * FROM bosworth WHERE {first_col} LIKE ?", [pattern]
        ).fetchall()

        return [dict(zip(columns, row)) for row in result]

    def search(self, term: str, column: Optional[str] = None) -> List[dict]:
        """
        Search for a term anywhere in the dictionary entries.

        Args:
            term: The term to search for (case-insensitive contains).
            column: Specific column to search, or None for all columns.

        Returns:
            List of matching dictionary entries as dictionaries.
        """
        logger.info(
            "Searching dictionary", term=term, column=column, schema=self._get_schema()
        )
        columns = self.get_columns()
        if not columns:
            return []

        # Use cleaned_definition for searching instead of definition (which has HTML)
        # Exclude cleaned_definition from the list since we're substituting it for definition
        search_columns = [
            "cleaned_definition" if col == "definition" else col
            for col in columns
            if col != "cleaned_definition"
        ]

        if column and column in columns:
            search_col = "cleaned_definition" if column == "definition" else column
            quoted_col = _quote_identifier(search_col)
            where_clause = f"LOWER({quoted_col}) LIKE LOWER(?)"
            logger.info("Searching in column", column=column, where_clause=where_clause)
        else:
            # Search all columns (using cleaned_definition instead of definition)
            conditions = [
                f"LOWER({_quote_identifier(col)}) LIKE LOWER(?)"
                for col in search_columns
            ]
            where_clause = " OR ".join(conditions)
            logger.info("Searching all columns", where_clause=where_clause)

        search_pattern = f"%{term}%"
        params = [search_pattern] if column else [search_pattern] * len(search_columns)

        result = self.conn.execute(
            f"SELECT * FROM bosworth WHERE {where_clause}", params
        ).fetchall()

        return [dict(zip(columns, row)) for row in result]


# Module-level convenience functions
_default_bt: Optional[BosworthToller] = None


def get_bt() -> BosworthToller:
    """Get the default BosworthToller instance."""
    global _default_bt
    if _default_bt is None:
        _default_bt = BosworthToller()
    return _default_bt


def lookup(word: str) -> List[dict]:
    """Look up a word in the Bosworth-Toller dictionary."""
    return get_bt().lookup(word)


def lookup_like(pattern: str) -> List[dict]:
    """Look up words matching a SQL LIKE pattern."""
    return get_bt().lookup_like(pattern)


def search(term: str, column: Optional[str] = None) -> List[dict]:
    """Search for a term in the dictionary."""
    return get_bt().search(term, column)


def load_dictionary(force: bool = False) -> int:
    """Load the dictionary from CSV into DuckDB."""
    return get_bt().load_from_csv(force)
