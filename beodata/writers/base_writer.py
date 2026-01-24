"""Base class for Beowulf text writers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List

from beodata.logging_config import get_logger


class BaseWriter(ABC):
    """Abstract base class for Beowulf text format writers."""

    def __init__(self) -> None:
        self.logger = get_logger()

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Return the name of the output format (e.g., 'JSON', 'CSV', 'ASS')."""
        ...

    @abstractmethod
    def write(self, lines: List[Dict[str, Any]], output_path: Path) -> None:
        """
        Write parsed lines to the output format.

        Args:
            lines: List of line dictionaries to write
            output_path: Path to the output file or directory
        """
        ...

    @abstractmethod
    def get_output_path(self, base_dir: Path, stem: str) -> Path:
        """
        Get the output path for this writer.

        Args:
            base_dir: Base directory for output files
            stem: Base filename stem (e.g., 'maintext')

        Returns:
            Path to the output file or directory
        """
        ...

    def _log_write_start(self, output_path: Path) -> None:
        """Log the start of a write operation."""
        self.logger.debug(f"Writing {self.format_name} to {output_path}")

    def _log_write_complete(self, output_path: Path, count: int) -> None:
        """Log completion of a write operation."""
        self.logger.info(
            f"{self.format_name} write complete",
            output_path=str(output_path),
            line_count=count,
        )
