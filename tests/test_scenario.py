"""Tests for scenario replay modules."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from verify_ai.scenario import (
    APILogEntry,
    APILogParser,
    parse_nginx_log,
    parse_json_log,
    HAREntry,
    HARParser,
    generate_tests_from_har,
    ErrorLog,
    ErrorLogParser,
    generate_reproduction_test,
)


class TestAPILogEntry:
    """Tests for APILogEntry."""

    def test_create_entry(self):
        """Test creating an API log entry."""
        entry = APILogEntry(
            method="GET",
            path="/api/users",
            status_code=200,
        )
        assert entry.method == "GET"
        assert entry.path == "/api/users"
        assert entry.is_success

    def test_full_path_with_query(self):
        """Test full path generation with query params."""
        entry = APILogEntry(
            method="GET",
            path="/api/search",
            query_params={"q": "test", "page": "1"},
        )
        assert "q=test" in entry.full_path
        assert "page=1" in entry.full_path

    def test_is_json_request(self):
        """Test JSON request detection."""
        entry = APILogEntry(
            method="POST",
            path="/api/data",
            headers={"content-type": "application/json"},
        )
        assert entry.is_json_request

    def test_to_test_case(self):
        """Test generating test case from entry."""
        entry = APILogEntry(
            method="POST",
            path="/api/users",
            headers={"content-type": "application/json"},
            body={"name": "John"},
            status_code=201,
        )
        test_code = entry.to_test_case()

        assert "def test_post_api_users" in test_code
        assert "client.post" in test_code
        assert "201" in test_code


class TestAPILogParser:
    """Tests for APILogParser."""

    def test_parse_nginx_log(self):
        """Test parsing nginx combined log format."""
        log = '127.0.0.1 - - [10/Oct/2024:13:55:36 +0000] "GET /api/users?page=1 HTTP/1.1" 200 1234 "-" "curl/7.64.1"'
        entries = parse_nginx_log(log)

        assert len(entries) == 1
        entry = entries[0]
        assert entry.method == "GET"
        assert entry.path == "/api/users"
        assert entry.query_params == {"page": "1"}
        assert entry.status_code == 200

    def test_parse_json_log(self):
        """Test parsing JSON log format."""
        log = json.dumps({
            "method": "POST",
            "path": "/api/data",
            "status": 201,
            "body": {"key": "value"},
            "response": {"id": 1},
        })
        entries = parse_json_log(log)

        assert len(entries) == 1
        entry = entries[0]
        assert entry.method == "POST"
        assert entry.path == "/api/data"
        assert entry.status_code == 201
        assert entry.body == {"key": "value"}

    def test_auto_detect_format(self):
        """Test auto-detecting log format."""
        parser = APILogParser(log_format="auto")

        # JSON format
        json_log = '{"method": "GET", "path": "/test"}'
        entries = parser.parse_lines([json_log])
        assert len(entries) == 1
        assert entries[0].method == "GET"


class TestHAREntry:
    """Tests for HAREntry."""

    def test_create_entry(self):
        """Test creating a HAR entry."""
        entry = HAREntry(
            method="GET",
            url="https://api.example.com/users",
            path="/users",
            status_code=200,
        )
        assert entry.host == "api.example.com"
        assert entry.is_success

    def test_is_api_call(self):
        """Test API call detection."""
        # API call
        api_entry = HAREntry(
            method="GET",
            url="https://api.example.com/api/v1/users",
            path="/api/v1/users",
            response_headers={"content-type": "application/json"},
        )
        assert api_entry.is_api_call

        # Static resource
        static_entry = HAREntry(
            method="GET",
            url="https://example.com/style.css",
            path="/style.css",
        )
        assert not static_entry.is_api_call

    def test_to_test_case(self):
        """Test generating test from HAR entry."""
        entry = HAREntry(
            method="POST",
            url="https://api.example.com/users",
            path="/users",
            mime_type="application/json",
            post_data='{"name": "John"}',
            status_code=201,
            response_headers={"content-type": "application/json"},
            response_body='{"id": 1, "name": "John"}',
        )
        code = entry.to_test_case()

        assert "def test_post_users" in code
        assert "client.post" in code
        assert "201" in code


class TestHARParser:
    """Tests for HARParser."""

    def test_parse_har_content(self):
        """Test parsing HAR content."""
        har_content = json.dumps({
            "log": {
                "version": "1.2",
                "entries": [
                    {
                        "request": {
                            "method": "GET",
                            "url": "https://api.example.com/api/users",
                            "headers": [{"name": "Accept", "value": "application/json"}],
                            "cookies": [],
                        },
                        "response": {
                            "status": 200,
                            "statusText": "OK",
                            "headers": [{"name": "content-type", "value": "application/json"}],
                            "content": {"size": 100, "text": '{"users": []}'},
                        },
                        "startedDateTime": "2024-01-15T10:30:00.000Z",
                        "time": 150,
                    }
                ]
            }
        })

        parser = HARParser(filter_api_only=True)
        entries = parser.parse_content(har_content)

        assert len(entries) == 1
        entry = entries[0]
        assert entry.method == "GET"
        assert entry.path == "/api/users"
        assert entry.status_code == 200

    def test_filter_static_resources(self):
        """Test filtering static resources."""
        har_content = json.dumps({
            "log": {
                "entries": [
                    {
                        "request": {"method": "GET", "url": "https://example.com/api/data", "headers": [], "cookies": []},
                        "response": {"status": 200, "headers": [{"name": "content-type", "value": "application/json"}], "content": {}},
                    },
                    {
                        "request": {"method": "GET", "url": "https://example.com/style.css", "headers": [], "cookies": []},
                        "response": {"status": 200, "headers": [], "content": {}},
                    },
                ]
            }
        })

        parser = HARParser(filter_api_only=True)
        entries = parser.parse_content(har_content)

        # Should only have API call
        assert len(entries) == 1
        assert entries[0].path == "/api/data"


class TestErrorLog:
    """Tests for ErrorLog."""

    def test_create_error_log(self):
        """Test creating an error log."""
        error = ErrorLog(
            error_type="ValueError",
            error_message="Invalid input",
            request_method="POST",
            request_path="/api/validate",
        )
        assert error.has_request_context
        assert error.error_type == "ValueError"

    def test_reproduction_steps(self):
        """Test getting reproduction steps."""
        error = ErrorLog(
            error_type="ValueError",
            error_message="Invalid email",
            request_method="POST",
            request_path="/api/users",
            request_body={"email": "invalid"},
        )
        steps = error.get_reproduction_steps()

        assert len(steps) >= 3
        assert "POST" in steps[0]
        assert "/api/users" in steps[0]


class TestErrorLogParser:
    """Tests for ErrorLogParser."""

    def test_parse_python_traceback(self):
        """Test parsing Python traceback."""
        log = """
2024-01-15 10:30:00 ERROR Something went wrong
Traceback (most recent call last):
  File "app.py", line 10, in handler
    raise ValueError("Invalid input")
ValueError: Invalid input

2024-01-15 10:31:00 INFO Recovered
"""
        parser = ErrorLogParser()
        errors = parser.parse_content(log)

        assert len(errors) >= 1
        error = errors[0]
        assert error.error_type == "ValueError"
        assert "Invalid input" in error.error_message

    def test_parse_json_error_log(self):
        """Test parsing JSON formatted error logs."""
        log = json.dumps({
            "level": "error",
            "error_type": "DatabaseError",
            "message": "Connection refused",
            "timestamp": "2024-01-15T10:30:00Z",
            "request_method": "GET",
            "request_path": "/api/data",
        })

        parser = ErrorLogParser()
        errors = parser.parse_content(log)

        assert len(errors) == 1
        error = errors[0]
        assert error.error_type == "DatabaseError"
        assert error.request_method == "GET"
        assert error.request_path == "/api/data"


class TestGenerateReproductionTest:
    """Tests for reproduction test generation."""

    def test_generate_with_request_context(self):
        """Test generating test with request context."""
        error = ErrorLog(
            error_type="ValidationError",
            error_message="Invalid email",
            request_method="POST",
            request_path="/api/users",
            request_body={"email": "bad"},
        )

        code = generate_reproduction_test(error)

        assert "def test_reproduce_validationerror" in code
        assert "client.post" in code
        assert '"/api/users"' in code

    def test_generate_without_request_context(self):
        """Test generating test without request context."""
        error = ErrorLog(
            error_type="RuntimeError",
            error_message="Something failed",
        )

        code = generate_reproduction_test(error)

        assert "pytest.skip" in code
        assert "Manual reproduction required" in code
