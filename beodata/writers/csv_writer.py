"""CSV export for Beowulf text data."""

import csv
from pathlib import Path
from typing import Any, Dict, List

from beodata.writers.base_writer import BaseWriter


class CsvWriter(BaseWriter):
    """Writer for CSV format output."""

    @property
    def format_name(self) -> str:
        return "CSV"

    def get_output_path(self, base_dir: Path, stem: str) -> Path:
        return base_dir / f"{stem}.csv"

    def write(self, lines: List[Dict[str, Any]], output_path: Path) -> None:
        """
        Write parsed lines to a CSV file.

        Args:
            lines: List of line dictionaries to write
            output_path: Path to the output CSV file
        """
        self._log_write_start(output_path)
        with output_path.open(mode="w", newline="", encoding="utf-8") as file:
            fieldnames = list(lines[0].keys())
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(lines)
        self._log_write_complete(output_path, len(lines))


# Convenience function for backward compatibility
def write_csv(lines: List[Dict[str, Any]], output_path: Path) -> None:
    """Write parsed lines to a CSV file."""
    CsvWriter().write(lines, output_path)
