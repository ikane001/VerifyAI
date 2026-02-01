"""OpenAPI specification parser."""

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class APIParameter:
    """API parameter definition."""

    name: str
    location: str  # path, query, header, cookie
    required: bool = False
    param_type: str = "string"
    description: str = ""


@dataclass
class APIEndpoint:
    """API endpoint definition."""

    path: str
    method: str
    operation_id: str | None = None
    summary: str = ""
    description: str = ""
    parameters: list[APIParameter] = field(default_factory=list)
    request_body: dict | None = None
    responses: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        """Get a descriptive name for this endpoint."""
        if self.operation_id:
            return self.operation_id
        return f"{self.method.upper()} {self.path}"


class OpenAPIParser:
    """Parser for OpenAPI/Swagger specifications."""

    def __init__(self, spec_path: Path | None = None, spec_data: dict | None = None):
        """Initialize parser with spec file path or data.

        Args:
            spec_path: Path to OpenAPI spec file (YAML or JSON)
            spec_data: Direct spec data as dictionary
        """
        if spec_path:
            self.spec = self._load_spec(spec_path)
        elif spec_data:
            self.spec = spec_data
        else:
            self.spec = {}

    def _load_spec(self, path: Path) -> dict:
        """Load OpenAPI spec from file."""
        content = path.read_text()
        if path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(content)
        elif path.suffix == ".json":
            return json.loads(content)
        else:
            # Try YAML first, then JSON
            try:
                return yaml.safe_load(content)
            except yaml.YAMLError:
                return json.loads(content)

    @property
    def title(self) -> str:
        """Get API title."""
        return self.spec.get("info", {}).get("title", "Unknown API")

    @property
    def version(self) -> str:
        """Get API version."""
        return self.spec.get("info", {}).get("version", "0.0.0")

    @property
    def base_url(self) -> str:
        """Get base URL for the API."""
        servers = self.spec.get("servers", [])
        if servers:
            return servers[0].get("url", "")
        return ""

    def get_endpoints(self) -> list[APIEndpoint]:
        """Extract all API endpoints from the spec."""
        endpoints = []
        paths = self.spec.get("paths", {})

        for path, path_item in paths.items():
            for method in ["get", "post", "put", "patch", "delete", "options", "head"]:
                if method not in path_item:
                    continue

                operation = path_item[method]
                endpoint = APIEndpoint(
                    path=path,
                    method=method,
                    operation_id=operation.get("operationId"),
                    summary=operation.get("summary", ""),
                    description=operation.get("description", ""),
                    parameters=self._parse_parameters(operation.get("parameters", [])),
                    request_body=operation.get("requestBody"),
                    responses=operation.get("responses", {}),
                    tags=operation.get("tags", []),
                )
                endpoints.append(endpoint)

        return endpoints

    def _parse_parameters(self, params: list) -> list[APIParameter]:
        """Parse parameter definitions."""
        result = []
        for param in params:
            schema = param.get("schema", {})
            result.append(
                APIParameter(
                    name=param.get("name", ""),
                    location=param.get("in", "query"),
                    required=param.get("required", False),
                    param_type=schema.get("type", "string"),
                    description=param.get("description", ""),
                )
            )
        return result

    def get_schemas(self) -> dict:
        """Get all schema definitions."""
        components = self.spec.get("components", {})
        return components.get("schemas", {})

    def to_summary(self) -> str:
        """Generate a summary of the API for LLM context."""
        endpoints = self.get_endpoints()
        lines = [
            f"API: {self.title} v{self.version}",
            f"Base URL: {self.base_url}",
            f"Endpoints: {len(endpoints)}",
            "",
            "Endpoint List:",
        ]

        for ep in endpoints:
            params = ", ".join([p.name for p in ep.parameters])
            lines.append(f"  - {ep.method.upper()} {ep.path}")
            if ep.summary:
                lines.append(f"    Summary: {ep.summary}")
            if params:
                lines.append(f"    Params: {params}")

        return "\n".join(lines)


def find_openapi_spec(project_path: Path) -> Path | None:
    """Find OpenAPI spec file in project.

    Looks for common OpenAPI spec file names.
    """
    spec_patterns = [
        "openapi.yaml",
        "openapi.yml",
        "openapi.json",
        "swagger.yaml",
        "swagger.yml",
        "swagger.json",
        "api-spec.yaml",
        "api-spec.yml",
        "api-spec.json",
        "docs/openapi.yaml",
        "docs/openapi.yml",
        "api/openapi.yaml",
        "spec/openapi.yaml",
    ]

    for pattern in spec_patterns:
        spec_file = project_path / pattern
        if spec_file.exists():
            return spec_file

    return None
