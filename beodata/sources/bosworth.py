"""Bosworth-Toller Old English Dictionary interface backed by DuckDB."""

from pathlib import Path
from typing import List, Optional

from beodata.assets import get_asset_path
from beodata.db import BeoDB, _quote_identifier
from beodata.logging_config import get_logger

logger = get_logger()

# Asset filename
BT_CSV_ASSET = "oe_bt.csv"

# Table name for this source
TABLE_NAME = "bosworth"


class BosworthToller:
    """Interface to the Bosworth-Toller Old English Dictionary."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """
        Initialize the dictionary interface.

        Args:
            db_path: Path to the DuckDB database file. Defaults to beodb.duckdb
                    in the assets directory.
        """
        self._db = BeoDB(db_path)

    def __enter__(self) -> "BosworthToller":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self._db.close()

    def load_from_csv(self, force: bool = False) -> int:
        """
        Load the Bosworth-Toller dictionary from CSV into DuckDB.

        Args:
            force: If True, drop and recreate the table even if it exists.

        Returns:
            Number of rows loaded.
        """
        if self._db.table_exists(TABLE_NAME):
            if not force:
                logger.info("bosworth table already exists, skipping load")
                return self._db.count(TABLE_NAME)
            logger.info("Dropping existing bosworth table")
            self._db.drop_table(TABLE_NAME)

        csv_path = get_asset_path(BT_CSV_ASSET)
        logger.info("Loading Bosworth-Toller from CSV", csv_path=str(csv_path))

        # Load CSV with @ delimiter, no header row, explicit column names and types
        self._db.conn.execute(
            f"""
            CREATE TABLE {TABLE_NAME} AS
            SELECT * FROM read_csv(
                '{csv_path}',
                header=false,
                delim='@',
                columns={{'headword': 'VARCHAR', 'definition': 'VARCHAR', 'references': 'VARCHAR'}}
            )
        """
        )

        # Strip HTML tags from the headword (first column)
        columns = self._db.get_columns(TABLE_NAME)
        if columns:
            first_col = _quote_identifier(columns[0])
            self._db.conn.execute(
                f"""
                UPDATE {TABLE_NAME}
                SET {first_col} = regexp_replace({first_col}, '<[^>]+>', '', 'g')
            """
            )

        # Add cleaned_definition column with HTML stripped (for searching)
        self._db.conn.execute(
            f"""
            ALTER TABLE {TABLE_NAME} ADD COLUMN cleaned_definition VARCHAR
        """
        )
        self._db.conn.execute(
            f"""
            UPDATE {TABLE_NAME}
            SET cleaned_definition = regexp_replace(definition, '<[^>]+>', '', 'g')
        """
        )

        row_count = self._db.count(TABLE_NAME)
        schema = self._db.get_schema(TABLE_NAME)
        logger.info(
            "Loaded Bosworth-Toller dictionary", row_count=row_count, schema=schema
        )
        return row_count

    def lookup(self, word: str, oper: str = "=") -> List[dict]:
        """
        Look up a word in the dictionary by the first column (headword).

        Args:
            word: The Old English word to look up.
            oper: SQL operator to use for matching (i.e., '=' or 'LIKE')
        Returns:
            List of matching dictionary entries as dictionaries.
        """
        columns = self._db.get_columns(TABLE_NAME)
        if not columns:
            return []

        if not oper.upper() in ["=", "LIKE"]:
            raise ValueError(f"Invalid operator: {oper}")

        first_col = _quote_identifier(columns[0])
        result = self._db.conn.execute(
            f"SELECT * FROM {TABLE_NAME} WHERE {first_col} {oper.upper()} ?", [word]
        ).fetchall()

        return [dict(zip(columns, row)) for row in result]

    def lookup_like(self, pattern: str) -> List[dict]:
        return self.lookup(pattern, oper="LIKE")

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
            "Searching dictionary",
            term=term,
            column=column,
            schema=self._db.get_schema(TABLE_NAME),
        )
        columns = self._db.get_columns(TABLE_NAME)
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

        result = self._db.conn.execute(
            f"SELECT * FROM {TABLE_NAME} WHERE {where_clause}", params
        ).fetchall()

        return [dict(zip(columns, row)) for row in result]

    @property
    def db(self):
        return self._db


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


def load(force: bool = False) -> int:
    """Load the dictionary from CSV into DuckDB."""
    return get_bt().load_from_csv(force)
