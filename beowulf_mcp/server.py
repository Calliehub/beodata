#!/usr/bin/env python3
"""
MCP Server for Beowulf text data.

A simple Model Context Protocol server that provides access to Beowulf text
as BeowulfLine objects in JSON format.
"""

import asyncio
import json
import sys
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListResourcesRequest,
    ListResourcesResult,
    ListToolsRequest,
    ListToolsResult,
    ReadResourceRequest,
    ReadResourceResult,
    Resource,
    ServerCapabilities,
    TextContent,
    Tool,
)
from pydantic import AnyUrl

from beodata.parse.heorot import HEOROT_URL, fetch_store_and_parse
from beodata.text.models import BeowulfLine, dict_data_to_beowulf_lines

# Initialize the MCP server
server = Server("beowulf-mcp-server")


def _handle_all_lines_resource() -> List[ReadResourceContents]:
    """Handle the beowulf://text/all resource."""
    beowulf_lines = _get_beowulf_data()
    lines_data = [beowulf_line_to_dict(line) for line in beowulf_lines]
    return [
        ReadResourceContents(
            content=json.dumps(lines_data, indent=2, ensure_ascii=False),
            mime_type="application/json",
        )
    ]


def _handle_summary_resource() -> List[ReadResourceContents]:
    """Handle the beowulf://text/summary resource."""
    beowulf_lines = _get_beowulf_data()

    title_lines = [line for line in beowulf_lines if line.is_title_line]
    empty_lines = [line for line in beowulf_lines if line.is_empty]

    summary = {
        "total_lines": len(beowulf_lines),
        "title_lines": len(title_lines),
        "empty_lines": len(empty_lines),
        "first_line": beowulf_line_to_dict(beowulf_lines[0]) if beowulf_lines else None,
        "last_line": beowulf_line_to_dict(beowulf_lines[-1]) if beowulf_lines else None,
        "fitt_titles": [line.title for line in title_lines],
    }

    return [
        ReadResourceContents(
            content=json.dumps(summary, indent=2, ensure_ascii=False),
            mime_type="application/json",
        )
    ]


def _get_beowulf_data() -> List[BeowulfLine]:
    """Get parsed Beowulf data, shared by multiple resource handlers."""
    raw_lines = fetch_store_and_parse("maintext", HEOROT_URL)
    return dict_data_to_beowulf_lines(raw_lines)


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


@server.list_tools()
async def list_tools() -> List:
    """List available tools."""
    return [
        Tool(
            name="get_beowulf_lines",
            description="Get all Beowulf text lines as JSON",
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["full", "summary"],
                        "default": "full",
                        "description": "Format of the response: 'full' for complete data, 'summary' for basic info",
                    }
                },
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
    ]


@server.list_resources()
async def list_resources() -> List[Resource]:
    """List available resources."""
    return [
        Resource(
            uri="beowulf://text/all",
            name="All Beowulf Lines",
            description="Complete Beowulf text as BeowulfLine objects",
            mimeType="application/json",
        ),
        Resource(
            uri="beowulf://text/summary",
            name="Beowulf Summary",
            description="Summary statistics of the Beowulf text",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def read_resource(uri: AnyUrl) -> List[ReadResourceContents]:
    """Read a specific resource."""
    match str(uri):
        case "beowulf://text/all":
            return _handle_all_lines_resource()
        case "beowulf://text/summary":
            return _handle_summary_resource()
        case _:
            raise ValueError(f"Unknown resource: {uri}")


@server.call_tool()
async def call_tool(request: CallToolRequest) -> CallToolResult:
    """Handle tool calls."""
    if request.name == "get_beowulf_lines":
        # Get all Beowulf lines
        raw_lines = fetch_store_and_parse("maintext", HEOROT_URL)
        beowulf_lines = dict_data_to_beowulf_lines(raw_lines)

        format_type = request.arguments.get("format", "full")

        if format_type == "summary":
            # Return summary info
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
        else:
            # Return full data
            result = {
                "lines": [beowulf_line_to_dict(line) for line in beowulf_lines],
                "count": len(beowulf_lines),
            }

        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, ensure_ascii=False),
                )
            ]
        )

    elif request.name == "get_fitt_lines":
        fitt_number = request.arguments["fitt_number"]

        if fitt_number == 24:
            raise ValueError("Fitt 24 does not exist in Beowulf")

        # Get all lines and filter for the fitt
        raw_lines = fetch_store_and_parse("maintext", HEOROT_URL)
        beowulf_lines = dict_data_to_beowulf_lines(raw_lines)

        from beodata.text.numbering import FITT_BOUNDARIES

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

        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, ensure_ascii=False),
                )
            ]
        )

    else:
        raise ValueError(f"Unknown tool: {request.name}")


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
