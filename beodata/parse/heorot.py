#!/usr/bin/env python3
"""
Beowulf text processing module for heorot.dk data.

This module handles fetching, parsing, and processing Beowulf text data
from heorot.dk, including conversion to various formats (JSON, CSV, ASS subtitles).
"""

import csv
import json
import logging
import os
import re
from typing import Dict, List, Optional, Self, Tuple, TypedDict

import pysubs2
import requests
import structlog
from bs4 import BeautifulSoup

from ..text.numbering import FITT_BOUNDARIES
from ..subtitle.constants import SECONDS_PER_LINE, ASS_PARAMS, LINE_NUMBER_MARKERS

# Configure logging
logging.basicConfig(
    format="%(message)s",
    level=logging.INFO,
)

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Get a logger
logger = structlog.get_logger()


def normalize_text(text: str) -> str:
    """
    Normalize text by converting line breaks to spaces and collapsing whitespace.

    Args:
        text: Raw text from HTML parsing

    Returns:
        Normalized text with consistent spacing
    """
    # Convert HTML entities to spaces (like &nbsp;)
    text = text.replace("&nbsp;", " ")

    # Convert line breaks and other whitespace to single spaces
    text = re.sub(r"\s+", " ", text)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


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
    if not os.path.exists(filename):
        logger.warning("Fetching HTML from heorot.dk")
        response = requests.get(url)
        response.raise_for_status()  # Ensure we got a valid response

        with open(filename, "w", encoding="utf-8") as file:
            file.write(response.text)
            return response.text
    else:
        logger.warning("HTML is already stored locally, skipping HTTP fetch")
        with open(filename, "r", encoding="utf-8") as file:
            return file.read()


def parse(html: str) -> List[Dict[str, str]]:
    """
    Parse HTML content and extract Beowulf text lines.

    Args:
        html: HTML content to parse

    Returns:
        List of dictionaries containing line data with 'line', 'OE', and 'ME' keys
    """
    current_line_number = 0
    soup = BeautifulSoup(html, "html.parser")

    # Extract table or divs containing the two columns
    # Use natural 1-based numbering in the array of lines, to make lining up with the original text easier
    lines = [{"line": 0, "OE": "", "ME": ""}]

    tables = soup.find_all("table", class_="c15")

    if len(tables) > 0:
        for table in tables:
            table_rows = table.find_all("tr")
            last_oe = None

            for row in table_rows:
                note_divs = row.find_all("div")
                if len(note_divs) > 0:
                    for note_div in note_divs:
                        if note_div.get("class") != [
                            "c35"
                        ]:  # malformation at line 1066 of the Heorot HTML
                            note_div.decompose()

                # Find all span elements with class 'c7' in this row
                columns = row.find_all("span", class_="c7")

                if len(columns) >= 2:
                    if len(columns) > 2:
                        logger.debug(
                            "long row found",
                            line=current_line_number + 1,
                            cols=len(columns),
                        )

                    # Take the first and last span with class 'c7' to ensure we get OE and ME
                    # The middle column might have different structure
                    oe_text = columns[0]
                    me_text = columns[-1]  # Last span should be ME text

                    if oe_text == last_oe:  # skip dupes
                        continue
                    else:
                        last_oe = oe_text

                    # Remove <a> tags
                    for tag in oe_text.find_all("a"):
                        tag.unwrap()
                    for tag in me_text.find_all("a"):
                        tag.unwrap()

                    current_line_number += 1

                    # Get raw text and normalize it
                    oe_raw = oe_text.get_text(strip=False)
                    me_raw = me_text.get_text(strip=False)

                    # Normalize the text to handle line breaks and whitespace
                    oe_normalized = normalize_text(oe_raw)
                    me_normalized = normalize_text(me_raw)

                    # Handle the special case of '--' which should be preserved as a single space
                    oe_final = oe_normalized.replace("--", " ")
                    me_final = me_normalized.replace("--", " ")

                    lines.append(
                        {"line": current_line_number, "OE": oe_final, "ME": me_final}
                    )

    return lines


def get_fitt(fitt_num: int, lines: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Extract lines for a specific fitt.

    Args:
        fitt_num: The fitt number to extract
        lines: List of all line data

    Returns:
        List of line data for the specified fitt
    """
    start = FITT_BOUNDARIES[fitt_num][0]
    end = FITT_BOUNDARIES[fitt_num][1] + 1
    return lines[start:end]


def do_file(filestem: str, url: str) -> None:
    """
    Process a file by fetching, parsing, and saving in multiple formats.

    Args:
        filestem: Base name for output files
        url: URL to fetch HTML content from
    """
    html = fetch_and_store(url, f"data/fitts/{filestem}.html")
    parsed_lines = parse(html)
    logger.info(
        "parsed the file", filestem=filestem, url=url, linecount=len(parsed_lines)
    )

    # Save to JSON file
    with open(f"data/fitts/{filestem}.json", "w", encoding="utf-8") as json_file:
        json.dump(parsed_lines, json_file, indent=4, ensure_ascii=False)

    with open(f"data/fitts/{filestem}.csv", mode="w", newline="") as file:
        fieldnames = parsed_lines[0].keys()
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(parsed_lines)

    write_ass(parsed_lines)


def write_ass(lines: List[Dict[str, str]]) -> None:
    """
    Generate ASS subtitle files for each fitt.

    Args:
        lines: List of all line data
    """
    for fitt_id, fitt_bounds in enumerate(FITT_BOUNDARIES):
        logger.info(
            "Writing .ass file for fitt", fitt_id=fitt_id, fitt_bounds=fitt_bounds
        )
        if fitt_id == 24:
            continue  # there's no 24 in Beowulf

        fitt = get_fitt(fitt_id, lines)

        # init our subtitle file based on the blank template
        subs = pysubs2.load(ASS_PARAMS["blank_template"], encoding="UTF-8")
        subs.clear()
        subs.info["Fitt"] = str(fitt_id)
        subs.info["First Line"] = fitt[0]["line"]
        subs.info["Last Line"] = fitt[-1]["line"]

        line_number = -1
        start_time = 0
        end_time = start_time + SECONDS_PER_LINE
        subtitle = None

        for line in fitt:
            # Old English
            subs.append(make_sub(line["OE"], start_time, end_time, "original_style"))
            subs.append(make_sub(line["ME"], start_time, end_time, "modern_style"))
            subs.append(
                make_sub(line["line"], start_time, end_time, "all_number_style")
            )
            try:
                if LINE_NUMBER_MARKERS[line["line"]]:
                    subs.append(
                        make_sub(
                            LINE_NUMBER_MARKERS[line["line"]],
                            start_time,
                            end_time,
                            "big_number_style",
                        )
                    )
            except KeyError:
                pass  # no big number for this line

            if line["line"] == fitt_bounds[0]:
                subs.append(
                    make_sub(fitt_bounds[2], start_time, end_time, "fitt_heading_style")
                )

            # increment for next subtitle
            start_time += SECONDS_PER_LINE
            end_time += SECONDS_PER_LINE
        subs.save(ASS_PARAMS["output_file"].format(fitt_id=fitt_id), encoding="UTF-8")


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


def run() -> None:
    """Main function to process the Beowulf text."""
    do_file("maintext", "https://heorot.dk/beowulf-rede-text.html")


if __name__ == "__main__":
    run()
