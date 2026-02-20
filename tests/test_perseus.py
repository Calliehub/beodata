"""Tests for the Perseus Digital Library Beowulf module."""

from pathlib import Path
from typing import Generator

import pytest

from beowulf_mcp.db import BeoDB
from sources.perseus import TABLE_NAME, Perseus, parse_line


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    """Create a sample Perseus text file in tmp_path."""
    txt_path = tmp_path / "perseus.txt"
    lines = [
        "1 Hwæt, wē Gār-Dena     in gēardagum,",
        "2 þēodcyninga     þrym gefrūnon,",
        "3 hū ðā æþelingas     ellen fremedon!",
        "4 Oft Scyld Scēfing     sceaþena þrēatum,",
        "5 monegum mǣgþum     meodosetla oftēah,",
    ]
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    return txt_path


@pytest.fixture
def perseus_with_data(
    tmp_path: Path, sample_txt: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Perseus, None, None]:
    """Create a Perseus instance with test data loaded."""
    monkeypatch.setattr("sources.perseus.get_asset_path", lambda filename: sample_txt)

    p = Perseus(db=BeoDB(tmp_path / "test_perseus.duckdb"))
    p.load_from_txt()
    yield p
    p._db.close()


class TestParseLine:
    """Tests for the parse_line function."""

    def test_normal_line(self) -> None:
        result = parse_line("1 Hwæt, wē Gār-Dena     in gēardagum,")
        assert result == {"line": 1, "oe": "Hwæt, wē Gār-Dena     in gēardagum,"}

    def test_empty_string(self) -> None:
        assert parse_line("") is None

    def test_blank_line(self) -> None:
        assert parse_line("   \n") is None

    def test_no_match(self) -> None:
        assert parse_line("not a valid line") is None


class TestPerseus:
    """Tests for Perseus class."""

    def test_table_exists_false_initially(self, tmp_path: Path) -> None:
        """Table should not exist before loading."""
        with Perseus(db=BeoDB(tmp_path / "empty.duckdb")) as p:
            assert p._db.table_exists(TABLE_NAME) is False

    def test_load_from_txt(self, perseus_with_data: Perseus) -> None:
        """Loading TXT should create table with correct row count."""
        assert perseus_with_data._db.table_exists(TABLE_NAME) is True
        assert perseus_with_data._db.count(TABLE_NAME) == 5

    def test_load_skips_if_exists(self, perseus_with_data: Perseus) -> None:
        """Loading again without force should skip."""
        initial_count = perseus_with_data._db.count(TABLE_NAME)
        perseus_with_data.load_from_txt(force=False)
        assert perseus_with_data._db.count(TABLE_NAME) == initial_count

    def test_load_force_reloads(
        self, tmp_path: Path, sample_txt: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Loading with force=True should reload the data."""
        monkeypatch.setattr(
            "sources.perseus.get_asset_path", lambda filename: sample_txt
        )

        with Perseus(db=BeoDB(tmp_path / "force_test.duckdb")) as p:
            p.load_from_txt()
            assert p._db.count(TABLE_NAME) == 5
            count = p.load_from_txt(force=True)
            assert count == 5

    def test_count(self, perseus_with_data: Perseus) -> None:
        """Count should return number of lines."""
        assert perseus_with_data.count() == 5

    def test_get_line(self, perseus_with_data: Perseus) -> None:
        """Should return a specific line by number."""
        result = perseus_with_data.get_line(1)
        assert result is not None
        assert result["line"] == 1
        assert "Hwæt" in result["oe"]

    def test_get_line_not_found(self, perseus_with_data: Perseus) -> None:
        """Should return None for missing line."""
        assert perseus_with_data.get_line(9999) is None

    def test_get_lines_range(self, perseus_with_data: Perseus) -> None:
        """Should return lines in a range."""
        results = perseus_with_data.get_lines(2, 4)
        assert len(results) == 3
        assert results[0]["line"] == 2
        assert results[-1]["line"] == 4

    def test_get_lines_from_start(self, perseus_with_data: Perseus) -> None:
        """Should return all lines from start when no end given."""
        results = perseus_with_data.get_lines(3)
        assert len(results) == 3
        assert results[0]["line"] == 3

    def test_search(self, perseus_with_data: Perseus) -> None:
        """Should find lines containing the search term."""
        results = perseus_with_data.search("Scyld")
        assert len(results) == 1
        assert results[0]["line"] == 4

    def test_search_case_insensitive(self, perseus_with_data: Perseus) -> None:
        """Search should be case-insensitive."""
        results = perseus_with_data.search("hwæt")
        assert len(results) == 1
        assert results[0]["line"] == 1

    def test_search_no_results(self, perseus_with_data: Perseus) -> None:
        """Search should return empty list for no matches."""
        assert perseus_with_data.search("nonexistent") == []

    def test_context_manager(self, tmp_path: Path) -> None:
        """Context manager should properly close connection."""
        with Perseus(db=BeoDB(tmp_path / "context.duckdb")) as p:
            assert p._db._conn is not None or p._db.table_exists(TABLE_NAME) is False
        assert p._db._conn is None
