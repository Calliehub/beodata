"""Tests for the Beowulf MCP server."""

import json
import logging
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Suppress INFO logs from mcp.server
logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)

# we need a path to proj root to use as working dir for server
PROJECT_ROOT = Path(__file__).parents[1]


async def _get_session_and_run(test_func):
    """Helper to create session and run the MCP server listening on stdio"""
    server_params = StdioServerParameters(
        cwd=PROJECT_ROOT,
        command="poetry",
        args=["run", "python", "beowulf_mcp/server.py"],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await test_func(session)


class TestListTools:
    """Tests for listing available tools."""

    async def test_list_tools_returns_six_tools(self) -> None:
        """Server exposes exactly six tools."""

        async def check(session: ClientSession):
            tools = await session.list_tools()
            assert len(tools.tools) == 6

        await _get_session_and_run(check)

    async def test_get_beowulf_lines_tool_exists(self) -> None:
        """get_beowulf_lines tool is available."""

        async def check(session: ClientSession):
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            assert "get_beowulf_lines" in tool_names

        await _get_session_and_run(check)

    async def test_get_beowulf_summary_tool_exists(self) -> None:
        """get_beowulf_summary tool is available."""

        async def check(session: ClientSession):
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            assert "get_beowulf_summary" in tool_names

        await _get_session_and_run(check)

    async def test_get_fitt_lines_tool_exists(self) -> None:
        """get_fitt_lines tool is available."""

        async def check(session: ClientSession):
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            assert "get_fitt_lines" in tool_names

        await _get_session_and_run(check)


class TestListResources:
    """Tests for listing available resources."""

    async def test_list_resources_returns_two_resources(self) -> None:
        """Server exposes exactly two resources."""

        async def check(session: ClientSession):
            resources = await session.list_resources()
            assert len(resources.resources) == 2

        await _get_session_and_run(check)

    async def test_all_lines_resource_exists(self) -> None:
        """beowulf://text/all resource is available."""

        async def check(session: ClientSession):
            resources = await session.list_resources()
            uris = [str(r.uri) for r in resources.resources]
            assert "beowulf://text/all" in uris

        await _get_session_and_run(check)

    async def test_summary_resource_exists(self) -> None:
        """beowulf://text/summary resource is available."""

        async def check(session: ClientSession):
            resources = await session.list_resources()
            uris = [str(r.uri) for r in resources.resources]
            assert "beowulf://text/summary" in uris

        await _get_session_and_run(check)


class TestReadResources:
    """Tests for reading resource content."""

    async def test_read_summary_resource(self) -> None:
        """Reading summary resource returns valid JSON with expected fields."""

        async def check(session: ClientSession):
            result = await session.read_resource("beowulf://text/summary")
            assert len(result.contents) == 1

            content = result.contents[0]
            text = content.text if hasattr(content, "text") else str(content)
            data = json.loads(text)

            assert "total_lines" in data
            assert "title_lines" in data
            assert "fitt_titles" in data
            assert data["total_lines"] > 3000

        await _get_session_and_run(check)

    async def test_read_all_lines_resource(self) -> None:
        """Reading all lines resource returns valid JSON array."""

        async def check(session: ClientSession):
            result = await session.read_resource("beowulf://text/all")
            assert len(result.contents) == 1

            content = result.contents[0]
            text = content.text if hasattr(content, "text") else str(content)
            data = json.loads(text)

            assert isinstance(data, list)
            assert len(data) == 3183

        await _get_session_and_run(check)


class TestCallTools:
    """Tests for calling tools."""

    async def test_get_fitt_lines_fitt_1(self) -> None:
        """get_fitt_lines returns correct data for fitt 1."""

        async def check(session: ClientSession):
            result = await session.call_tool(
                name="get_fitt_lines", arguments={"fitt_number": 1}
            )
            assert len(result.content) == 1

            content = result.content[0]
            text = content.text if hasattr(content, "text") else str(content)
            data = json.loads(text)

            assert data["fitt_number"] == 1
            assert data["fitt_name"] == "I"
            assert data["start_line"] == 53
            assert data["end_line"] == 114
            assert len(data["lines"]) > 0

        await _get_session_and_run(check)

    async def test_get_fitt_lines_prologue(self) -> None:
        """get_fitt_lines returns correct data for prologue (fitt 0)."""

        async def check(session: ClientSession):
            result = await session.call_tool(
                name="get_fitt_lines", arguments={"fitt_number": 0}
            )

            content = result.content[0]
            text = content.text if hasattr(content, "text") else str(content)
            data = json.loads(text)

            assert data["fitt_number"] == 0
            assert data["fitt_name"] == "Prologue"

        await _get_session_and_run(check)

    async def test_get_beowulf_summary(self) -> None:
        """get_beowulf_summary returns summary data."""

        async def check(session: ClientSession):
            result = await session.call_tool(name="get_beowulf_summary", arguments={})

            content = result.content[0]
            text = content.text if hasattr(content, "text") else str(content)
            data = json.loads(text)

            assert "total_lines" in data
            assert "sample_lines" in data
            assert len(data["sample_lines"]) == 3

        await _get_session_and_run(check)

    async def test_get_beowulf_lines_from_to(self) -> None:
        """get_beowulf_lines with from/to returns only lines in that range."""

        async def check(session: ClientSession):
            result = await session.call_tool(
                name="get_beowulf_lines",
                arguments={"from": 10, "to": 20},
            )

            content = result.content[0]
            text = content.text if hasattr(content, "text") else str(content)
            data = json.loads(text)

            assert data["count"] == 11
            line_numbers = [line["line_number"] for line in data["lines"]]
            assert min(line_numbers) == 10
            assert max(line_numbers) == 20

        await _get_session_and_run(check)

    async def test_get_beowulf_lines_from_only(self) -> None:
        """get_beowulf_lines with only from returns lines from that point to end."""

        async def check(session: ClientSession):
            result = await session.call_tool(
                name="get_beowulf_lines",
                arguments={"from": 3180},
            )

            content = result.content[0]
            text = content.text if hasattr(content, "text") else str(content)
            data = json.loads(text)

            line_numbers = [line["line_number"] for line in data["lines"]]
            assert min(line_numbers) == 3180
            assert max(line_numbers) == 3182
            assert data["count"] == 3

        await _get_session_and_run(check)

    async def test_get_beowulf_lines_to_only(self) -> None:
        """get_beowulf_lines with only to returns lines from start up to that point."""

        async def check(session: ClientSession):
            result = await session.call_tool(
                name="get_beowulf_lines",
                arguments={"to": 2},
            )

            content = result.content[0]
            text = content.text if hasattr(content, "text") else str(content)
            data = json.loads(text)

            line_numbers = [line["line_number"] for line in data["lines"]]
            assert min(line_numbers) == 0
            assert max(line_numbers) == 2
            assert data["count"] == 3

        await _get_session_and_run(check)

    async def test_get_beowulf_lines_single_line(self) -> None:
        """get_beowulf_lines with from==to returns exactly one line."""

        async def check(session: ClientSession):
            result = await session.call_tool(
                name="get_beowulf_lines",
                arguments={"from": 1757, "to": 1757},
            )

            content = result.content[0]
            text = content.text if hasattr(content, "text") else str(content)
            data = json.loads(text)

            assert data["count"] == 1
            assert data["lines"][0]["line_number"] == 1757

        await _get_session_and_run(check)


class TestBosworthTools:
    """Tests for Bosworth-Toller dictionary tools."""

    async def test_bt_lookup_tool_exists(self) -> None:
        """bt_lookup tool is available."""

        async def check(session: ClientSession):
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            assert "bt_lookup" in tool_names

        await _get_session_and_run(check)

    async def test_bt_lookup_like_tool_exists(self) -> None:
        """bt_lookup_like tool is available."""

        async def check(session: ClientSession):
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            assert "bt_lookup_like" in tool_names

        await _get_session_and_run(check)

    async def test_bt_search_tool_exists(self) -> None:
        """bt_search tool is available."""

        async def check(session: ClientSession):
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            assert "bt_search" in tool_names

        await _get_session_and_run(check)

    async def test_bt_lookup_finds_word(self) -> None:
        """bt_lookup returns results with expected keys for a known OE word."""

        async def check(session: ClientSession):
            result = await session.call_tool(
                name="bt_lookup", arguments={"word": "cyning"}
            )
            content = result.content[0]
            text = content.text if hasattr(content, "text") else str(content)
            data = json.loads(text)

            assert data["count"] >= 1
            entry = data["results"][0]
            assert "headword" in entry
            assert "definition" in entry
            assert "references" in entry

        await _get_session_and_run(check)

    async def test_bt_lookup_no_match(self) -> None:
        """bt_lookup returns empty results for gibberish."""

        async def check(session: ClientSession):
            result = await session.call_tool(
                name="bt_lookup", arguments={"word": "xyzzyplugh"}
            )
            content = result.content[0]
            text = content.text if hasattr(content, "text") else str(content)
            data = json.loads(text)

            assert data["count"] == 0
            assert data["results"] == []

        await _get_session_and_run(check)

    async def test_bt_lookup_like_prefix(self) -> None:
        """bt_lookup_like with a prefix pattern returns multiple results."""

        async def check(session: ClientSession):
            result = await session.call_tool(
                name="bt_lookup_like", arguments={"pattern": "cyn%"}
            )
            content = result.content[0]
            text = content.text if hasattr(content, "text") else str(content)
            data = json.loads(text)

            assert data["count"] > 1

        await _get_session_and_run(check)

    async def test_bt_search_in_definition(self) -> None:
        """bt_search finds results matching a term."""

        async def check(session: ClientSession):
            result = await session.call_tool(
                name="bt_search", arguments={"term": "warrior"}
            )
            content = result.content[0]
            text = content.text if hasattr(content, "text") else str(content)
            data = json.loads(text)

            assert data["count"] >= 1

        await _get_session_and_run(check)

    async def test_bt_search_with_column(self) -> None:
        """bt_search with column param restricts search to that column."""

        async def check(session: ClientSession):
            result = await session.call_tool(
                name="bt_search",
                arguments={"term": "king", "column": "definition"},
            )
            content = result.content[0]
            text = content.text if hasattr(content, "text") else str(content)
            data = json.loads(text)

            assert data["count"] >= 1

        await _get_session_and_run(check)
