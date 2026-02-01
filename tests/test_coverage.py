"""Tests for coverage analysis module."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from verify_ai.coverage.models import (
    CoverageReport,
    CoverageSummary,
    FileMetrics,
    FunctionCoverage,
    LineCoverage,
    UncoveredSuggestion,
)
from verify_ai.coverage.analyzer import CoverageAnalyzer
from verify_ai.coverage.reporter import (
    ConsoleReporter,
    HTMLReporter,
    JSONReporter,
    create_reporter,
)


class TestLineCoverage:
    """Tests for LineCoverage model."""

    def test_create_covered_line(self):
        """Test creating a covered line."""
        line = LineCoverage(line_number=10, is_covered=True, hit_count=5)
        assert line.line_number == 10
        assert line.is_covered is True
        assert line.hit_count == 5

    def test_create_uncovered_line(self):
        """Test creating an uncovered line."""
        line = LineCoverage(line_number=20, is_covered=False)
        assert line.line_number == 20
        assert line.is_covered is False
        assert line.hit_count == 0


class TestFunctionCoverage:
    """Tests for FunctionCoverage model."""

    def test_create_function_coverage(self):
        """Test creating function coverage."""
        func = FunctionCoverage(
            name="test_func",
            file_path="src/module.py",
            start_line=10,
            end_line=20,
            is_covered=True,
            total_lines=10,
            covered_lines=8,
        )
        assert func.name == "test_func"
        assert func.coverage_percent == 80.0

    def test_coverage_percent_zero_lines(self):
        """Test coverage percent with zero lines."""
        func = FunctionCoverage(
            name="empty_func",
            file_path="src/module.py",
            start_line=1,
            end_line=1,
            is_covered=False,
            total_lines=0,
            covered_lines=0,
        )
        assert func.coverage_percent == 0.0


class TestFileMetrics:
    """Tests for FileMetrics model."""

    def test_create_file_metrics(self):
        """Test creating file metrics."""
        metrics = FileMetrics(
            file_path="src/module.py",
            total_lines=100,
            covered_lines=80,
            missed_lines=20,
        )
        assert metrics.coverage_percent == 80.0

    def test_uncovered_lines(self):
        """Test getting uncovered lines."""
        metrics = FileMetrics(
            file_path="src/module.py",
            total_lines=10,
            covered_lines=7,
            missed_lines=3,
            line_coverage=[
                LineCoverage(1, True),
                LineCoverage(2, True),
                LineCoverage(3, False),
                LineCoverage(4, True),
                LineCoverage(5, False),
            ],
        )
        uncovered = metrics.uncovered_lines
        assert 3 in uncovered
        assert 5 in uncovered
        assert 1 not in uncovered

    def test_uncovered_functions(self):
        """Test getting uncovered functions."""
        metrics = FileMetrics(
            file_path="src/module.py",
            total_lines=50,
            covered_lines=40,
            missed_lines=10,
            functions=[
                FunctionCoverage("func1", "src/module.py", 1, 10, True),
                FunctionCoverage("func2", "src/module.py", 11, 20, False),
                FunctionCoverage("func3", "src/module.py", 21, 30, True),
            ],
        )
        uncovered = metrics.uncovered_functions
        assert len(uncovered) == 1
        assert uncovered[0].name == "func2"

    def test_branch_coverage_percent(self):
        """Test branch coverage calculation."""
        metrics = FileMetrics(
            file_path="src/module.py",
            total_lines=10,
            covered_lines=8,
            missed_lines=2,
            total_branches=20,
            covered_branches=15,
        )
        assert metrics.branch_coverage_percent == 75.0


class TestCoverageSummary:
    """Tests for CoverageSummary model."""

    def test_create_summary(self):
        """Test creating coverage summary."""
        summary = CoverageSummary(
            total_files=5,
            total_lines=500,
            covered_lines=400,
            missed_lines=100,
            total_functions=20,
            covered_functions=18,
        )
        assert summary.line_coverage_percent == 80.0
        assert summary.function_coverage_percent == 90.0

    def test_zero_lines(self):
        """Test summary with zero lines."""
        summary = CoverageSummary(
            total_files=0,
            total_lines=0,
            covered_lines=0,
            missed_lines=0,
        )
        assert summary.line_coverage_percent == 0.0


class TestCoverageReport:
    """Tests for CoverageReport model."""

    def test_create_report(self):
        """Test creating coverage report."""
        report = CoverageReport(
            project_path="/project",
            file_reports=[
                FileMetrics("file1.py", 100, 80, 20),
                FileMetrics("file2.py", 50, 45, 5),
            ],
        )
        assert report.coverage_percent == pytest.approx(83.33, rel=0.01)
        assert report.summary is not None
        assert report.summary.total_files == 2

    def test_get_uncovered_files(self):
        """Test getting files below threshold."""
        report = CoverageReport(
            project_path="/project",
            file_reports=[
                FileMetrics("file1.py", 100, 90, 10),  # 90%
                FileMetrics("file2.py", 100, 70, 30),  # 70%
                FileMetrics("file3.py", 100, 85, 15),  # 85%
            ],
        )
        uncovered = report.get_uncovered_files(threshold=80.0)
        assert len(uncovered) == 1
        assert uncovered[0].file_path == "file2.py"

    def test_to_dict(self):
        """Test converting report to dictionary."""
        report = CoverageReport(
            project_path="/project",
            file_reports=[
                FileMetrics("file1.py", 100, 80, 20),
            ],
            duration_seconds=5.5,
        )
        data = report.to_dict()
        assert data["project_path"] == "/project"
        assert data["duration_seconds"] == 5.5
        assert "summary" in data
        assert "files" in data


class TestUncoveredSuggestion:
    """Tests for UncoveredSuggestion model."""

    def test_from_large_function(self):
        """Test suggestion for large function."""
        func = FunctionCoverage(
            name="big_func",
            file_path="src/module.py",
            start_line=1,
            end_line=50,
            is_covered=False,
            total_lines=50,
            covered_lines=0,
        )
        suggestion = UncoveredSuggestion.from_function(func)
        assert suggestion.priority == "high"
        assert len(suggestion.suggested_test_cases) >= 1

    def test_from_small_function(self):
        """Test suggestion for small function."""
        func = FunctionCoverage(
            name="small_func",
            file_path="src/module.py",
            start_line=1,
            end_line=5,
            is_covered=False,
            total_lines=5,
            covered_lines=0,
        )
        suggestion = UncoveredSuggestion.from_function(func)
        assert suggestion.priority == "low"


class TestCoverageAnalyzer:
    """Tests for CoverageAnalyzer."""

    def test_create_analyzer(self):
        """Test creating analyzer."""
        analyzer = CoverageAnalyzer(Path("."))
        assert analyzer.project_path == Path(".").resolve()

    def test_check_threshold_no_data(self):
        """Test threshold check without data."""
        analyzer = CoverageAnalyzer(Path("."))
        passes, message = analyzer.check_threshold(80.0)
        assert passes is False
        assert "No coverage report" in message

    def test_get_summary_no_data(self):
        """Test summary without data."""
        analyzer = CoverageAnalyzer(Path("."))
        summary = analyzer.get_summary()
        assert summary["has_data"] is False


class TestJSONReporter:
    """Tests for JSON reporter."""

    def test_generate_json(self):
        """Test generating JSON report."""
        report = CoverageReport(
            project_path="/project",
            file_reports=[
                FileMetrics("file1.py", 100, 80, 20),
            ],
        )
        reporter = JSONReporter()
        content = reporter.generate(report)

        data = json.loads(content)
        assert data["project_path"] == "/project"
        assert len(data["files"]) == 1

    def test_save_to_file(self):
        """Test saving JSON report to file."""
        report = CoverageReport(
            project_path="/project",
            file_reports=[],
        )
        reporter = JSONReporter()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            reporter.generate(report, output_path)

            assert output_path.exists()
            data = json.loads(output_path.read_text())
            assert data["project_path"] == "/project"


class TestHTMLReporter:
    """Tests for HTML reporter."""

    def test_generate_html(self):
        """Test generating HTML report."""
        report = CoverageReport(
            project_path="/project",
            file_reports=[
                FileMetrics("file1.py", 100, 80, 20),
                FileMetrics("file2.py", 50, 25, 25),
            ],
        )
        reporter = HTMLReporter(title="Test Report")
        html = reporter.generate(report)

        assert "Test Report" in html
        assert "file1.py" in html
        assert "file2.py" in html
        assert "80.0%" in html or "80%" in html

    def test_save_to_file(self):
        """Test saving HTML report to file."""
        report = CoverageReport(
            project_path="/project",
            file_reports=[],
        )
        reporter = HTMLReporter()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            reporter.generate(report, output_path)

            assert output_path.exists()
            content = output_path.read_text()
            assert "<html" in content


class TestConsoleReporter:
    """Tests for console reporter."""

    def test_create_reporter(self):
        """Test creating console reporter."""
        reporter = ConsoleReporter(threshold=90.0)
        assert reporter.threshold == 90.0

    def test_generate_returns_empty(self):
        """Test that console reporter returns empty string."""
        report = CoverageReport(
            project_path="/project",
            file_reports=[],
        )
        reporter = ConsoleReporter()
        result = reporter.generate(report)
        assert result == ""


class TestReporterFactory:
    """Tests for reporter factory."""

    def test_create_console_reporter(self):
        """Test creating console reporter."""
        reporter = create_reporter("console")
        assert isinstance(reporter, ConsoleReporter)

    def test_create_json_reporter(self):
        """Test creating JSON reporter."""
        reporter = create_reporter("json")
        assert isinstance(reporter, JSONReporter)

    def test_create_html_reporter(self):
        """Test creating HTML reporter."""
        reporter = create_reporter("html")
        assert isinstance(reporter, HTMLReporter)

    def test_invalid_format(self):
        """Test invalid format raises error."""
        with pytest.raises(ValueError):
            create_reporter("invalid")
