#!/usr/bin/env python3
"""
MCP Server for Beowulf text data.

A simple Model Context Protocol server that provides access to Beowulf text
as BeowulfLine objects in JSON format.
"""

import asyncio
import json
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    Resource,
    ResourceTemplate,
    ServerCapabilities,
    TextContent,
    Tool,
)
from pydantic import AnyUrl

from beowulf_mcp.cli import fetch_and_store, fetch_store_and_parse
from sources import abbreviations, analytical_lexicon, bosworth
from sources import brunanburh as brunanburh_source
from sources import brunanburh_normalized as brunanburh_norm_source
from sources import brunetti, ebeowulf
from sources import heorot as heorot_source
from sources import mcmaster, mit, oldenglishaerobics, perseus
from sources.heorot import HEOROT_URL, Heorot
from text.models import BeowulfLine, dict_data_to_beowulf_lines

# Initialize the MCP server
server = Server("beowulf-mcp-server")

# ─────────────────────────────────────────────────────────────
# Text edition registry — five OE-only editions with identical interfaces.
# Each exposes get_line, get_lines, and search via module-level functions.
# ─────────────────────────────────────────────────────────────
_TEXT_EDITIONS = {
    "ebeowulf": {
        "module": ebeowulf,
        "label": "eBeowulf",
        "desc": "eBeowulf edition (OE text only)",
    },
    "perseus": {
        "module": perseus,
        "label": "Perseus",
        "desc": "Perseus Digital Library edition (OE text only)",
    },
    "mit": {
        "module": mit,
        "label": "MIT",
        "desc": "MIT edition (OE text only)",
    },
    "mcmaster": {
        "module": mcmaster,
        "label": "McMaster",
        "desc": "McMaster University edition (OE text only)",
    },
    "oea": {
        "module": oldenglishaerobics,
        "label": "OE Aerobics",
        "desc": "Old English Aerobics edition (OE text only)",
    },
}

# ─────────────────────────────────────────────────────────────
# Resource edition registry — text editions exposed as resources.
# Each module must provide load(), get_line(n), get_lines(start, end).
# ─────────────────────────────────────────────────────────────
_RESOURCE_EDITIONS = {
    "ebeowulf": {"module": ebeowulf, "label": "eBeowulf"},
    "heorot": {"module": heorot_source, "label": "Heorot"},
    "mcmaster": {"module": mcmaster, "label": "McMaster"},
    "mit": {"module": mit, "label": "MIT"},
    "perseus": {"module": perseus, "label": "Perseus"},
    "oldenglishaerobics": {"module": oldenglishaerobics, "label": "OE Aerobics"},
}

# Heorot singleton for DuckDB-backed search
_heorot_db: Heorot | None = None


def _ensure_heorot_db() -> Heorot:
    """Ensure the Heorot DuckDB table is loaded and return the instance."""
    global _heorot_db
    if _heorot_db is None:
        _heorot_db = Heorot()
    if not _heorot_db.db.table_exists("heorot"):
        html = fetch_and_store(HEOROT_URL, "maintext.html")
        _heorot_db.load_from_html(html)
    return _heorot_db


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def _handle_edition_resource(uri_str: str) -> List[ReadResourceContents]:
    """Handle beowulf://text/{edition}[/line/...] resources."""
    prefix = "beowulf://text/"
    rest = uri_str[len(prefix) :]

    for key, cfg in _RESOURCE_EDITIONS.items():
        if rest == key or rest.startswith(key + "/"):
            mod = cfg["module"]
            mod.load()
            suffix = rest[len(key) :]

            if suffix == "" or suffix == "/":
                results = mod.get_lines()
            elif suffix.startswith("/line/"):
                line_rest = suffix[len("/line/") :]
                parts = line_rest.split("/")
                if len(parts) == 1:
                    result = mod.get_line(int(parts[0]))
                    results = [result] if result else []
                elif len(parts) == 2:
                    results = mod.get_lines(int(parts[0]), int(parts[1]))
                else:
                    raise ValueError(f"Invalid line URI: {uri_str}")
            else:
                raise ValueError(f"Unknown resource path: {uri_str}")

            return [
                ReadResourceContents(
                    content=json.dumps(results, indent=2, ensure_ascii=False),
                    mime_type="application/json",
                )
            ]

    raise ValueError(f"Unknown edition in URI: {uri_str}")


def _handle_brunetti_resource(uri_str: str) -> List[ReadResourceContents]:
    """Handle beowulf://text/brunetti[/...] resources."""
    brunetti.load()

    prefix = "beowulf://text/brunetti"
    suffix = uri_str[len(prefix) :]  # "" or "/fitt/1" or "/line/5" or "/line/1/10"

    if suffix == "" or suffix == "/":
        # All rows
        results = brunetti.search("")
    elif suffix.startswith("/fitt/"):
        fitt_num = suffix[len("/fitt/") :]
        results = brunetti.get_by_fitt(str(int(fitt_num)).zfill(2))
    elif suffix.startswith("/line/"):
        rest = suffix[len("/line/") :]
        parts = rest.split("/")
        if len(parts) == 1:
            line_num = parts[0]
            results = brunetti.get_by_line(str(int(line_num)).zfill(4))
        elif len(parts) == 2:
            start = int(parts[0])
            end = int(parts[1])
            results = []
            for n in range(start, end + 1):
                results.extend(brunetti.get_by_line(str(n).zfill(4)))
        else:
            raise ValueError(f"Invalid brunetti line URI: {uri_str}")
    else:
        raise ValueError(f"Unknown brunetti resource path: {uri_str}")

    return [
        ReadResourceContents(
            content=json.dumps(results, indent=2, ensure_ascii=False),
            mime_type="application/json",
        )
    ]


def beowulf_line_to_dict(line: BeowulfLine) -> Dict[str, Any]:
    """Convert a BeowulfLine to a dictionary for JSON serialization."""
    return {
        "line_number": line.line_number,
        "old_english": line.old_english,
        "modern_english": line.modern_english,
        "title": line.title,
        "is_empty": line.is_empty,
        "is_title_line": line.is_title_line,
    }


def _json_result(data: Any) -> CallToolResult:
    """Wrap data as a JSON CallToolResult."""
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(data, indent=2, ensure_ascii=False),
            )
        ]
    )


# ─────────────────────────────────────────────────────────────
# Tool definitions
# ─────────────────────────────────────────────────────────────


def _edition_tools() -> List[Tool]:
    """Generate get_line / get_lines / search tools for each text edition."""
    tools = []
    for prefix, cfg in _TEXT_EDITIONS.items():
        label = cfg["label"]
        tools.append(
            Tool(
                name=f"{prefix}_get_line",
                description=f"Get a specific line by number from the {label} edition",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "line_number": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 3182,
                            "description": "The line number to retrieve",
                        },
                    },
                    "required": ["line_number"],
                },
            )
        )
        tools.append(
            Tool(
                name=f"{prefix}_get_lines",
                description=f"Get a range of lines from the {label} edition",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "start": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 3182,
                            "description": "Start line number (inclusive)",
                        },
                        "end": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 3182,
                            "description": "End line number (inclusive). Omit for all lines from start.",
                        },
                    },
                    "required": ["start"],
                },
            )
        )
        tools.append(
            Tool(
                name=f"{prefix}_search",
                description=f"Search the Old English text of the {label} edition (case-insensitive)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "term": {
                            "type": "string",
                            "description": "The term to search for",
                        },
                    },
                    "required": ["term"],
                },
            )
        )
    return tools


@server.list_tools()
async def list_tools() -> List:
    """List available tools."""
    return [
        # ── Heorot (OE + ME bilingual) ──────────────────────────
        Tool(
            name="get_beowulf_lines",
            description="Get Beowulf text lines as JSON, optionally filtered by line number range",
            inputSchema={
                "type": "object",
                "properties": {
                    "from": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 3182,
                        "description": "Start line number (inclusive)",
                    },
                    "to": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 3182,
                        "description": "End line number (inclusive)",
                    },
                },
            },
        ),
        Tool(
            name="get_beowulf_summary",
            description="Get summary statistics about the Beowulf text",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_fitt_lines",
            description="Get Beowulf lines for a specific fitt",
            inputSchema={
                "type": "object",
                "properties": {
                    "fitt_number": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 43,
                        "description": "Fitt number to retrieve (0-43, excluding 24)",
                    }
                },
                "required": ["fitt_number"],
            },
        ),
        Tool(
            name="heorot_search",
            description="Search the heorot.dk Beowulf text (OE, ME, or both)",
            inputSchema={
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "The term to search for (case-insensitive)",
                    },
                    "language": {
                        "type": "string",
                        "description": "Restrict to Old English or Modern English. Omit to search both.",
                        "enum": ["oe", "me"],
                    },
                },
                "required": ["term"],
            },
        ),
        # ── Bosworth-Toller dictionary ──────────────────────────
        Tool(
            name="bt_lookup",
            description="Look up an exact Old English headword in the Bosworth-Toller dictionary",
            inputSchema={
                "type": "object",
                "properties": {
                    "word": {
                        "type": "string",
                        "description": "The Old English word to look up",
                    },
                },
                "required": ["word"],
            },
        ),
        Tool(
            name="bt_lookup_like",
            description="Look up Old English headwords matching a SQL LIKE pattern in the Bosworth-Toller dictionary",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "SQL LIKE pattern to match headwords (e.g. 'cyn%')",
                    },
                },
                "required": ["pattern"],
            },
        ),
        Tool(
            name="bt_search",
            description="Full-text search across Bosworth-Toller dictionary entries",
            inputSchema={
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "The term to search for (case-insensitive)",
                    },
                    "column": {
                        "type": "string",
                        "description": "Specific column to search: headword, definition, or references. Omit to search all columns.",
                        "enum": ["headword", "definition", "references"],
                    },
                },
                "required": ["term"],
            },
        ),
        Tool(
            name="bt_abbreviation",
            description="Look up a Bosworth-Toller abbreviation by partial match (e.g. 'Beo.' to find Beowulf references)",
            inputSchema={
                "type": "object",
                "properties": {
                    "abbrev": {
                        "type": "string",
                        "description": "The abbreviation to look up (partial match supported)",
                    },
                },
                "required": ["abbrev"],
            },
        ),
        # ── Brunetti tokenized Beowulf ──────────────────────────
        Tool(
            name="brunetti_lookup",
            description="Look up an exact Old English lemma in the Brunetti tokenized Beowulf",
            inputSchema={
                "type": "object",
                "properties": {
                    "lemma": {
                        "type": "string",
                        "description": "The Old English lemma to look up",
                    },
                },
                "required": ["lemma"],
            },
        ),
        Tool(
            name="brunetti_lookup_like",
            description="Look up Old English lemmas matching a SQL LIKE pattern in the Brunetti tokenized Beowulf",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "SQL LIKE pattern to match lemmas (e.g. 'cyn%')",
                    },
                },
                "required": ["pattern"],
            },
        ),
        Tool(
            name="brunetti_search",
            description="Full-text search across Brunetti tokenized Beowulf entries",
            inputSchema={
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "The term to search for (case-insensitive)",
                    },
                    "column": {
                        "type": "string",
                        "description": "Specific column to search. Omit to search all columns.",
                        "enum": [
                            "fitt_id",
                            "line_id",
                            "text",
                            "lemma",
                            "pos",
                            "gloss",
                            "with_length",
                        ],
                    },
                },
                "required": ["term"],
            },
        ),
        Tool(
            name="brunetti_get_by_line",
            description="Get all Brunetti tokens for a specific line number",
            inputSchema={
                "type": "object",
                "properties": {
                    "line_id": {
                        "type": "string",
                        "description": "Line number as zero-padded string (e.g. '0001')",
                    },
                },
                "required": ["line_id"],
            },
        ),
        Tool(
            name="brunetti_get_by_fitt",
            description="Get all Brunetti tokens for a specific fitt",
            inputSchema={
                "type": "object",
                "properties": {
                    "fitt_id": {
                        "type": "string",
                        "description": "Fitt number as zero-padded string (e.g. '01')",
                    },
                },
                "required": ["fitt_id"],
            },
        ),
        # ── Analytical Lexicon ──────────────────────────────────
        Tool(
            name="lexicon_lookup",
            description="Look up an exact headword in the Analytical Lexicon of Beowulf",
            inputSchema={
                "type": "object",
                "properties": {
                    "headword": {
                        "type": "string",
                        "description": "The Old English headword to look up",
                    },
                },
                "required": ["headword"],
            },
        ),
        Tool(
            name="lexicon_lookup_like",
            description="Look up headwords matching a SQL LIKE pattern in the Analytical Lexicon",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "SQL LIKE pattern to match headwords (e.g. 'cyn%')",
                    },
                },
                "required": ["pattern"],
            },
        ),
        Tool(
            name="lexicon_search",
            description="Full-text search across the Analytical Lexicon of Beowulf",
            inputSchema={
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "The term to search for (case-insensitive)",
                    },
                    "column": {
                        "type": "string",
                        "description": "Specific column to search. Omit to search all columns.",
                        "enum": [
                            "headword",
                            "part_of_speech",
                            "form",
                            "inflection",
                            "line_refs",
                        ],
                    },
                },
                "required": ["term"],
            },
        ),
        # ── Brunanburh (sacred-texts, OE only) ────────────────────
        Tool(
            name="brunanburh_get_line",
            description="Get a specific line by number from the Battle of Brunanburh (sacred-texts edition)",
            inputSchema={
                "type": "object",
                "properties": {
                    "line_number": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 73,
                        "description": "The line number to retrieve",
                    },
                },
                "required": ["line_number"],
            },
        ),
        Tool(
            name="brunanburh_get_lines",
            description="Get a range of lines from the Battle of Brunanburh (sacred-texts edition)",
            inputSchema={
                "type": "object",
                "properties": {
                    "start": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 73,
                        "description": "Start line number (inclusive)",
                    },
                    "end": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 73,
                        "description": "End line number (inclusive). Omit for all lines from start.",
                    },
                },
                "required": ["start"],
            },
        ),
        Tool(
            name="brunanburh_search",
            description="Search the Old English text of the Battle of Brunanburh (sacred-texts edition, case-insensitive)",
            inputSchema={
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "The term to search for",
                    },
                },
                "required": ["term"],
            },
        ),
        # ── Brunanburh Normalized (CLASP, OE + normalized) ────────
        Tool(
            name="brunanburh_normalized_get_line",
            description="Get a specific line by number from the Battle of Brunanburh (CLASP normalized edition, OE + normalized text with macrons)",
            inputSchema={
                "type": "object",
                "properties": {
                    "line_number": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 73,
                        "description": "The line number to retrieve",
                    },
                },
                "required": ["line_number"],
            },
        ),
        Tool(
            name="brunanburh_normalized_get_lines",
            description="Get a range of lines from the Battle of Brunanburh (CLASP normalized edition, OE + normalized text with macrons)",
            inputSchema={
                "type": "object",
                "properties": {
                    "start": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 73,
                        "description": "Start line number (inclusive)",
                    },
                    "end": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 73,
                        "description": "End line number (inclusive). Omit for all lines from start.",
                    },
                },
                "required": ["start"],
            },
        ),
        Tool(
            name="brunanburh_normalized_search",
            description="Search the Battle of Brunanburh (CLASP normalized edition, case-insensitive)",
            inputSchema={
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "The term to search for",
                    },
                    "column": {
                        "type": "string",
                        "description": "Restrict to original OE or normalized text. Omit to search both.",
                        "enum": ["oe", "normed"],
                    },
                },
                "required": ["term"],
            },
        ),
        # ── Text editions (generated) ───────────────────────────
        *_edition_tools(),
    ]


# ─────────────────────────────────────────────────────────────
# Resources
# ─────────────────────────────────────────────────────────────


@server.list_resources()
async def list_resources() -> List[Resource]:
    """List available resources."""
    resources = [
        Resource(
            uri=f"beowulf://text/{key}",
            name=f"{cfg['label']} (All Lines)",
            description=f"All lines from the {cfg['label']} edition",
            mimeType="application/json",
        )
        for key, cfg in _RESOURCE_EDITIONS.items()
    ]
    resources.append(
        Resource(
            uri="beowulf://text/brunetti",
            name="Brunetti Tokens (All)",
            description="All tokenized Beowulf data from the Brunetti edition",
            mimeType="application/json",
        ),
    )
    return resources


@server.list_resource_templates()
async def list_resource_templates() -> list[ResourceTemplate]:
    """List available resource templates."""
    templates: list[ResourceTemplate] = []
    for key, cfg in _RESOURCE_EDITIONS.items():
        label = cfg["label"]
        templates.append(
            ResourceTemplate(
                uriTemplate=f"beowulf://text/{key}/line/{{line_number}}",
                name=f"{label} Line",
                description=f"A specific line from the {label} edition",
                mimeType="application/json",
            )
        )
        templates.append(
            ResourceTemplate(
                uriTemplate=f"beowulf://text/{key}/line/{{from}}/{{to}}",
                name=f"{label} Line Range",
                description=f"A range of lines from the {label} edition (inclusive)",
                mimeType="application/json",
            )
        )
    # Brunetti templates
    templates.extend(
        [
            ResourceTemplate(
                uriTemplate="beowulf://text/brunetti/fitt/{fitt_id}",
                name="Brunetti Tokens by Fitt",
                description="All tokenized Beowulf data for a specific fitt number",
                mimeType="application/json",
            ),
            ResourceTemplate(
                uriTemplate="beowulf://text/brunetti/line/{line_id}",
                name="Brunetti Tokens by Line",
                description="All tokenized Beowulf data for a specific line number",
                mimeType="application/json",
            ),
            ResourceTemplate(
                uriTemplate="beowulf://text/brunetti/line/{from}/{to}",
                name="Brunetti Tokens by Line Range",
                description="All tokenized Beowulf data for a range of line numbers (inclusive)",
                mimeType="application/json",
            ),
        ]
    )
    return templates


@server.read_resource()
async def read_resource(uri: AnyUrl) -> List[ReadResourceContents]:
    """Read a specific resource."""
    uri_str = str(uri)

    if uri_str.startswith("beowulf://text/brunetti"):
        return _handle_brunetti_resource(uri_str)

    if uri_str.startswith("beowulf://text/"):
        return _handle_edition_resource(uri_str)

    raise ValueError(f"Unknown resource: {uri}")


# ─────────────────────────────────────────────────────────────
# Tool dispatch
# ─────────────────────────────────────────────────────────────


def _handle_edition_tool(
    tool_name: str, tool_args: dict[str, Any]
) -> CallToolResult | None:
    """Handle text edition tools. Returns None if tool_name doesn't match."""
    for prefix, cfg in _TEXT_EDITIONS.items():
        mod = cfg["module"]
        if tool_name == f"{prefix}_get_line":
            mod.load()
            line = mod.get_line(tool_args["line_number"])
            result = {"result": line, "found": line is not None}
            return _json_result(result)
        elif tool_name == f"{prefix}_get_lines":
            mod.load()
            end = tool_args.get("end")
            results = mod.get_lines(tool_args["start"], end)
            return _json_result({"results": results, "count": len(results)})
        elif tool_name == f"{prefix}_search":
            mod.load()
            results = mod.search(tool_args["term"])
            return _json_result({"results": results, "count": len(results)})
    return None


@server.call_tool()
async def call_tool(tool_name: str, tool_args: dict[str, Any]) -> CallToolResult:
    """Handle tool calls."""
    if tool_name == "get_beowulf_lines":
        raw_lines = fetch_store_and_parse("maintext", HEOROT_URL)
        beowulf_lines = dict_data_to_beowulf_lines(raw_lines)

        # Apply optional line range filter
        line_from = tool_args.get("from")
        line_to = tool_args.get("to")
        if line_from is not None or line_to is not None:
            start = line_from if line_from is not None else 0
            end = line_to if line_to is not None else 3182
            beowulf_lines = [
                line for line in beowulf_lines if start <= line.line_number <= end
            ]

        result = {
            "lines": [beowulf_line_to_dict(line) for line in beowulf_lines],
            "count": len(beowulf_lines),
        }
        return _json_result(result)

    elif tool_name == "get_beowulf_summary":
        raw_lines = fetch_store_and_parse("maintext", HEOROT_URL)
        beowulf_lines = dict_data_to_beowulf_lines(raw_lines)

        title_lines = [line for line in beowulf_lines if line.is_title_line]
        result = {
            "total_lines": len(beowulf_lines),
            "title_lines": len(title_lines),
            "empty_lines": len([line for line in beowulf_lines if line.is_empty]),
            "sample_lines": [
                beowulf_line_to_dict(beowulf_lines[0]),
                beowulf_line_to_dict(beowulf_lines[1]),
                beowulf_line_to_dict(beowulf_lines[-1]),
            ],
        }
        return _json_result(result)

    elif tool_name == "get_fitt_lines":
        fitt_number = tool_args["fitt_number"]

        if fitt_number == 24:
            raise ValueError("Fitt 24 does not exist in Beowulf")

        # Get all lines and filter for the fitt
        raw_lines = fetch_store_and_parse("maintext", HEOROT_URL)
        beowulf_lines = dict_data_to_beowulf_lines(raw_lines)

        from text.numbering import FITT_BOUNDARIES

        start_line = FITT_BOUNDARIES[fitt_number][0]
        end_line = FITT_BOUNDARIES[fitt_number][1]
        fitt_name = FITT_BOUNDARIES[fitt_number][2]

        fitt_lines = [
            line for line in beowulf_lines if start_line <= line.line_number <= end_line
        ]

        result = {
            "fitt_number": fitt_number,
            "fitt_name": fitt_name,
            "start_line": start_line,
            "end_line": end_line,
            "lines": [beowulf_line_to_dict(line) for line in fitt_lines],
            "count": len(fitt_lines),
        }
        return _json_result(result)

    elif tool_name == "heorot_search":
        heorot = _ensure_heorot_db()
        term = tool_args["term"]
        language = tool_args.get("language")
        if language == "oe":
            results = heorot.search_oe(term)
        elif language == "me":
            results = heorot.search_me(term)
        else:
            results = heorot.search(term)
        return _json_result({"results": results, "count": len(results)})

    # ── Bosworth-Toller ─────────────────────────────────────
    elif tool_name == "bt_lookup":
        bosworth.load()
        results = bosworth.lookup(tool_args["word"])
        return _json_result({"results": results, "count": len(results)})

    elif tool_name == "bt_lookup_like":
        bosworth.load()
        results = bosworth.lookup_like(tool_args["pattern"])
        return _json_result({"results": results, "count": len(results)})

    elif tool_name == "bt_search":
        bosworth.load()
        column = tool_args.get("column")
        results = bosworth.search(tool_args["term"], column=column)
        return _json_result({"results": results, "count": len(results)})

    elif tool_name == "bt_abbreviation":
        abbreviations.load()
        results = abbreviations.lookup(tool_args["abbrev"])
        return _json_result({"results": results, "count": len(results)})

    # ── Brunetti ────────────────────────────────────────────
    elif tool_name == "brunetti_lookup":
        brunetti.load()
        results = brunetti.lookup(tool_args["lemma"])
        return _json_result({"results": results, "count": len(results)})

    elif tool_name == "brunetti_lookup_like":
        brunetti.load()
        results = brunetti.lookup_like(tool_args["pattern"])
        return _json_result({"results": results, "count": len(results)})

    elif tool_name == "brunetti_search":
        brunetti.load()
        column = tool_args.get("column")
        results = brunetti.search(tool_args["term"], column=column)
        return _json_result({"results": results, "count": len(results)})

    elif tool_name == "brunetti_get_by_line":
        brunetti.load()
        results = brunetti.get_by_line(tool_args["line_id"])
        return _json_result({"results": results, "count": len(results)})

    elif tool_name == "brunetti_get_by_fitt":
        brunetti.load()
        results = brunetti.get_by_fitt(tool_args["fitt_id"])
        return _json_result({"results": results, "count": len(results)})

    # ── Analytical Lexicon ──────────────────────────────────
    elif tool_name == "lexicon_lookup":
        analytical_lexicon.load()
        results = analytical_lexicon.lookup(tool_args["headword"])
        return _json_result({"results": results, "count": len(results)})

    elif tool_name == "lexicon_lookup_like":
        analytical_lexicon.load()
        results = analytical_lexicon.lookup_like(tool_args["pattern"])
        return _json_result({"results": results, "count": len(results)})

    elif tool_name == "lexicon_search":
        analytical_lexicon.load()
        column = tool_args.get("column")
        results = analytical_lexicon.search(tool_args["term"], column=column)
        return _json_result({"results": results, "count": len(results)})

    # ── Brunanburh (sacred-texts) ──────────────────────────
    elif tool_name == "brunanburh_get_line":
        brunanburh_source.load()
        line = brunanburh_source.get_line(tool_args["line_number"])
        return _json_result({"result": line, "found": line is not None})

    elif tool_name == "brunanburh_get_lines":
        brunanburh_source.load()
        end = tool_args.get("end")
        results = brunanburh_source.get_lines(tool_args["start"], end)
        return _json_result({"results": results, "count": len(results)})

    elif tool_name == "brunanburh_search":
        brunanburh_source.load()
        results = brunanburh_source.search(tool_args["term"])
        return _json_result({"results": results, "count": len(results)})

    # ── Brunanburh Normalized (CLASP) ────────────────────
    elif tool_name == "brunanburh_normalized_get_line":
        brunanburh_norm_source.load()
        line = brunanburh_norm_source.get_line(tool_args["line_number"])
        return _json_result({"result": line, "found": line is not None})

    elif tool_name == "brunanburh_normalized_get_lines":
        brunanburh_norm_source.load()
        end = tool_args.get("end")
        results = brunanburh_norm_source.get_lines(tool_args["start"], end)
        return _json_result({"results": results, "count": len(results)})

    elif tool_name == "brunanburh_normalized_search":
        brunanburh_norm_source.load()
        column = tool_args.get("column")
        if column == "oe":
            results = brunanburh_norm_source.get_brunanburh_normalized().search_oe(
                tool_args["term"]
            )
        elif column == "normed":
            results = brunanburh_norm_source.get_brunanburh_normalized().search_normed(
                tool_args["term"]
            )
        else:
            results = brunanburh_norm_source.search(tool_args["term"])
        return _json_result({"results": results, "count": len(results)})

    else:
        # Try text edition tools
        edition_result = _handle_edition_tool(tool_name, tool_args)
        if edition_result is not None:
            return edition_result

        raise ValueError(f"Unknown tool: {tool_name}")


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="beowulf-mcp-server",
                server_version="1.0.0",
                capabilities=ServerCapabilities(
                    tools={},
                    resources={},
                ),
            ),
        )


def run_server():
    """Entry point for poetry script."""
    asyncio.run(main())


if __name__ == "__main__":
    run_server()
