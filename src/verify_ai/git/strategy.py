"""Verification strategies for different trigger types."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal
import logging

logger = logging.getLogger(__name__)


class VerificationLevel(Enum):
    """Level of verification to perform."""

    # Quick checks - fast, for every push
    QUICK = "quick"

    # Standard checks - for PRs
    STANDARD = "standard"

    # Full checks - for merges to main
    FULL = "full"

    # Comprehensive - scheduled, includes all tests
    COMPREHENSIVE = "comprehensive"


TriggerType = Literal["push", "pr", "merge", "scheduled", "manual"]


@dataclass
class VerificationConfig:
    """Configuration for a verification run."""

    # What to verify
    verify_changed_files: bool = True
    verify_affected_files: bool = False  # Files that import changed files
    verify_all_files: bool = False

    # Test generation
    generate_missing_tests: bool = True
    regenerate_existing_tests: bool = False
    max_tests_to_generate: int = 50

    # Test execution
    run_existing_tests: bool = True
    run_generated_tests: bool = True
    fail_fast: bool = True
    parallel_execution: bool = True
    max_parallel_jobs: int = 4

    # Reporting
    detailed_report: bool = False
    create_pr_comment: bool = False
    block_on_failure: bool = False

    # Timeouts (seconds)
    total_timeout: int = 600  # 10 minutes
    per_test_timeout: int = 60

    # LLM usage
    use_llm_for_analysis: bool = True
    use_llm_for_fix_suggestions: bool = False


@dataclass
class VerificationStrategy:
    """Strategy for verification based on trigger type."""

    trigger: TriggerType
    level: VerificationLevel
    config: VerificationConfig
    description: str = ""

    # Files to verify
    file_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)

    # Priority settings
    priority: int = 0  # Higher = more important
    can_skip_if_no_changes: bool = True


# Pre-defined strategies
PUSH_STRATEGY = VerificationStrategy(
    trigger="push",
    level=VerificationLevel.QUICK,
    description="Quick verification on every push",
    config=VerificationConfig(
        verify_changed_files=True,
        verify_affected_files=False,
        generate_missing_tests=False,  # Don't generate tests on push
        regenerate_existing_tests=False,
        run_existing_tests=True,
        run_generated_tests=False,
        fail_fast=True,
        detailed_report=False,
        block_on_failure=False,
        total_timeout=120,  # 2 minutes
        use_llm_for_analysis=False,  # Skip LLM for speed
    ),
    priority=1,
    can_skip_if_no_changes=True,
)

PR_STRATEGY = VerificationStrategy(
    trigger="pr",
    level=VerificationLevel.STANDARD,
    description="Standard verification for pull requests",
    config=VerificationConfig(
        verify_changed_files=True,
        verify_affected_files=True,  # Also check affected files
        generate_missing_tests=True,
        regenerate_existing_tests=False,
        max_tests_to_generate=20,
        run_existing_tests=True,
        run_generated_tests=True,
        fail_fast=False,  # Run all tests to see full picture
        detailed_report=True,
        create_pr_comment=True,
        block_on_failure=True,
        total_timeout=300,  # 5 minutes
        use_llm_for_analysis=True,
        use_llm_for_fix_suggestions=True,
    ),
    priority=2,
    can_skip_if_no_changes=False,
)

MERGE_STRATEGY = VerificationStrategy(
    trigger="merge",
    level=VerificationLevel.FULL,
    description="Full verification before merge to main",
    config=VerificationConfig(
        verify_changed_files=True,
        verify_affected_files=True,
        verify_all_files=False,
        generate_missing_tests=True,
        regenerate_existing_tests=False,
        max_tests_to_generate=50,
        run_existing_tests=True,
        run_generated_tests=True,
        fail_fast=False,
        parallel_execution=True,
        max_parallel_jobs=8,
        detailed_report=True,
        create_pr_comment=True,
        block_on_failure=True,
        total_timeout=600,  # 10 minutes
        use_llm_for_analysis=True,
        use_llm_for_fix_suggestions=True,
    ),
    priority=3,
    can_skip_if_no_changes=False,
)

SCHEDULED_STRATEGY = VerificationStrategy(
    trigger="scheduled",
    level=VerificationLevel.COMPREHENSIVE,
    description="Comprehensive verification on schedule",
    config=VerificationConfig(
        verify_changed_files=False,
        verify_affected_files=False,
        verify_all_files=True,  # Verify everything
        generate_missing_tests=True,
        regenerate_existing_tests=True,  # Regenerate outdated tests
        max_tests_to_generate=100,
        run_existing_tests=True,
        run_generated_tests=True,
        fail_fast=False,
        parallel_execution=True,
        max_parallel_jobs=16,
        detailed_report=True,
        create_pr_comment=False,
        block_on_failure=False,
        total_timeout=3600,  # 1 hour
        use_llm_for_analysis=True,
        use_llm_for_fix_suggestions=True,
    ),
    priority=4,
    can_skip_if_no_changes=False,
)

MANUAL_STRATEGY = VerificationStrategy(
    trigger="manual",
    level=VerificationLevel.STANDARD,
    description="Manual verification triggered by user",
    config=VerificationConfig(
        verify_changed_files=True,
        verify_affected_files=True,
        generate_missing_tests=True,
        run_existing_tests=True,
        run_generated_tests=True,
        fail_fast=False,
        detailed_report=True,
        total_timeout=600,
        use_llm_for_analysis=True,
        use_llm_for_fix_suggestions=True,
    ),
    priority=2,
    can_skip_if_no_changes=False,
)


def get_strategy_for_trigger(trigger: TriggerType) -> VerificationStrategy:
    """Get the appropriate strategy for a trigger type.

    Args:
        trigger: Type of trigger (push, pr, merge, scheduled, manual)

    Returns:
        VerificationStrategy for the trigger
    """
    strategies = {
        "push": PUSH_STRATEGY,
        "pr": PR_STRATEGY,
        "merge": MERGE_STRATEGY,
        "scheduled": SCHEDULED_STRATEGY,
        "manual": MANUAL_STRATEGY,
    }

    return strategies.get(trigger, MANUAL_STRATEGY)


@dataclass
class AffectedFilesAnalysis:
    """Analysis of files affected by changes."""

    # Directly changed files
    changed_files: list[str] = field(default_factory=list)

    # Files that import changed files
    affected_files: list[str] = field(default_factory=list)

    # Test files for changed functions
    related_tests: list[str] = field(default_factory=list)

    # Changed functions/classes
    changed_entities: list[dict] = field(default_factory=list)


class ImpactAnalyzer:
    """Analyze the impact of code changes."""

    def __init__(self, project_info):
        """Initialize with project info.

        Args:
            project_info: ProjectInfo from scanner
        """
        self.project_info = project_info
        self._build_dependency_graph()

    def _build_dependency_graph(self):
        """Build reverse dependency graph."""
        # Map: module -> files that depend on it
        self.reverse_deps: dict[str, set[str]] = {}

        for file_path, dep_info in self.project_info.dependencies.items():
            for dep in dep_info.dependencies:
                if dep not in self.reverse_deps:
                    self.reverse_deps[dep] = set()
                self.reverse_deps[dep].add(file_path)

    def get_affected_files(self, changed_files: list[str]) -> list[str]:
        """Get files that may be affected by changes.

        Args:
            changed_files: List of changed file paths

        Returns:
            List of affected file paths
        """
        affected = set()

        for file_path in changed_files:
            # Get module name from file path
            module = self._file_to_module(file_path)
            if module:
                # Find files that depend on this module
                if module in self.reverse_deps:
                    affected.update(self.reverse_deps[module])

        # Remove the original changed files
        affected -= set(changed_files)

        return list(affected)

    def _file_to_module(self, file_path: str) -> str | None:
        """Convert file path to module name."""
        from pathlib import Path

        path = Path(file_path)

        # Remove extension
        if path.suffix in (".py", ".js", ".ts", ".go", ".java"):
            name = path.stem
            # Remove common prefixes
            if name in ("__init__", "index", "main"):
                return path.parent.name
            return name

        return None

    def get_related_tests(self, changed_files: list[str]) -> list[str]:
        """Find test files related to changed files.

        Args:
            changed_files: List of changed file paths

        Returns:
            List of related test file paths
        """
        related_tests = set()

        for file_path in changed_files:
            from pathlib import Path
            path = Path(file_path)
            name = path.stem

            # Look for test files with matching names
            for test_file in self.project_info.test_files:
                test_name = test_file.stem.lower()
                if name.lower() in test_name:
                    related_tests.add(str(test_file))

        return list(related_tests)

    def analyze(self, changed_files: list[str]) -> AffectedFilesAnalysis:
        """Perform full impact analysis.

        Args:
            changed_files: List of changed file paths

        Returns:
            AffectedFilesAnalysis with all affected entities
        """
        return AffectedFilesAnalysis(
            changed_files=changed_files,
            affected_files=self.get_affected_files(changed_files),
            related_tests=self.get_related_tests(changed_files),
        )
