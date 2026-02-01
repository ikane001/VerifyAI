"""Tests for project scanner."""

from pathlib import Path

import pytest

from verify_ai.core.scanner import ProjectScanner, ProjectInfo


@pytest.fixture
def sample_project_path():
    """Path to the sample project."""
    return Path(__file__).parent.parent / "examples" / "sample_project"


def test_scanner_initialization(sample_project_path):
    """Test scanner can be initialized."""
    scanner = ProjectScanner(sample_project_path)
    assert scanner.project_path == sample_project_path.resolve()


def test_scanner_scan(sample_project_path):
    """Test scanner can scan a project."""
    scanner = ProjectScanner(sample_project_path)
    info = scanner.scan()

    assert isinstance(info, ProjectInfo)
    assert info.name == "sample_project"
    assert "python" in info.languages


def test_scanner_finds_source_files(sample_project_path):
    """Test scanner finds source files."""
    scanner = ProjectScanner(sample_project_path)
    info = scanner.scan()

    assert len(info.source_files) >= 2
    file_names = [f.name for f in info.source_files]
    assert "calculator.py" in file_names
    assert "user_service.py" in file_names


def test_scanner_finds_functions(sample_project_path):
    """Test scanner finds functions."""
    scanner = ProjectScanner(sample_project_path)
    info = scanner.scan()

    assert len(info.functions) >= 4  # add, subtract, multiply, divide, etc.
    func_names = [f.name for f in info.functions]
    assert "add" in func_names
    assert "subtract" in func_names


def test_scanner_finds_classes(sample_project_path):
    """Test scanner finds classes."""
    scanner = ProjectScanner(sample_project_path)
    info = scanner.scan()

    assert len(info.classes) >= 2
    class_names = [c.name for c in info.classes]
    assert "Calculator" in class_names
    assert "UserService" in class_names


def test_scanner_finds_api_endpoints(sample_project_path):
    """Test scanner finds API endpoints."""
    scanner = ProjectScanner(sample_project_path)
    info = scanner.scan()

    assert len(info.api_endpoints) == 6
    paths = [ep.path for ep in info.api_endpoints]
    assert "/users" in paths
    assert "/users/{userId}" in paths


def test_scanner_summary(sample_project_path):
    """Test scanner generates summary."""
    scanner = ProjectScanner(sample_project_path)
    info = scanner.scan()

    summary = info.summary()
    assert "sample_project" in summary
    assert "python" in summary
