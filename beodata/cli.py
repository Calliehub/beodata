"""Command-line entry points for beodata."""
from pathlib import Path

import requests

from beodata.db import DEFAULT_DB_PATH
from beodata.logging_config import get_logger
from beodata.sources.abbreviations import Abbreviations
from beodata.sources.bosworth import BosworthToller
from beodata.sources.heorot import HEOROT_URL, parse
from beodata.text.models import dict_data_to_beowulf_lines
from beodata.writers import get_all_writers

# Define the data directory relative to this file (for test and output data)
DATA_DIR = Path(__file__).parent.parent / "tests" / "data" / "fitts"

logger = get_logger()


def fetch_store_parse_and_write(output_file_stem: str, url: str):
    parsed_lines = fetch_store_and_parse("maintext", HEOROT_URL)
    call_output_writers(output_file_stem, parsed_lines)


def fetch_store_and_parse(output_file_stem: str, url: str) -> list:
    """
    Process a file by fetching, parsing, and saving in multiple formats.

    Args:
        output_file_stem: Base name for output files
        url: URL to fetch HTML content from

    Returns:
        List of parsed line dictionaries
    """
    html = fetch_and_store(url, f"{output_file_stem}.html")
    parsed_lines = parse(html)
    logger.info(
        "parsed the file",
        output_file_stem=output_file_stem,
        url=url,
        n_lines=len(parsed_lines),
    )

    return parsed_lines


def fetch_and_store(url: str, filename: str) -> str:
    """
    Fetch HTML content from URL and store locally if not already present.

    Args:
        url: The URL to fetch content from
        filename: Local file path to store the content

    Returns:
        The HTML content as a string

    Raises:
        requests.RequestException: If the HTTP request fails
    """
    file_path = DATA_DIR / Path(filename).name
    if not file_path.exists():
        logger.info("Fetching HTML", url=url, file=file_path.name)
        response = requests.get(url)
        response.raise_for_status()

        with file_path.open("w", encoding="utf-8") as file:
            file.write(response.text)
            return response.text
    else:
        logger.info("HTML is already stored locally, skipping HTTP fetch")
        with file_path.open("r", encoding="utf-8") as file:
            logger.debug(
                "File opened successfully, reading content...", file=file_path.name
            )
            return file.read()


def call_output_writers(output_file_stem: str, parsed_lines: list[dict] = []) -> None:
    """Write parsed lines using all registered writers."""
    for writer in get_all_writers():
        output_path = writer.get_output_path(DATA_DIR, output_file_stem)
        writer.write(parsed_lines, output_path)


def model_dump() -> None:
    """Dump the Beowulf text as model objects."""
    raw_lines = fetch_store_and_parse("maintext", HEOROT_URL)
    model_lines = dict_data_to_beowulf_lines(raw_lines)
    for line in model_lines:
        print(str(line))


def load_heorot() -> None:
    """Main function to process and load the Beowulf text from heorot.dk."""
    fetch_store_parse_and_write("maintext", HEOROT_URL)


def load_bosworth() -> None:
    """Main function to process and load the Bosworth-Toller dictionary from csv."""
    bt = BosworthToller(DEFAULT_DB_PATH)
    bt.load_from_csv(force=True)


def load_abbreviations() -> None:
    """Main function to process and load the abbreviation dictionary from XML."""
    abbr = Abbreviations(DEFAULT_DB_PATH)
    abbr.load_from_xml(force=True)


def load_all() -> None:
    """Run all processing steps."""
    load_heorot()
    load_bosworth()
    load_abbreviations()
