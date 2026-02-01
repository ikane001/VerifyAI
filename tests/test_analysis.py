"""Tests for analysis and fix suggestion modules."""

import pytest

from verify_ai.analysis import (
    TestFailure,
    FailureAnalysis,
    TestAnalyzer,
    FixSuggestion,
    FixType,
    FixGenerator,
)
from verify_ai.analysis.analyzer import FailureType


class TestTestAnalyzer:
    """Tests for TestAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create test analyzer."""
        return TestAnalyzer()

    def test_parse_assertion_failure(self, analyzer):
        """Test parsing assertion failures."""
        pytest_output = """
============================= FAILURES =============================
_____________________ test_add_numbers _____________________

    def test_add_numbers():
>       assert add(2, 2) == 5
E       AssertionError: assert 4 == 5

tests/test_calc.py:10: AssertionError
========================= short test summary info =========================
"""
        failures = analyzer.parse_pytest_output(pytest_output)
        assert len(failures) == 1

        failure = failures[0]
        assert failure.failure_type == FailureType.ASSERTION
        assert "4 == 5" in failure.error_message or "AssertionError" in failure.error_message

    def test_parse_import_failure(self, analyzer):
        """Test parsing import failures."""
        pytest_output = """
============================= FAILURES =============================
_____________________ test_import _____________________

E   ImportError: No module named 'missing_module'

tests/test_import.py:1: ImportError
========================= short test summary info =========================
"""
        failures = analyzer.parse_pytest_output(pytest_output)
        assert len(failures) == 1

        failure = failures[0]
        assert failure.failure_type == FailureType.IMPORT
        assert "missing_module" in failure.error_message

    def test_analyze_assertion_failure(self, analyzer):
        """Test analyzing assertion failures."""
        failure = TestFailure(
            test_name="test_add",
            test_file="tests/test_calc.py",
            failure_type=FailureType.ASSERTION,
            error_message="assert 4 == 5",
            expected_value="5",
            actual_value="4",
            line_number=10,
        )

        analysis = analyzer.analyze_failure(failure)

        assert analysis.failure == failure
        assert "4" in analysis.root_cause
        assert "5" in analysis.root_cause
        assert analysis.confidence > 0.5
        assert analysis.fix_type in ("test", "source", "both")

    def test_analyze_import_failure(self, analyzer):
        """Test analyzing import failures."""
        failure = TestFailure(
            test_name="test_foo",
            test_file="tests/test_foo.py",
            failure_type=FailureType.IMPORT,
            error_message="No module named 'foo_lib'",
        )

        analysis = analyzer.analyze_failure(failure)

        assert "Import error" in analysis.root_cause
        assert analysis.fix_type == "source"

    def test_group_failures(self, analyzer):
        """Test grouping related failures."""
        failures = [
            TestFailure(
                test_name="test_a",
                test_file="tests/test.py",
                failure_type=FailureType.ASSERTION,
                error_message="assert x == 1",
            ),
            TestFailure(
                test_name="test_b",
                test_file="tests/test.py",
                failure_type=FailureType.ASSERTION,
                error_message="assert x == 1",
            ),
            TestFailure(
                test_name="test_c",
                test_file="tests/test.py",
                failure_type=FailureType.IMPORT,
                error_message="No module named 'foo'",
            ),
        ]

        groups = analyzer.group_failures(failures)

        # Should have 2 groups: assertion and import
        assert len(groups) == 2

        # Assertion group should have 2 failures
        assertion_group = [g for g in groups.values() if len(g) == 2]
        assert len(assertion_group) == 1


class TestTestFailure:
    """Tests for TestFailure dataclass."""

    def test_failure_creation(self):
        """Test creating a test failure."""
        failure = TestFailure(
            test_name="test_foo",
            test_file="tests/test_foo.py",
            failure_type=FailureType.ASSERTION,
            error_message="failed",
        )

        assert failure.test_name == "test_foo"
        assert failure.failure_type == FailureType.ASSERTION


class TestFixSuggestion:
    """Tests for FixSuggestion."""

    def test_fix_suggestion_creation(self):
        """Test creating a fix suggestion."""
        fix = FixSuggestion(
            file_path="tests/test_foo.py",
            fix_type=FixType.REPLACE,
            description="Fix assertion",
            confidence=0.8,
            old_code="assert x == 5",
            new_code="assert x == 4",
        )

        assert fix.file_path == "tests/test_foo.py"
        assert fix.fix_type == FixType.REPLACE
        assert fix.confidence == 0.8

    def test_get_diff(self):
        """Test generating diff for a fix."""
        fix = FixSuggestion(
            file_path="test.py",
            fix_type=FixType.REPLACE,
            description="Fix",
            confidence=0.8,
            old_code="x = 1\ny = 2",
            new_code="x = 1\ny = 3",
        )

        diff = fix.get_diff()

        assert "---" in diff
        assert "+++" in diff
        assert "-y = 2" in diff
        assert "+y = 3" in diff


class TestFixGenerator:
    """Tests for FixGenerator."""

    @pytest.fixture
    def generator(self):
        """Create fix generator without LLM."""
        return FixGenerator()

    def test_fix_import_error(self, generator):
        """Test generating fix for import error."""
        failure = TestFailure(
            test_name="test_foo",
            test_file="tests/test_foo.py",
            failure_type=FailureType.IMPORT,
            error_message="No module named 'requests'",
        )
        analysis = FailureAnalysis(
            failure=failure,
            root_cause="Import error",
            probable_location="tests/test_foo.py",
            confidence=0.8,
        )

        fix = generator._fix_import_error(failure)

        assert fix is not None
        assert fix.file_path == "requirements.txt"
        assert "requests" in fix.new_code

    def test_fix_fixture_error(self, generator):
        """Test generating fix for fixture error."""
        failure = TestFailure(
            test_name="test_foo",
            test_file="tests/test_foo.py",
            failure_type=FailureType.FIXTURE,
            error_message="fixture 'db_session' not found",
        )
        analysis = FailureAnalysis(
            failure=failure,
            root_cause="Fixture not found",
            probable_location="tests/test_foo.py",
            confidence=0.8,
        )

        fix = generator._fix_fixture_error(failure)

        assert fix is not None
        assert "@pytest.fixture" in fix.new_code
        assert "db_session" in fix.new_code

    def test_fix_assertion_error(self, generator):
        """Test generating fix for assertion error."""
        failure = TestFailure(
            test_name="test_foo",
            test_file="tests/test_foo.py",
            failure_type=FailureType.ASSERTION,
            error_message="assert 4 == 5",
            expected_value="5",
            actual_value="4",
        )

        fix = generator._fix_assertion_error(failure, "", "")

        assert fix is not None
        assert fix.old_code == "5"
        assert fix.new_code == "4"
        assert fix.requires_approval  # Low confidence fix
