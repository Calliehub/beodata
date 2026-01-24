#!/usr/bin/env python3
"""
Test constraints for Beowulf digital models.

Collection of validation rules and data integrity checks for ensuring
the quality and consistency of Beowulf text data.
"""

import json
from pathlib import Path
from typing import Any, List

import pytest

import beodata.sources.heorot
from beodata.text.numbering import FITT_BOUNDARIES


# all tests use 1 fetch of the text
@pytest.fixture(scope="session")
def heorot_text() -> List[dict[str, Any]]:
    beodata.sources.heorot.run()
    path = Path(__file__).parent.parent / "data" / "fitts" / "maintext.json"
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
