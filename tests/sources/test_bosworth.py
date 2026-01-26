"""Tests for the Bosworth-Toller dictionary module."""

from pathlib import Path
from typing import Generator

import pytest

from beodata.db import _quote_identifier
from beodata.sources.bosworth import TABLE_NAME, BosworthToller


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """Create a sample CSV file for testing with @ delimiter, no header."""
    csv_path = tmp_path / "oe_bt.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        # Use @ as delimiter since definitions contain commas, no header row
        f.write("<b>cyning</b>@king, ruler@Beowulf 11\n")
        f.write("<i>cynn</i>@kin, race, family@Beowulf 98\n")
        f.write("cyne-rīce@kingdom@Beowulf 466\n")
        f.write("<b>burg</b>@fortified place, castle@Beowulf 53\n")
        f.write("beorn@man, warrior, hero@Beowulf 211\n")
    return csv_path


@pytest.fixture
def bt_with_data(
    tmp_path: Path, sample_csv: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[BosworthToller, None, None]:
    """Create a BosworthToller instance with test data loaded."""
    db_path = tmp_path / "test_beodb.duckdb"

    # Monkeypatch get_asset_path to return our test CSV
    monkeypatch.setattr(
        "beodata.sources.bosworth.get_asset_path", lambda filename: sample_csv
    )

    bt = BosworthToller(db_path=db_path)
    bt.load_from_csv()
    yield bt
    bt.db.close()


class TestBosworthToller:
    """Tests for BosworthToller class."""

    def test_table_exists_false_initially(self, tmp_path: Path) -> None:
        """Table should not exist before loading."""
        db_path = tmp_path / "empty.duckdb"
        with BosworthToller(db_path=db_path) as bt:
            assert bt._db.table_exists(TABLE_NAME) is False

    def test_load_from_csv(self, bt_with_data: BosworthToller) -> None:
        """Loading CSV should create table with correct row count."""
        assert bt_with_data._db.table_exists(TABLE_NAME) is True
        assert bt_with_data._db.count(TABLE_NAME) == 5

    def test_load_from_csv_skips_if_exists(self, bt_with_data: BosworthToller) -> None:
        """Loading again without force should skip."""
        initial_count = bt_with_data._db.count(TABLE_NAME)
        bt_with_data.load_from_csv(force=False)
        assert bt_with_data._db.count(TABLE_NAME) == initial_count

    def test_load_from_csv_force_reloads(
        self, tmp_path: Path, sample_csv: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Loading with force=True should reload the data."""
        db_path = tmp_path / "force_test.duckdb"
        monkeypatch.setattr(
            "beodata.sources.bosworth.get_asset_path", lambda filename: sample_csv
        )

        with BosworthToller(db_path=db_path) as bt:
            bt.load_from_csv()
            assert bt._db.count(TABLE_NAME) == 5
            # Force reload
            count = bt.load_from_csv(force=True)
            assert count == 5

    def test_get_columns(self, bt_with_data: BosworthToller) -> None:
        """Should return correct column names."""
        columns = bt_with_data._db.get_columns(TABLE_NAME)
        assert columns == ["headword", "definition", "references", "cleaned_definition"]

    def test_lookup_exact_match(self, bt_with_data: BosworthToller) -> None:
        """Lookup should find exact headword matches."""
        results = bt_with_data.lookup("cyning")
        assert len(results) == 1
        assert results[0]["headword"] == "cyning"
        assert results[0]["definition"] == "king, ruler"

    def test_html_stripped_from_headword(self, bt_with_data: BosworthToller) -> None:
        """HTML tags should be stripped from headwords."""
        # The CSV has <b>cyning</b> but lookup should work with plain text
        results = bt_with_data.lookup("cyning")
        assert len(results) == 1
        assert "<b>" not in results[0]["headword"]
        assert "</b>" not in results[0]["headword"]

    def test_commas_preserved_in_definition(self, bt_with_data: BosworthToller) -> None:
        """Commas should be preserved in definitions (@ delimiter works)."""
        results = bt_with_data.lookup("cynn")
        assert len(results) == 1
        assert results[0]["definition"] == "kin, race, family"

    def test_lookup_no_match(self, bt_with_data: BosworthToller) -> None:
        """Lookup should return empty list for no match."""
        results = bt_with_data.lookup("nonexistent")
        assert results == []

    def test_lookup_like_prefix(self, bt_with_data: BosworthToller) -> None:
        """Lookup like should match prefix patterns."""
        results = bt_with_data.lookup_like("cyn%")
        assert len(results) == 3
        headwords = [r["headword"] for r in results]
        assert "cyning" in headwords
        assert "cynn" in headwords
        assert "cyne-rīce" in headwords

    def test_lookup_like_no_match(self, bt_with_data: BosworthToller) -> None:
        """Lookup like should return empty list for no match."""
        results = bt_with_data.lookup_like("xyz%")
        assert results == []

    def test_search_in_definition(self, bt_with_data: BosworthToller) -> None:
        """Search should find terms in definitions."""
        results = bt_with_data.search("warrior")
        assert len(results) == 1
        assert results[0]["headword"] == "beorn"

    def test_search_case_insensitive(self, bt_with_data: BosworthToller) -> None:
        """Search should be case-insensitive."""
        results = bt_with_data.search("KING")
        assert len(results) >= 1
        headwords = [r["headword"] for r in results]
        assert "cyning" in headwords

    def test_search_specific_column(self, bt_with_data: BosworthToller) -> None:
        """Search with column specified should only search that column."""
        results = bt_with_data.search("Beowulf", column="references")
        assert len(results) == 5  # All entries have Beowulf references

    def test_cleaned_definition_exists(self, bt_with_data: BosworthToller) -> None:
        """Should have cleaned_definition column without HTML."""
        results = bt_with_data.lookup("cyning")
        assert len(results) == 1
        # Original definition keeps HTML for display
        assert "king, ruler" in results[0]["definition"]
        # cleaned_definition has no HTML tags
        assert "<" not in results[0]["cleaned_definition"]
        assert ">" not in results[0]["cleaned_definition"]

    def test_context_manager(self, tmp_path: Path) -> None:
        """Context manager should properly close connection."""
        db_path = tmp_path / "context.duckdb"
        with BosworthToller(db_path=db_path) as bt:
            assert bt._db._conn is not None or bt._db.table_exists(TABLE_NAME) is False
        assert bt._db._conn is None


class TestQuoteIdentifier:
    """Tests for SQL identifier quoting."""

    def test_simple_name(self) -> None:
        """Simple names should be quoted."""
        assert _quote_identifier("headword") == '"headword"'

    def test_name_with_double_quote(self) -> None:
        """Double quotes in names should be escaped by doubling."""
        assert _quote_identifier('foo"bar') == '"foo""bar"'

    def test_name_with_multiple_quotes(self) -> None:
        """Multiple double quotes should all be escaped."""
        assert _quote_identifier('a"b"c') == '"a""b""c"'

    def test_reserved_word(self) -> None:
        """Reserved words should be safely quoted."""
        assert _quote_identifier("references") == '"references"'
