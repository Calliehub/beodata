# Beodata

This is a small Python toy for me to play around with architectural and coding styles. It's also a package for
processing Beowulf text data from [Heorot.dk](https://heorot.dk/beo-ru.html). The data is then made available in an MCP
server for easy
integration into agentic applications.

For specific use cases of this tool, look in [./findings/](./findings) for case studies using the MCP server to augment
Claude Code's knowledge of the Beowulf text. The foundation LLM knows the full Beowulf text from its training, but it's inconsistently
aligned, worded, and the translations are highly variable. Constraining Claude to the project's "official" Beowulf text
makes the results more consistent and comparable with each other.

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
```

This will:

1. Fetch the HTML content from heorot.dk (if not already cached)
2. Parse the dual-language text
3. Generate JSON and CSV files in `./output`
4. Create ASS subtitle files for each fitt in `./output`

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

- `./assets/blank.ass` - Template file for ASS subtitle formatting

### Output Files

After running the script, you'll find:

**In `./output/`:**

- `maintext.json` - Complete text data in JSON format
- `maintext.csv` - Complete text data in CSV format
- `maintext.html` - Cached HTML from heorot.dk

**In `./output/`:**

- `fitt_0.ass` through `fitt_43.ass` - ASS subtitle files for each fitt (except fitt 24, which doesn't exist)

## Project Structure

Reader, please note: "Sources" here means "Sources of Old English text" not "Source code".

- `sources/heorot.py` - Main parsing and processing logic for Heorot.DK HTML text
- `sources/bosworth.py` - Bosworth-Toller Old English dictionary loader
- `sources/abbreviations.py` - Dictionary abbreviation loader
- `text/models.py` - Model classes for BeowulfLine objects
- `text/numbering.py` - Fitt boundaries and text structure constants
- `writers/` - Output writers (JSON, CSV, ASS subtitle formats)
- `beowulf_mcp/` - MCP server for Beowulf data
- `assets/` - Static data files (blank.ass template, oe_bt.csv, abbreviations XML)
- `findings/` - Callie's attempts to put the MCP server to use in a Claude session
- `output/` - Generated output (JSON, CSV, HTML, ASS subtitle files, DuckDB)

## Old English Texts

The project uses several Old English texts as the basis for its data:

1. [Heorot.dk](https://heorot.dk/beo-ru.html) - dual-language text of Beowulf
2. [Germanic Lexicon Project](https://www.germanic-lexicon-project.org/texts/oe_bosworthtoller_about.html) - XML
   abbreviation file
3. [Bosworth-Toller Old English Dictionary](https://bosworthtoller.com/) - Old English dictionary site
4. [Brunetti Beowulf](https://www.giuseppebrunetti.eu/Brunetti/OE/Varianti/) - Brunetti's lemmatized text

## Token Structure

Each token is a word-level unit with rich linguistic annotations imported from a pipe-delimited file
(`assets/brunetti-length.txt`). The Token model stores:

| Field                           | Purpose                                       |
|:--------------------------------|:----------------------------------------------|
| `fitt_id`, `para_id`, `line_id` | Structural position in the poem               |
| `half_line`                     | 'a' or 'b' half of the Old English verse line |
| `token_offset`                  | Position within the half-line                 |
| `caesura_code`                  | Marks metrical pauses                         |
| `pre_punc`, `post_punc`         | Surrounding punctuation                       |
| `text`                          | The actual Old English word                   |
| `syntax`, `parse`, `pos`        | Grammatical analysis                          |
| `lemma`                         | Dictionary headword                           |
| `gloss`                         | Modern English translation                    |
| `with_length`                   | Text with vowel length markers                |

## Key Design Choices

1. **Pre-annotated corpus** - Tokens come from Brunetti's parsed Beowulf edition, not generated at runtime
2. **Composite key** - Tokens are uniquely identified by
   `(fitt_id, para_id, para_first, non_verse, line_id, half_line, token_offset)`
3. **Half-line aware** - Respects Old English verse structure (each line has an 'a' and 'b' half)
4. **Lemmatized** - Each token links to its canonical dictionary form (aka "headword") for vocabulary lookups

This is a scholarly tokenization aligned with traditional Old English philological practice rather than
NLP-style tokenization.

## Abbreviations

You can decode the cryptic references often found in dictionary entries:

- Beo. Th. = The Anglo-Saxon Poem of Beowulf, edited by Benjamin Thorpe, Oxford, 1855
- Exon. Th. = Codex Exoniensis, edited by Thorpe
- Chr. Erl. = Two of the Saxon Chronicles parallel with supplementary extracts...

```python
from sources.abbreviations import Abbreviations
with Abbreviations(db_path=db_path) as abbv:
    abbv.lookup("Chr. Erl")
```

## OE Dictionary

There's a full Old English dictionary represented here, derived from [./assets/oe_bt.csv](./assets/oe_bt.csv). You can query it from Python:

```python
from sources.bosworth import BosworthToller
with BosworthToller(db_path=db_path) as bt:
    bt.lookup("cyning")
```

## Copyright

This work is copyright 2025-2026 by Callie Tweney, and licensed
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/?ref=chooser-v1).

The Heorot source text is copyright [Benjamin Slade](https://heorot.dk/) 2002-2020.
