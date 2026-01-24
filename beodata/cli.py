"""Command-line entry points for beodata."""

from beodata.logging_config import get_logger
from beodata.parse.fetch import DATA_DIR, HEOROT_URL, fetch_and_store
from beodata.parse.parser import parse
from beodata.text.models import dict_data_to_beowulf_lines
from beodata.writers import get_all_writers

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


def run() -> None:
    """Main function to process the Beowulf text."""
    fetch_store_parse_and_write("maintext", HEOROT_URL)
