"""Database management for beodata DuckDB instance."""

import os
from pathlib import Path
from typing import Optional

import duckdb
from dotenv import load_dotenv

from logging_config import get_logger

load_dotenv()

logger = get_logger()

# Database path: override with DB_PATH env var or .env file
DEFAULT_DB_PATH = Path(
    os.environ.get("DB_PATH", Path(__file__).parents[1] / "output" / "beodb.duckdb")
)


class BeoDB:
    """Manages the shared DuckDB database connection.

    This is the central database manager for all beodata tables:
    - bosworth: Bosworth-Toller dictionary entries
    - abbreviations: Dictionary abbreviation expansions
    - (future) beowulf: Tokenized Beowulf text
    """

    _instance: Optional["BeoDB"] = None

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """
        Initialize database connection.

        Args:
            db_path: Path to the DuckDB database file. Defaults to beodb.duckdb
                    in the assets directory.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        logger.debug("BeoDB initialized", db_path=str(self.db_path))

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = duckdb.connect(str(self.db_path))
            logger.debug("DuckDB connection opened", db_path=str(self.db_path))
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.debug("DuckDB connection closed")

    def __enter__(self) -> "BeoDB":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        result = self.conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
            [table_name],
        ).fetchone()
        return result is not None and result[0] > 0

    def get_schema(self, table_name: str) -> dict[str, str]:
        """Get the schema of a table as {column_name: data_type}."""
        result = self.conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = ? ORDER BY ordinal_position",
            [table_name],
        ).fetchall()
        logger.info("Schema fetched!")
        return {row[0]: row[1] for row in result}

    def get_columns(self, table_name: str) -> list[str]:
        """Get the column names of a table."""
        result = self.conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = ? ORDER BY ordinal_position",
            [table_name],
        ).fetchall()
        return [row[0] for row in result]

    def drop_table(self, table_name: str) -> None:
        """Drop a table if it exists."""
        # Use safe quoting for table name
        safe_name = _quote_identifier(table_name)
        self.conn.execute(f"DROP TABLE IF EXISTS {safe_name}")
        logger.info("Dropped table", table_name=table_name)

    def count(self, table_name: str) -> int:
        """Return the number of rows in a table."""
        safe_name = _quote_identifier(table_name)
        result = self.conn.execute(f"SELECT COUNT(*) FROM {safe_name}").fetchone()
        return result[0] if result else 0

    def list_tables(self) -> list[str]:
        """List all tables in the database."""
        result = self.conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
        return [row[0] for row in result]


def _quote_identifier(name: str) -> str:
    """Safely quote a SQL identifier to prevent injection."""
    # Double any internal double quotes, then wrap in double quotes
    return '"' + name.replace('"', '""') + '"'


# Singleton access
_default_db: Optional[BeoDB] = None


def get_db() -> BeoDB:
    """Get the default BeoDB instance (singleton pattern).

    Returns:
        The shared BeoDB instance, using the configured DEFAULT_DB_PATH.
    """
    global _default_db
    if _default_db is None:
        _default_db = BeoDB()
    return _default_db


def reset_db() -> None:
    """Reset the singleton database instance (mainly for testing)."""
    global _default_db
    if _default_db is not None:
        _default_db.close()
        _default_db = None
