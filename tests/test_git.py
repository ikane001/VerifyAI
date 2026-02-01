"""Tests for git tracking and verification strategies."""

from pathlib import Path
import subprocess

import pytest

from verify_ai.git import (
    GitTracker,
    CommitInfo,
    FileChange,
    ChangeType,
    VerificationLevel,
    VerificationStrategy,
    get_strategy_for_trigger,
)
from verify_ai.git.strategy import (
    PUSH_STRATEGY,
    PR_STRATEGY,
    MERGE_STRATEGY,
    SCHEDULED_STRATEGY,
    ImpactAnalyzer,
)


@pytest.fixture
def verify_ai_repo():
    """Path to the verify-ai repo (which is a git repo)."""
    return Path(__file__).parent.parent


class TestGitTracker:
    """Tests for GitTracker."""

    def test_tracker_valid_repo(self, verify_ai_repo):
        """Test tracker with valid git repo."""
        tracker = GitTracker(verify_ai_repo)
        assert tracker.is_valid

    def test_tracker_invalid_repo(self, tmp_path):
        """Test tracker with non-git directory."""
        tracker = GitTracker(tmp_path)
        assert not tracker.is_valid

    def test_current_branch(self, verify_ai_repo):
        """Test getting current branch."""
        tracker = GitTracker(verify_ai_repo)
        branch = tracker.current_branch
        # Should be 'main' or some branch name
        assert branch is not None
        assert isinstance(branch, str)

    def test_head_commit(self, verify_ai_repo):
        """Test getting HEAD commit."""
        tracker = GitTracker(verify_ai_repo)
        commit = tracker.head_commit

        assert commit is not None
        assert isinstance(commit, CommitInfo)
        assert len(commit.sha) == 40
        assert len(commit.short_sha) == 7
        assert commit.message
        assert commit.author

    def test_get_uncommitted_changes(self, verify_ai_repo):
        """Test getting uncommitted changes."""
        tracker = GitTracker(verify_ai_repo)
        changes = tracker.get_uncommitted_changes()

        # May or may not have changes, just verify it returns a list
        assert isinstance(changes, list)
        for change in changes:
            assert isinstance(change, FileChange)

    def test_get_changes_in_commit(self, verify_ai_repo):
        """Test getting changes in a specific commit."""
        tracker = GitTracker(verify_ai_repo)

        # Get changes in HEAD
        changes = tracker.get_changes_in_commit("HEAD")

        assert isinstance(changes, list)
        for change in changes:
            assert isinstance(change, FileChange)
            assert change.path
            assert isinstance(change.change_type, ChangeType)

    def test_get_commits(self, verify_ai_repo):
        """Test getting commit history."""
        tracker = GitTracker(verify_ai_repo)
        commits = tracker.get_commits(max_count=5)

        assert isinstance(commits, list)
        assert len(commits) <= 5

        for commit in commits:
            assert isinstance(commit, CommitInfo)
            assert commit.sha
            assert commit.message


class TestFileChange:
    """Tests for FileChange."""

    def test_is_source_file(self):
        """Test source file detection."""
        assert FileChange(path="foo.py", change_type=ChangeType.MODIFIED).is_source_file
        assert FileChange(path="bar.js", change_type=ChangeType.ADDED).is_source_file
        assert FileChange(path="baz.go", change_type=ChangeType.MODIFIED).is_source_file
        assert not FileChange(path="readme.md", change_type=ChangeType.MODIFIED).is_source_file
        assert not FileChange(path="config.yaml", change_type=ChangeType.MODIFIED).is_source_file

    def test_is_test_file(self):
        """Test test file detection."""
        assert FileChange(path="test_foo.py", change_type=ChangeType.MODIFIED).is_test_file
        assert FileChange(path="tests/test_bar.py", change_type=ChangeType.MODIFIED).is_test_file
        assert FileChange(path="foo.spec.js", change_type=ChangeType.MODIFIED).is_test_file
        assert not FileChange(path="foo.py", change_type=ChangeType.MODIFIED).is_test_file


class TestVerificationStrategy:
    """Tests for verification strategies."""

    def test_push_strategy(self):
        """Test push strategy configuration."""
        strategy = PUSH_STRATEGY
        assert strategy.trigger == "push"
        assert strategy.level == VerificationLevel.QUICK
        assert strategy.config.verify_changed_files
        assert not strategy.config.verify_affected_files
        assert not strategy.config.generate_missing_tests
        assert strategy.config.fail_fast
        assert strategy.config.total_timeout == 120

    def test_pr_strategy(self):
        """Test PR strategy configuration."""
        strategy = PR_STRATEGY
        assert strategy.trigger == "pr"
        assert strategy.level == VerificationLevel.STANDARD
        assert strategy.config.verify_changed_files
        assert strategy.config.verify_affected_files
        assert strategy.config.generate_missing_tests
        assert not strategy.config.fail_fast
        assert strategy.config.block_on_failure

    def test_merge_strategy(self):
        """Test merge strategy configuration."""
        strategy = MERGE_STRATEGY
        assert strategy.trigger == "merge"
        assert strategy.level == VerificationLevel.FULL
        assert strategy.config.parallel_execution
        assert strategy.config.max_parallel_jobs == 8
        assert strategy.config.use_llm_for_fix_suggestions

    def test_scheduled_strategy(self):
        """Test scheduled strategy configuration."""
        strategy = SCHEDULED_STRATEGY
        assert strategy.trigger == "scheduled"
        assert strategy.level == VerificationLevel.COMPREHENSIVE
        assert strategy.config.verify_all_files
        assert strategy.config.regenerate_existing_tests
        assert strategy.config.max_tests_to_generate == 100

    def test_get_strategy_for_trigger(self):
        """Test getting strategy by trigger type."""
        assert get_strategy_for_trigger("push").trigger == "push"
        assert get_strategy_for_trigger("pr").trigger == "pr"
        assert get_strategy_for_trigger("merge").trigger == "merge"
        assert get_strategy_for_trigger("scheduled").trigger == "scheduled"
        assert get_strategy_for_trigger("manual").trigger == "manual"

        # Unknown trigger should return manual strategy
        assert get_strategy_for_trigger("unknown").trigger == "manual"  # type: ignore


class TestImpactAnalyzer:
    """Tests for ImpactAnalyzer."""

    def test_get_related_tests(self, verify_ai_repo):
        """Test finding related tests."""
        from verify_ai.core.scanner import ProjectScanner

        scanner = ProjectScanner(verify_ai_repo)
        info = scanner.scan()

        analyzer = ImpactAnalyzer(info)

        # Find tests related to scanner.py
        related = analyzer.get_related_tests(["src/verify_ai/core/scanner.py"])

        # Should find test_scanner.py
        assert any("scanner" in t.lower() for t in related)
