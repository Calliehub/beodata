#!/usr/bin/env python3
"""
Subtitle generation constants for Beowulf text.

This module contains constants used for generating ASS subtitle files
from Beowulf text data.
"""

from pathlib import Path
from typing import Dict, Final

# Timing constants
SECONDS_PER_LINE: Final[int] = 4

# Define subtitle and blank template paths relative to the test file location
SUBTITLE_DIR = Path(__file__).parent.parent.parent / "tests" / "data" / "subtitles"
BLANK_ASS_PATH = Path(__file__).parent.parent.parent / "tests" / "data" / "blank.ass"

# ASS subtitle parameters
ASS_PARAMS: Final[Dict[str, str]] = {
    "original_style": "Old English",
    "modern_style": "Modern English",
    "big_number_style": "Big Numbers",
    "all_number_style": "All Numbers",
    "fitt_heading_style": "Fitt Headings",
    "blank_template": str(BLANK_ASS_PATH),
    "output_file": str(SUBTITLE_DIR / "fitt_{fitt_id}.ass"),
}

# Line number markers for special display
# These lines get special formatting in the subtitles
# Generated as every 5th line from 5 to 3178, plus some specific irregular ones
LINE_NUMBER_MARKERS: Final[Dict[int, int]] = {
    line: line for line in range(5, 3179, 5)
} | {
    # Add specific irregular markers
    391: 391,
    1173: 1173,
    1707: 1707,
    2230: 2230,
    2234: 2234,
    2998: 2998,
}
