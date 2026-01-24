"""
Beowulf text processing module for heorot.dk data.

This module is maintained for backward compatibility.
The functionality has been split into separate modules:
- beodata.sources.fetch - HTTP fetching and caching
- beodata.sources.parser - HTML parsing
- beodata.writers - JSON, CSV, ASS export
- beodata.cli - Command-line entry points
"""

# Re-export for backward compatibility
from beodata.cli import fetch_store_and_parse, model_dump, run
from beodata.sources.fetch import DATA_DIR, HEOROT_URL, fetch_and_store
from beodata.sources.parser import normalize_text, parse
from beodata.writers.ass_writer import get_fitt, make_sub, write_ass

__all__ = [
    "DATA_DIR",
    "HEOROT_URL",
    "fetch_and_store",
    "fetch_store_and_parse",
    "get_fitt",
    "make_sub",
    "model_dump",
    "normalize_text",
    "parse",
    "run",
    "write_ass",
]
