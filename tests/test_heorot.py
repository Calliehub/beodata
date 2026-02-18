#!/usr/bin/env python3
"""
Test constraints for Beowulf digital models.

Collection of validation rules and data integrity checks for ensuring
the quality and consistency of Beowulf text data.
"""

import json
from pathlib import Path
from typing import Any, Generator, List

import pytest

from beowulf_mcp.cli import load_heorot
from beowulf_mcp.db import BeoDB
from sources.heorot import TABLE_NAME, Heorot
from text.numbering import FITT_BOUNDARIES


# all tests use 1 fetch of the text
@pytest.fixture(scope="session")
def heorot_text() -> List[dict[str, Any]]:
    load_heorot()
    path = Path(__file__).parent.parent / "output" / "maintext.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_line_numbering_sequential(heorot_text: List[dict[str, Any]]) -> None:
    """Line numbers should be sequential starting from 0."""
    for i, line_data in enumerate(heorot_text):
        assert line_data["line"] == i, f"Line {i} has wrong number: {line_data['line']}"


def test_total_line_count(heorot_text: List[dict[str, Any]]) -> None:
    """Total line count should match expected value."""
    expected_count = 3183
    actual_count = len(heorot_text)
    assert (
        actual_count == expected_count
    ), f"Expected {expected_count} lines, got {actual_count}"


def test_fitt_boundaries_valid(heorot_text: List[dict[str, Any]]) -> None:
    """Fitt boundaries should be within valid line ranges."""
    max_line = len(heorot_text) - 1
    for i, (start, end, name) in enumerate(FITT_BOUNDARIES):
        if i == 24:  # Skip non-existent fitt 24
            continue
        assert 0 <= start <= max_line, f"Fitt {i} start {start} out of range"
        assert 0 <= end <= max_line, f"Fitt {i} end {end} out of range"
        assert start <= end, f"Fitt {i} start {start} > end {end}"


def test_required_fields_present(heorot_text: List[dict[str, Any]]) -> None:
    """Each line must have 'line', 'OE', and 'ME' fields."""
    required_fields = {"line", "OE", "ME"}
    for i, line_data in enumerate(heorot_text):
        missing = required_fields - set(line_data.keys())
        assert not missing, f"Line {i} missing fields: {missing}"


def test_line_zero_empty(heorot_text: List[dict[str, Any]]) -> None:
    """Line 0 should have empty OE and ME text."""
    line_0 = heorot_text[0]
    assert line_0["line"] == 0, "First entry should be line 0"
    assert line_0["OE"] == "", "Line 0 OE text should be empty"
    assert line_0["ME"] == "", "Line 0 ME text should be empty"


def test_famous_opening_line(heorot_text: List[dict[str, Any]]) -> None:
    """Line 1 should contain the famous 'Hwæt!' opening."""
    line_1 = heorot_text[1]
    assert line_1["line"] == 1, "Second entry should be line 1"
    assert "Hwæt!" in line_1["OE"], "Line 1 should contain 'Hwæt!'"
    # The translation varies by source, so just check that it's not empty
    assert line_1["ME"].strip(), "Line 1 should have a translation"


def test_no_empty_text_after_line_zero(heorot_text: List[dict[str, Any]]) -> None:
    """Lines 1+ should not have empty OE or ME text, unless both are empty (structural)."""
    for line_data in heorot_text[1:]:
        line_num = line_data["line"]
        oe_empty = not line_data["OE"].strip()
        me_empty = not line_data["ME"].strip()

        # line 2229 doesn't exist, so both OE and ME are empty
        if line_num == 2229:
            assert oe_empty, f"Line {line_num} has non-empty OE text"
            assert me_empty, f"Line {line_num} has non-empty ME text"
        else:
            assert not oe_empty, f"Line {line_num} has empty OE text"
            assert not me_empty, f"Line {line_num} has empty ME text"


def test_line_2229_empty(heorot_text: List[dict[str, Any]]) -> None:
    """Line 2229 should be empty (it's missing in the ms)"""
    line_2229 = heorot_text[2229]
    assert line_2229["line"] == 2229, "Line 2229 should be line 2229"
    assert line_2229["OE"] == "", "Line 2229 OE text should be empty"
    assert line_2229["ME"] == "", "Line 2229 ME text should be empty"


# Tests for Heorot class (database persistence)


@pytest.fixture
def sample_html() -> str:
    """Create minimal HTML for testing."""
    return """
    <html>
    <body>
    <table class="c15">
        <tr>
            <td><span class="c7">Hwæt! We Gardena</span></td>
            <td><span class="c7">Lo! We of the Spear-Danes</span></td>
        </tr>
        <tr>
            <td><span class="c7">in geardagum,</span></td>
            <td><span class="c7">in days of yore,</span></td>
        </tr>
        <tr>
            <td><span class="c7">þeodcyninga</span></td>
            <td><span class="c7">of the folk-kings</span></td>
        </tr>
    </table>
    </body>
    </html>
    """


@pytest.fixture
def heorot_with_data(tmp_path: Path, sample_html: str) -> Generator[Heorot, None, None]:
    """Create a Heorot instance with test data loaded."""
    h = Heorot(db=BeoDB(tmp_path / "test_beodb.duckdb"))
    h.load_from_html(sample_html)
    yield h
    h._db.close()


class TestHeorotClass:
    """Tests for Heorot class database persistence."""

    def test_table_exists_false_initially(self, tmp_path: Path) -> None:
        """Table should not exist before loading."""
        with Heorot(db=BeoDB(tmp_path / "empty.duckdb")) as h:
            assert h._db.table_exists(TABLE_NAME) is False

    def test_load_from_html(self, heorot_with_data: Heorot) -> None:
        """Loading HTML should create table with correct row count."""
        assert heorot_with_data._db.table_exists(TABLE_NAME) is True
        # 3 lines + line 0 = 4 rows
        assert heorot_with_data.count() == 4

    def test_load_from_html_skips_if_exists(self, heorot_with_data: Heorot) -> None:
        """Loading again without force should skip."""
        initial_count = heorot_with_data.count()
        heorot_with_data.load_from_html("<html></html>", force=False)
        assert heorot_with_data.count() == initial_count

    def test_load_from_html_force_reloads(
        self, tmp_path: Path, sample_html: str
    ) -> None:
        """Loading with force=True should reload the data."""
        with Heorot(db=BeoDB(tmp_path / "force_test.duckdb")) as h:
            h.load_from_html(sample_html)
            assert h.count() == 4
            # Force reload with empty HTML
            count = h.load_from_html("<html></html>", force=True)
            assert count == 1  # Just line 0

    def test_get_line(self, heorot_with_data: Heorot) -> None:
        """Should retrieve a specific line."""
        line = heorot_with_data.get_line(1)
        assert line is not None
        assert line["line"] == 1
        assert "Hwæt" in line["OE"]
        assert "Spear-Danes" in line["ME"]

    def test_get_line_not_found(self, heorot_with_data: Heorot) -> None:
        """Should return None for non-existent line."""
        line = heorot_with_data.get_line(9999)
        assert line is None

    def test_get_lines_range(self, heorot_with_data: Heorot) -> None:
        """Should retrieve a range of lines."""
        lines = heorot_with_data.get_lines(1, 2)
        assert len(lines) == 2
        assert lines[0]["line"] == 1
        assert lines[1]["line"] == 2

    def test_get_lines_from_start(self, heorot_with_data: Heorot) -> None:
        """Should retrieve all lines from start."""
        lines = heorot_with_data.get_lines(2)
        assert len(lines) == 2  # Lines 2 and 3
        assert lines[0]["line"] == 2
        assert lines[1]["line"] == 3

    def test_search_oe(self, heorot_with_data: Heorot) -> None:
        """Should search in Old English text."""
        results = heorot_with_data.search_oe("geardagum")
        assert len(results) == 1
        assert results[0]["line"] == 2

    def test_search_me(self, heorot_with_data: Heorot) -> None:
        """Should search in Modern English text."""
        results = heorot_with_data.search_me("yore")
        assert len(results) == 1
        assert results[0]["line"] == 2

    def test_search_both(self, heorot_with_data: Heorot) -> None:
        """Should search in both OE and ME text."""
        results = heorot_with_data.search("days")
        assert len(results) == 1
        assert results[0]["line"] == 2

    def test_search_case_insensitive(self, heorot_with_data: Heorot) -> None:
        """Search should be case-insensitive."""
        results = heorot_with_data.search_oe("GARDENA")
        assert len(results) == 1

    def test_context_manager(self, tmp_path: Path) -> None:
        """Context manager should properly close connection."""
        with Heorot(db=BeoDB(tmp_path / "context.duckdb")) as h:
            assert h._db._conn is not None or h._db.table_exists(TABLE_NAME) is False
        assert h._db._conn is None
