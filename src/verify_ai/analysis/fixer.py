"""Fix suggestion generation and application."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal
import difflib
import logging
import re

from .analyzer import TestFailure, FailureAnalysis, FailureType

logger = logging.getLogger(__name__)


class FixType(Enum):
    """Type of fix to apply."""

    REPLACE = "replace"  # Replace specific code
    INSERT = "insert"  # Insert new code
    DELETE = "delete"  # Delete code
    REFACTOR = "refactor"  # Complex refactoring


@dataclass
class FixSuggestion:
    """A suggested fix for a test failure."""

    file_path: str
    fix_type: FixType
    description: str
    confidence: float  # 0-1

    # For replace/delete
    old_code: str = ""
    new_code: str = ""

    # Location
    start_line: int | None = None
    end_line: int | None = None

    # Metadata
    requires_approval: bool = True
    is_auto_fixable: bool = False
    related_failure: str = ""

    def get_diff(self) -> str:
        """Generate a unified diff for this fix."""
        if not self.old_code or self.fix_type == FixType.INSERT:
            return f"+++ {self.new_code}"

        old_lines = self.old_code.splitlines(keepends=True)
        new_lines = self.new_code.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{self.file_path}",
            tofile=f"b/{self.file_path}",
            lineterm="",
        )

        return "".join(diff)


# Prompt templates for fix generation
FIX_PROMPT_TEMPLATE = """You are analyzing a test failure and need to suggest a fix.

## Test Failure
- Test: {test_name}
- File: {test_file}
- Error Type: {failure_type}
- Error Message: {error_message}

## Stack Trace
{stack_trace}

## Expected vs Actual
Expected: {expected}
Actual: {actual}

## Root Cause Analysis
{root_cause}

## Source Code
```{language}
{source_code}
```

## Test Code
```{language}
{test_code}
```

## Task
Analyze the failure and suggest a fix. Consider:
1. Is this a bug in the source code or the test?
2. What is the minimal fix needed?
3. Will this fix cause any side effects?

Provide your response in the following format:

FIX_TYPE: [test|source|both]
CONFIDENCE: [0.0-1.0]
DESCRIPTION: [Brief description of the fix]

OLD_CODE:
```
[Original code to replace]
```

NEW_CODE:
```
[Fixed code]
```

EXPLANATION:
[Detailed explanation of why this fix works]
"""


class FixGenerator:
    """Generate fix suggestions using LLM."""

    def __init__(self, llm_client=None, project_path: Path | None = None):
        """Initialize the fix generator.

        Args:
            llm_client: LLM client for generating fixes
            project_path: Path to the project root
        """
        self.llm_client = llm_client
        self.project_path = project_path

    async def generate_fix(
        self,
        analysis: FailureAnalysis,
        source_code: str = "",
        test_code: str = "",
    ) -> FixSuggestion | None:
        """Generate a fix suggestion for a failure.

        Args:
            analysis: FailureAnalysis from the analyzer
            source_code: Source code being tested
            test_code: Test code that failed

        Returns:
            FixSuggestion or None if no fix could be generated
        """
        failure = analysis.failure

        if not self.llm_client:
            # Use rule-based fix generation
            return self._generate_rule_based_fix(analysis, source_code, test_code)

        # Use LLM for intelligent fix generation
        prompt = FIX_PROMPT_TEMPLATE.format(
            test_name=failure.test_name,
            test_file=failure.test_file,
            failure_type=failure.failure_type.value,
            error_message=failure.error_message,
            stack_trace=failure.stack_trace,
            expected=failure.expected_value or "N/A",
            actual=failure.actual_value or "N/A",
            root_cause=analysis.root_cause,
            language=self._detect_language(failure.test_file),
            source_code=source_code or "Not available",
            test_code=test_code or "Not available",
        )

        try:
            response = await self.llm_client.generate(prompt)
            return self._parse_fix_response(response.content, analysis)
        except Exception as e:
            logger.error(f"Failed to generate fix with LLM: {e}")
            return self._generate_rule_based_fix(analysis, source_code, test_code)

    def _generate_rule_based_fix(
        self,
        analysis: FailureAnalysis,
        source_code: str,
        test_code: str,
    ) -> FixSuggestion | None:
        """Generate fix using rule-based approach."""
        failure = analysis.failure

        # Handle common patterns
        if failure.failure_type == FailureType.IMPORT:
            return self._fix_import_error(failure)

        elif failure.failure_type == FailureType.SYNTAX:
            return self._fix_syntax_error(failure, test_code)

        elif failure.failure_type == FailureType.FIXTURE:
            return self._fix_fixture_error(failure)

        elif failure.failure_type == FailureType.ASSERTION:
            return self._fix_assertion_error(failure, source_code, test_code)

        return None

    def _fix_import_error(self, failure: TestFailure) -> FixSuggestion | None:
        """Generate fix for import errors."""
        # Extract missing module name
        match = re.search(r"No module named\s+['\"]?(\w+)", failure.error_message)
        if not match:
            return None

        module_name = match.group(1)

        return FixSuggestion(
            file_path="requirements.txt",
            fix_type=FixType.INSERT,
            description=f"Add missing dependency: {module_name}",
            confidence=0.7,
            new_code=f"{module_name}>=0.1.0\n",
            requires_approval=True,
            is_auto_fixable=False,
            related_failure=failure.test_name,
        )

    def _fix_syntax_error(
        self, failure: TestFailure, test_code: str
    ) -> FixSuggestion | None:
        """Generate fix for syntax errors."""
        # Common syntax fixes
        if "unexpected indent" in failure.error_message.lower():
            return FixSuggestion(
                file_path=failure.test_file,
                fix_type=FixType.REFACTOR,
                description="Fix indentation error",
                confidence=0.6,
                requires_approval=True,
                is_auto_fixable=False,
                related_failure=failure.test_name,
            )

        return None

    def _fix_fixture_error(self, failure: TestFailure) -> FixSuggestion | None:
        """Generate fix for fixture errors."""
        # Extract fixture name
        match = re.search(r"fixture\s+['\"]?(\w+)", failure.error_message)
        if not match:
            return None

        fixture_name = match.group(1)

        # Suggest creating the fixture
        fixture_code = f'''
@pytest.fixture
def {fixture_name}():
    """Fixture for {fixture_name}."""
    # TODO: Implement fixture
    return None
'''

        return FixSuggestion(
            file_path=failure.test_file,
            fix_type=FixType.INSERT,
            description=f"Add missing fixture: {fixture_name}",
            confidence=0.8,
            new_code=fixture_code,
            requires_approval=True,
            is_auto_fixable=True,
            related_failure=failure.test_name,
        )

    def _fix_assertion_error(
        self,
        failure: TestFailure,
        source_code: str,
        test_code: str,
    ) -> FixSuggestion | None:
        """Generate fix for assertion errors."""
        # If we have expected/actual values, we can suggest updating test expectations
        if failure.expected_value and failure.actual_value:
            # Check if test expectation is wrong (source is correct)
            # This is a heuristic - in practice, need more context
            return FixSuggestion(
                file_path=failure.test_file,
                fix_type=FixType.REPLACE,
                description=f"Update test expectation from {failure.expected_value} to {failure.actual_value}",
                confidence=0.5,  # Low confidence - need human review
                old_code=failure.expected_value,
                new_code=failure.actual_value,
                requires_approval=True,
                is_auto_fixable=False,
                related_failure=failure.test_name,
            )

        return None

    def _parse_fix_response(
        self, response: str, analysis: FailureAnalysis
    ) -> FixSuggestion | None:
        """Parse LLM response into a FixSuggestion."""
        try:
            # Extract fix type
            fix_type_match = re.search(r"FIX_TYPE:\s*(\w+)", response, re.IGNORECASE)
            fix_target = fix_type_match.group(1).lower() if fix_type_match else "test"

            # Extract confidence
            conf_match = re.search(r"CONFIDENCE:\s*([\d.]+)", response)
            confidence = float(conf_match.group(1)) if conf_match else 0.5

            # Extract description
            desc_match = re.search(r"DESCRIPTION:\s*(.+?)(?:\n|OLD_CODE)", response, re.DOTALL)
            description = desc_match.group(1).strip() if desc_match else "LLM-generated fix"

            # Extract old/new code
            old_code_match = re.search(r"OLD_CODE:\s*```.*?\n(.*?)```", response, re.DOTALL)
            new_code_match = re.search(r"NEW_CODE:\s*```.*?\n(.*?)```", response, re.DOTALL)

            old_code = old_code_match.group(1).strip() if old_code_match else ""
            new_code = new_code_match.group(1).strip() if new_code_match else ""

            # Determine file to fix
            file_path = (
                analysis.failure.source_file or analysis.failure.test_file
                if fix_target == "source"
                else analysis.failure.test_file
            )

            return FixSuggestion(
                file_path=file_path,
                fix_type=FixType.REPLACE if old_code else FixType.INSERT,
                description=description,
                confidence=confidence,
                old_code=old_code,
                new_code=new_code,
                requires_approval=True,
                is_auto_fixable=confidence > 0.8,
                related_failure=analysis.failure.test_name,
            )

        except Exception as e:
            logger.error(f"Failed to parse LLM fix response: {e}")
            return None

    def _detect_language(self, file_path: str) -> str:
        """Detect language from file extension."""
        suffix = Path(file_path).suffix.lower()
        return {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".go": "go",
            ".java": "java",
        }.get(suffix, "python")


def apply_fix(fix: FixSuggestion, dry_run: bool = True) -> bool:
    """Apply a fix suggestion to the file.

    Args:
        fix: FixSuggestion to apply
        dry_run: If True, only show what would be changed

    Returns:
        True if fix was applied successfully
    """
    file_path = Path(fix.file_path)

    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return False

    try:
        content = file_path.read_text()

        if fix.fix_type == FixType.REPLACE:
            if fix.old_code not in content:
                logger.error(f"Old code not found in {file_path}")
                return False
            new_content = content.replace(fix.old_code, fix.new_code, 1)

        elif fix.fix_type == FixType.INSERT:
            if fix.start_line:
                lines = content.splitlines(keepends=True)
                lines.insert(fix.start_line - 1, fix.new_code + "\n")
                new_content = "".join(lines)
            else:
                new_content = content + "\n" + fix.new_code

        elif fix.fix_type == FixType.DELETE:
            new_content = content.replace(fix.old_code, "", 1)

        else:
            logger.error(f"Unsupported fix type: {fix.fix_type}")
            return False

        if dry_run:
            logger.info(f"Would apply fix to {file_path}")
            logger.info(fix.get_diff())
            return True

        # Write the fix
        file_path.write_text(new_content)
        logger.info(f"Applied fix to {file_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to apply fix: {e}")
        return False
