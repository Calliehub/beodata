"""Tests for the McMaster University Beowulf module."""

from pathlib import Path
from typing import Generator

import pytest

from beowulf_mcp.db import BeoDB
from sources.mcmaster import TABLE_NAME, McMaster, parse_line


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    """Create a sample McMaster text file in tmp_path."""
    txt_path = tmp_path / "mcmaster.txt"
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
def mcmaster_with_data(
    tmp_path: Path, sample_txt: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[McMaster, None, None]:
    """Create a McMaster instance with test data loaded."""
    monkeypatch.setattr("sources.mcmaster.get_asset_path", lambda filename: sample_txt)

    mc = McMaster(db=BeoDB(tmp_path / "test_mcmaster.duckdb"))
    mc.load_from_txt()
    yield mc
    mc._db.close()


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


class TestMcMaster:
    """Tests for McMaster class."""

    def test_table_exists_false_initially(self, tmp_path: Path) -> None:
        """Table should not exist before loading."""
        with McMaster(db=BeoDB(tmp_path / "empty.duckdb")) as mc:
            assert mc._db.table_exists(TABLE_NAME) is False

    def test_load_from_txt(self, mcmaster_with_data: McMaster) -> None:
        """Loading TXT should create table with correct row count."""
        assert mcmaster_with_data._db.table_exists(TABLE_NAME) is True
        assert mcmaster_with_data._db.count(TABLE_NAME) == 5

    def test_load_skips_if_exists(self, mcmaster_with_data: McMaster) -> None:
        """Loading again without force should skip."""
        initial_count = mcmaster_with_data._db.count(TABLE_NAME)
        mcmaster_with_data.load_from_txt(force=False)
        assert mcmaster_with_data._db.count(TABLE_NAME) == initial_count

    def test_load_force_reloads(
        self, tmp_path: Path, sample_txt: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Loading with force=True should reload the data."""
        monkeypatch.setattr(
            "sources.mcmaster.get_asset_path", lambda filename: sample_txt
        )

        with McMaster(db=BeoDB(tmp_path / "force_test.duckdb")) as mc:
            mc.load_from_txt()
            assert mc._db.count(TABLE_NAME) == 5
            count = mc.load_from_txt(force=True)
            assert count == 5

    def test_count(self, mcmaster_with_data: McMaster) -> None:
        """Count should return number of lines."""
        assert mcmaster_with_data.count() == 5

    def test_get_line(self, mcmaster_with_data: McMaster) -> None:
        """Should return a specific line by number."""
        result = mcmaster_with_data.get_line(1)
        assert result is not None
        assert result["line"] == 1
        assert "Hwæt" in result["oe"]

    def test_get_line_not_found(self, mcmaster_with_data: McMaster) -> None:
        """Should return None for missing line."""
        assert mcmaster_with_data.get_line(9999) is None

    def test_get_lines_range(self, mcmaster_with_data: McMaster) -> None:
        """Should return lines in a range."""
        results = mcmaster_with_data.get_lines(2, 4)
        assert len(results) == 3
        assert results[0]["line"] == 2
        assert results[-1]["line"] == 4

    def test_get_lines_from_start(self, mcmaster_with_data: McMaster) -> None:
        """Should return all lines from start when no end given."""
        results = mcmaster_with_data.get_lines(3)
        assert len(results) == 3
        assert results[0]["line"] == 3

    def test_search(self, mcmaster_with_data: McMaster) -> None:
        """Should find lines containing the search term."""
        results = mcmaster_with_data.search("Scyld")
        assert len(results) == 1
        assert results[0]["line"] == 4

    def test_search_case_insensitive(self, mcmaster_with_data: McMaster) -> None:
        """Search should be case-insensitive."""
        results = mcmaster_with_data.search("hwæt")
        assert len(results) == 1
        assert results[0]["line"] == 1

    def test_search_no_results(self, mcmaster_with_data: McMaster) -> None:
        """Search should return empty list for no matches."""
        assert mcmaster_with_data.search("nonexistent") == []

    def test_context_manager(self, tmp_path: Path) -> None:
        """Context manager should properly close connection."""
        with McMaster(db=BeoDB(tmp_path / "context.duckdb")) as mc:
            assert mc._db._conn is not None or mc._db.table_exists(TABLE_NAME) is False
        assert mc._db._conn is None
