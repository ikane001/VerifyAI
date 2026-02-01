"""Tests for parsers."""

from pathlib import Path

import pytest

from verify_ai.parsers.openapi import OpenAPIParser, find_openapi_spec
from verify_ai.parsers.code_parser import CodeParser, detect_language


@pytest.fixture
def sample_project_path():
    """Path to the sample project."""
    return Path(__file__).parent.parent / "examples" / "sample_project"


@pytest.fixture
def openapi_spec_path(sample_project_path):
    """Path to sample OpenAPI spec."""
    return sample_project_path / "openapi.yaml"


class TestOpenAPIParser:
    """Tests for OpenAPIParser."""

    def test_load_spec(self, openapi_spec_path):
        """Test loading OpenAPI spec."""
        parser = OpenAPIParser(openapi_spec_path)
        assert parser.title == "Sample User API"
        assert parser.version == "1.0.0"

    def test_get_endpoints(self, openapi_spec_path):
        """Test getting endpoints."""
        parser = OpenAPIParser(openapi_spec_path)
        endpoints = parser.get_endpoints()

        assert len(endpoints) == 6

        # Check specific endpoint
        list_users = next((e for e in endpoints if e.operation_id == "listUsers"), None)
        assert list_users is not None
        assert list_users.method == "get"
        assert list_users.path == "/users"

    def test_endpoint_parameters(self, openapi_spec_path):
        """Test endpoint parameters are parsed."""
        parser = OpenAPIParser(openapi_spec_path)
        endpoints = parser.get_endpoints()

        get_user = next((e for e in endpoints if e.operation_id == "getUser"), None)
        assert get_user is not None
        assert len(get_user.parameters) >= 1

        user_id_param = next((p for p in get_user.parameters if p.name == "userId"), None)
        assert user_id_param is not None
        assert user_id_param.required is True
        assert user_id_param.location == "path"

    def test_get_schemas(self, openapi_spec_path):
        """Test getting schemas."""
        parser = OpenAPIParser(openapi_spec_path)
        schemas = parser.get_schemas()

        assert "User" in schemas
        assert "CreateUserRequest" in schemas

    def test_to_summary(self, openapi_spec_path):
        """Test summary generation."""
        parser = OpenAPIParser(openapi_spec_path)
        summary = parser.to_summary()

        assert "Sample User API" in summary
        assert "GET /users" in summary


class TestFindOpenAPISpec:
    """Tests for find_openapi_spec."""

    def test_find_spec(self, sample_project_path):
        """Test finding OpenAPI spec."""
        spec_path = find_openapi_spec(sample_project_path)
        assert spec_path is not None
        assert spec_path.name == "openapi.yaml"

    def test_find_spec_not_found(self, tmp_path):
        """Test when spec is not found."""
        spec_path = find_openapi_spec(tmp_path)
        assert spec_path is None


class TestCodeParser:
    """Tests for CodeParser."""

    def test_parse_python_file(self, sample_project_path):
        """Test parsing Python file."""
        parser = CodeParser(language="python")
        calc_path = sample_project_path / "calculator.py"

        functions, classes = parser.parse_file(calc_path)

        assert len(functions) >= 4  # add, subtract, multiply, divide
        assert len(classes) >= 1  # Calculator

        func_names = [f.name for f in functions]
        assert "add" in func_names

    def test_function_info(self, sample_project_path):
        """Test function info extraction."""
        parser = CodeParser(language="python")
        calc_path = sample_project_path / "calculator.py"

        functions, _ = parser.parse_file(calc_path)
        add_func = next((f for f in functions if f.name == "add"), None)

        assert add_func is not None
        assert len(add_func.parameters) >= 2
        assert add_func.return_type is not None
        assert add_func.docstring != ""

    def test_class_info(self, sample_project_path):
        """Test class info extraction."""
        parser = CodeParser(language="python")
        calc_path = sample_project_path / "calculator.py"

        _, classes = parser.parse_file(calc_path)
        calc_class = next((c for c in classes if c.name == "Calculator"), None)

        assert calc_class is not None
        assert len(calc_class.methods) >= 5  # add, subtract, multiply, divide, clear, get_memory
        assert calc_class.docstring != ""


class TestDetectLanguage:
    """Tests for detect_language."""

    def test_detect_python(self):
        """Test detecting Python."""
        assert detect_language(Path("test.py")) == "python"

    def test_detect_javascript(self):
        """Test detecting JavaScript."""
        assert detect_language(Path("test.js")) == "javascript"
        assert detect_language(Path("test.jsx")) == "javascript"

    def test_detect_typescript(self):
        """Test detecting TypeScript."""
        assert detect_language(Path("test.ts")) == "typescript"
        assert detect_language(Path("test.tsx")) == "typescript"

    def test_detect_unknown(self):
        """Test unknown extension."""
        assert detect_language(Path("test.xyz")) is None
