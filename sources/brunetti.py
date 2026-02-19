"""Brunetti tokenized Beowulf interface backed by DuckDB."""

from typing import List, Optional

from assets import get_asset_path
from beowulf_mcp.db import BeoDB, _quote_identifier
from logging_config import get_logger

logger = get_logger()

# Asset filename
BRUNETTI_ASSET = "brunetti-length.txt"

# Table name for this source
TABLE_NAME = "brunetti"

# Column definitions (18 pipe-delimited columns, all VARCHAR)
COLUMNS = [
    "fitt_id",
    "para_id",
    "para_first",
    "non_verse",
    "line_id",
    "half_line",
    "token_offset",
    "caesura_code",
    "pre_punc",
    "text",
    "post_punc",
    "syntax",
    "parse",
    "lemma",
    "pos",
    "inflection",
    "gloss",
    "with_length",
]


class Brunetti:
    """Interface to Brunetti's tokenized Beowulf edition."""

    def __init__(self, db: Optional[BeoDB] = None) -> None:
        """
        Initialize the Brunetti interface.

        Args:
            db: BeoDB instance. Defaults to BeoDB() using the configured DB_PATH.
        """
        self._db = db or BeoDB()

    def __enter__(self) -> "Brunetti":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self._db.close()

    def load_from_txt(self, force: bool = False) -> int:
        """
        Load Brunetti token data from pipe-delimited text into DuckDB.

        Args:
            force: If True, drop and recreate the table even if it exists.

        Returns:
            Number of rows loaded.
        """
        if self._db.table_exists(TABLE_NAME):
            if not force:
                logger.info("brunetti table already exists, skipping load")
                return self._db.count(TABLE_NAME)
            logger.info("Dropping existing brunetti table")
            self._db.drop_table(TABLE_NAME)

        txt_path = get_asset_path(BRUNETTI_ASSET)
        logger.info("Loading Brunetti tokens from TXT", txt_path=str(txt_path))

        # Build column spec: all 18 columns as VARCHAR
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
        logger.info("Loaded Brunetti tokens", row_count=row_count, schema=schema)
        return row_count

    def lookup(self, lemma: str, oper: str = "=") -> List[dict]:
        """
        Look up tokens by lemma.

        Args:
            lemma: The Old English lemma to look up.
            oper: SQL operator to use for matching (i.e., '=' or 'LIKE')

        Returns:
            List of matching token rows as dictionaries.
        """
        columns = self._db.get_columns(TABLE_NAME)
        if not columns:
            return []

        if oper.upper() not in ["=", "LIKE"]:
            raise ValueError(f"Invalid operator: {oper}")

        lemma_col = _quote_identifier("lemma")
        result = self._db.conn.execute(
            f"SELECT * FROM {TABLE_NAME} WHERE {lemma_col} {oper.upper()} ?", [lemma]
        ).fetchall()

        return [dict(zip(columns, row)) for row in result]

    def lookup_like(self, pattern: str) -> List[dict]:
        """Look up lemmas matching a SQL LIKE pattern."""
        return self.lookup(pattern, oper="LIKE")

    def search(self, term: str, column: Optional[str] = None) -> List[dict]:
        """
        Search for a term anywhere in the token data.

        Args:
            term: The term to search for (case-insensitive contains).
            column: Specific column to search, or None for all columns.

        Returns:
            List of matching token rows as dictionaries.
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

    def get_by_line(self, line_id: str) -> List[dict]:
        """
        Get all tokens for a given line number.

        Args:
            line_id: The line number (zero-padded string, e.g. '0001').

        Returns:
            List of token rows for that line.
        """
        columns = self._db.get_columns(TABLE_NAME)
        if not columns:
            return []

        line_col = _quote_identifier("line_id")
        result = self._db.conn.execute(
            f"SELECT * FROM {TABLE_NAME} WHERE {line_col} = ? ORDER BY {_quote_identifier('half_line')}, {_quote_identifier('token_offset')}",
            [line_id],
        ).fetchall()

        return [dict(zip(columns, row)) for row in result]

    def get_by_fitt(self, fitt_id: str) -> List[dict]:
        """
        Get all tokens for a given fitt.

        Args:
            fitt_id: The fitt number (zero-padded string, e.g. '00').

        Returns:
            List of token rows for that fitt.
        """
        columns = self._db.get_columns(TABLE_NAME)
        if not columns:
            return []

        fitt_col = _quote_identifier("fitt_id")
        result = self._db.conn.execute(
            f"SELECT * FROM {TABLE_NAME} WHERE {fitt_col} = ? ORDER BY {_quote_identifier('line_id')}, {_quote_identifier('half_line')}, {_quote_identifier('token_offset')}",
            [fitt_id],
        ).fetchall()

        return [dict(zip(columns, row)) for row in result]

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


def lookup(lemma: str) -> List[dict]:
    """Look up tokens by lemma in the Brunetti data."""
    return get_brunetti().lookup(lemma)


def lookup_like(pattern: str) -> List[dict]:
    """Look up lemmas matching a SQL LIKE pattern."""
    return get_brunetti().lookup_like(pattern)


def search(term: str, column: Optional[str] = None) -> List[dict]:
    """Search for a term in the Brunetti token data."""
    return get_brunetti().search(term, column)


def get_by_line(line_id: str) -> List[dict]:
    """Get all tokens for a line number."""
    return get_brunetti().get_by_line(line_id)


def get_by_fitt(fitt_id: str) -> List[dict]:
    """Get all tokens for a fitt."""
    return get_brunetti().get_by_fitt(fitt_id)


def load(force: bool = False) -> int:
    """Load Brunetti tokens from text into DuckDB."""
    return get_brunetti().load_from_txt(force)
