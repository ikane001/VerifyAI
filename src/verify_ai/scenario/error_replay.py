"""Error log parsing and reproduction test generation."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
import json
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class ErrorLog:
    """Parsed error log entry."""

    # Error info
    error_type: str
    error_message: str
    stack_trace: str = ""

    # Context
    timestamp: datetime | None = None
    level: Literal["error", "warning", "critical", "fatal"] = "error"
    logger_name: str = ""

    # Request context (if available)
    request_method: str | None = None
    request_path: str | None = None
    request_body: Any = None
    request_headers: dict[str, str] = field(default_factory=dict)

    # User context
    user_id: str | None = None
    session_id: str | None = None

    # Additional context
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def has_request_context(self) -> bool:
        """Check if this error has request context."""
        return bool(self.request_method and self.request_path)

    def get_reproduction_steps(self) -> list[str]:
        """Get human-readable reproduction steps.

        Returns:
            List of steps to reproduce the error
        """
        steps = []

        if self.has_request_context:
            steps.append(f"1. Make a {self.request_method} request to {self.request_path}")
            if self.request_body:
                steps.append(f"   With body: {self.request_body}")
            if self.request_headers:
                important_headers = {k: v for k, v in self.request_headers.items()
                                   if k.lower() in ("authorization", "content-type", "x-api-key")}
                if important_headers:
                    steps.append(f"   With headers: {important_headers}")

        steps.append(f"2. Expected: Request succeeds")
        steps.append(f"3. Actual: {self.error_type}: {self.error_message}")

        return steps


class ErrorLogParser:
    """Parse error logs from various formats."""

    def __init__(self):
        """Initialize error log parser."""
        self._patterns = self._compile_patterns()

    def _compile_patterns(self) -> dict[str, re.Pattern]:
        """Compile regex patterns for parsing."""
        return {
            # Python traceback
            "python_traceback": re.compile(
                r"Traceback \(most recent call last\):(.*?)(\w+Error|\w+Exception):\s*(.+?)(?:\n\n|\Z)",
                re.DOTALL
            ),

            # Python error line
            "python_error": re.compile(
                r"(\w+Error|\w+Exception):\s*(.+)"
            ),

            # JSON structured log
            "json_log": re.compile(
                r'^\s*\{.*"(?:level|severity)".*\}',
                re.MULTILINE
            ),

            # Common log format with error
            "common_error": re.compile(
                r"\[(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\]]*)\]\s*"
                r"(?:ERROR|CRITICAL|FATAL)\s*"
                r"(?:\[([^\]]+)\])?\s*"
                r"(.+)"
            ),

            # Request context in log
            "request_context": re.compile(
                r"(?:request|req)(?:_|\.)?(method|path|url|body|headers)\s*[=:]\s*([^\n,}]+)",
                re.IGNORECASE
            ),
        }

    def parse_file(self, file_path: Path) -> list[ErrorLog]:
        """Parse error logs from a file.

        Args:
            file_path: Path to log file

        Returns:
            List of parsed error logs
        """
        content = file_path.read_text()
        return self.parse_content(content)

    def parse_content(self, content: str) -> list[ErrorLog]:
        """Parse error logs from content.

        Args:
            content: Log content

        Returns:
            List of parsed error logs
        """
        errors = []

        # Try JSON format first
        if self._patterns["json_log"].search(content):
            errors.extend(self._parse_json_logs(content))

        # Try Python tracebacks
        for match in self._patterns["python_traceback"].finditer(content):
            stack_trace = match.group(1).strip()
            error_type = match.group(2)
            error_message = match.group(3).strip()

            error = ErrorLog(
                error_type=error_type,
                error_message=error_message,
                stack_trace=stack_trace,
            )

            # Try to extract request context from surrounding text
            context_start = max(0, match.start() - 500)
            context_text = content[context_start:match.start()]
            self._extract_request_context(error, context_text)

            errors.append(error)

        # Try common log format
        for match in self._patterns["common_error"].finditer(content):
            timestamp_str = match.group(1)
            logger_name = match.group(2) or ""
            message = match.group(3).strip()

            # Extract error type from message
            error_match = self._patterns["python_error"].search(message)
            if error_match:
                error_type = error_match.group(1)
                error_message = error_match.group(2)
            else:
                error_type = "Error"
                error_message = message

            error = ErrorLog(
                error_type=error_type,
                error_message=error_message,
                logger_name=logger_name,
                timestamp=self._parse_timestamp(timestamp_str),
            )

            errors.append(error)

        return errors

    def _parse_json_logs(self, content: str) -> list[ErrorLog]:
        """Parse JSON formatted logs."""
        errors = []

        for line in content.split("\n"):
            line = line.strip()
            if not line.startswith("{"):
                continue

            try:
                data = json.loads(line)

                # Check if it's an error
                level = data.get("level", data.get("severity", "")).lower()
                if level not in ("error", "critical", "fatal", "exception"):
                    continue

                error = ErrorLog(
                    error_type=data.get("error_type", data.get("exception_type", "Error")),
                    error_message=data.get("message", data.get("error", "")),
                    stack_trace=data.get("stack_trace", data.get("traceback", "")),
                    level=level if level in ("error", "warning", "critical", "fatal") else "error",
                    logger_name=data.get("logger", data.get("name", "")),
                    timestamp=self._parse_timestamp(data.get("timestamp", data.get("time"))),
                    request_method=data.get("request_method", data.get("method")),
                    request_path=data.get("request_path", data.get("path", data.get("url"))),
                    request_body=data.get("request_body", data.get("body")),
                    user_id=data.get("user_id"),
                    session_id=data.get("session_id"),
                    extra=data,
                )

                errors.append(error)

            except json.JSONDecodeError:
                continue

        return errors

    def _extract_request_context(self, error: ErrorLog, context: str):
        """Extract request context from surrounding log text."""
        for match in self._patterns["request_context"].finditer(context):
            field = match.group(1).lower()
            value = match.group(2).strip().strip("'\"")

            if field == "method":
                error.request_method = value.upper()
            elif field in ("path", "url"):
                error.request_path = value
            elif field == "body":
                try:
                    error.request_body = json.loads(value)
                except json.JSONDecodeError:
                    error.request_body = value

    def _parse_timestamp(self, ts: str | None) -> datetime | None:
        """Parse timestamp string."""
        if not ts:
            return None

        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(ts, fmt)
            except ValueError:
                continue

        return None


def generate_reproduction_test(
    error: ErrorLog,
    base_url: str = "http://localhost:8000",
) -> str:
    """Generate a test that reproduces an error.

    Args:
        error: ErrorLog to reproduce
        base_url: Base URL for API

    Returns:
        Python test code
    """
    if not error.has_request_context:
        # Can't generate API test without request context
        return f'''
def test_reproduce_{error.error_type.lower()}():
    """Reproduce {error.error_type}: {error.error_message[:50]}

    Error occurred at: {error.timestamp or "unknown time"}

    Steps to reproduce:
    {chr(10).join("    " + s for s in error.get_reproduction_steps())}

    Stack trace:
    {error.stack_trace[:500] if error.stack_trace else "Not available"}
    """
    # TODO: Add reproduction steps manually
    pytest.skip("Manual reproduction required - no request context available")
'''

    # Generate API reproduction test
    test_name = re.sub(r"[^a-zA-Z0-9]", "_", error.request_path or "unknown")
    test_name = f"test_reproduce_{error.error_type.lower()}_{test_name[:20]}"

    # Build request kwargs
    kwargs = []
    if error.request_body:
        if isinstance(error.request_body, dict):
            kwargs.append(f"json={error.request_body!r}")
        else:
            kwargs.append(f"content={error.request_body!r}")

    if error.request_headers:
        kwargs.append(f"headers={error.request_headers!r}")

    kwargs_str = ", ".join(kwargs)

    code = f'''
def {test_name}(client):
    """Reproduce {error.error_type}: {error.error_message[:50]}

    This test reproduces an error found in production logs.
    Error timestamp: {error.timestamp or "unknown"}
    """
    # This request triggered the error in production
    response = client.{(error.request_method or "GET").lower()}(
        "{error.request_path}",
        {kwargs_str}
    )

    # The original request failed with {error.error_type}
    # If this test passes, the bug may be fixed
    # If it fails with the same error, the bug is reproduced
    assert response.status_code < 500, f"Server error: {{response.status_code}}"
'''

    return code


def generate_reproduction_tests(
    errors: list[ErrorLog],
    base_url: str = "http://localhost:8000",
) -> str:
    """Generate tests for multiple errors.

    Args:
        errors: List of errors to reproduce
        base_url: Base URL for API

    Returns:
        Python test file content
    """
    header = f'''"""Error reproduction tests.

Auto-generated from error logs to help reproduce and fix production issues.
"""

import pytest
from httpx import Client


@pytest.fixture
def client():
    """Create HTTP client."""
    with Client(base_url="{base_url}") as client:
        yield client


'''

    tests = []
    for error in errors:
        tests.append(generate_reproduction_test(error, base_url))

    return header + "\n".join(tests)
