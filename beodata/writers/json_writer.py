"""JSON export for Beowulf text data."""

import json
from pathlib import Path
from typing import Any, Dict, List

from beodata.writers.base_writer import BaseWriter


class JsonWriter(BaseWriter):
    """Writer for JSON format output."""

    @property
    def format_name(self) -> str:
        return "JSON"

    def get_output_path(self, base_dir: Path, stem: str) -> Path:
        return base_dir / f"{stem}.json"

    def write(self, lines: List[Dict[str, Any]], output_path: Path) -> None:
        """
        Write parsed lines to a JSON file.

        Args:
            lines: List of line dictionaries to write
            output_path: Path to the output JSON file
        """
        self._log_write_start(output_path)
        with output_path.open("w", encoding="utf-8") as json_file:
            json.dump(lines, json_file, indent=4, ensure_ascii=False)
        self._log_write_complete(output_path, len(lines))


# Convenience function for backward compatibility
def write_json(lines: List[Dict[str, Any]], output_path: Path) -> None:
    """Write parsed lines to a JSON file."""
    JsonWriter().write(lines, output_path)
