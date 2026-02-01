"""Tests for MCP server."""

from pathlib import Path

import pytest

from verify_ai.mcp import MCPServer, create_mcp_server
from verify_ai.mcp.server import handle_mcp_request


@pytest.fixture
def server():
    """Create MCP server."""
    return create_mcp_server(project_path=Path(__file__).parent.parent)


class TestMCPServer:
    """Tests for MCPServer."""

    def test_create_server(self, server):
        """Test server creation."""
        assert server is not None
        assert isinstance(server, MCPServer)

    def test_get_tools(self, server):
        """Test getting available tools."""
        tools = server.get_tools()
        assert len(tools) >= 5

        tool_names = [t["name"] for t in tools]
        assert "vai_scan" in tool_names
        assert "vai_generate" in tool_names
        assert "vai_verify" in tool_names

    def test_get_resources(self, server):
        """Test getting available resources."""
        resources = server.get_resources()
        assert len(resources) >= 2

        uris = [r["uri"] for r in resources]
        assert "vai://config" in uris
        assert "vai://scan-result" in uris

    @pytest.mark.asyncio
    async def test_call_scan_tool(self, server):
        """Test calling scan tool."""
        result = await server.call_tool("vai_scan", {"path": "."})

        assert "content" in result
        content = result["content"]
        assert "project" in content
        assert "languages" in content
        assert "functions" in content

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self, server):
        """Test calling unknown tool."""
        result = await server.call_tool("unknown_tool", {})

        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_call_diff_tool(self, server):
        """Test calling diff tool."""
        result = await server.call_tool("vai_diff", {
            "path": ".",
            "from_ref": "HEAD~1",
            "to_ref": "HEAD",
        })

        assert "content" in result
        content = result["content"]
        assert "files" in content

    @pytest.mark.asyncio
    async def test_call_verify_tool(self, server):
        """Test calling verify tool."""
        result = await server.call_tool("vai_verify", {
            "path": ".",
            "trigger": "pr",
        })

        assert "content" in result
        content = result["content"]
        assert content["trigger"] == "pr"
        assert "level" in content
        assert "config" in content


class TestMCPProtocol:
    """Tests for MCP protocol handling."""

    @pytest.mark.asyncio
    async def test_initialize(self, server):
        """Test initialize request."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        }

        response = await handle_mcp_request(request, server)

        assert response["id"] == 1
        assert "result" in response
        assert "capabilities" in response["result"]
        assert "serverInfo" in response["result"]

    @pytest.mark.asyncio
    async def test_tools_list(self, server):
        """Test tools/list request."""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }

        response = await handle_mcp_request(request, server)

        assert response["id"] == 2
        assert "result" in response
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) >= 5

    @pytest.mark.asyncio
    async def test_tools_call(self, server):
        """Test tools/call request."""
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "vai_scan",
                "arguments": {"path": "."},
            },
        }

        response = await handle_mcp_request(request, server)

        assert response["id"] == 3
        assert "result" in response

    @pytest.mark.asyncio
    async def test_resources_list(self, server):
        """Test resources/list request."""
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/list",
            "params": {},
        }

        response = await handle_mcp_request(request, server)

        assert response["id"] == 4
        assert "result" in response
        assert "resources" in response["result"]

    @pytest.mark.asyncio
    async def test_unknown_method(self, server):
        """Test unknown method."""
        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "unknown/method",
            "params": {},
        }

        response = await handle_mcp_request(request, server)

        assert response["id"] == 5
        assert "error" in response
        assert response["error"]["code"] == -32601
