"""Tests for the Brunanburh source module."""

from pathlib import Path
from typing import Generator

import pytest

from beowulf_mcp.db import BeoDB
from sources.brunanburh import TABLE_NAME, Brunanburh, parse

SAMPLE_HTML = """<HTML><BODY>
<h1>The Battle of Brunanburh</h1>
<dl compact>
<dt></dt>
<dd>
Her &aelig;&thorn;elstan cyning, &nbsp;&nbsp;&nbsp;&nbsp; eorla dryhten, <br>
beorna beahgifa, &nbsp;&nbsp;&nbsp;&nbsp; and his bro&thorn;or eac, <br>
Eadmund &aelig;&thorn;eling, &nbsp;&nbsp;&nbsp;&nbsp; ealdorlangne tir <br>
geslogon &aelig;t s&aelig;cce &nbsp;&nbsp;&nbsp;&nbsp; sweorda ecgum <br>
</dd>
<dt>5</dt>
<dd>
ymbe Brunanburh. &nbsp;&nbsp;&nbsp;&nbsp; Bordweal clufan, <br>
heowan hea&thorn;olinde &nbsp;&nbsp;&nbsp;&nbsp; hamora lafan, <br>
</dd>
</dl>
</BODY></HTML>"""


class TestParse:
    """Tests for the parse() function."""

    def test_parses_correct_count(self) -> None:
        lines = parse(SAMPLE_HTML)
        assert len(lines) == 6

    def test_first_line_number(self) -> None:
        lines = parse(SAMPLE_HTML)
        assert lines[0]["line"] == 1

    def test_line_numbering_continues_at_dt(self) -> None:
        lines = parse(SAMPLE_HTML)
        assert lines[4]["line"] == 5

    def test_html_entities_decoded(self) -> None:
        lines = parse(SAMPLE_HTML)
        # &aelig; → æ, &thorn; → þ
        assert "æþelstan" in lines[0]["oe"]

    def test_strong_tags_stripped(self) -> None:
        html = """<dl compact><dt></dt><dd>
        <strong>heardes</strong> hondplegan <br>
        </dd></dl>"""
        lines = parse(html)
        assert lines[0]["oe"] == "heardes hondplegan"

    def test_caesura_normalized(self) -> None:
        lines = parse(SAMPLE_HTML)
        # The &nbsp;&nbsp;&nbsp;&nbsp; caesura should become 4 spaces
        assert "    " in lines[0]["oe"]

    def test_empty_html_returns_empty(self) -> None:
        assert parse("<html><body>no dl here</body></html>") == []

    def test_empty_br_segments_skipped(self) -> None:
        html = """<dl compact><dt></dt><dd>
        line one <br>
        <br>
        line two <br>
        </dd></dl>"""
        lines = parse(html)
        assert len(lines) == 2


class TestBrunanburh:
    """Tests for the Brunanburh class."""

    @pytest.fixture
    def brunanburh_with_data(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> Generator[Brunanburh, None, None]:
        monkeypatch.setattr(
            "sources.brunanburh.read_asset_text", lambda filename: SAMPLE_HTML
        )
        b = Brunanburh(db=BeoDB(tmp_path / "test_brunanburh.duckdb"))
        b.load()
        yield b
        b._db.close()

    def test_table_exists_false_initially(self, tmp_path: Path) -> None:
        with Brunanburh(db=BeoDB(tmp_path / "empty.duckdb")) as b:
            assert b._db.table_exists(TABLE_NAME) is False

    def test_load(self, brunanburh_with_data: Brunanburh) -> None:
        assert brunanburh_with_data._db.table_exists(TABLE_NAME) is True
        assert brunanburh_with_data._db.count(TABLE_NAME) == 6

    def test_load_skips_if_exists(self, brunanburh_with_data: Brunanburh) -> None:
        initial_count = brunanburh_with_data._db.count(TABLE_NAME)
        brunanburh_with_data.load(force=False)
        assert brunanburh_with_data._db.count(TABLE_NAME) == initial_count

    def test_load_force_reloads(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "sources.brunanburh.read_asset_text", lambda filename: SAMPLE_HTML
        )
        with Brunanburh(db=BeoDB(tmp_path / "force_test.duckdb")) as b:
            b.load()
            assert b._db.count(TABLE_NAME) == 6
            count = b.load(force=True)
            assert count == 6

    def test_count(self, brunanburh_with_data: Brunanburh) -> None:
        assert brunanburh_with_data.count() == 6

    def test_get_line(self, brunanburh_with_data: Brunanburh) -> None:
        result = brunanburh_with_data.get_line(1)
        assert result is not None
        assert result["line"] == 1
        assert "æþelstan" in result["oe"]

    def test_get_line_not_found(self, brunanburh_with_data: Brunanburh) -> None:
        assert brunanburh_with_data.get_line(9999) is None

    def test_get_lines_range(self, brunanburh_with_data: Brunanburh) -> None:
        results = brunanburh_with_data.get_lines(2, 4)
        assert len(results) == 3
        assert results[0]["line"] == 2
        assert results[-1]["line"] == 4

    def test_get_lines_from_start(self, brunanburh_with_data: Brunanburh) -> None:
        results = brunanburh_with_data.get_lines(5)
        assert len(results) == 2
        assert results[0]["line"] == 5

    def test_search(self, brunanburh_with_data: Brunanburh) -> None:
        results = brunanburh_with_data.search("Brunanburh")
        assert len(results) == 1
        assert results[0]["line"] == 5

    def test_search_case_insensitive(self, brunanburh_with_data: Brunanburh) -> None:
        results = brunanburh_with_data.search("brunanburh")
        assert len(results) == 1

    def test_search_no_results(self, brunanburh_with_data: Brunanburh) -> None:
        assert brunanburh_with_data.search("nonexistent") == []

    def test_context_manager(self, tmp_path: Path) -> None:
        with Brunanburh(db=BeoDB(tmp_path / "context.duckdb")) as b:
            assert b._db.table_exists(TABLE_NAME) is False
        assert b._db._conn is None
