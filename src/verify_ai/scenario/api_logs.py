"""API log parsing for test generation."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Any
import json
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class APILogEntry:
    """A single API request/response log entry."""

    # Request
    method: str
    path: str
    query_params: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body: Any = None

    # Response
    status_code: int = 200
    response_body: Any = None
    response_headers: dict[str, str] = field(default_factory=dict)

    # Metadata
    timestamp: datetime | None = None
    duration_ms: float | None = None
    client_ip: str | None = None
    user_id: str | None = None

    @property
    def full_path(self) -> str:
        """Get path with query string."""
        if self.query_params:
            qs = "&".join(f"{k}={v}" for k, v in self.query_params.items())
            return f"{self.path}?{qs}"
        return self.path

    @property
    def is_success(self) -> bool:
        """Check if response was successful."""
        return 200 <= self.status_code < 400

    @property
    def is_json_request(self) -> bool:
        """Check if request body is JSON."""
        content_type = self.headers.get("content-type", "").lower()
        return "json" in content_type

    def to_test_case(self, base_url: str = "http://localhost:8000") -> str:
        """Generate a pytest test case from this log entry.

        Args:
            base_url: Base URL for the API

        Returns:
            Python test code
        """
        # Sanitize path for test name
        test_name = re.sub(r"[^a-zA-Z0-9]", "_", self.path.strip("/"))
        test_name = f"test_{self.method.lower()}_{test_name}"

        # Build request kwargs
        kwargs = []
        if self.headers:
            # Filter out common headers
            headers = {k: v for k, v in self.headers.items()
                      if k.lower() not in ("host", "content-length", "connection")}
            if headers:
                kwargs.append(f"headers={headers!r}")

        if self.body:
            if self.is_json_request:
                kwargs.append(f"json={self.body!r}")
            else:
                kwargs.append(f"content={self.body!r}")

        if self.query_params:
            kwargs.append(f"params={self.query_params!r}")

        kwargs_str = ", ".join(kwargs)

        # Build test code
        code = f'''
def {test_name}(client):
    """Test {self.method} {self.path} - generated from API log."""
    response = client.{self.method.lower()}(
        "{self.path}",
        {kwargs_str}
    )

    assert response.status_code == {self.status_code}
'''

        # Add response body assertion if available
        if self.response_body and isinstance(self.response_body, dict):
            # Only check key fields
            if len(self.response_body) <= 5:
                code += f'''
    data = response.json()
    # Verify response structure
'''
                for key in list(self.response_body.keys())[:3]:
                    code += f'    assert "{key}" in data\n'

        return code.strip()


class APILogParser:
    """Parse various API log formats."""

    def __init__(self, log_format: Literal["nginx", "json", "combined", "auto"] = "auto"):
        """Initialize parser.

        Args:
            log_format: Expected log format
        """
        self.log_format = log_format

    def parse_file(self, file_path: Path) -> list[APILogEntry]:
        """Parse a log file.

        Args:
            file_path: Path to log file

        Returns:
            List of parsed log entries
        """
        content = file_path.read_text()

        if self.log_format == "auto":
            # Try to detect format
            if content.strip().startswith("{"):
                return parse_json_log(content)
            else:
                return parse_nginx_log(content)

        elif self.log_format == "json":
            return parse_json_log(content)

        elif self.log_format in ("nginx", "combined"):
            return parse_nginx_log(content)

        return []

    def parse_lines(self, lines: list[str]) -> list[APILogEntry]:
        """Parse log lines.

        Args:
            lines: List of log lines

        Returns:
            List of parsed log entries
        """
        entries = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                if line.startswith("{"):
                    entry = self._parse_json_line(line)
                else:
                    entry = self._parse_nginx_line(line)

                if entry:
                    entries.append(entry)

            except Exception as e:
                logger.debug(f"Failed to parse line: {e}")
                continue

        return entries

    def _parse_json_line(self, line: str) -> APILogEntry | None:
        """Parse a JSON log line."""
        try:
            data = json.loads(line)

            return APILogEntry(
                method=data.get("method", "GET"),
                path=data.get("path", data.get("url", "/")),
                query_params=data.get("query", {}),
                headers=data.get("headers", {}),
                body=data.get("body", data.get("request_body")),
                status_code=data.get("status", data.get("status_code", 200)),
                response_body=data.get("response", data.get("response_body")),
                duration_ms=data.get("duration", data.get("duration_ms")),
                client_ip=data.get("client_ip", data.get("remote_addr")),
                timestamp=self._parse_timestamp(data.get("timestamp", data.get("time"))),
            )

        except json.JSONDecodeError:
            return None

    def _parse_nginx_line(self, line: str) -> APILogEntry | None:
        """Parse a nginx/combined log line."""
        # Combined log format:
        # 127.0.0.1 - - [10/Oct/2024:13:55:36 +0000] "GET /api/users HTTP/1.1" 200 1234 "-" "curl/7.64.1"
        pattern = r'^(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+) \S+" (\d+) (\d+)'

        match = re.match(pattern, line)
        if not match:
            return None

        client_ip, timestamp_str, method, path, status, size = match.groups()

        # Parse path and query
        if "?" in path:
            path, query_string = path.split("?", 1)
            query_params = dict(p.split("=", 1) for p in query_string.split("&") if "=" in p)
        else:
            query_params = {}

        return APILogEntry(
            method=method,
            path=path,
            query_params=query_params,
            status_code=int(status),
            client_ip=client_ip,
            timestamp=self._parse_nginx_timestamp(timestamp_str),
        )

    def _parse_timestamp(self, ts: str | None) -> datetime | None:
        """Parse various timestamp formats."""
        if not ts:
            return None

        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(ts, fmt)
            except ValueError:
                continue

        return None

    def _parse_nginx_timestamp(self, ts: str) -> datetime | None:
        """Parse nginx timestamp format."""
        try:
            # Format: 10/Oct/2024:13:55:36 +0000
            return datetime.strptime(ts.split()[0], "%d/%b/%Y:%H:%M:%S")
        except ValueError:
            return None


def parse_nginx_log(content: str) -> list[APILogEntry]:
    """Parse nginx/combined log format.

    Args:
        content: Log file content

    Returns:
        List of API log entries
    """
    parser = APILogParser(log_format="nginx")
    return parser.parse_lines(content.split("\n"))


def parse_json_log(content: str) -> list[APILogEntry]:
    """Parse JSON log format (one JSON object per line).

    Args:
        content: Log file content

    Returns:
        List of API log entries
    """
    parser = APILogParser(log_format="json")
    return parser.parse_lines(content.split("\n"))


def generate_tests_from_logs(
    entries: list[APILogEntry],
    base_url: str = "http://localhost:8000",
    group_by_path: bool = True,
) -> str:
    """Generate pytest tests from API log entries.

    Args:
        entries: List of API log entries
        base_url: Base URL for tests
        group_by_path: Group tests by API path

    Returns:
        Generated test code
    """
    header = '''"""Generated API tests from logs."""

import pytest
from httpx import Client


@pytest.fixture
def client():
    """Create HTTP client."""
    with Client(base_url="{base_url}") as client:
        yield client

'''.format(base_url=base_url)

    tests = []
    seen_tests = set()

    for entry in entries:
        test_code = entry.to_test_case(base_url)

        # Avoid duplicate tests
        test_signature = f"{entry.method}_{entry.path}_{entry.status_code}"
        if test_signature in seen_tests:
            continue
        seen_tests.add(test_signature)

        tests.append(test_code)

    return header + "\n\n".join(tests)
