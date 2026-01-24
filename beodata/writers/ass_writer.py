"""ASS subtitle generation for Beowulf text."""

from pathlib import Path
from typing import Any, Dict, Final, List

import pysubs2

from beodata.text.models import BeowulfLine, dict_data_to_beowulf_lines
from beodata.text.numbering import FITT_BOUNDARIES
from beodata.writers.base_writer import BaseWriter

# Timing constants
SECONDS_PER_LINE: Final[int] = 4

# Define subtitle and blank template paths relative to this file
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


def get_fitt(fitt_num: int, lines: List[BeowulfLine]) -> List[BeowulfLine]:
    """
    Extract BeowulfLine objects for a specific fitt.

    Args:
        fitt_num: The fitt number to extract
        lines: List of all BeowulfLine objects

    Returns:
        List of BeowulfLine objects for the specified fitt
    """
    start_line = FITT_BOUNDARIES[fitt_num][0]
    end_line = FITT_BOUNDARIES[fitt_num][1]

    return [line for line in lines if start_line <= line.line_number <= end_line]


def make_sub(
    text: str, start_time: float, end_time: float, style: str
) -> pysubs2.SSAEvent:
    """
    Create a subtitle event.

    Args:
        text: The subtitle text
        start_time: Start time in seconds
        end_time: End time in seconds
        style: Style name for the subtitle

    Returns:
        SSAEvent object for the subtitle
    """
    subtitle = pysubs2.SSAEvent(
        start=pysubs2.make_time(s=start_time),
        end=pysubs2.make_time(s=end_time),
        style=ASS_PARAMS[style],
    )
    subtitle.name = style
    subtitle.text = text
    return subtitle


class AssWriter(BaseWriter):
    """Writer for ASS subtitle format output.

    Unlike JSON/CSV writers, this generates multiple files (one per fitt).
    The output_path is used as a directory for the generated files.
    """

    @property
    def format_name(self) -> str:
        return "ASS"

    def get_output_path(self, base_dir: Path, stem: str) -> Path:
        # ASS writer outputs to its own subtitles directory
        return SUBTITLE_DIR

    def write(self, lines: List[Dict[str, Any]], output_path: Path) -> None:
        """
        Generate ASS subtitle files for each fitt.

        Args:
            lines: List of all line data
            output_path: Directory to write subtitle files to
        """
        beowulf_lines = dict_data_to_beowulf_lines(lines)
        total_subs = 0

        for fitt_id, fitt_bounds in enumerate(FITT_BOUNDARIES):
            if fitt_id == 24:
                continue  # there's no 24 in Beowulf

            fitt = get_fitt(fitt_id, beowulf_lines)
            fitt_output_path = output_path / f"fitt_{fitt_id}.ass"

            self.logger.debug(
                "Writing .ass file for fitt",
                fitt_id=fitt_id,
                fitt_bounds=fitt_bounds,
            )

            subs = self._create_fitt_subtitles(fitt_id, fitt)
            subs.save(str(fitt_output_path), encoding="UTF-8")
            total_subs += len(subs)

            self.logger.info(
                "Subtitles saved",
                output_file_path=str(fitt_output_path),
                sub_count=len(subs),
            )

        self._log_write_complete(output_path, total_subs)

    def _create_fitt_subtitles(
        self, fitt_id: int, fitt: List[BeowulfLine]
    ) -> pysubs2.SSAFile:
        """Create subtitle file for a single fitt."""
        blank_template_path = Path(ASS_PARAMS["blank_template"])
        subs = pysubs2.load(str(blank_template_path), encoding="UTF-8")
        subs.clear()
        subs.info["Fitt"] = str(fitt_id)
        subs.info["First Line"] = fitt[0].line_number
        subs.info["Last Line"] = fitt[-1].line_number

        start_time = 0
        end_time = start_time + SECONDS_PER_LINE

        for line in fitt:
            subs.append(
                make_sub(line.old_english, start_time, end_time, "original_style")
            )
            subs.append(
                make_sub(line.modern_english, start_time, end_time, "modern_style")
            )
            subs.append(
                make_sub(
                    str(line.line_number), start_time, end_time, "all_number_style"
                )
            )

            if line.line_number in LINE_NUMBER_MARKERS:
                subs.append(
                    make_sub(
                        str(LINE_NUMBER_MARKERS[line.line_number]),
                        start_time,
                        end_time,
                        "big_number_style",
                    )
                )

            if line.is_title_line:
                subs.append(
                    make_sub(line.title, start_time, end_time, "fitt_heading_style")
                )

            start_time += SECONDS_PER_LINE
            end_time += SECONDS_PER_LINE

        return subs


# Convenience function for backward compatibility
def write_ass(lines: List[Dict[str, Any]]) -> None:
    """Generate ASS subtitle files for each fitt."""
    AssWriter().write(lines, SUBTITLE_DIR)
