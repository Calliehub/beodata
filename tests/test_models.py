#!/usr/bin/env python3
"""
Unit tests for Beowulf text models.

Tests for BeowulfLine dataclass and conversion functions.
"""

from typing import Any, Dict, List

import pytest

from text.models import BeowulfLine, dict_data_to_beowulf_lines


class TestBeowulfLine:
    """Test cases for BeowulfLine dataclass."""

    def test_basic_line_creation(self) -> None:
        """Test creating a basic BeowulfLine."""
        line = BeowulfLine(
            line_number=1,
            old_english="Hwæt! wē Gār-Dena",
            modern_english="Listen! We of the Spear-Danes",
        )

        assert line.line_number == 1
        assert line.old_english == "Hwæt! wē Gār-Dena"
        assert line.modern_english == "Listen! We of the Spear-Danes"
        assert line.title is None

    def test_line_with_title(self) -> None:
        """Test creating a BeowulfLine with a title."""
        line = BeowulfLine(
            line_number=1,
            old_english="Hwæt! wē Gār-Dena",
            modern_english="Listen! We of the Spear-Danes",
            title="Prologue",
        )

        assert line.title == "Prologue"
        assert line.is_title_line is True

    def test_is_empty_property(self) -> None:
        """Test is_empty property for various line states."""
        # Both empty
        empty_line = BeowulfLine(0, "", "", None)
        assert empty_line.is_empty is True

        # Whitespace only
        whitespace_line = BeowulfLine(0, "   ", "\t\n", None)
        assert whitespace_line.is_empty is True

        # OE only
        oe_only = BeowulfLine(1, "Hwæt!", "", None)
        assert oe_only.is_empty is False

        # ME only
        me_only = BeowulfLine(1, "", "Listen!", None)
        assert me_only.is_empty is False

        # Both present
        full_line = BeowulfLine(1, "Hwæt!", "Listen!", None)
        assert full_line.is_empty is False

    def test_is_title_line_property(self) -> None:
        """Test is_title_line property."""
        line_without_title = BeowulfLine(1, "text", "text", None)
        assert line_without_title.is_title_line is False

        line_with_title = BeowulfLine(1, "text", "text", "Prologue")
        assert line_with_title.is_title_line is True

    def test_str_representation(self) -> None:
        """Test string representation of BeowulfLine."""
        # Basic line
        line = BeowulfLine(1, "Hwæt! wē Gār-Dena", "Listen! We", None)
        str_repr = str(line)
        assert "Line 1" in str_repr
        assert "OE: Hwæt! wē Gār-Dena..." in str_repr
        assert "ME: Listen! We..." in str_repr

        # Line with title
        titled_line = BeowulfLine(1, "text", "text", "Prologue")
        titled_str = str(titled_line)
        assert "Title: Prologue" in titled_str

    def test_frozen_dataclass(self) -> None:
        """Test that BeowulfLine is immutable (frozen)."""
        line = BeowulfLine(1, "original", "original", None)

        with pytest.raises(AttributeError):
            line.old_english = "modified"  # type: ignore

        with pytest.raises(AttributeError):
            line.line_number = 2  # type: ignore

    def test_hashable(self) -> None:
        """Test that BeowulfLine is hashable (can be used in sets/dicts)."""
        line1 = BeowulfLine(1, "text", "text", None)
        line2 = BeowulfLine(1, "text", "text", None)
        line3 = BeowulfLine(2, "different", "different", None)

        # Should be able to create a set
        line_set = {line1, line2, line3}
        assert len(line_set) == 2  # line1 and line2 are equal

        # Should be able to use as dict key
        line_dict = {line1: "value"}
        assert line_dict[line2] == "value"  # line2 should work as key too


class TestDictDataToBeowulfLines:
    """Test cases for dict_data_to_beowulf_lines function."""

    def test_basic_conversion(self) -> None:
        """Test basic conversion from dict data to BeowulfLine objects."""
        dict_data = [
            {"line": 0, "OE": "", "ME": ""},
            {
                "line": 1,
                "OE": "Hwæt! wē Gār-Dena",
                "ME": "Listen! We of the Spear-Danes",
            },
            {"line": 2, "OE": "in gēar-dagum", "ME": "in days of yore"},
        ]

        lines = dict_data_to_beowulf_lines(dict_data)

        assert len(lines) == 3
        assert all(isinstance(line, BeowulfLine) for line in lines)

        # Check first line (empty)
        assert lines[0].line_number == 0
        assert lines[0].old_english == ""
        assert lines[0].modern_english == ""
        assert lines[0].title is None
        assert lines[0].is_empty is True

        # Check second line
        assert lines[1].line_number == 1
        assert lines[1].old_english == "Hwæt! wē Gār-Dena"
        assert lines[1].modern_english == "Listen! We of the Spear-Danes"
        assert lines[1].title == "Prologue"  # Line 1 starts Prologue
        assert lines[1].is_title_line is True

    def test_fitt_boundary_titles(self) -> None:
        """Test that fitt boundary lines get correct titles."""
        # Test several fitt starting lines
        dict_data = [
            {
                "line": 1,
                "OE": "Prologue text",
                "ME": "Prologue translation",
            },  # Prologue
            {"line": 53, "OE": "Fitt I text", "ME": "Fitt I translation"},  # Fitt I
            {"line": 115, "OE": "Fitt II text", "ME": "Fitt II translation"},  # Fitt II
            {"line": 320, "OE": "Fitt V text", "ME": "Fitt V translation"},  # Fitt V
            {"line": 662, "OE": "Fitt X text", "ME": "Fitt X translation"},  # Fitt X
            {
                "line": 100,
                "OE": "Regular text",
                "ME": "Regular translation",
            },  # Not a fitt start
        ]

        lines = dict_data_to_beowulf_lines(dict_data)

        # Check fitt boundary titles
        assert lines[0].title == "Prologue"
        assert lines[1].title == "I"
        assert lines[2].title == "II"
        assert lines[3].title == "V"
        assert lines[4].title == "X"

        # Check non-boundary line
        assert lines[5].title is None
        assert lines[5].is_title_line is False

    def test_empty_input(self) -> None:
        """Test conversion with empty input."""
        lines = dict_data_to_beowulf_lines([])
        assert lines == []

    def test_line_2229_missing(self) -> None:
        """Test handling of missing line 2229 (known missing line in Beowulf)."""
        dict_data = [
            {"line": 2228, "OE": "some text", "ME": "some translation"},
            {"line": 2229, "OE": "", "ME": ""},  # Missing line
            {"line": 2230, "OE": "more text", "ME": "more translation"},
        ]

        lines = dict_data_to_beowulf_lines(dict_data)

        assert lines[1].line_number == 2229
        assert lines[1].is_empty is True
        assert lines[1].title is None

    def test_preserves_order(self) -> None:
        """Test that conversion preserves the order of input data."""
        dict_data = [
            {"line": 100, "OE": "third", "ME": "third"},
            {"line": 1, "OE": "first", "ME": "first"},
            {"line": 50, "OE": "second", "ME": "second"},
        ]

        lines = dict_data_to_beowulf_lines(dict_data)

        # Should preserve input order, not sort by line number
        assert lines[0].line_number == 100
        assert lines[1].line_number == 1
        assert lines[2].line_number == 50

        assert lines[0].old_english == "third"
        assert lines[1].old_english == "first"
        assert lines[2].old_english == "second"

    def test_unicode_handling(self) -> None:
        """Test proper handling of Unicode characters in Old English."""
        dict_data = [
            {"line": 100, "OE": "æðēāīōūȳ", "ME": "with special chars"},
            {"line": 101, "OE": "Þāt wǣs gōd cyning!", "ME": "That was a good king!"},
        ]

        lines = dict_data_to_beowulf_lines(dict_data)

        assert lines[0].old_english == "æðēāīōūȳ"
        assert lines[1].old_english == "Þāt wǣs gōd cyning!"

    def test_fitt_24_boundary_skipped(self) -> None:
        """Test that fitt 24 (which doesn't exist) doesn't create a title."""
        # Fitt 24 has boundary (0, 0, "XXIIII") but shouldn't match line 0
        dict_data = [
            {
                "line": 0,
                "OE": "",
                "ME": "",
            }  # Line 0 exists but shouldn't get fitt 24 title
        ]

        lines = dict_data_to_beowulf_lines(dict_data)

        # Line 0 should not get the XXIIII title since fitt 24 is fake
        assert lines[0].title is None

    def test_all_required_fields_present(self) -> None:
        """Test that all required fields are properly converted."""
        dict_data = [{"line": 123, "OE": "test_oe", "ME": "test_me"}]

        lines = dict_data_to_beowulf_lines(dict_data)
        line = lines[0]

        assert hasattr(line, "line_number")
        assert hasattr(line, "old_english")
        assert hasattr(line, "modern_english")
        assert hasattr(line, "title")

        assert line.line_number == 123
        assert line.old_english == "test_oe"
        assert line.modern_english == "test_me"
