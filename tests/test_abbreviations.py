"""Tests for the Bosworth-Toller abbreviations module."""

from pathlib import Path

from beowulf_mcp.db import BeoDB
from sources.abbreviations import TABLE_NAME, Abbreviations


class TestAbbreviations:
    """Tests for Abbreviations class."""

    def test_table_exists_false_initially(self, tmp_path: Path) -> None:
        """Table should not exist before loading."""
        with Abbreviations(db=BeoDB(tmp_path / "empty.duckdb")) as abbr:
            assert abbr._db.table_exists(TABLE_NAME) is False

    def test_load(self, tmp_path: Path) -> None:
        """Should load abbreviations from XML."""
        with Abbreviations(db=BeoDB(tmp_path / "abbrev_test.duckdb")) as abbr:
            count = abbr.load()
            assert count == 632
            assert abbr._db.table_exists(TABLE_NAME)

    def test_load_skips_if_exists(self, tmp_path: Path) -> None:
        """Loading again without force should skip."""
        with Abbreviations(db=BeoDB(tmp_path / "abbrev_skip.duckdb")) as abbr:
            abbr.load()
            initial_count = abbr._db.count(TABLE_NAME)
            abbr.load(force=False)
            assert abbr._db.count(TABLE_NAME) == initial_count

    def test_load_force_reloads(self, tmp_path: Path) -> None:
        """Loading with force=True should reload the data."""
        with Abbreviations(db=BeoDB(tmp_path / "abbrev_force.duckdb")) as abbr:
            abbr.load()
            assert abbr._db.count(TABLE_NAME) == 632
            # Force reload
            count = abbr.load(force=True)
            assert count == 632

    def test_lookup(self, tmp_path: Path) -> None:
        """Should find abbreviations by partial match."""
        with Abbreviations(db=BeoDB(tmp_path / "abbrev_lookup.duckdb")) as abbr:
            abbr.load()
            results = abbr.lookup("Beo.")
            assert len(results) >= 1
            assert any("Beowulf" in r["description"] for r in results)

    def test_lookup_returns_all_fields(self, tmp_path: Path) -> None:
        """Lookup should return abbreviation, expansion, and description."""
        with Abbreviations(db=BeoDB(tmp_path / "abbrev_fields.duckdb")) as abbr:
            abbr.load()
            results = abbr.lookup("Beo.")
            assert len(results) >= 1
            result = results[0]
            assert "abbreviation" in result
            assert "expansion" in result
            assert "description" in result

    def test_context_manager(self, tmp_path: Path) -> None:
        """Context manager should properly close connection."""
        with Abbreviations(db=BeoDB(tmp_path / "context.duckdb")) as abbr:
            assert (
                abbr._db._conn is not None or abbr._db.table_exists(TABLE_NAME) is False
            )
        assert abbr._db._conn is None
