"""HTTP fetching and local caching for Beowulf text data."""

from pathlib import Path

import requests

from beodata.logging_config import get_logger

logger = get_logger()

# Define the data directory relative to this file (for test and output data)
DATA_DIR = Path(__file__).parent.parent.parent / "tests" / "data" / "fitts"


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
        logger.warning("Fetching HTML from heorot.dk")
        response = requests.get(url)
        response.raise_for_status()

        with file_path.open("w", encoding="utf-8") as file:
            file.write(response.text)
            return response.text
    else:
        logger.warning("HTML is already stored locally, skipping HTTP fetch")
        with file_path.open("r", encoding="utf-8") as file:
            return file.read()
