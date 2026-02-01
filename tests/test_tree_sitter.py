"""Tests for tree-sitter parser."""

from pathlib import Path

import pytest

from verify_ai.parsers.tree_sitter_parser import (
    TreeSitterParser,
    create_parser,
    TREE_SITTER_AVAILABLE,
)
from verify_ai.core.scanner import ProjectScanner


@pytest.fixture
def multi_lang_project_path():
    """Path to the multi-language project."""
    return Path(__file__).parent.parent / "examples" / "multi_lang_project"


@pytest.fixture
def sample_project_path():
    """Path to the sample project."""
    return Path(__file__).parent.parent / "examples" / "sample_project"


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
class TestTreeSitterParser:
    """Tests for TreeSitterParser."""

    def test_create_parser(self):
        """Test parser creation."""
        parser = create_parser()
        assert parser is not None

    def test_parse_python_file(self, sample_project_path):
        """Test parsing Python file."""
        parser = create_parser()
        assert parser is not None

        calc_path = sample_project_path / "calculator.py"
        functions, classes = parser.parse_file(calc_path)

        assert len(functions) >= 4  # add, subtract, multiply, divide
        assert len(classes) >= 1  # Calculator

        func_names = [f.name for f in functions]
        assert "add" in func_names
        assert "divide" in func_names

    def test_parse_go_file(self, multi_lang_project_path):
        """Test parsing Go file."""
        parser = create_parser()
        assert parser is not None

        go_path = multi_lang_project_path / "src" / "main.go"
        if not go_path.exists():
            pytest.skip("Go file not found")

        functions, classes = parser.parse_file(go_path)

        # Should find functions and struct types
        assert len(functions) >= 3
        func_names = [f.name for f in functions]
        assert "NewUserService" in func_names

    def test_parse_java_file(self, multi_lang_project_path):
        """Test parsing Java file."""
        parser = create_parser()
        assert parser is not None

        java_path = multi_lang_project_path / "src" / "UserController.java"
        if not java_path.exists():
            pytest.skip("Java file not found")

        functions, classes = parser.parse_file(java_path)

        # Should find classes and methods
        assert len(classes) >= 2
        class_names = [c.name for c in classes]
        assert "User" in class_names or "UserService" in class_names

    def test_parse_typescript_file(self, multi_lang_project_path):
        """Test parsing TypeScript file."""
        parser = create_parser()
        assert parser is not None

        ts_path = multi_lang_project_path / "src" / "utils.ts"
        if not ts_path.exists():
            pytest.skip("TypeScript file not found")

        functions, classes = parser.parse_file(ts_path)

        # Should find functions and classes
        assert len(functions) >= 2
        func_names = [f.name for f in functions]
        assert "formatDate" in func_names or "fetchUser" in func_names

    def test_parse_python_imports(self, sample_project_path):
        """Test parsing Python imports."""
        parser = create_parser()
        assert parser is not None

        user_service_path = sample_project_path / "user_service.py"
        dep_info = parser.parse_imports(user_service_path)

        assert dep_info is not None
        assert len(dep_info.imports) >= 2
        assert "re" in dep_info.dependencies or "dataclasses" in dep_info.dependencies


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
class TestScannerWithTreeSitter:
    """Tests for ProjectScanner with tree-sitter."""

    def test_scan_multi_lang_project(self, multi_lang_project_path):
        """Test scanning multi-language project."""
        scanner = ProjectScanner(multi_lang_project_path)
        info = scanner.scan()

        # Should detect multiple languages
        assert len(info.languages) >= 3
        assert "python" in info.languages
        assert "go" in info.languages
        assert "java" in info.languages

        # Should find functions from all languages
        assert len(info.functions) >= 10

        # Should find classes from all languages
        assert len(info.classes) >= 3

        # Should have dependency info
        assert info.uses_tree_sitter

    def test_scan_summary_includes_parser_info(self, multi_lang_project_path):
        """Test that summary includes parser info."""
        scanner = ProjectScanner(multi_lang_project_path)
        info = scanner.scan()
        summary = info.summary()

        assert "tree-sitter" in summary or "multi-language" in summary

    def test_scan_with_tree_sitter_disabled(self, sample_project_path):
        """Test scanning with tree-sitter disabled."""
        scanner = ProjectScanner(sample_project_path, use_tree_sitter=False)
        info = scanner.scan()

        # Should still work with fallback parser
        assert len(info.functions) >= 4
        assert len(info.classes) >= 1
        assert not info.uses_tree_sitter
