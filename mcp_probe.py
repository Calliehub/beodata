#!/usr/bin/env python3
"""
Probe the Beowulf MCP server to list available tools and resources.

Usage:
    poetry run python probe_mcp.py
"""

import asyncio
import logging

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Suppress INFO logs from mcp.server
logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)


async def probe_server() -> None:
    """Connect to the MCP server and list all available tools and resources."""
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_server.py"],
        env={"PYTHONPATH": "/Users/chris/dev/beodata"},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("=== Server Info ===")
            print("Connected to: beowulf-mcp-server v1.0.0")

            print("\n=== Tools ===")
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f"\n  Tool: {tool.name}")
                print(f"    Description: {tool.description}")
                print(f"    Input Schema: {tool.inputSchema}")

            print("\n=== Resources ===")
            resources = await session.list_resources()
            for resource in resources.resources:
                print(f"\n  Resource: {resource.name}")
                print(f"    URI: {resource.uri}")
                print(f"    Description: {resource.description}")
                print(f"    MIME Type: {resource.mimeType}")

                result = await session.read_resource(resource.uri)
                for content in result.contents:
                    text = content.text if hasattr(content, "text") else str(content)
                    preview = text[:500] + "..." if len(text) > 500 else text
                    print(f"    Content ({len(text)} chars):")
                    for line in preview.split("\n")[:10]:
                        print(f"      {line}")
                    if len(text) > 500 or preview.count("\n") >= 10:
                        print("      ...")

            print("\n=== Probe Complete ===")


def main() -> None:
    """Entry point."""
    asyncio.run(probe_server())


if __name__ == "__main__":
    main()
