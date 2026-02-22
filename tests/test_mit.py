"""Tests for the MIT Beowulf module."""

from pathlib import Path
from typing import Generator

import pytest

from beowulf_mcp.db import BeoDB
from sources.mit import TABLE_NAME, Mit, parse_line


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    """Create a sample MIT text file in tmp_path."""
    txt_path = tmp_path / "mit.txt"
    lines = [
        "1 Hwæt! We Gardena     in geardagum,",
        "2 þeodcyninga,     þrym gefrunon,",
        "3 hu ða æþelingas     ellen fremedon.",
        "4 Oft Scyld Scefing     sceaþena þreatum,",
        "5 monegum mægþum,     meodosetla ofteah,",
    ]
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    return txt_path


@pytest.fixture
def mit_with_data(
    tmp_path: Path, sample_txt: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Mit, None, None]:
    """Create a Mit instance with test data loaded."""
    monkeypatch.setattr("sources.mit.get_asset_path", lambda filename: sample_txt)

    m = Mit(db=BeoDB(tmp_path / "test_mit.duckdb"))
    m.load()
    yield m
    m._db.close()


class TestParseLine:
    """Tests for the parse_line function."""

    def test_normal_line(self) -> None:
        result = parse_line("1 Hwæt! We Gardena     in geardagum,")
        assert result == {"line": 1, "oe": "Hwæt! We Gardena     in geardagum,"}

    def test_empty_string(self) -> None:
        assert parse_line("") is None

    def test_blank_line(self) -> None:
        assert parse_line("   \n") is None

    def test_no_match(self) -> None:
        assert parse_line("not a valid line") is None


class TestMit:
    """Tests for Mit class."""

    def test_table_exists_false_initially(self, tmp_path: Path) -> None:
        """Table should not exist before loading."""
        with Mit(db=BeoDB(tmp_path / "empty.duckdb")) as m:
            assert m._db.table_exists(TABLE_NAME) is False

    def test_load(self, mit_with_data: Mit) -> None:
        """Loading TXT should create table with correct row count."""
        assert mit_with_data._db.table_exists(TABLE_NAME) is True
        assert mit_with_data._db.count(TABLE_NAME) == 5

    def test_load_skips_if_exists(self, mit_with_data: Mit) -> None:
        """Loading again without force should skip."""
        initial_count = mit_with_data._db.count(TABLE_NAME)
        mit_with_data.load(force=False)
        assert mit_with_data._db.count(TABLE_NAME) == initial_count

    def test_load_force_reloads(
        self, tmp_path: Path, sample_txt: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Loading with force=True should reload the data."""
        monkeypatch.setattr("sources.mit.get_asset_path", lambda filename: sample_txt)

        with Mit(db=BeoDB(tmp_path / "force_test.duckdb")) as m:
            m.load()
            assert m._db.count(TABLE_NAME) == 5
            count = m.load(force=True)
            assert count == 5

    def test_count(self, mit_with_data: Mit) -> None:
        """Count should return number of lines."""
        assert mit_with_data.count() == 5

    def test_get_line(self, mit_with_data: Mit) -> None:
        """Should return a specific line by number."""
        result = mit_with_data.get_line(1)
        assert result is not None
        assert result["line"] == 1
        assert "Hwæt" in result["oe"]

    def test_get_line_not_found(self, mit_with_data: Mit) -> None:
        """Should return None for missing line."""
        assert mit_with_data.get_line(9999) is None

    def test_get_lines_range(self, mit_with_data: Mit) -> None:
        """Should return lines in a range."""
        results = mit_with_data.get_lines(2, 4)
        assert len(results) == 3
        assert results[0]["line"] == 2
        assert results[-1]["line"] == 4

    def test_get_lines_from_start(self, mit_with_data: Mit) -> None:
        """Should return all lines from start when no end given."""
        results = mit_with_data.get_lines(3)
        assert len(results) == 3
        assert results[0]["line"] == 3

    def test_search(self, mit_with_data: Mit) -> None:
        """Should find lines containing the search term."""
        results = mit_with_data.search("Scyld")
        assert len(results) == 1
        assert results[0]["line"] == 4

    def test_search_case_insensitive(self, mit_with_data: Mit) -> None:
        """Search should be case-insensitive."""
        results = mit_with_data.search("hwæt")
        assert len(results) == 1
        assert results[0]["line"] == 1

    def test_search_no_results(self, mit_with_data: Mit) -> None:
        """Search should return empty list for no matches."""
        assert mit_with_data.search("nonexistent") == []

    def test_context_manager(self, tmp_path: Path) -> None:
        """Context manager should properly close connection."""
        with Mit(db=BeoDB(tmp_path / "context.duckdb")) as m:
            assert m._db._conn is not None or m._db.table_exists(TABLE_NAME) is False
        assert m._db._conn is None
