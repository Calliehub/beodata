"""Writers package for exporting Beowulf text data to various formats."""

from typing import List

# Import all writer modules to register subclasses
from beodata.writers.ass_writer import AssWriter, write_ass  # noqa: F401
from beodata.writers.base_writer import BaseWriter
from beodata.writers.csv_writer import CsvWriter, write_csv  # noqa: F401
from beodata.writers.json_writer import JsonWriter, write_json  # noqa: F401


def get_all_writers() -> List[BaseWriter]:
    """Return instances of all BaseWriter subclasses."""
    return [writer_class() for writer_class in BaseWriter.__subclasses__()]


__all__ = [
    "AssWriter",
    "BaseWriter",
    "CsvWriter",
    "JsonWriter",
    "get_all_writers",
    "write_ass",
    "write_csv",
    "write_json",
]
