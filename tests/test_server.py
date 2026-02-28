"""Tests for the Beowulf MCP server."""

import json
import logging
import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Suppress INFO logs from mcp.server
logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def mcp_session(
    project_root: Path, tmp_path_factory: pytest.TempPathFactory
) -> AsyncGenerator[ClientSession, None]:
    """Single MCP server session shared by all tests in this module."""
    # Give the test server its own DuckDB file so it doesn't collide
    # with a running MCP server's lock on output/beodb.duckdb.
    test_db = tmp_path_factory.mktemp("server") / "test_beodb.duckdb"
    env = {**os.environ, "DB_PATH": str(test_db)}
    server_params = StdioServerParameters(
        cwd=project_root,
        command="poetry",
        args=["run", "python", "beowulf_mcp/server.py"],
        env=env,
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

    async def test_list_tools_returns_all_tools(
        self, mcp_session: ClientSession
    ) -> None:
        """Server exposes exactly 37 tools (22 static + 15 edition-generated)."""
        tools = await mcp_session.list_tools()
        assert len(tools.tools) == 37

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

    async def test_list_resources_returns_expected_count(
        self, mcp_session: ClientSession
    ) -> None:
        """Server exposes 7 resources (6 editions + brunetti)."""
        resources = await mcp_session.list_resources()
        assert len(resources.resources) == 7

    async def test_edition_resources_exist(self, mcp_session: ClientSession) -> None:
        """All six text edition resources are listed."""
        resources = await mcp_session.list_resources()
        uris = [str(r.uri) for r in resources.resources]
        for key in (
            "ebeowulf",
            "heorot",
            "mcmaster",
            "mit",
            "perseus",
            "oldenglishaerobics",
        ):
            assert f"beowulf://text/{key}" in uris

    async def test_brunetti_resource_exists(self, mcp_session: ClientSession) -> None:
        """beowulf://text/brunetti resource is available."""
        resources = await mcp_session.list_resources()
        uris = [str(r.uri) for r in resources.resources]
        assert "beowulf://text/brunetti" in uris


@pytest.mark.asyncio(loop_scope="module")
class TestReadResources:
    """Tests for reading edition resource content."""

    async def test_read_ebeowulf_line(self, mcp_session: ClientSession) -> None:
        """Reading a single ebeowulf line returns valid JSON."""
        result = await mcp_session.read_resource("beowulf://text/ebeowulf/line/1")
        assert len(result.contents) == 1

        content = result.contents[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert isinstance(data, list)
        assert len(data) == 1

    async def test_read_heorot_line_range(self, mcp_session: ClientSession) -> None:
        """Reading a heorot line range returns multiple lines."""
        result = await mcp_session.read_resource("beowulf://text/heorot/line/1/5")
        assert len(result.contents) == 1

        content = result.contents[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert isinstance(data, list)
        assert len(data) >= 5


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


@pytest.mark.asyncio(loop_scope="module")
class TestBrunettiTools:
    """Tests for Brunetti tokenized Beowulf tools."""

    async def test_brunetti_lookup_tool_exists(
        self, mcp_session: ClientSession
    ) -> None:
        """brunetti_lookup tool is available."""
        tools = await mcp_session.list_tools()
        tool_names = [t.name for t in tools.tools]
        assert "brunetti_lookup" in tool_names

    async def test_brunetti_lookup_like_tool_exists(
        self, mcp_session: ClientSession
    ) -> None:
        """brunetti_lookup_like tool is available."""
        tools = await mcp_session.list_tools()
        tool_names = [t.name for t in tools.tools]
        assert "brunetti_lookup_like" in tool_names

    async def test_brunetti_search_tool_exists(
        self, mcp_session: ClientSession
    ) -> None:
        """brunetti_search tool is available."""
        tools = await mcp_session.list_tools()
        tool_names = [t.name for t in tools.tools]
        assert "brunetti_search" in tool_names

    async def test_brunetti_lookup_finds_lemma(
        self, mcp_session: ClientSession
    ) -> None:
        """brunetti_lookup returns results for a known OE lemma."""
        result = await mcp_session.call_tool(
            name="brunetti_lookup", arguments={"lemma": "cyning"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1
        entry = data["results"][0]
        assert "lemma" in entry
        assert "text" in entry
        assert "gloss" in entry

    async def test_brunetti_lookup_no_match(self, mcp_session: ClientSession) -> None:
        """brunetti_lookup returns empty results for gibberish."""
        result = await mcp_session.call_tool(
            name="brunetti_lookup", arguments={"lemma": "xyzzyplugh"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] == 0
        assert data["results"] == []

    async def test_brunetti_lookup_like_prefix(
        self, mcp_session: ClientSession
    ) -> None:
        """brunetti_lookup_like with a prefix pattern returns results."""
        result = await mcp_session.call_tool(
            name="brunetti_lookup_like", arguments={"pattern": "cyn%"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1

    async def test_brunetti_search_in_gloss(self, mcp_session: ClientSession) -> None:
        """brunetti_search finds results matching a gloss term."""
        result = await mcp_session.call_tool(
            name="brunetti_search", arguments={"term": "king"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1

    async def test_brunetti_search_with_column(
        self, mcp_session: ClientSession
    ) -> None:
        """brunetti_search with column param restricts search to that column."""
        result = await mcp_session.call_tool(
            name="brunetti_search",
            arguments={"term": "warrior", "column": "gloss"},
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1

    async def test_brunetti_get_by_line(self, mcp_session: ClientSession) -> None:
        """brunetti_get_by_line returns tokens for a known line."""
        result = await mcp_session.call_tool(
            name="brunetti_get_by_line", arguments={"line_id": "0001"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1
        assert "results" in data

    async def test_brunetti_get_by_fitt(self, mcp_session: ClientSession) -> None:
        """brunetti_get_by_fitt returns tokens for a known fitt."""
        result = await mcp_session.call_tool(
            name="brunetti_get_by_fitt", arguments={"fitt_id": "01"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1
        assert "results" in data


@pytest.mark.asyncio(loop_scope="module")
class TestHeorotSearch:
    """Tests for the heorot_search tool."""

    async def test_heorot_search_both_languages(
        self, mcp_session: ClientSession
    ) -> None:
        """heorot_search without language param searches both OE and ME."""
        result = await mcp_session.call_tool(
            name="heorot_search", arguments={"term": "Beowulf"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1

    async def test_heorot_search_oe_only(self, mcp_session: ClientSession) -> None:
        """heorot_search with language='oe' restricts to Old English."""
        result = await mcp_session.call_tool(
            name="heorot_search",
            arguments={"term": "Beowulf", "language": "oe"},
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1

    async def test_heorot_search_me_only(self, mcp_session: ClientSession) -> None:
        """heorot_search with language='me' restricts to Modern English."""
        result = await mcp_session.call_tool(
            name="heorot_search",
            arguments={"term": "warrior", "language": "me"},
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1


@pytest.mark.asyncio(loop_scope="module")
class TestLexiconTools:
    """Tests for the Analytical Lexicon tools."""

    async def test_lexicon_lookup_finds_word(self, mcp_session: ClientSession) -> None:
        """lexicon_lookup returns results for a known headword."""
        result = await mcp_session.call_tool(
            name="lexicon_lookup", arguments={"headword": "cyning"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1

    async def test_lexicon_lookup_no_match(self, mcp_session: ClientSession) -> None:
        """lexicon_lookup returns empty results for gibberish."""
        result = await mcp_session.call_tool(
            name="lexicon_lookup", arguments={"headword": "xyzzyplugh"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] == 0

    async def test_lexicon_lookup_like_prefix(self, mcp_session: ClientSession) -> None:
        """lexicon_lookup_like with a prefix pattern returns results."""
        result = await mcp_session.call_tool(
            name="lexicon_lookup_like", arguments={"pattern": "cyn%"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1

    async def test_lexicon_search(self, mcp_session: ClientSession) -> None:
        """lexicon_search finds results for a term."""
        result = await mcp_session.call_tool(
            name="lexicon_search", arguments={"term": "cyning"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1


@pytest.mark.asyncio(loop_scope="module")
class TestEditionTools:
    """Tests for text edition tools (eBeowulf, Perseus, MIT, McMaster, OE Aerobics)."""

    async def test_all_edition_tools_exist(self, mcp_session: ClientSession) -> None:
        """All 15 edition tools are listed."""
        tools = await mcp_session.list_tools()
        tool_names = {t.name for t in tools.tools}
        for prefix in ("ebeowulf", "perseus", "mit", "mcmaster", "oea"):
            assert f"{prefix}_get_line" in tool_names
            assert f"{prefix}_get_lines" in tool_names
            assert f"{prefix}_search" in tool_names

    async def test_ebeowulf_get_line(self, mcp_session: ClientSession) -> None:
        """ebeowulf_get_line returns data for a valid line number."""
        result = await mcp_session.call_tool(
            name="ebeowulf_get_line", arguments={"line_number": 1}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["found"] is True
        assert data["result"] is not None

    async def test_ebeowulf_get_lines_range(self, mcp_session: ClientSession) -> None:
        """ebeowulf_get_lines returns a range of lines."""
        result = await mcp_session.call_tool(
            name="ebeowulf_get_lines", arguments={"start": 1, "end": 5}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1

    async def test_ebeowulf_search(self, mcp_session: ClientSession) -> None:
        """ebeowulf_search finds lines containing the term."""
        result = await mcp_session.call_tool(
            name="ebeowulf_search", arguments={"term": "Beowulf"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1

    async def test_perseus_get_line(self, mcp_session: ClientSession) -> None:
        """perseus_get_line returns data for a valid line number."""
        result = await mcp_session.call_tool(
            name="perseus_get_line", arguments={"line_number": 1}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["found"] is True

    async def test_mit_search(self, mcp_session: ClientSession) -> None:
        """mit_search finds results."""
        result = await mcp_session.call_tool(
            name="mit_search", arguments={"term": "Beowulf"}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["count"] >= 1

    async def test_mcmaster_get_line(self, mcp_session: ClientSession) -> None:
        """mcmaster_get_line returns data for a valid line number."""
        result = await mcp_session.call_tool(
            name="mcmaster_get_line", arguments={"line_number": 1}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["found"] is True

    async def test_oea_get_line(self, mcp_session: ClientSession) -> None:
        """oea_get_line returns data for a valid line number."""
        result = await mcp_session.call_tool(
            name="oea_get_line", arguments={"line_number": 1}
        )
        content = result.content[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert data["found"] is True


@pytest.mark.asyncio(loop_scope="module")
class TestBrunettiResources:
    """Tests for Brunetti resource templates and static resource."""

    async def test_brunetti_all_resource_exists(
        self, mcp_session: ClientSession
    ) -> None:
        """beowulf://text/brunetti resource is listed."""
        resources = await mcp_session.list_resources()
        uris = [str(r.uri) for r in resources.resources]
        assert "beowulf://text/brunetti" in uris

    async def test_brunetti_templates_listed(self, mcp_session: ClientSession) -> None:
        """Brunetti resource templates are present among all templates."""
        templates = await mcp_session.list_resource_templates()
        # 6 editions × 2 (line + line range) + 3 brunetti = 15
        assert len(templates.resourceTemplates) == 15
        uri_templates = [t.uriTemplate for t in templates.resourceTemplates]
        assert "beowulf://text/brunetti/fitt/{fitt_id}" in uri_templates
        assert "beowulf://text/brunetti/line/{line_id}" in uri_templates
        assert "beowulf://text/brunetti/line/{from}/{to}" in uri_templates

    async def test_read_brunetti_all(self, mcp_session: ClientSession) -> None:
        """Reading beowulf://text/brunetti returns a non-empty JSON array."""
        result = await mcp_session.read_resource("beowulf://text/brunetti")
        assert len(result.contents) == 1

        content = result.contents[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert isinstance(data, list)
        assert len(data) > 0

    async def test_read_brunetti_fitt(self, mcp_session: ClientSession) -> None:
        """Reading brunetti fitt 1 returns tokens."""
        result = await mcp_session.read_resource("beowulf://text/brunetti/fitt/1")
        assert len(result.contents) == 1

        content = result.contents[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert isinstance(data, list)
        assert len(data) > 0
        assert all(entry["fitt_id"] == "01" for entry in data)

    async def test_read_brunetti_line(self, mcp_session: ClientSession) -> None:
        """Reading brunetti line 1 returns tokens."""
        result = await mcp_session.read_resource("beowulf://text/brunetti/line/1")
        assert len(result.contents) == 1

        content = result.contents[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert isinstance(data, list)
        assert len(data) > 0
        assert all(entry["line_id"] == "0001" for entry in data)

    async def test_read_brunetti_line_range(self, mcp_session: ClientSession) -> None:
        """Reading brunetti lines 1-5 returns tokens from multiple lines."""
        result = await mcp_session.read_resource("beowulf://text/brunetti/line/1/5")
        assert len(result.contents) == 1

        content = result.contents[0]
        text = content.text if hasattr(content, "text") else str(content)
        data = json.loads(text)

        assert isinstance(data, list)
        assert len(data) > 0
        line_ids = {entry["line_id"] for entry in data}
        assert len(line_ids) > 1
        assert all(lid in {"0001", "0002", "0003", "0004", "0005"} for lid in line_ids)
