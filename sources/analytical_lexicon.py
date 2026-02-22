"""Analytical Lexicon of Beowulf interface backed by DuckDB."""

from typing import List, Optional

from assets import get_asset_path
from beowulf_mcp.db import BeoDB, _quote_identifier
from logging_config import get_logger

logger = get_logger()

# Asset filename
LEXICON_ASSET = "analytical_lexicon.txt"

# Table name for this source
TABLE_NAME = "analytical_lexicon"

# Column definitions (5 pipe-delimited columns)
COLUMNS = [
    "headword",
    "part_of_speech",
    "form",
    "inflection",
    "line_refs",
]


class AnalyticalLexicon:
    """Interface to the Analytical Lexicon of Beowulf."""

    def __init__(self, db: Optional[BeoDB] = None) -> None:
        """
        Initialize the Analytical Lexicon interface.

        Args:
            db: BeoDB instance. Defaults to BeoDB() using the configured DB_PATH.
        """
        self._db = db or BeoDB()

    def __enter__(self) -> "AnalyticalLexicon":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self._db.close()

    def load(self, force: bool = False) -> int:
        """
        Load the Analytical Lexicon from pipe-delimited text into DuckDB.

        Args:
            force: If True, drop and recreate the table even if it exists.

        Returns:
            Number of rows loaded.
        """
        if self._db.table_exists(TABLE_NAME):
            if not force:
                logger.info("analytical_lexicon table already exists, skipping load")
                return self._db.count(TABLE_NAME)
            logger.info("Dropping existing analytical_lexicon table")
            self._db.drop_table(TABLE_NAME)

        txt_path = get_asset_path(LEXICON_ASSET)
        logger.info("Loading Analytical Lexicon from TXT", txt_path=str(txt_path))

        # Build column spec: all columns as VARCHAR
        col_spec = ", ".join(f"'{col}': 'VARCHAR'" for col in COLUMNS)

        self._db.conn.execute(
            f"""
            CREATE TABLE {TABLE_NAME} AS
            SELECT * FROM read_csv(
                '{txt_path}',
                header=false,
                delim='|',
                columns={{{col_spec}}}
            )
        """
        )

        row_count = self._db.count(TABLE_NAME)
        schema = self._db.get_schema(TABLE_NAME)
        logger.info("Loaded Analytical Lexicon", row_count=row_count, schema=schema)
        return row_count

    def lookup(self, headword: str, oper: str = "=") -> List[dict]:
        """
        Look up entries by headword.

        Args:
            headword: The Old English headword to look up.
            oper: SQL operator to use for matching ('=' or 'LIKE').

        Returns:
            List of matching entries as dictionaries.
        """
        columns = self._db.get_columns(TABLE_NAME)
        if not columns:
            return []

        if oper.upper() not in ["=", "LIKE"]:
            raise ValueError(f"Invalid operator: {oper}")

        hw_col = _quote_identifier("headword")
        result = self._db.conn.execute(
            f"SELECT * FROM {TABLE_NAME} WHERE {hw_col} {oper.upper()} ?",
            [headword],
        ).fetchall()

        return [dict(zip(columns, row)) for row in result]

    def lookup_like(self, pattern: str) -> List[dict]:
        """Look up headwords matching a SQL LIKE pattern."""
        return self.lookup(pattern, oper="LIKE")

    def search(self, term: str, column: Optional[str] = None) -> List[dict]:
        """
        Search for a term anywhere in the lexicon data.

        Args:
            term: The term to search for (case-insensitive contains).
            column: Specific column to search, or None for all columns.

        Returns:
            List of matching entries as dictionaries.
        """
        columns = self._db.get_columns(TABLE_NAME)
        if not columns:
            return []

        if column and column in columns:
            quoted_col = _quote_identifier(column)
            where_clause = f"LOWER({quoted_col}) LIKE LOWER(?)"
        else:
            conditions = [
                f"LOWER({_quote_identifier(col)}) LIKE LOWER(?)" for col in columns
            ]
            where_clause = " OR ".join(conditions)

        search_pattern = f"%{term}%"
        params = [search_pattern] if column else [search_pattern] * len(columns)

        result = self._db.conn.execute(
            f"SELECT * FROM {TABLE_NAME} WHERE {where_clause}", params
        ).fetchall()

        return [dict(zip(columns, row)) for row in result]

    def get_by_headword(self, headword: str) -> List[dict]:
        """
        Get all entries for a given headword (exact match).

        Args:
            headword: The headword to look up.

        Returns:
            List of entries for that headword.
        """
        return self.lookup(headword)

    @property
    def db(self) -> BeoDB:
        return self._db


# Module-level convenience functions
_default_lexicon: Optional[AnalyticalLexicon] = None


def get_analytical_lexicon() -> AnalyticalLexicon:
    """Get the default AnalyticalLexicon instance."""
    global _default_lexicon
    if _default_lexicon is None:
        _default_lexicon = AnalyticalLexicon()
    return _default_lexicon


def lookup(headword: str) -> List[dict]:
    """Look up entries by headword in the Analytical Lexicon."""
    return get_analytical_lexicon().lookup(headword)


def lookup_like(pattern: str) -> List[dict]:
    """Look up headwords matching a SQL LIKE pattern."""
    return get_analytical_lexicon().lookup_like(pattern)


def search(term: str, column: Optional[str] = None) -> List[dict]:
    """Search for a term in the Analytical Lexicon."""
    return get_analytical_lexicon().search(term, column)


def load(force: bool = False) -> int:
    """Load the Analytical Lexicon into DuckDB."""
    return get_analytical_lexicon().load(force)
