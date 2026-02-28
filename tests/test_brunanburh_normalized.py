"""Tests for the BrunanburhNormalized source module."""

from pathlib import Path
from typing import Generator

import pytest

from beowulf_mcp.db import BeoDB
from sources.brunanburh_normalized import TABLE_NAME, BrunanburhNormalized, parse

SAMPLE_HTML = """<!DOCTYPE html><body>
<table class="withrefs">
<tr><td class="ref">Brun 1.</td><td class="line" id="1">

    <span class="corepoem">
    <a href="/word/ang/her">her</a>
    <a href="/word/ang/æþelstan">æþelstan</a>
    <a href="/word/ang/cyning">cyning</a>
    <span class="caesura">||</span>
    <a href="/word/ang/eorla">eorla</a>
    <a href="/word/ang/dryhten">dryhten</a>
    </span>

    <span class="normed">
        <a href="/word/ang_normalised/hēr">Hēr</a>
        <a href="/word/ang_normalised/æðelstān">Æðel·stān</a>
        <a href="/word/ang_normalised/cyning">cyning,</a>
        <span class="caesura">||</span>
        <a href="/word/ang_normalised/eorla">eorla</a>
        <a href="/word/ang_normalised/drihten">drihten,</a>
    </span>

    <span class="metre"><br />Bliss: 3B1a</span>
    <span class="syntax"><br />Syntax: NN</span>
    <span class="allit"><br />hs: V</span>
</td></tr>

<tr><td class="ref">Brun 2.</td><td class="line" id="2">

    <span class="corepoem">
    <a href="/word/ang/beorna">beorna</a>
    <a href="/word/ang/beahgifa">beahgifa</a>
    <span class="caesura">||</span>
    <a href="/word/ang/and">and</a>
    <a href="/word/ang/his">his</a>
    <a href="/word/ang/broþor">broþor</a>
    <a href="/word/ang/eac">eac</a>
    </span>

    <span class="normed">
        <a href="/word/ang_normalised/beorna">beorna</a>
        <a href="/word/ang_normalised/bēahġiefa">bēah-ġiefa</a>
        <span class="caesura">||</span>
        <a href="/word/ang_normalised/and">and</a>
        <a href="/word/ang_normalised/his">his</a>
        <a href="/word/ang_normalised/brōðor">brōðor</a>
        <a href="/word/ang_normalised/ēac">ēac,</a>
    </span>

    <span class="metre"><br />Bliss: 1D*3</span>
</td></tr>

<tr><td class="ref">Brun 3.</td><td class="line" id="3">

    <span class="corepoem">
    <a href="/word/ang/eadmund">eadmund</a>
    <a href="/word/ang/æþeling">æþeling</a>
    <span class="caesura">||</span>
    <a href="/word/ang/ealdorlangne">ealdorlangne</a>
    <a href="/word/ang/tir">tir</a>
    </span>

    <span class="normed">
        <a href="/word/ang_normalised/ēadmund">Ēadmund</a>
        <a href="/word/ang_normalised/æðeling">æðeling,</a>
        <span class="caesura">||</span>
        <a href="/word/ang_normalised/ealdorlangne">ealdor-langne</a>
        <a href="/word/ang_normalised/tīr">tīr</a>
    </span>
</td></tr>
</table>
</body>"""


class TestParse:
    """Tests for the parse() function."""

    def test_parses_correct_count(self) -> None:
        lines = parse(SAMPLE_HTML)
        assert len(lines) == 3

    def test_line_numbers(self) -> None:
        lines = parse(SAMPLE_HTML)
        assert [l["line"] for l in lines] == [1, 2, 3]

    def test_oe_text_extracted(self) -> None:
        lines = parse(SAMPLE_HTML)
        assert lines[0]["oe"] == "her æþelstan cyning    eorla dryhten"

    def test_normed_text_extracted(self) -> None:
        lines = parse(SAMPLE_HTML)
        assert lines[0]["normed"] == "Hēr Æðel·stān cyning,    eorla drihten,"

    def test_caesura_is_four_spaces(self) -> None:
        lines = parse(SAMPLE_HTML)
        assert "    " in lines[0]["oe"]
        assert "    " in lines[0]["normed"]

    def test_metre_syntax_allit_excluded(self) -> None:
        """Metre, syntax, and alliteration spans should not leak into text."""
        lines = parse(SAMPLE_HTML)
        for line in lines:
            assert "Bliss" not in line["oe"]
            assert "Syntax" not in line["normed"]

    def test_empty_html_returns_empty(self) -> None:
        assert parse("<html><body>no table here</body></html>") == []

    def test_normed_preserves_macrons(self) -> None:
        lines = parse(SAMPLE_HTML)
        # Line 1: Hēr has a macron
        assert "Hēr" in lines[0]["normed"]

    def test_normed_preserves_middots(self) -> None:
        lines = parse(SAMPLE_HTML)
        assert "Æðel·stān" in lines[0]["normed"]


class TestBrunanburhNormalized:
    """Tests for the BrunanburhNormalized class."""

    @pytest.fixture
    def bn_with_data(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> Generator[BrunanburhNormalized, None, None]:
        monkeypatch.setattr(
            "sources.brunanburh_normalized.read_asset_text",
            lambda filename: SAMPLE_HTML,
        )
        bn = BrunanburhNormalized(db=BeoDB(tmp_path / "test_bn.duckdb"))
        bn.load()
        yield bn
        bn._db.close()

    def test_table_exists_false_initially(self, tmp_path: Path) -> None:
        with BrunanburhNormalized(db=BeoDB(tmp_path / "empty.duckdb")) as bn:
            assert bn._db.table_exists(TABLE_NAME) is False

    def test_load(self, bn_with_data: BrunanburhNormalized) -> None:
        assert bn_with_data._db.table_exists(TABLE_NAME) is True
        assert bn_with_data._db.count(TABLE_NAME) == 3

    def test_load_skips_if_exists(self, bn_with_data: BrunanburhNormalized) -> None:
        initial_count = bn_with_data._db.count(TABLE_NAME)
        bn_with_data.load(force=False)
        assert bn_with_data._db.count(TABLE_NAME) == initial_count

    def test_load_force_reloads(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "sources.brunanburh_normalized.read_asset_text",
            lambda filename: SAMPLE_HTML,
        )
        with BrunanburhNormalized(db=BeoDB(tmp_path / "force.duckdb")) as bn:
            bn.load()
            assert bn._db.count(TABLE_NAME) == 3
            count = bn.load(force=True)
            assert count == 3

    def test_count(self, bn_with_data: BrunanburhNormalized) -> None:
        assert bn_with_data.count() == 3

    def test_get_line(self, bn_with_data: BrunanburhNormalized) -> None:
        result = bn_with_data.get_line(1)
        assert result is not None
        assert result["line"] == 1
        assert "æþelstan" in result["oe"]
        assert "Æðel·stān" in result["normed"]

    def test_get_line_not_found(self, bn_with_data: BrunanburhNormalized) -> None:
        assert bn_with_data.get_line(9999) is None

    def test_get_lines_range(self, bn_with_data: BrunanburhNormalized) -> None:
        results = bn_with_data.get_lines(1, 2)
        assert len(results) == 2
        assert results[0]["line"] == 1
        assert results[-1]["line"] == 2

    def test_get_lines_from_start(self, bn_with_data: BrunanburhNormalized) -> None:
        results = bn_with_data.get_lines(2)
        assert len(results) == 2
        assert results[0]["line"] == 2

    def test_search(self, bn_with_data: BrunanburhNormalized) -> None:
        results = bn_with_data.search("eadmund")
        assert len(results) == 1
        assert results[0]["line"] == 3

    def test_search_finds_normed(self, bn_with_data: BrunanburhNormalized) -> None:
        results = bn_with_data.search("Ēadmund")
        assert len(results) == 1
        assert results[0]["line"] == 3

    def test_search_oe(self, bn_with_data: BrunanburhNormalized) -> None:
        results = bn_with_data.search_oe("beahgifa")
        assert len(results) == 1
        assert results[0]["line"] == 2

    def test_search_normed(self, bn_with_data: BrunanburhNormalized) -> None:
        results = bn_with_data.search_normed("bēah-ġiefa")
        assert len(results) == 1
        assert results[0]["line"] == 2

    def test_search_no_results(self, bn_with_data: BrunanburhNormalized) -> None:
        assert bn_with_data.search("nonexistent") == []

    def test_context_manager(self, tmp_path: Path) -> None:
        with BrunanburhNormalized(db=BeoDB(tmp_path / "context.duckdb")) as bn:
            assert bn._db.table_exists(TABLE_NAME) is False
        assert bn._db._conn is None
