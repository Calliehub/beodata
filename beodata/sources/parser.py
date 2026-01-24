"""HTML parsing for Beowulf text from heorot.dk."""

import re
from typing import Any, Dict, List

from bs4 import BeautifulSoup, Tag

from beodata.logging_config import get_logger

logger = get_logger()


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


def parse(html: str) -> List[Dict[str, Any]]:
    """
    Parse HTML content and extract Beowulf text lines.

    Args:
        html: HTML content to sources

    Returns:
        List of dictionaries containing line data with 'line', 'OE', and 'ME' keys
    """
    current_line_number = 0
    soup = BeautifulSoup(html, "html.parser")

    # Extract table or divs containing the two columns
    # Use natural 1-based numbering in the array of lines
    lines: List[Dict[str, Any]] = [{"line": 0, "OE": "", "ME": ""}]

    tables = soup.find_all("table", class_="c15")

    if len(tables) > 0:
        for table in tables:
            if isinstance(table, Tag):
                table_rows = table.find_all("tr")
            else:
                continue
            last_oe = None

            for row in table_rows:
                if not isinstance(row, Tag):
                    continue
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

                    # Take first and last span with class 'c7' to ensure we get OE and ME
                    oe_text = columns[0]
                    me_text = columns[-1]

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

                    # Handle the special case of '--' which should be preserved as space
                    oe_final = oe_normalized.replace("--", " ")
                    me_final = me_normalized.replace("--", " ")

                    lines.append(
                        {"line": current_line_number, "OE": oe_final, "ME": me_final}
                    )

    return lines
