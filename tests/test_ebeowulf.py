"""Tests for the eBeowulf module."""

from pathlib import Path
from typing import Generator

import pytest

from beowulf_mcp.db import BeoDB
from sources.ebeowulf import TABLE_NAME, EBeowulf, parse_line


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    """Create a sample eBeowulf text file in tmp_path."""
    txt_path = tmp_path / "ebeowulf.txt"
    lines = [
        "1 HWÆT: WE GAR-DENA     IN GEARDAGUM",
        "2 þeodcyninga     þrym gefrunon.",
        "3 Hu ða æþelingas     ellen fremedon!",
        "4 Oft Scyld Scefing     sceaþena þreatum",
        "5 monegum mægþum     meodosetla ofteah,",
    ]
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    return txt_path


@pytest.fixture
def ebeowulf_with_data(
    tmp_path: Path, sample_txt: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[EBeowulf, None, None]:
    """Create an EBeowulf instance with test data loaded."""
    monkeypatch.setattr("sources.ebeowulf.get_asset_path", lambda filename: sample_txt)

    eb = EBeowulf(db=BeoDB(tmp_path / "test_ebeowulf.duckdb"))
    eb.load()
    yield eb
    eb._db.close()


class TestParseLine:
    """Tests for the parse_line function."""

    def test_normal_line(self) -> None:
        result = parse_line("1 HWÆT: WE GAR-DENA     IN GEARDAGUM")
        assert result == {"line": 1, "oe": "HWÆT: WE GAR-DENA     IN GEARDAGUM"}

    def test_empty_string(self) -> None:
        assert parse_line("") is None

    def test_blank_line(self) -> None:
        assert parse_line("   \n") is None

    def test_no_match(self) -> None:
        assert parse_line("not a valid line") is None


class TestEBeowulf:
    """Tests for EBeowulf class."""

    def test_table_exists_false_initially(self, tmp_path: Path) -> None:
        """Table should not exist before loading."""
        with EBeowulf(db=BeoDB(tmp_path / "empty.duckdb")) as eb:
            assert eb._db.table_exists(TABLE_NAME) is False

    def test_load(self, ebeowulf_with_data: EBeowulf) -> None:
        """Loading TXT should create table with correct row count."""
        assert ebeowulf_with_data._db.table_exists(TABLE_NAME) is True
        assert ebeowulf_with_data._db.count(TABLE_NAME) == 5

    def test_load_skips_if_exists(self, ebeowulf_with_data: EBeowulf) -> None:
        """Loading again without force should skip."""
        initial_count = ebeowulf_with_data._db.count(TABLE_NAME)
        ebeowulf_with_data.load(force=False)
        assert ebeowulf_with_data._db.count(TABLE_NAME) == initial_count

    def test_load_force_reloads(
        self, tmp_path: Path, sample_txt: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Loading with force=True should reload the data."""
        monkeypatch.setattr(
            "sources.ebeowulf.get_asset_path", lambda filename: sample_txt
        )

        with EBeowulf(db=BeoDB(tmp_path / "force_test.duckdb")) as eb:
            eb.load()
            assert eb._db.count(TABLE_NAME) == 5
            count = eb.load(force=True)
            assert count == 5

    def test_count(self, ebeowulf_with_data: EBeowulf) -> None:
        """Count should return number of lines."""
        assert ebeowulf_with_data.count() == 5

    def test_get_line(self, ebeowulf_with_data: EBeowulf) -> None:
        """Should return a specific line by number."""
        result = ebeowulf_with_data.get_line(1)
        assert result is not None
        assert result["line"] == 1
        assert "HWÆT" in result["oe"]

    def test_get_line_not_found(self, ebeowulf_with_data: EBeowulf) -> None:
        """Should return None for missing line."""
        assert ebeowulf_with_data.get_line(9999) is None

    def test_get_lines_range(self, ebeowulf_with_data: EBeowulf) -> None:
        """Should return lines in a range."""
        results = ebeowulf_with_data.get_lines(2, 4)
        assert len(results) == 3
        assert results[0]["line"] == 2
        assert results[-1]["line"] == 4

    def test_get_lines_from_start(self, ebeowulf_with_data: EBeowulf) -> None:
        """Should return all lines from start when no end given."""
        results = ebeowulf_with_data.get_lines(3)
        assert len(results) == 3
        assert results[0]["line"] == 3

    def test_search(self, ebeowulf_with_data: EBeowulf) -> None:
        """Should find lines containing the search term."""
        results = ebeowulf_with_data.search("Scyld")
        assert len(results) == 1
        assert results[0]["line"] == 4

    def test_search_case_insensitive(self, ebeowulf_with_data: EBeowulf) -> None:
        """Search should be case-insensitive."""
        results = ebeowulf_with_data.search("hwæt")
        assert len(results) == 1
        assert results[0]["line"] == 1

    def test_search_no_results(self, ebeowulf_with_data: EBeowulf) -> None:
        """Search should return empty list for no matches."""
        assert ebeowulf_with_data.search("nonexistent") == []

    def test_context_manager(self, tmp_path: Path) -> None:
        """Context manager should properly close connection."""
        with EBeowulf(db=BeoDB(tmp_path / "context.duckdb")) as eb:
            assert eb._db._conn is not None or eb._db.table_exists(TABLE_NAME) is False
        assert eb._db._conn is None
