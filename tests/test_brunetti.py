"""Tests for the Brunetti source module."""

import csv
from pathlib import Path
from typing import Generator

import pytest

from beowulf_mcp.db import BeoDB
from sources.brunetti import (
    CSV_COLUMNS,
    TABLE_NAME,
    Brunetti,
    _clean_oe_text,
    _count_real_words,
    _parse_pos_code,
    parse,
    parse_glosses,
)

# Minimal HTML that mirrors the real page structure (3 lines).
SAMPLE_HTML = (
    "<HTML><BODY>"
    '<span class="nverso">0001</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
    "  Hwæt! We Gar-Dena    in geardagum<BR>"
    '<span class="glosse">'
    " <b>hwæt</b> "
    '<a title="INTERJECTION">e  </a> '
    "<i>well</i>&nbsp;&nbsp;/ <i>ecco</i><br>"
    " <b>we</b> "
    '<a title="PRONOUN nominative plural">p np </a> '
    "<i>we</i>&nbsp;&nbsp;/ <i>noi</i><br>"
    " <b>Gar-Dene</b> "
    '<a title="NOUN proper genitive plural">np gp </a> '
    "<i>Spear-Danes</i>&nbsp;&nbsp;/ <i>Danesi delle Lance</i><br>"
    " <b>in</b> "
    '<a title="PREPOSITION with dative">pp-rd  </a> '
    "<i>in</i>&nbsp;&nbsp;/ <i>in</i><br>"
    " <b>gear-dagas</b> "
    '<a title="NOUN masculine dative plural">m dp </a> '
    "<i>days of yore</i>&nbsp;&nbsp;/ <i>giorni remoti</i><br>"
    "</span>"
    '<span class="nverso">0002</span>&nbsp;&nbsp;&nbsp;'
    "  þeodcyninga    þrym gefrunon·<BR>"
    '<span class="glosse">'
    " <b>þeod-cyning</b> "
    '<a title="NOUN masculine genitive plural">m gp </a> '
    "<i>king of the nation</i>&nbsp;&nbsp;/ <i>re della nazione</i><br>"
    " <b>þrym</b> "
    '<a title="NOUN masculine accusative singular">m as </a> '
    "<i>glory</i>&nbsp;&nbsp;/ <i>gloria</i><br>"
    " <b>gefrignan</b> "
    '<a title="VERB with accusative and dependent clause, preterite 1 pl.">'
    "v-a+ p1p </a> "
    "<i>hear</i>&nbsp;&nbsp;/ <i>apprendere</i><br>"
    "</span>"
    # Line with no caesura (all a-verse, like line 552 in the real data)
    '<span class="nverso">0552</span>&nbsp;&nbsp;&nbsp;'
    "  beadohrægl broden on breostum læg<BR>"
    '<span class="glosse">'
    " <b>beadu-hrægl</b> "
    '<a title="NOUN neuter nominative singular">n ns </a> '
    "<i>battle garment</i>&nbsp;&nbsp;/ <i>veste da battaglia</i><br>"
    " <b>bregdan</b> "
    '<a title="VERB past participle nominative singular neuter">v ppnsn </a> '
    "<i>weave</i>&nbsp;&nbsp;/ <i>intrecciare</i><br>"
    " <b>on</b> "
    '<a title="PREPOSITION with dative">pp-rd  </a> '
    "<i>on</i>&nbsp;&nbsp;/ <i>su</i><br>"
    " <b>breost</b> "
    '<a title="NOUN neuter dative plural">n dp </a> '
    "<i>breast</i>&nbsp;&nbsp;/ <i>petto</i><br>"
    " <b>licgan</b> "
    '<a title="VERB preterite 3 sing.">v p3s </a> '
    "<i>lie</i>&nbsp;&nbsp;/ <i>giacere</i><br>"
    "</span>"
    "</BODY></HTML>"
)


# ─────────────────────────────────────────────────────────────
# Unit tests for helper functions
# ─────────────────────────────────────────────────────────────


class TestCleanOeText:
    def test_normalizes_nbsp(self) -> None:
        raw = "&nbsp;&nbsp;&nbsp; Hwæt! We"
        assert _clean_oe_text(raw) == "Hwæt! We"

    def test_normalizes_caesura(self) -> None:
        raw = "Hwæt! We Gar-Dena&nbsp;&nbsp;&nbsp;&nbsp;in geardagum"
        result = _clean_oe_text(raw)
        assert "    " in result

    def test_strips_outer_whitespace(self) -> None:
        assert _clean_oe_text("  hello  ") == "hello"


class TestCountRealWords:
    def test_simple(self) -> None:
        assert _count_real_words("Hwæt We Gar-Dena") == 3

    def test_strips_dashes(self) -> None:
        assert _count_real_words("– blæd wide sprang –") == 3

    def test_strips_brackets(self) -> None:
        assert _count_real_words("hyrde ic þæt [            ]elan cwen") == 5

    def test_empty_string(self) -> None:
        assert _count_real_words("") == 0


class TestParsePosCode:
    def test_simple_pos(self) -> None:
        result = _parse_pos_code("e  ")
        assert result == {"pos": "e", "parse": "", "syntax": ""}

    def test_pos_with_parse(self) -> None:
        result = _parse_pos_code("m gp ")
        assert result == {"pos": "m", "parse": "gp", "syntax": ""}

    def test_pos_with_syntax_and_parse(self) -> None:
        result = _parse_pos_code("v-a p3s ")
        assert result == {"pos": "v", "parse": "p3s", "syntax": "a"}

    def test_complex_syntax(self) -> None:
        result = _parse_pos_code("v-dg p3s ")
        assert result == {"pos": "v", "parse": "p3s", "syntax": "dg"}

    def test_pos_with_plus_syntax(self) -> None:
        result = _parse_pos_code("v-a+ p1p ")
        assert result == {"pos": "v", "parse": "p1p", "syntax": "a+"}

    def test_empty(self) -> None:
        result = _parse_pos_code("")
        assert result == {"pos": "", "parse": "", "syntax": ""}


class TestParseGlosses:
    def test_extracts_entries(self) -> None:
        glosse = (
            '<b>hwæt</b> <a title="INTERJECTION">e  </a> '
            "<i>well</i>&nbsp;&nbsp;/ <i>ecco</i><br>"
            '<b>we</b> <a title="PRONOUN nominative plural">p np </a> '
            "<i>we</i>&nbsp;&nbsp;/ <i>noi</i><br>"
        )
        entries = parse_glosses(glosse)
        assert len(entries) == 2

    def test_entry_fields(self) -> None:
        glosse = (
            '<b>gear-dagas</b> <a title="NOUN masculine dative plural">m dp </a> '
            "<i>days of yore</i>&nbsp;&nbsp;/ <i>giorni remoti</i><br>"
        )
        entries = parse_glosses(glosse)
        assert len(entries) == 1
        e = entries[0]
        assert e["lemma"] == "gear-dagas"
        assert e["pos"] == "m"
        assert e["parse"] == "dp"
        assert e["syntax"] == ""
        assert e["gloss_en"] == "days of yore"
        assert e["gloss_it"] == "giorni remoti"
        assert e["pos_description"] == "NOUN masculine dative plural"

    def test_syntax_in_code(self) -> None:
        glosse = (
            '<b>in</b> <a title="PREPOSITION with dative">pp-rd  </a> '
            "<i>in</i>&nbsp;&nbsp;/ <i>in</i><br>"
        )
        entries = parse_glosses(glosse)
        assert entries[0]["pos"] == "pp"
        assert entries[0]["syntax"] == "rd"

    def test_empty_glosse(self) -> None:
        assert parse_glosses("") == []


# ─────────────────────────────────────────────────────────────
# Tests for full parse()
# ─────────────────────────────────────────────────────────────


class TestParse:
    def test_total_row_count(self) -> None:
        rows = parse(SAMPLE_HTML)
        # line 1: 5 glosses, line 2: 3 glosses, line 552: 5 glosses
        assert len(rows) == 13

    def test_line_ids(self) -> None:
        rows = parse(SAMPLE_HTML)
        ids = {r["line_id"] for r in rows}
        assert ids == {"0001", "0002", "0552"}

    def test_half_line_assignment_line1(self) -> None:
        rows = parse(SAMPLE_HTML)
        line1 = [r for r in rows if r["line_id"] == "0001"]
        a_tokens = [r for r in line1 if r["half_line"] == "a"]
        b_tokens = [r for r in line1 if r["half_line"] == "b"]
        assert len(a_tokens) == 3  # hwæt, we, Gar-Dene
        assert len(b_tokens) == 2  # in, gear-dagas

    def test_half_line_no_caesura(self) -> None:
        """Line 552 has no caesura — all tokens should be a-verse."""
        rows = parse(SAMPLE_HTML)
        line552 = [r for r in rows if r["line_id"] == "0552"]
        assert all(r["half_line"] == "a" for r in line552)
        assert len(line552) == 5

    def test_token_offset(self) -> None:
        rows = parse(SAMPLE_HTML)
        line1 = [r for r in rows if r["line_id"] == "0001"]
        a_offsets = [r["token_offset"] for r in line1 if r["half_line"] == "a"]
        b_offsets = [r["token_offset"] for r in line1 if r["half_line"] == "b"]
        assert a_offsets == [1, 2, 3]
        assert b_offsets == [1, 2]

    def test_oe_line_preserved(self) -> None:
        rows = parse(SAMPLE_HTML)
        line1_oe = rows[0]["oe_line"]
        assert "Hwæt!" in line1_oe
        assert "geardagum" in line1_oe

    def test_gloss_data_correct(self) -> None:
        rows = parse(SAMPLE_HTML)
        first = rows[0]
        assert first["lemma"] == "hwæt"
        assert first["pos"] == "e"
        assert first["gloss_en"] == "well"
        assert first["gloss_it"] == "ecco"

    def test_empty_html(self) -> None:
        assert parse("<html><body></body></html>") == []

    def test_all_columns_present(self) -> None:
        rows = parse(SAMPLE_HTML)
        for row in rows:
            for col in CSV_COLUMNS:
                assert col in row, f"Missing column: {col}"


# ─────────────────────────────────────────────────────────────
# Tests for Brunetti class
# ─────────────────────────────────────────────────────────────


class TestBrunetti:
    @pytest.fixture
    def br_with_data(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> Generator[Brunetti, None, None]:
        br = Brunetti(db=BeoDB(tmp_path / "test_br.duckdb"))
        br.load_from_html(SAMPLE_HTML)
        yield br
        br._db.close()

    def test_table_exists_false_initially(self, tmp_path: Path) -> None:
        with Brunetti(db=BeoDB(tmp_path / "empty.duckdb")) as br:
            assert br._db.table_exists(TABLE_NAME) is False

    def test_load(self, br_with_data: Brunetti) -> None:
        assert br_with_data._db.table_exists(TABLE_NAME) is True
        assert br_with_data.count() == 13

    def test_load_skips_if_exists(self, br_with_data: Brunetti) -> None:
        count = br_with_data.load_from_html(SAMPLE_HTML, force=False)
        assert count == 13

    def test_load_force_reloads(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with Brunetti(db=BeoDB(tmp_path / "force.duckdb")) as br:
            br.load_from_html(SAMPLE_HTML)
            assert br.count() == 13
            count = br.load_from_html(SAMPLE_HTML, force=True)
            assert count == 13

    def test_get_line(self, br_with_data: Brunetti) -> None:
        result = br_with_data.get_line("0001")
        assert len(result) == 5
        assert result[0]["lemma"] == "hwæt"
        assert result[0]["half_line"] == "a"

    def test_get_line_empty(self, br_with_data: Brunetti) -> None:
        assert br_with_data.get_line("9999") == []

    def test_get_by_line(self, br_with_data: Brunetti) -> None:
        """get_by_line is an alias for get_line."""
        result = br_with_data.get_by_line("0001")
        assert len(result) == 5
        assert result[0]["lemma"] == "hwæt"

    def test_get_lines_range(self, br_with_data: Brunetti) -> None:
        result = br_with_data.get_lines(1, 2)
        line_ids = {r["line_id"] for r in result}
        assert line_ids == {"0001", "0002"}

    def test_get_lines_from_start(self, br_with_data: Brunetti) -> None:
        result = br_with_data.get_lines(2)
        line_ids = {r["line_id"] for r in result}
        assert "0002" in line_ids
        assert "0552" in line_ids

    def test_get_by_fitt_returns_empty_for_invalid(
        self, br_with_data: Brunetti
    ) -> None:
        assert br_with_data.get_by_fitt("99") == []

    def test_get_by_fitt_uses_line_range(self, br_with_data: Brunetti) -> None:
        """Fitt 0 covers lines 1-52, so should return line 0001 and 0002."""
        result = br_with_data.get_by_fitt("00")
        line_ids = {r["line_id"] for r in result}
        assert "0001" in line_ids
        assert "0002" in line_ids
        assert "0552" not in line_ids

    def test_lookup_exact(self, br_with_data: Brunetti) -> None:
        results = br_with_data.lookup("hwæt")
        assert len(results) == 1
        assert results[0]["lemma"] == "hwæt"
        assert results[0]["gloss_en"] == "well"

    def test_lookup_no_match(self, br_with_data: Brunetti) -> None:
        results = br_with_data.lookup("nonexistent")
        assert results == []

    def test_lookup_like(self, br_with_data: Brunetti) -> None:
        results = br_with_data.lookup_like("Gar%")
        assert len(results) == 1
        assert results[0]["lemma"] == "Gar-Dene"

    def test_lookup_invalid_operator(self, br_with_data: Brunetti) -> None:
        with pytest.raises(ValueError, match="Invalid operator"):
            br_with_data.lookup("test", oper="DROP")

    def test_search(self, br_with_data: Brunetti) -> None:
        result = br_with_data.search("Spear-Danes")
        assert len(result) == 1
        assert result[0]["lemma"] == "Gar-Dene"

    def test_search_column(self, br_with_data: Brunetti) -> None:
        result = br_with_data.search("glory", column="gloss_en")
        assert len(result) == 1
        assert result[0]["lemma"] == "þrym"

    def test_search_no_results(self, br_with_data: Brunetti) -> None:
        assert br_with_data.search("zzzznonexistent") == []

    def test_context_manager(self, tmp_path: Path) -> None:
        with Brunetti(db=BeoDB(tmp_path / "ctx.duckdb")) as br:
            assert br._db.table_exists(TABLE_NAME) is False
        assert br._db._conn is None


# ─────────────────────────────────────────────────────────────
# Tests for CSV writing
# ─────────────────────────────────────────────────────────────


class TestWriteCsv:
    @pytest.fixture
    def br_with_data(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> Generator[Brunetti, None, None]:
        br = Brunetti(db=BeoDB(tmp_path / "test_csv.duckdb"))
        br.load_from_html(SAMPLE_HTML)
        yield br
        br._db.close()

    def test_csv_written(self, br_with_data: Brunetti, tmp_path: Path) -> None:
        out = tmp_path / "output" / "test.csv"
        result_path = br_with_data.write_csv(out)
        assert result_path == out
        assert out.exists()

    def test_csv_has_header(self, br_with_data: Brunetti, tmp_path: Path) -> None:
        out = tmp_path / "test.csv"
        br_with_data.write_csv(out)
        with out.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == CSV_COLUMNS

    def test_csv_row_count(self, br_with_data: Brunetti, tmp_path: Path) -> None:
        out = tmp_path / "test.csv"
        br_with_data.write_csv(out)
        with out.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 13

    def test_csv_content(self, br_with_data: Brunetti, tmp_path: Path) -> None:
        out = tmp_path / "test.csv"
        br_with_data.write_csv(out)
        with out.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            first = next(reader)
        assert first["line_id"] == "0001"
        assert first["half_line"] == "a"
        assert first["token_offset"] == "1"
        assert first["lemma"] == "hwæt"
        assert first["gloss_en"] == "well"

    def test_csv_creates_directory(
        self, br_with_data: Brunetti, tmp_path: Path
    ) -> None:
        out = tmp_path / "nested" / "dir" / "output.csv"
        br_with_data.write_csv(out)
        assert out.exists()
