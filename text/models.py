#!/usr/bin/env python3
"""
Text data models for Beowulf processing.

This module contains dataclasses for representing Beowulf text structures.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .numbering import FITT_BOUNDARIES


@dataclass(frozen=True)
class BeowulfLine:
    """Represents a single line of Beowulf text with dual-language content."""

    line_number: int
    old_english: str
    modern_english: str
    title: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        """Check if both OE and ME text are empty (structural/missing lines)."""
        return not self.old_english.strip() and not self.modern_english.strip()

    @property
    def is_title_line(self) -> bool:
        """Check if this line has a title (fitt heading)."""
        return self.title is not None

    def __str__(self) -> str:
        """String representation for debugging."""
        parts = [f"Line {self.line_number}"]
        if self.title:
            parts.append(f"Title: {self.title}")
        if self.old_english:
            parts.append(f"OE: {self.old_english[:50]}...")
        if self.modern_english:
            parts.append(f"ME: {self.modern_english[:50]}...")
        return " | ".join(parts)


def dict_data_to_beowulf_lines(lines_data: List[Dict[str, Any]]) -> List[BeowulfLine]:
    """
    Convert output from fetch_store_and_parse to BeowulfLine objects.

    Args:
        lines_data: List of dictionaries with 'line', 'OE', 'ME' keys

    Returns:
        List of BeowulfLine objects
    """
    beowulf_lines = []

    for line_data in lines_data:
        line_number = line_data["line"]

        # Check if this line is the start of a fitt (has a title)
        title = None
        for fitt_id, fitt_bounds in enumerate(FITT_BOUNDARIES):
            if fitt_id == 24:  # Skip non-existent fitt 24
                continue
            if line_number == fitt_bounds[0]:  # Start line of fitt
                title = fitt_bounds[2]  # Fitt name
                break

        line = BeowulfLine(
            line_number=line_number,
            old_english=line_data["OE"],
            modern_english=line_data["ME"],
            title=title,
        )
        beowulf_lines.append(line)

    return beowulf_lines
