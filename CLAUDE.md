# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Beodata is a Python package for processing Beowulf text data from heorot.dk. It parses dual-language Beowulf text and converts it to JSON, CSV, and ASS subtitle formats.

## Development Commands

### Package Management
```bash
# Install dependencies
poetry install

# Install pre-commit hooks
pre-commit install
```

### Running the Application
```bash
# Main entry point - processes Beowulf text and generates all formats
poetry run heorot
# Alternative:
poetry run python -m beodata.parse.heorot
```

### Testing and Quality Checks
```bash
# Run tests with coverage
poetry run pytest

# Run specific test file
poetry run pytest tests/parse/test_heorot.py

# Code formatting and linting (these run automatically via pre-commit)
poetry run black .
poetry run isort .
poetry run flake8 .
poetry run mypy .
```

## Project Architecture

### Core Modules
- **`beodata/parse/heorot.py`** - Main parsing logic for heorot.dk HTML content
- **`beodata/text/numbering.py`** - Fitt boundaries and line numbering constants
- **`beodata/subtitle/constants.py`** - ASS subtitle generation constants

### Key Data Structures
- **FITT_BOUNDARIES** - Tuples defining (start_line, end_line, fitt_name) for each section
- Text processing handles both Old English (OE) and Modern English (ME) content
- Line numbering follows heorot.dk system

### Output Structure
- **`tests/data/fitts/`** - JSON/CSV output and cached HTML
- **`tests/data/subtitles/`** - ASS subtitle files (fitt_0.ass through fitt_43.ass, except 24)
- **`tests/data/blank.ass`** - Required template for subtitle generation

## Code Style

The project uses comprehensive Python style guidelines defined in `.cursorrules`:
- Black formatting (88 character line length)
- Type hints required
- Structlog for logging (pass variables as named params, not extras)
- Pre-commit hooks enforce quality checks
- Python 3.13 target

## Key Dependencies

- **pysubs2** - ASS subtitle format handling
- **beautifulsoup4** - HTML parsing
- **structlog** - Structured logging
- **requests** - HTTP fetching

## Testing

- Uses pytest with coverage reporting
- Pre-commit hooks run tests automatically
- Test files follow `test_*.py` pattern in corresponding test directories
