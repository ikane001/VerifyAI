"""HAR (HTTP Archive) file parsing for browser session replay."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class HAREntry:
    """A single HAR entry (request/response pair)."""

    # Request
    method: str
    url: str
    path: str
    query_params: dict[str, list[str]] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    post_data: Any = None
    mime_type: str = ""

    # Response
    status_code: int = 200
    status_text: str = ""
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body: str = ""
    response_size: int = 0

    # Timing
    started: datetime | None = None
    duration_ms: float = 0

    # Metadata
    page_ref: str = ""
    server_ip: str = ""

    @property
    def host(self) -> str:
        """Get host from URL."""
        parsed = urlparse(self.url)
        return parsed.netloc

    @property
    def is_api_call(self) -> bool:
        """Check if this is likely an API call (not static resource)."""
        # Skip static resources
        static_extensions = {".js", ".css", ".png", ".jpg", ".gif", ".ico", ".svg", ".woff", ".woff2"}
        path_lower = self.path.lower()

        if any(path_lower.endswith(ext) for ext in static_extensions):
            return False

        # Check content type
        content_type = self.response_headers.get("content-type", "").lower()
        if "json" in content_type or "xml" in content_type:
            return True

        # Check path patterns
        api_patterns = ["/api/", "/v1/", "/v2/", "/graphql", "/rest/"]
        return any(p in path_lower for p in api_patterns)

    @property
    def is_success(self) -> bool:
        """Check if response was successful."""
        return 200 <= self.status_code < 400

    def to_test_case(self, test_name_prefix: str = "test") -> str:
        """Generate a pytest test case from this entry.

        Args:
            test_name_prefix: Prefix for test function name

        Returns:
            Python test code
        """
        import re

        # Create test name
        path_slug = re.sub(r"[^a-zA-Z0-9]", "_", self.path.strip("/"))
        path_slug = re.sub(r"_+", "_", path_slug)[:30]
        test_name = f"{test_name_prefix}_{self.method.lower()}_{path_slug}"

        # Build request
        lines = [
            f'def {test_name}(client):',
            f'    """Test {self.method} {self.path}"""',
        ]

        # Build kwargs
        kwargs = []

        # Headers (filter browser-specific ones)
        important_headers = {}
        skip_headers = {"host", "connection", "accept-encoding", "user-agent",
                       "accept-language", "cache-control", "pragma", "content-length"}
        for k, v in self.headers.items():
            if k.lower() not in skip_headers:
                important_headers[k] = v

        if important_headers:
            kwargs.append(f"headers={important_headers!r}")

        # Query params
        if self.query_params:
            # Flatten single-value lists
            params = {k: v[0] if len(v) == 1 else v for k, v in self.query_params.items()}
            kwargs.append(f"params={params!r}")

        # Post data
        if self.post_data:
            if self.mime_type and "json" in self.mime_type:
                try:
                    data = json.loads(self.post_data) if isinstance(self.post_data, str) else self.post_data
                    kwargs.append(f"json={data!r}")
                except json.JSONDecodeError:
                    kwargs.append(f"content={self.post_data!r}")
            else:
                kwargs.append(f"content={self.post_data!r}")

        # Build request line
        kwargs_str = ",\n        ".join(kwargs)
        if kwargs_str:
            lines.append(f'    response = client.{self.method.lower()}(')
            lines.append(f'        "{self.path}",')
            lines.append(f'        {kwargs_str}')
            lines.append('    )')
        else:
            lines.append(f'    response = client.{self.method.lower()}("{self.path}")')

        lines.append('')
        lines.append(f'    assert response.status_code == {self.status_code}')

        # Check response body if JSON
        if self.response_body and "json" in self.response_headers.get("content-type", "").lower():
            try:
                resp_data = json.loads(self.response_body)
                if isinstance(resp_data, dict) and len(resp_data) <= 5:
                    lines.append('    data = response.json()')
                    for key in list(resp_data.keys())[:3]:
                        lines.append(f'    assert "{key}" in data')
            except (json.JSONDecodeError, TypeError):
                pass

        return "\n".join(lines)


class HARParser:
    """Parse HAR (HTTP Archive) files."""

    def __init__(self, filter_api_only: bool = True):
        """Initialize HAR parser.

        Args:
            filter_api_only: Only include API calls (skip static resources)
        """
        self.filter_api_only = filter_api_only

    def parse_file(self, file_path: Path) -> list[HAREntry]:
        """Parse a HAR file.

        Args:
            file_path: Path to HAR file

        Returns:
            List of HAR entries
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            return self.parse_content(content)
        except Exception as e:
            logger.error(f"Failed to parse HAR file {file_path}: {e}")
            return []

    def parse_content(self, content: str) -> list[HAREntry]:
        """Parse HAR content.

        Args:
            content: HAR file content (JSON)

        Returns:
            List of HAR entries
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in HAR content: {e}")
            return []

        if "log" not in data:
            logger.error("Invalid HAR format: missing 'log' key")
            return []

        entries = []
        for entry_data in data["log"].get("entries", []):
            entry = self._parse_entry(entry_data)
            if entry:
                if not self.filter_api_only or entry.is_api_call:
                    entries.append(entry)

        return entries

    def _parse_entry(self, data: dict) -> HAREntry | None:
        """Parse a single HAR entry."""
        try:
            request = data.get("request", {})
            response = data.get("response", {})

            # Parse URL
            url = request.get("url", "")
            parsed = urlparse(url)

            # Parse query params
            query_params = parse_qs(parsed.query)

            # Parse headers
            headers = {}
            for h in request.get("headers", []):
                headers[h["name"]] = h["value"]

            # Parse cookies
            cookies = {}
            for c in request.get("cookies", []):
                cookies[c["name"]] = c["value"]

            # Parse post data
            post_data = None
            post_data_obj = request.get("postData", {})
            if post_data_obj:
                post_data = post_data_obj.get("text", "")
                mime_type = post_data_obj.get("mimeType", "")
            else:
                mime_type = ""

            # Parse response headers
            response_headers = {}
            for h in response.get("headers", []):
                response_headers[h["name"].lower()] = h["value"]

            # Parse response body
            response_content = response.get("content", {})
            response_body = response_content.get("text", "")
            response_size = response_content.get("size", 0)

            # Parse timing
            started = None
            started_str = data.get("startedDateTime")
            if started_str:
                try:
                    # ISO format: 2024-01-15T10:30:00.000Z
                    started = datetime.fromisoformat(started_str.replace("Z", "+00:00"))
                except ValueError:
                    pass

            duration_ms = data.get("time", 0)

            return HAREntry(
                method=request.get("method", "GET"),
                url=url,
                path=parsed.path,
                query_params=query_params,
                headers=headers,
                cookies=cookies,
                post_data=post_data,
                mime_type=mime_type,
                status_code=response.get("status", 200),
                status_text=response.get("statusText", ""),
                response_headers=response_headers,
                response_body=response_body,
                response_size=response_size,
                started=started,
                duration_ms=duration_ms,
                page_ref=data.get("pageref", ""),
                server_ip=data.get("serverIPAddress", ""),
            )

        except Exception as e:
            logger.debug(f"Failed to parse HAR entry: {e}")
            return None

    def group_by_page(self, entries: list[HAREntry]) -> dict[str, list[HAREntry]]:
        """Group entries by page reference.

        Args:
            entries: List of HAR entries

        Returns:
            Dictionary mapping page refs to entries
        """
        groups: dict[str, list[HAREntry]] = {}
        for entry in entries:
            page = entry.page_ref or "default"
            if page not in groups:
                groups[page] = []
            groups[page].append(entry)
        return groups


def generate_tests_from_har(
    file_path: Path,
    base_url: str | None = None,
    filter_api_only: bool = True,
) -> str:
    """Generate pytest tests from a HAR file.

    Args:
        file_path: Path to HAR file
        base_url: Override base URL (extracted from HAR if not provided)
        filter_api_only: Only include API calls

    Returns:
        Generated Python test code
    """
    parser = HARParser(filter_api_only=filter_api_only)
    entries = parser.parse_file(file_path)

    if not entries:
        return "# No API entries found in HAR file"

    # Determine base URL
    if not base_url and entries:
        parsed = urlparse(entries[0].url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Generate header
    code = f'''"""Generated API tests from HAR file: {file_path.name}

Auto-generated from browser session recording.
"""

import pytest
from httpx import Client


@pytest.fixture
def client():
    """Create HTTP client."""
    with Client(base_url="{base_url}") as client:
        yield client


'''

    # Generate tests
    seen_tests = set()
    for entry in entries:
        # Avoid duplicates
        sig = f"{entry.method}_{entry.path}_{entry.status_code}"
        if sig in seen_tests:
            continue
        seen_tests.add(sig)

        code += entry.to_test_case() + "\n\n"

    return code
