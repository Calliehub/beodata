"""Tests for the Brunetti tokenized Beowulf module."""

from pathlib import Path
from typing import Generator

import pytest

from beowulf_mcp.db import BeoDB
from sources.brunetti import COLUMNS, TABLE_NAME, Brunetti


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    """Create a sample pipe-delimited test file in tmp_path."""
    txt_path = tmp_path / "brunetti-length.txt"
    lines = [
        "00|001|1|0|0001|a|1|-||Hwæt|!|||hwæt|e||well|Hwæt",
        "00|001|0|0|0001|a|2|-||We|||np|we|p||we|Wē",
        "00|001|0|0|0001|a|3|/||Gar-Dena|||gp|Gar-Dene|np||Spear-Danes|Gār-Dena",
        "00|001|0|0|0001|b|1|/||in||rd||in|pp||in|in",
        "00|001|0|0|0001|b|2|-||geardagum|,||dp|gear-dagas|m||days of yore|gēardagum",
        "01|002|1|0|0053|a|1|/||þeodcyninga|||gp|cyning|m||king|þēodcyninga",
    ]
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    return txt_path


@pytest.fixture
def brunetti_with_data(
    tmp_path: Path, sample_txt: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Brunetti, None, None]:
    """Create a Brunetti instance with test data loaded."""
    monkeypatch.setattr("sources.brunetti.get_asset_path", lambda filename: sample_txt)

    br = Brunetti(db=BeoDB(tmp_path / "test_brunetti.duckdb"))
    br.load_from_txt()
    yield br
    br._db.close()


class TestBrunetti:
    """Tests for Brunetti class."""

    def test_table_exists_false_initially(self, tmp_path: Path) -> None:
        """Table should not exist before loading."""
        with Brunetti(db=BeoDB(tmp_path / "empty.duckdb")) as br:
            assert br._db.table_exists(TABLE_NAME) is False

    def test_load_from_txt(self, brunetti_with_data: Brunetti) -> None:
        """Loading TXT should create table with correct row count."""
        assert brunetti_with_data._db.table_exists(TABLE_NAME) is True
        assert brunetti_with_data._db.count(TABLE_NAME) == 6

    def test_load_skips_if_exists(self, brunetti_with_data: Brunetti) -> None:
        """Loading again without force should skip."""
        initial_count = brunetti_with_data._db.count(TABLE_NAME)
        brunetti_with_data.load_from_txt(force=False)
        assert brunetti_with_data._db.count(TABLE_NAME) == initial_count

    def test_load_force_reloads(
        self, tmp_path: Path, sample_txt: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Loading with force=True should reload the data."""
        monkeypatch.setattr(
            "sources.brunetti.get_asset_path", lambda filename: sample_txt
        )

        with Brunetti(db=BeoDB(tmp_path / "force_test.duckdb")) as br:
            br.load_from_txt()
            assert br._db.count(TABLE_NAME) == 6
            count = br.load_from_txt(force=True)
            assert count == 6

    def test_get_columns(self, brunetti_with_data: Brunetti) -> None:
        """Should return all 18 column names."""
        columns = brunetti_with_data._db.get_columns(TABLE_NAME)
        assert columns == COLUMNS

    def test_lookup_exact(self, brunetti_with_data: Brunetti) -> None:
        """Lookup lemma 'cyning' returns match."""
        results = brunetti_with_data.lookup("cyning")
        assert len(results) == 1
        assert results[0]["lemma"] == "cyning"
        assert results[0]["gloss"] == "king"

    def test_lookup_no_match(self, brunetti_with_data: Brunetti) -> None:
        """Lookup should return empty list for no match."""
        results = brunetti_with_data.lookup("nonexistent")
        assert results == []

    def test_lookup_like_prefix(self, brunetti_with_data: Brunetti) -> None:
        """Lookup like 'Gar%' finds Gar-Dene."""
        results = brunetti_with_data.lookup_like("Gar%")
        assert len(results) == 1
        assert results[0]["lemma"] == "Gar-Dene"

    def test_search_in_gloss(self, brunetti_with_data: Brunetti) -> None:
        """Search 'king' finds match in gloss."""
        results = brunetti_with_data.search("king")
        assert len(results) >= 1
        glosses = [r["gloss"] for r in results]
        assert "king" in glosses

    def test_search_specific_column(self, brunetti_with_data: Brunetti) -> None:
        """Search with column param restricts to that column."""
        results = brunetti_with_data.search("days of yore", column="gloss")
        assert len(results) == 1
        assert results[0]["lemma"] == "gear-dagas"

    def test_get_by_line(self, brunetti_with_data: Brunetti) -> None:
        """Returns all tokens for a line."""
        results = brunetti_with_data.get_by_line("0001")
        assert len(results) == 5
        # Should be ordered by half_line, token_offset
        assert results[0]["half_line"] == "a"
        assert results[-1]["half_line"] == "b"

    def test_get_by_fitt(self, brunetti_with_data: Brunetti) -> None:
        """Returns tokens for fitt 00."""
        results = brunetti_with_data.get_by_fitt("00")
        assert len(results) == 5
        assert all(r["fitt_id"] == "00" for r in results)

    def test_context_manager(self, tmp_path: Path) -> None:
        """Context manager should properly close connection."""
        with Brunetti(db=BeoDB(tmp_path / "context.duckdb")) as br:
            assert br._db._conn is not None or br._db.table_exists(TABLE_NAME) is False
        assert br._db._conn is None
