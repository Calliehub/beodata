"""Tests for the Old English Aerobics Beowulf module."""

from pathlib import Path
from typing import Generator

import pytest

from beowulf_mcp.db import BeoDB
from sources.oldenglishaerobics import TABLE_NAME, OldEnglishAerobics, parse_line


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    """Create a sample Old English Aerobics text file in tmp_path."""
    txt_path = tmp_path / "oldenglishaerobics.txt"
    lines = [
        "1 Hwæt, wē Gārdena     in ġeārdagum",
        "2 þēodcyninga     þrym ġefrūnon",
        "3 hū ðā æþelingas     ellen fremedon.",
        "4 Oft Scyld Scēfing     sceaþena þrēatum,",
        "5 monegum mǣġþum     meodosetla oftēah,",
    ]
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    return txt_path


@pytest.fixture
def oea_with_data(
    tmp_path: Path, sample_txt: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[OldEnglishAerobics, None, None]:
    """Create an OldEnglishAerobics instance with test data loaded."""
    monkeypatch.setattr(
        "sources.oldenglishaerobics.get_asset_path", lambda filename: sample_txt
    )

    oea = OldEnglishAerobics(db=BeoDB(tmp_path / "test_oea.duckdb"))
    oea.load_from_txt()
    yield oea
    oea._db.close()


class TestParseLine:
    """Tests for the parse_line function."""

    def test_normal_line(self) -> None:
        result = parse_line("1 Hwæt, wē Gārdena     in ġeārdagum")
        assert result == {"line": 1, "oe": "Hwæt, wē Gārdena     in ġeārdagum"}

    def test_empty_string(self) -> None:
        assert parse_line("") is None

    def test_blank_line(self) -> None:
        assert parse_line("   \n") is None

    def test_no_match(self) -> None:
        assert parse_line("not a valid line") is None


class TestOldEnglishAerobics:
    """Tests for OldEnglishAerobics class."""

    def test_table_exists_false_initially(self, tmp_path: Path) -> None:
        """Table should not exist before loading."""
        with OldEnglishAerobics(db=BeoDB(tmp_path / "empty.duckdb")) as oea:
            assert oea._db.table_exists(TABLE_NAME) is False

    def test_load_from_txt(self, oea_with_data: OldEnglishAerobics) -> None:
        """Loading TXT should create table with correct row count."""
        assert oea_with_data._db.table_exists(TABLE_NAME) is True
        assert oea_with_data._db.count(TABLE_NAME) == 5

    def test_load_skips_if_exists(self, oea_with_data: OldEnglishAerobics) -> None:
        """Loading again without force should skip."""
        initial_count = oea_with_data._db.count(TABLE_NAME)
        oea_with_data.load_from_txt(force=False)
        assert oea_with_data._db.count(TABLE_NAME) == initial_count

    def test_load_force_reloads(
        self, tmp_path: Path, sample_txt: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Loading with force=True should reload the data."""
        monkeypatch.setattr(
            "sources.oldenglishaerobics.get_asset_path", lambda filename: sample_txt
        )

        with OldEnglishAerobics(db=BeoDB(tmp_path / "force_test.duckdb")) as oea:
            oea.load_from_txt()
            assert oea._db.count(TABLE_NAME) == 5
            count = oea.load_from_txt(force=True)
            assert count == 5

    def test_count(self, oea_with_data: OldEnglishAerobics) -> None:
        """Count should return number of lines."""
        assert oea_with_data.count() == 5

    def test_get_line(self, oea_with_data: OldEnglishAerobics) -> None:
        """Should return a specific line by number."""
        result = oea_with_data.get_line(1)
        assert result is not None
        assert result["line"] == 1
        assert "Hwæt" in result["oe"]

    def test_get_line_not_found(self, oea_with_data: OldEnglishAerobics) -> None:
        """Should return None for missing line."""
        assert oea_with_data.get_line(9999) is None

    def test_get_lines_range(self, oea_with_data: OldEnglishAerobics) -> None:
        """Should return lines in a range."""
        results = oea_with_data.get_lines(2, 4)
        assert len(results) == 3
        assert results[0]["line"] == 2
        assert results[-1]["line"] == 4

    def test_get_lines_from_start(self, oea_with_data: OldEnglishAerobics) -> None:
        """Should return all lines from start when no end given."""
        results = oea_with_data.get_lines(3)
        assert len(results) == 3
        assert results[0]["line"] == 3

    def test_search(self, oea_with_data: OldEnglishAerobics) -> None:
        """Should find lines containing the search term."""
        results = oea_with_data.search("Scyld")
        assert len(results) == 1
        assert results[0]["line"] == 4

    def test_search_case_insensitive(self, oea_with_data: OldEnglishAerobics) -> None:
        """Search should be case-insensitive."""
        results = oea_with_data.search("hwæt")
        assert len(results) == 1
        assert results[0]["line"] == 1

    def test_search_no_results(self, oea_with_data: OldEnglishAerobics) -> None:
        """Search should return empty list for no matches."""
        assert oea_with_data.search("nonexistent") == []

    def test_context_manager(self, tmp_path: Path) -> None:
        """Context manager should properly close connection."""
        with OldEnglishAerobics(db=BeoDB(tmp_path / "context.duckdb")) as oea:
            assert (
                oea._db._conn is not None or oea._db.table_exists(TABLE_NAME) is False
            )
        assert oea._db._conn is None
