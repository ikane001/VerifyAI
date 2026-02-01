"""MCP Server implementation for VerifyAI.

Exposes VerifyAI functionality through the Model Context Protocol,
allowing AI assistants to interact with the verification system.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """Definition of an MCP tool."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable


@dataclass
class MCPResource:
    """Definition of an MCP resource."""

    uri: str
    name: str
    description: str
    mime_type: str = "application/json"


class MCPServer:
    """MCP Server for VerifyAI.

    Implements the Model Context Protocol to expose verification
    capabilities to AI assistants.
    """

    def __init__(self, project_path: Path | None = None):
        """Initialize MCP server.

        Args:
            project_path: Default project path for operations
        """
        self.project_path = project_path or Path.cwd()
        self._tools: dict[str, MCPTool] = {}
        self._resources: dict[str, MCPResource] = {}
        self._register_tools()
        self._register_resources()

    def _register_tools(self):
        """Register all available tools."""
        # Scan tool
        self._tools["vai_scan"] = MCPTool(
            name="vai_scan",
            description="Scan a project to analyze its structure, languages, functions, and API endpoints",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the project (default: current directory)",
                    },
                    "verbose": {
                        "type": "boolean",
                        "description": "Include detailed output",
                        "default": False,
                    },
                },
            },
            handler=self._handle_scan,
        )

        # Generate tool
        self._tools["vai_generate"] = MCPTool(
            name="vai_generate",
            description="Generate tests for a project using LLM",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the project",
                    },
                    "test_type": {
                        "type": "string",
                        "enum": ["api", "unit", "all"],
                        "description": "Type of tests to generate",
                        "default": "all",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Show what would be generated without writing",
                        "default": False,
                    },
                },
            },
            handler=self._handle_generate,
        )

        # Verify tool
        self._tools["vai_verify"] = MCPTool(
            name="vai_verify",
            description="Run verification with layered strategy",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the project",
                    },
                    "trigger": {
                        "type": "string",
                        "enum": ["push", "pr", "merge", "scheduled", "manual"],
                        "description": "Verification trigger type",
                        "default": "manual",
                    },
                    "base_branch": {
                        "type": "string",
                        "description": "Base branch for comparison",
                        "default": "main",
                    },
                },
            },
            handler=self._handle_verify,
        )

        # Diff tool
        self._tools["vai_diff"] = MCPTool(
            name="vai_diff",
            description="Show git changes between two references",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the project",
                    },
                    "from_ref": {
                        "type": "string",
                        "description": "Starting reference",
                        "default": "HEAD~1",
                    },
                    "to_ref": {
                        "type": "string",
                        "description": "Ending reference",
                        "default": "HEAD",
                    },
                },
            },
            handler=self._handle_diff,
        )

        # Analyze tool
        self._tools["vai_analyze"] = MCPTool(
            name="vai_analyze",
            description="Analyze test failures and suggest fixes",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the project",
                    },
                    "test_output": {
                        "type": "string",
                        "description": "Path to pytest output file",
                    },
                },
            },
            handler=self._handle_analyze,
        )

        # Replay tool
        self._tools["vai_replay"] = MCPTool(
            name="vai_replay",
            description="Generate tests from logs (HAR, API logs, error logs)",
            parameters={
                "type": "object",
                "properties": {
                    "log_file": {
                        "type": "string",
                        "description": "Path to log file",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["auto", "har", "json", "nginx", "error"],
                        "description": "Log format",
                        "default": "auto",
                    },
                    "base_url": {
                        "type": "string",
                        "description": "Base URL for generated tests",
                        "default": "http://localhost:8000",
                    },
                },
                "required": ["log_file"],
            },
            handler=self._handle_replay,
        )

    def _register_resources(self):
        """Register available resources."""
        self._resources["vai://config"] = MCPResource(
            uri="vai://config",
            name="VerifyAI Configuration",
            description="Current project configuration (verify-ai.yaml)",
        )

        self._resources["vai://scan-result"] = MCPResource(
            uri="vai://scan-result",
            name="Last Scan Result",
            description="Results from the last project scan",
        )

        self._resources["vai://test-report"] = MCPResource(
            uri="vai://test-report",
            name="Test Report",
            description="Latest test execution report",
        )

    def get_tools(self) -> list[dict]:
        """Get list of available tools in MCP format.

        Returns:
            List of tool definitions
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.parameters,
            }
            for tool in self._tools.values()
        ]

    def get_resources(self) -> list[dict]:
        """Get list of available resources in MCP format.

        Returns:
            List of resource definitions
        """
        return [
            {
                "uri": res.uri,
                "name": res.name,
                "description": res.description,
                "mimeType": res.mime_type,
            }
            for res in self._resources.values()
        ]

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Call a tool by name.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result
        """
        if name not in self._tools:
            return {"error": f"Unknown tool: {name}"}

        try:
            result = await self._tools[name].handler(arguments)
            return {"content": result}
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            return {"error": str(e)}

    async def read_resource(self, uri: str) -> dict:
        """Read a resource by URI.

        Args:
            uri: Resource URI

        Returns:
            Resource content
        """
        if uri not in self._resources:
            return {"error": f"Unknown resource: {uri}"}

        try:
            if uri == "vai://config":
                return await self._read_config()
            elif uri == "vai://scan-result":
                return await self._read_scan_result()
            elif uri == "vai://test-report":
                return await self._read_test_report()
            else:
                return {"error": f"Resource not implemented: {uri}"}
        except Exception as e:
            logger.error(f"Failed to read resource {uri}: {e}")
            return {"error": str(e)}

    # Tool handlers

    async def _handle_scan(self, args: dict) -> dict:
        """Handle vai_scan tool call."""
        from ..core.scanner import ProjectScanner

        path = Path(args.get("path", ".")).resolve()
        scanner = ProjectScanner(path)
        info = scanner.scan()

        return {
            "project": info.name,
            "path": str(info.path),
            "languages": info.languages,
            "source_files": len(info.source_files),
            "test_files": len(info.test_files),
            "functions": len(info.functions),
            "classes": len(info.classes),
            "api_endpoints": len(info.api_endpoints),
            "git_branch": info.git_info.current_branch,
            "uses_tree_sitter": info.uses_tree_sitter,
            "summary": info.summary(),
        }

    async def _handle_generate(self, args: dict) -> dict:
        """Handle vai_generate tool call."""
        from ..core.scanner import ProjectScanner
        from ..core.generator import TestGenerator
        from ..config import ProjectConfig

        path = Path(args.get("path", ".")).resolve()
        test_type = args.get("test_type", "all")
        dry_run = args.get("dry_run", False)

        # Scan project
        scanner = ProjectScanner(path)
        info = scanner.scan()

        # Load config
        config = ProjectConfig.find_and_load(path)

        if dry_run:
            return {
                "dry_run": True,
                "would_generate": {
                    "functions": len(info.functions),
                    "api_endpoints": len(info.api_endpoints) if test_type in ("api", "all") else 0,
                },
            }

        # Generate tests
        generator = TestGenerator(config=config)
        tests = []

        if test_type in ("unit", "all"):
            for func in info.functions[:10]:  # Limit for MCP
                if not func.name.startswith("_"):
                    test = await generator.generate_unit_test(func)
                    tests.append(test)

        return {
            "generated": len(tests),
            "test_type": test_type,
        }

    async def _handle_verify(self, args: dict) -> dict:
        """Handle vai_verify tool call."""
        from ..git import GitTracker, get_strategy_for_trigger

        path = Path(args.get("path", ".")).resolve()
        trigger = args.get("trigger", "manual")

        strategy = get_strategy_for_trigger(trigger)
        tracker = GitTracker(path)

        changes = []
        if tracker.is_valid:
            if trigger == "push":
                changes = tracker.get_uncommitted_changes()
            elif trigger in ("pr", "merge"):
                base = args.get("base_branch", "main")
                changes = tracker.get_pr_changes(base_branch=base)

        source_changes = [c for c in changes if c.is_source_file and not c.is_test_file]

        return {
            "trigger": trigger,
            "level": strategy.level.value,
            "config": {
                "verify_changed_files": strategy.config.verify_changed_files,
                "generate_missing_tests": strategy.config.generate_missing_tests,
                "timeout": strategy.config.total_timeout,
            },
            "changed_files": len(source_changes),
            "files": [c.path for c in source_changes[:20]],
        }

    async def _handle_diff(self, args: dict) -> dict:
        """Handle vai_diff tool call."""
        from ..git import GitTracker

        path = Path(args.get("path", ".")).resolve()
        from_ref = args.get("from_ref", "HEAD~1")
        to_ref = args.get("to_ref", "HEAD")

        tracker = GitTracker(path)
        if not tracker.is_valid:
            return {"error": "Not a git repository"}

        changes = tracker.get_changes_between(from_ref, to_ref)

        return {
            "from": from_ref,
            "to": to_ref,
            "total_changes": len(changes),
            "files": [
                {
                    "path": c.path,
                    "type": c.change_type.value,
                    "additions": c.additions,
                    "deletions": c.deletions,
                }
                for c in changes
            ],
        }

    async def _handle_analyze(self, args: dict) -> dict:
        """Handle vai_analyze tool call."""
        from ..analysis import TestAnalyzer, FixGenerator

        path = Path(args.get("path", ".")).resolve()
        test_output = args.get("test_output")

        if test_output:
            output_path = Path(test_output)
            if not output_path.exists():
                return {"error": f"File not found: {test_output}"}
            content = output_path.read_text()
        else:
            return {"error": "test_output is required"}

        analyzer = TestAnalyzer()
        failures = analyzer.parse_pytest_output(content)

        results = []
        for failure in failures:
            analysis = analyzer.analyze_failure(failure)
            results.append({
                "test": failure.test_name,
                "type": failure.failure_type.value,
                "message": failure.error_message[:100],
                "root_cause": analysis.root_cause,
                "confidence": analysis.confidence,
                "fix_target": analysis.fix_type,
            })

        return {
            "total_failures": len(failures),
            "failures": results,
        }

    async def _handle_replay(self, args: dict) -> dict:
        """Handle vai_replay tool call."""
        from ..scenario import APILogParser, HARParser

        log_file = Path(args.get("log_file", ""))
        if not log_file.exists():
            return {"error": f"File not found: {log_file}"}

        fmt = args.get("format", "auto")
        base_url = args.get("base_url", "http://localhost:8000")

        # Detect format
        if fmt == "auto":
            if log_file.suffix == ".har":
                fmt = "har"
            elif log_file.suffix == ".json":
                fmt = "json"
            else:
                fmt = "nginx"

        # Parse
        if fmt == "har":
            parser = HARParser()
            entries = parser.parse_file(log_file)
            return {
                "format": "har",
                "entries": len(entries),
                "api_calls": len([e for e in entries if e.is_api_call]),
            }
        else:
            parser = APILogParser(log_format=fmt)
            entries = parser.parse_file(log_file)
            return {
                "format": fmt,
                "entries": len(entries),
            }

    # Resource handlers

    async def _read_config(self) -> dict:
        """Read project configuration."""
        from ..config import ProjectConfig

        config = ProjectConfig.find_and_load(self.project_path)
        return {
            "name": config.name,
            "languages": config.languages,
            "test_output": config.test_output,
            "llm": {
                "provider": config.llm.provider,
                "model": config.llm.model,
            },
        }

    async def _read_scan_result(self) -> dict:
        """Read last scan result."""
        # In a real implementation, this would cache results
        return await self._handle_scan({"path": str(self.project_path)})

    async def _read_test_report(self) -> dict:
        """Read test report."""
        return {"message": "No test report available"}


def create_mcp_server(project_path: Path | None = None) -> MCPServer:
    """Create an MCP server instance.

    Args:
        project_path: Default project path

    Returns:
        MCPServer instance
    """
    return MCPServer(project_path=project_path)


# MCP Protocol handlers for stdio communication

async def handle_mcp_request(request: dict, server: MCPServer) -> dict:
    """Handle an MCP protocol request.

    Args:
        request: MCP request
        server: MCPServer instance

    Returns:
        MCP response
    """
    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                },
                "serverInfo": {
                    "name": "verify-ai",
                    "version": "0.1.0",
                },
            },
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": server.get_tools()},
        }

    elif method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments", {})
        result = await server.call_tool(name, args)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result,
        }

    elif method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"resources": server.get_resources()},
        }

    elif method == "resources/read":
        uri = params.get("uri", "")
        result = await server.read_resource(uri)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"contents": [result]},
        }

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


async def run_mcp_server():
    """Run MCP server in stdio mode."""
    import sys

    server = create_mcp_server()

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            request = json.loads(line)
            response = await handle_mcp_request(request, server)
            print(json.dumps(response), flush=True)

        except json.JSONDecodeError:
            continue
        except Exception as e:
            logger.error(f"MCP server error: {e}")
            continue
