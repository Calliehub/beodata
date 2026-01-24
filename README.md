# Beodata

This is a small Python toy for me to play around with architectural and coding styles. It's also a package for
processing Beowulf text data from [Heorot.dk](https://heorot.dk/beo-ru.html). The data is then made available in an MCP server for easy
integration into agentic applications.

## Features

The `heorot.py` module can parse the dual-language edition of Beowulf and render the complete text in several formats:
- as a List[BeowulfLine] instances in memory
- as a single combined JSON file
- as a single combined CSV
- as separate .ASS (Advanced SubStation Alpha subtitle format) files, one file per fitt

The module follows the Heorot.dk line numbering and fitt numbering system. There are some missing lines and one missing
fitt; this is expected since the historical Beowulf manuscript has missing pieces.

## Installation

Get on Python 3.13 and install poetry:

```shell
curl -sSL https://install.python-poetry.org | python3 -
```

```shell
poetry install
pre-commit install
```

## Usage

### Running heorot.py

To process the Beowulf text and generate all output formats:

```shell
poetry run heorot
# or more directly:
poetry run python -m beodata.sources.heorot
```

This will:
1. Fetch the HTML content from heorot.dk (if not already cached)
2. Parse the dual-language text
3. Generate JSON and CSV files in `tests/data/fitts/`
4. Create ASS subtitle files for each fitt in `tests/data/subtitles/`

To run the MCP server:

```shell
poetry run server
```

To run the test suite:

```shell
poetry run pytest
```

### Required Files

The parsing script requires a blank ASS template file:
- `tests/data/blank.ass` - Template file for ASS subtitle formatting

### Output Files

After running the script, you'll find:

**In `tests/data/fitts/`:**
- `maintext.json` - Complete text data in JSON format
- `maintext.csv` - Complete text data in CSV format
- `maintext.html` - Cached HTML from heorot.dk

**In `tests/data/subtitles/`:**
- `fitt_0.ass` through `fitt_43.ass` - ASS subtitle files for each fitt (except fitt 24, which doesn't exist)

## Project Structure

- `beodata/parse/heorot.py` - Main parsing and processing logic for Heorot.DK HTML text
- `beodata/text/models.py` - Model classes for BeowulfLine objects
- `beodata/text/numbering.py` - Fitt boundaries and text structure constants
- `beodata/subtitle/constants.py` - Subtitle generation constants
- `tests/data/fitts/` - Output directory for generated files
- `tests/data/subtitles/` - Output directory for ASS subtitle files

## Copyright

This work is copyright 2025-2026 by Callie Tweney, and licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/?ref=chooser-v1).

The Heorot source text is copyright [Benjamin Slade](https://heorot.dk/) 2002-2020.
