"""Tests for the Analytical Lexicon of Beowulf module."""

from pathlib import Path
from typing import Generator

import pytest

from beowulf_mcp.db import BeoDB
from sources.analytical_lexicon import COLUMNS, TABLE_NAME, AnalyticalLexicon


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    """Create a sample pipe-delimited lexicon file in tmp_path."""
    txt_path = tmp_path / "analytical_lexicon.txt"
    lines = [
        "á-léogan|II|áléh|pret. 3 sg.|80",
        "á-settan|w1.|áseted|pp.|667",
        "á-settan|w1.|ásetton|pret. 3 pl.|47",
        "æfter/I|prep.|æfter|-|85,117,119",
        "æfter/II|adv.|æfter|-|12,315,341",
        "cyning|m.|cyning|ns.|11,863,920",
        "cyning|m.|cyninga|gp.|2,98",
    ]
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    return txt_path


@pytest.fixture
def lexicon_with_data(
    tmp_path: Path, sample_txt: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[AnalyticalLexicon, None, None]:
    """Create an AnalyticalLexicon instance with test data loaded."""
    monkeypatch.setattr(
        "sources.analytical_lexicon.get_asset_path", lambda filename: sample_txt
    )

    lex = AnalyticalLexicon(db=BeoDB(tmp_path / "test_lexicon.duckdb"))
    lex.load_from_txt()
    yield lex
    lex._db.close()


class TestAnalyticalLexicon:
    """Tests for AnalyticalLexicon class."""

    def test_table_exists_false_initially(self, tmp_path: Path) -> None:
        """Table should not exist before loading."""
        with AnalyticalLexicon(db=BeoDB(tmp_path / "empty.duckdb")) as lex:
            assert lex._db.table_exists(TABLE_NAME) is False

    def test_load_from_txt(self, lexicon_with_data: AnalyticalLexicon) -> None:
        """Loading TXT should create table with correct row count."""
        assert lexicon_with_data._db.table_exists(TABLE_NAME) is True
        assert lexicon_with_data._db.count(TABLE_NAME) == 7

    def test_load_skips_if_exists(self, lexicon_with_data: AnalyticalLexicon) -> None:
        """Loading again without force should skip."""
        initial_count = lexicon_with_data._db.count(TABLE_NAME)
        lexicon_with_data.load_from_txt(force=False)
        assert lexicon_with_data._db.count(TABLE_NAME) == initial_count

    def test_load_force_reloads(
        self, tmp_path: Path, sample_txt: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Loading with force=True should reload the data."""
        monkeypatch.setattr(
            "sources.analytical_lexicon.get_asset_path",
            lambda filename: sample_txt,
        )

        with AnalyticalLexicon(db=BeoDB(tmp_path / "force_test.duckdb")) as lex:
            lex.load_from_txt()
            assert lex._db.count(TABLE_NAME) == 7
            count = lex.load_from_txt(force=True)
            assert count == 7

    def test_get_columns(self, lexicon_with_data: AnalyticalLexicon) -> None:
        """Should return all 5 column names."""
        columns = lexicon_with_data._db.get_columns(TABLE_NAME)
        assert columns == COLUMNS

    def test_lookup_exact(self, lexicon_with_data: AnalyticalLexicon) -> None:
        """Lookup headword 'cyning' returns matches."""
        results = lexicon_with_data.lookup("cyning")
        assert len(results) == 2
        assert all(r["headword"] == "cyning" for r in results)

    def test_lookup_no_match(self, lexicon_with_data: AnalyticalLexicon) -> None:
        """Lookup should return empty list for no match."""
        results = lexicon_with_data.lookup("nonexistent")
        assert results == []

    def test_lookup_like_prefix(self, lexicon_with_data: AnalyticalLexicon) -> None:
        """Lookup like 'á-set%' finds á-settan entries."""
        results = lexicon_with_data.lookup_like("á-set%")
        assert len(results) == 2
        assert all(r["headword"] == "á-settan" for r in results)

    def test_search_in_form(self, lexicon_with_data: AnalyticalLexicon) -> None:
        """Search 'cyninga' finds match in form column."""
        results = lexicon_with_data.search("cyninga")
        assert len(results) >= 1
        forms = [r["form"] for r in results]
        assert "cyninga" in forms

    def test_search_specific_column(self, lexicon_with_data: AnalyticalLexicon) -> None:
        """Search with column param restricts to that column."""
        results = lexicon_with_data.search("pret. 3 sg.", column="inflection")
        assert len(results) == 1
        assert results[0]["headword"] == "á-léogan"

    def test_search_in_line_refs(self, lexicon_with_data: AnalyticalLexicon) -> None:
        """Search for a line number in references."""
        results = lexicon_with_data.search("667", column="line_refs")
        assert len(results) == 1
        assert results[0]["headword"] == "á-settan"

    def test_get_by_headword(self, lexicon_with_data: AnalyticalLexicon) -> None:
        """get_by_headword should return all forms of a headword."""
        results = lexicon_with_data.get_by_headword("á-settan")
        assert len(results) == 2
        forms = {r["form"] for r in results}
        assert forms == {"áseted", "ásetton"}

    def test_context_manager(self, tmp_path: Path) -> None:
        """Context manager should properly close connection."""
        with AnalyticalLexicon(db=BeoDB(tmp_path / "context.duckdb")) as lex:
            assert (
                lex._db._conn is not None or lex._db.table_exists(TABLE_NAME) is False
            )
        assert lex._db._conn is None
