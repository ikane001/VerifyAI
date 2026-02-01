"""Test failure analysis module."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal
import re
import logging

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """Type of test failure."""

    ASSERTION = "assertion"
    EXCEPTION = "exception"
    TIMEOUT = "timeout"
    IMPORT = "import"
    SYNTAX = "syntax"
    FIXTURE = "fixture"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


@dataclass
class TestFailure:
    """Information about a test failure."""

    test_name: str
    test_file: str
    failure_type: FailureType
    error_message: str
    stack_trace: str = ""
    line_number: int | None = None
    duration: float | None = None

    # Context
    source_file: str | None = None  # File being tested
    function_under_test: str | None = None
    expected_value: str | None = None
    actual_value: str | None = None


@dataclass
class FailureAnalysis:
    """Analysis of a test failure."""

    failure: TestFailure
    root_cause: str
    probable_location: str  # File:line where the bug likely is
    confidence: float  # 0-1 confidence in the analysis

    # Suggestions
    suggested_fix: str | None = None
    fix_type: Literal["test", "source", "both"] | None = None
    fix_explanation: str | None = None

    # Related context
    related_failures: list[str] = field(default_factory=list)
    similar_patterns: list[str] = field(default_factory=list)


class TestAnalyzer:
    """Analyze test failures to identify root causes."""

    def __init__(self):
        """Initialize the test analyzer."""
        self._patterns = self._compile_patterns()

    def _compile_patterns(self) -> dict[FailureType, list[re.Pattern]]:
        """Compile regex patterns for failure detection."""
        return {
            FailureType.ASSERTION: [
                re.compile(r"AssertionError:?\s*(.*)"),
                re.compile(r"assert\s+.*==.*failed"),
                re.compile(r"Expected:?\s*(.*?)\s*(?:but\s+)?(?:got|Actual):?\s*(.*)"),
                re.compile(r"pytest\.raises.*did not raise"),
            ],
            FailureType.EXCEPTION: [
                re.compile(r"(\w+Error):?\s*(.*)"),
                re.compile(r"(\w+Exception):?\s*(.*)"),
                re.compile(r"raise\s+(\w+)"),
            ],
            FailureType.IMPORT: [
                re.compile(r"ImportError:?\s*(.*)"),
                re.compile(r"ModuleNotFoundError:?\s*(.*)"),
                re.compile(r"No module named\s+['\"]?(\w+)"),
            ],
            FailureType.SYNTAX: [
                re.compile(r"SyntaxError:?\s*(.*)"),
                re.compile(r"IndentationError:?\s*(.*)"),
            ],
            FailureType.TIMEOUT: [
                re.compile(r"TimeoutError:?\s*(.*)"),
                re.compile(r"timed?\s*out", re.IGNORECASE),
            ],
            FailureType.FIXTURE: [
                re.compile(r"fixture\s+['\"]?(\w+)['\"]?\s+not found"),
                re.compile(r"FixtureLookupError"),
            ],
        }

    def parse_pytest_output(self, output: str) -> list[TestFailure]:
        """Parse pytest output to extract test failures.

        Args:
            output: Raw pytest output

        Returns:
            List of TestFailure objects
        """
        failures = []

        # Split by test separator
        test_sections = re.split(r"_{3,}\s*(\S+)\s*_{3,}", output)

        # Find FAILURES section
        failure_match = re.search(
            r"=+\s*FAILURES\s*=+(.*?)(?:=+\s*(?:ERRORS|short test summary|warnings summary|=+$))",
            output,
            re.DOTALL,
        )

        if not failure_match:
            return failures

        failure_section = failure_match.group(1)

        # Split by test name headers
        test_blocks = re.split(r"_{5,}\s*(\S+)\s*_{5,}", failure_section)

        for i in range(1, len(test_blocks), 2):
            if i + 1 >= len(test_blocks):
                break

            test_name = test_blocks[i].strip()
            test_content = test_blocks[i + 1]

            failure = self._parse_failure_block(test_name, test_content)
            if failure:
                failures.append(failure)

        return failures

    def _parse_failure_block(self, test_name: str, content: str) -> TestFailure | None:
        """Parse a single test failure block."""
        # Extract file and line from test name
        file_match = re.search(r"(\S+\.py)::(\w+)", test_name)
        test_file = file_match.group(1) if file_match else ""

        # Determine failure type
        failure_type = FailureType.UNKNOWN
        error_message = ""

        # Check patterns in priority order (more specific first)
        priority_order = [
            FailureType.IMPORT,
            FailureType.SYNTAX,
            FailureType.TIMEOUT,
            FailureType.FIXTURE,
            FailureType.ASSERTION,
            FailureType.EXCEPTION,
        ]

        for ftype in priority_order:
            patterns = self._patterns.get(ftype, [])
            for pattern in patterns:
                match = pattern.search(content)
                if match:
                    failure_type = ftype
                    error_message = match.group(1) if match.groups() else match.group(0)
                    break
            if failure_type != FailureType.UNKNOWN:
                break

        # Extract expected/actual values
        expected = None
        actual = None
        expected_match = re.search(r"Expected:?\s*(.+?)(?:\n|$)", content)
        actual_match = re.search(r"(?:Actual|Got):?\s*(.+?)(?:\n|$)", content)

        if expected_match:
            expected = expected_match.group(1).strip()
        if actual_match:
            actual = actual_match.group(1).strip()

        # Extract line number
        line_match = re.search(r":(\d+):", content)
        line_number = int(line_match.group(1)) if line_match else None

        # Find stack trace
        stack_trace = ""
        trace_match = re.search(r"(.*?(?:Traceback|File).*?)(?:>{3}|E\s+)", content, re.DOTALL)
        if trace_match:
            stack_trace = trace_match.group(1).strip()

        return TestFailure(
            test_name=test_name,
            test_file=test_file,
            failure_type=failure_type,
            error_message=error_message,
            stack_trace=stack_trace,
            line_number=line_number,
            expected_value=expected,
            actual_value=actual,
        )

    def analyze_failure(self, failure: TestFailure) -> FailureAnalysis:
        """Analyze a test failure to determine root cause.

        Args:
            failure: TestFailure to analyze

        Returns:
            FailureAnalysis with root cause and suggestions
        """
        # Determine root cause based on failure type
        root_cause = self._determine_root_cause(failure)
        probable_location = self._find_probable_location(failure)
        confidence = self._calculate_confidence(failure)
        fix_type = self._determine_fix_type(failure)

        return FailureAnalysis(
            failure=failure,
            root_cause=root_cause,
            probable_location=probable_location,
            confidence=confidence,
            fix_type=fix_type,
        )

    def _determine_root_cause(self, failure: TestFailure) -> str:
        """Determine the root cause of a failure."""
        if failure.failure_type == FailureType.ASSERTION:
            if failure.expected_value and failure.actual_value:
                return (
                    f"Assertion failed: expected '{failure.expected_value}' "
                    f"but got '{failure.actual_value}'"
                )
            return f"Assertion failed: {failure.error_message}"

        elif failure.failure_type == FailureType.EXCEPTION:
            return f"Unexpected exception raised: {failure.error_message}"

        elif failure.failure_type == FailureType.IMPORT:
            return f"Import error: {failure.error_message}"

        elif failure.failure_type == FailureType.SYNTAX:
            return f"Syntax error in code: {failure.error_message}"

        elif failure.failure_type == FailureType.TIMEOUT:
            return "Test timed out - possible infinite loop or slow operation"

        elif failure.failure_type == FailureType.FIXTURE:
            return f"Fixture not found or failed: {failure.error_message}"

        return f"Unknown error: {failure.error_message}"

    def _find_probable_location(self, failure: TestFailure) -> str:
        """Find the probable location of the bug."""
        if failure.source_file and failure.line_number:
            return f"{failure.source_file}:{failure.line_number}"

        if failure.test_file and failure.line_number:
            return f"{failure.test_file}:{failure.line_number}"

        if failure.test_file:
            return failure.test_file

        return "unknown"

    def _calculate_confidence(self, failure: TestFailure) -> float:
        """Calculate confidence in the analysis."""
        confidence = 0.5  # Base confidence

        # Higher confidence if we have expected/actual values
        if failure.expected_value and failure.actual_value:
            confidence += 0.2

        # Higher confidence for specific failure types
        if failure.failure_type in (FailureType.ASSERTION, FailureType.SYNTAX):
            confidence += 0.1

        # Higher confidence if we have line number
        if failure.line_number:
            confidence += 0.1

        # Lower confidence for unknown failures
        if failure.failure_type == FailureType.UNKNOWN:
            confidence -= 0.2

        return min(max(confidence, 0.0), 1.0)

    def _determine_fix_type(self, failure: TestFailure) -> Literal["test", "source", "both"]:
        """Determine whether to fix test or source code."""
        # Syntax errors in test file -> fix test
        if failure.failure_type == FailureType.SYNTAX:
            if "test_" in failure.test_file:
                return "test"
            return "source"

        # Import errors usually need source fix
        if failure.failure_type == FailureType.IMPORT:
            return "source"

        # Fixture errors need test fix
        if failure.failure_type == FailureType.FIXTURE:
            return "test"

        # Assertions - could be either
        if failure.failure_type == FailureType.ASSERTION:
            # If test is checking for exception that wasn't raised
            if "did not raise" in failure.error_message:
                return "source"  # Source needs to raise exception
            return "both"  # Could be test or source issue

        return "both"

    def group_failures(
        self, failures: list[TestFailure]
    ) -> dict[str, list[TestFailure]]:
        """Group related failures together.

        Args:
            failures: List of test failures

        Returns:
            Dictionary grouping failures by probable root cause
        """
        groups: dict[str, list[TestFailure]] = {}

        for failure in failures:
            # Group by error type and message
            key = f"{failure.failure_type.value}:{failure.error_message[:50]}"

            if key not in groups:
                groups[key] = []
            groups[key].append(failure)

        return groups
