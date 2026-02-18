"""Tests for the Beowulf MCP server."""

import json
import logging
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Suppress INFO logs from mcp.server
logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)

# we need a path to proj root to use as working dir for server
PROJECT_ROOT = Path(__file__).parents[1]


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def mcp_session() -> AsyncGenerator[ClientSession, None]:
    """Single MCP server session shared by all tests in this module."""
    server_params = StdioServerParameters(
        cwd=PROJECT_ROOT,
        command="poetry",
        args=["run", "python", "beowulf_mcp/server.py"],
    )
    # Manually manage context managers so we can suppress the anyio
    # cancel-scope task-mismatch error during teardown (a known issue
    # with module-scoped async fixtures in pytest-asyncio).
    client_cm = stdio_client(server_params)
    read, write = await client_cm.__aenter__()
    session_cm = ClientSession(read, write)
    session = await session_cm.__aenter__()
    await session.initialize()

    yield session

    try:
        await session_cm.__aexit__(None, None, None)
    except (RuntimeError, BaseExceptionGroup):
        pass
    try:
        await client_cm.__aexit__(None, None, None)
    except (RuntimeError, BaseExceptionGroup):
        pass


@pytest.mark.asyncio(loop_scope="module")
class TestListTools:
    """Tests for listing available tools."""

    async def test_list_tools_returns_seven_tools(
        self, mcp_session: ClientSession
    ) -> None:
        """Server exposes exactly seven tools."""
        tools = await mcp_session.list_tools()
        assert len(tools.tools) == 7

    async def test_get_beowulf_lines_tool_exists(
        self, mcp_session: ClientSession
    ) -> None:
        """get_beowulf_lines tool is available."""
        tools = await mcp_session.list_tools()
        tool_names = [t.name for t in tools.tools]
        assert "get_beowulf_lines" in tool_names

    async def test_get_beowulf_summary_tool_exists(
        self, mcp_session: ClientSession
    ) -> None:
        """get_beowulf_summary tool is available."""
        tools = await mcp_session.list_tools()
        tool_names = [t.name for t in tools.tools]
        assert "get_beowulf_summary" in tool_names

    async def test_get_fitt_lines_tool_exists(self, mcp_session: ClientSession) -> None:
        """get_fitt_lines tool is available."""
        tools = await mcp_session.list_tools()
        tool_names = [t.name for t in tools.tools]
        assert "get_fitt_lines" in tool_names


@pytest.mark.asyncio(loop_scope="module")
class TestListResources:
    """Tests for listing available resources."""

    async def test_list_resources_returns_two_resources(
        self, mcp_session: ClientSession
    ) -> None:
        """Server exposes exactly two resources."""
        resources = await mcp_session.list_resources()
        assert len(resources.resources) == 2

    async def test_all_lines_resource_exists(self, mcp_session: ClientSession) -> None:
        """beowulf://text/all resource is available."""
        resources = await mcp_session.list_resources()
        uris = [str(r.uri) for r in resources.resources]
        assert "beowulf://text/all" in uris

    async def test_summary_resource_exists(self, mcp_session: ClientSession) -> None:
        """beowulf://text/summary resource is available."""
        resources = await mcp_session.list_resources()
        uris = [str(r.uri) for r in resources.resources]
        assert "beowulf://text/summary" in uris


@pytest.mark.asyncio(loop_scope="module")
class TestReadResources:
    """Tests for reading resource content."""

    async def test_read_summary_resource(self, mcp_session: ClientSession) -> None:
        """Reading summary resource returns valid JSON with expected fields."""
        result = await mcp_session.read_resource("beowulf://text/summary")
        assert len(result.contents) == 1

        content = result.contents[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert "total_lines" in data
        assert "title_lines" in data
        assert "fitt_titles" in data
        assert data["total_lines"] > 3000

    async def test_read_all_lines_resource(self, mcp_session: ClientSession) -> None:
        """Reading all lines resource returns valid JSON array."""
        result = await mcp_session.read_resource("beowulf://text/all")
        assert len(result.contents) == 1

        content = result.contents[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert isinstance(data, list)
        assert len(data) == 3183


@pytest.mark.asyncio(loop_scope="module")
class TestCallTools:
    """Tests for calling tools."""

    async def test_get_fitt_lines_fitt_1(self, mcp_session: ClientSession) -> None:
        """get_fitt_lines returns correct data for fitt 1."""
        result = await mcp_session.call_tool(
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

    async def test_get_fitt_lines_prologue(self, mcp_session: ClientSession) -> None:
        """get_fitt_lines returns correct data for prologue (fitt 0)."""
        result = await mcp_session.call_tool(
            name="get_fitt_lines", arguments={"fitt_number": 0}
        )

        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["fitt_number"] == 0
        assert data["fitt_name"] == "Prologue"

    async def test_get_beowulf_summary(self, mcp_session: ClientSession) -> None:
        """get_beowulf_summary returns summary data."""
        result = await mcp_session.call_tool(name="get_beowulf_summary", arguments={})

        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert "total_lines" in data
        assert "sample_lines" in data
        assert len(data["sample_lines"]) == 3

    async def test_get_beowulf_lines_from_to(self, mcp_session: ClientSession) -> None:
        """get_beowulf_lines with from/to returns only lines in that range."""
        result = await mcp_session.call_tool(
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

    async def test_get_beowulf_lines_from_only(
        self, mcp_session: ClientSession
    ) -> None:
        """get_beowulf_lines with only from returns lines from that point to end."""
        result = await mcp_session.call_tool(
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

    async def test_get_beowulf_lines_to_only(self, mcp_session: ClientSession) -> None:
        """get_beowulf_lines with only to returns lines from start up to that point."""
        result = await mcp_session.call_tool(
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

    async def test_get_beowulf_lines_single_line(
        self, mcp_session: ClientSession
    ) -> None:
        """get_beowulf_lines with from==to returns exactly one line."""
        result = await mcp_session.call_tool(
            name="get_beowulf_lines",
            arguments={"from": 1757, "to": 1757},
        )

        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] == 1
        assert data["lines"][0]["line_number"] == 1757


@pytest.mark.asyncio(loop_scope="module")
class TestBosworthTools:
    """Tests for Bosworth-Toller dictionary tools."""

    async def test_bt_lookup_tool_exists(self, mcp_session: ClientSession) -> None:
        """bt_lookup tool is available."""
        tools = await mcp_session.list_tools()
        tool_names = [t.name for t in tools.tools]
        assert "bt_lookup" in tool_names

    async def test_bt_lookup_like_tool_exists(self, mcp_session: ClientSession) -> None:
        """bt_lookup_like tool is available."""
        tools = await mcp_session.list_tools()
        tool_names = [t.name for t in tools.tools]
        assert "bt_lookup_like" in tool_names

    async def test_bt_search_tool_exists(self, mcp_session: ClientSession) -> None:
        """bt_search tool is available."""
        tools = await mcp_session.list_tools()
        tool_names = [t.name for t in tools.tools]
        assert "bt_search" in tool_names

    async def test_bt_lookup_finds_word(self, mcp_session: ClientSession) -> None:
        """bt_lookup returns results with expected keys for a known OE word."""
        result = await mcp_session.call_tool(
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

    async def test_bt_lookup_no_match(self, mcp_session: ClientSession) -> None:
        """bt_lookup returns empty results for gibberish."""
        result = await mcp_session.call_tool(
            name="bt_lookup", arguments={"word": "xyzzyplugh"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] == 0
        assert data["results"] == []

    async def test_bt_lookup_like_prefix(self, mcp_session: ClientSession) -> None:
        """bt_lookup_like with a prefix pattern returns multiple results."""
        result = await mcp_session.call_tool(
            name="bt_lookup_like", arguments={"pattern": "cyn%"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] > 1

    async def test_bt_search_in_definition(self, mcp_session: ClientSession) -> None:
        """bt_search finds results matching a term."""
        result = await mcp_session.call_tool(
            name="bt_search", arguments={"term": "warrior"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1

    async def test_bt_search_with_column(self, mcp_session: ClientSession) -> None:
        """bt_search with column param restricts search to that column."""
        result = await mcp_session.call_tool(
            name="bt_search",
            arguments={"term": "king", "column": "definition"},
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1


@pytest.mark.asyncio(loop_scope="module")
class TestAbbreviationTools:
    """Tests for Bosworth-Toller abbreviation tools."""

    async def test_bt_abbreviation_tool_exists(
        self, mcp_session: ClientSession
    ) -> None:
        """bt_abbreviation tool is available."""
        tools = await mcp_session.list_tools()
        tool_names = [t.name for t in tools.tools]
        assert "bt_abbreviation" in tool_names

    async def test_bt_abbreviation_finds_match(
        self, mcp_session: ClientSession
    ) -> None:
        """bt_abbreviation returns results for a known abbreviation."""
        result = await mcp_session.call_tool(
            name="bt_abbreviation", arguments={"abbrev": "Beo."}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1
        entry = data["results"][0]
        assert "abbreviation" in entry
        assert "expansion" in entry
        assert "description" in entry

    async def test_bt_abbreviation_no_match(self, mcp_session: ClientSession) -> None:
        """bt_abbreviation returns empty results for gibberish."""
        result = await mcp_session.call_tool(
            name="bt_abbreviation", arguments={"abbrev": "xyzzyplugh"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] == 0
        assert data["results"] == []

    async def test_bt_abbreviation_returns_description(
        self, mcp_session: ClientSession
    ) -> None:
        """bt_abbreviation results for 'Beo.' mention Beowulf in description."""
        result = await mcp_session.call_tool(
            name="bt_abbreviation", arguments={"abbrev": "Beo."}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert any("Beowulf" in r["description"] for r in data["results"])
