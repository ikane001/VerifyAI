"""Tests for dashboard module."""

import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from verify_ai.dashboard.models import (
    CoverageTrend,
    DashboardStats,
    TestRun,
    TestRunStatus,
    CommitTestResult,
    FileTestInfo,
)
from verify_ai.dashboard.storage import DashboardStorage


class TestTestRunStatus:
    """Tests for TestRunStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert TestRunStatus.PENDING.value == "pending"
        assert TestRunStatus.RUNNING.value == "running"
        assert TestRunStatus.PASSED.value == "passed"
        assert TestRunStatus.FAILED.value == "failed"
        assert TestRunStatus.ERROR.value == "error"


class TestTestRun:
    """Tests for TestRun model."""

    def test_create_test_run(self):
        """Test creating a test run."""
        run = TestRun(
            id="test-123",
            project_path="/project",
            timestamp=datetime.now(),
            status=TestRunStatus.PASSED,
            trigger="push",
            total_tests=100,
            passed_tests=95,
            failed_tests=5,
        )
        assert run.id == "test-123"
        assert run.status == TestRunStatus.PASSED
        assert run.pass_rate == 95.0

    def test_pass_rate_zero_tests(self):
        """Test pass rate with zero tests."""
        run = TestRun(
            id="test-123",
            project_path="/project",
            timestamp=datetime.now(),
            status=TestRunStatus.PASSED,
            trigger="manual",
            total_tests=0,
        )
        assert run.pass_rate == 0.0

    def test_to_dict(self):
        """Test converting to dictionary."""
        run = TestRun(
            id="test-123",
            project_path="/project",
            timestamp=datetime(2024, 1, 15, 10, 30),
            status=TestRunStatus.PASSED,
            trigger="pr",
            total_tests=50,
            passed_tests=48,
            failed_tests=2,
            coverage_percent=85.5,
        )
        data = run.to_dict()
        
        assert data["id"] == "test-123"
        assert data["status"] == "passed"
        assert data["trigger"] == "pr"
        assert data["pass_rate"] == 96.0

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "id": "test-456",
            "project_path": "/project",
            "timestamp": "2024-01-15T10:30:00",
            "status": "failed",
            "trigger": "merge",
            "total_tests": 100,
            "passed_tests": 80,
            "failed_tests": 20,
        }
        run = TestRun.from_dict(data)
        
        assert run.id == "test-456"
        assert run.status == TestRunStatus.FAILED
        assert run.pass_rate == 80.0


class TestCoverageTrend:
    """Tests for CoverageTrend model."""

    def test_create_coverage_trend(self):
        """Test creating coverage trend."""
        trend = CoverageTrend(
            timestamp=datetime.now(),
            coverage_percent=85.5,
            total_lines=1000,
            covered_lines=855,
            commit_sha="abc123",
        )
        assert trend.coverage_percent == 85.5
        assert trend.commit_sha == "abc123"

    def test_to_dict(self):
        """Test converting to dictionary."""
        trend = CoverageTrend(
            timestamp=datetime(2024, 1, 15, 10, 0),
            coverage_percent=75.0,
            total_lines=500,
            covered_lines=375,
        )
        data = trend.to_dict()
        
        assert data["coverage_percent"] == 75.0
        assert data["total_lines"] == 500
        assert "timestamp" in data


class TestDashboardStats:
    """Tests for DashboardStats model."""

    def test_create_stats(self):
        """Test creating dashboard stats."""
        stats = DashboardStats(
            project_path="/project",
            total_test_runs=100,
            successful_runs=90,
            failed_runs=10,
            current_coverage=85.0,
        )
        assert stats.total_test_runs == 100
        assert stats.current_coverage == 85.0

    def test_to_dict(self):
        """Test converting to dictionary."""
        stats = DashboardStats(
            project_path="/project",
            total_test_runs=50,
            successful_runs=45,
            failed_runs=5,
        )
        data = stats.to_dict()
        
        assert data["total_test_runs"] == 50
        assert data["success_rate"] == 90.0


class TestCommitTestResult:
    """Tests for CommitTestResult model."""

    def test_create_commit_result(self):
        """Test creating commit test result."""
        result = CommitTestResult(
            commit_sha="abc123def456",
            commit_message="Fix bug in parser",
            author="Developer",
            timestamp=datetime.now(),
            test_status=TestRunStatus.PASSED,
            coverage_percent=88.5,
        )
        assert result.commit_sha == "abc123def456"
        assert result.test_status == TestRunStatus.PASSED

    def test_to_dict(self):
        """Test converting to dictionary."""
        result = CommitTestResult(
            commit_sha="abc123",
            commit_message="Add feature",
            author="Dev",
            timestamp=datetime(2024, 1, 15, 10, 0),
            test_status=TestRunStatus.FAILED,
        )
        data = result.to_dict()
        
        assert data["commit_sha"] == "abc123"
        assert data["test_status"] == "failed"


class TestFileTestInfo:
    """Tests for FileTestInfo model."""

    def test_create_file_info(self):
        """Test creating file test info."""
        info = FileTestInfo(
            file_path="src/module.py",
            has_tests=True,
            test_count=5,
            coverage_percent=90.0,
        )
        assert info.file_path == "src/module.py"
        assert info.has_tests is True

    def test_to_dict(self):
        """Test converting to dictionary."""
        info = FileTestInfo(
            file_path="src/other.py",
            has_tests=False,
            test_count=0,
        )
        data = info.to_dict()
        
        assert data["file_path"] == "src/other.py"
        assert data["has_tests"] is False


class TestDashboardStorage:
    """Tests for DashboardStorage."""

    @pytest.fixture
    def storage(self):
        """Create temporary storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_dashboard.db"
            yield DashboardStorage(db_path=db_path)

    def test_create_storage(self, storage):
        """Test creating storage."""
        assert storage.db_path.exists()

    def test_save_and_get_test_run(self, storage):
        """Test saving and retrieving test run."""
        run = TestRun(
            id=str(uuid.uuid4()),
            project_path="/test/project",
            timestamp=datetime.now(),
            status=TestRunStatus.PASSED,
            trigger="push",
            total_tests=50,
            passed_tests=48,
            failed_tests=2,
        )
        
        saved_id = storage.save_test_run(run)
        assert saved_id == run.id
        
        retrieved = storage.get_test_run(run.id)
        assert retrieved is not None
        assert retrieved.id == run.id
        assert retrieved.status == TestRunStatus.PASSED
        assert retrieved.total_tests == 50

    def test_get_test_runs(self, storage):
        """Test getting multiple test runs."""
        project = "/test/project"
        
        # Save multiple runs
        for i in range(5):
            run = TestRun(
                id=str(uuid.uuid4()),
                project_path=project,
                timestamp=datetime.now() - timedelta(hours=i),
                status=TestRunStatus.PASSED if i % 2 == 0 else TestRunStatus.FAILED,
                trigger="push",
            )
            storage.save_test_run(run)
        
        # Get runs
        runs = storage.get_test_runs(project, limit=10)
        assert len(runs) == 5
        
        # Should be ordered by timestamp DESC
        assert runs[0].timestamp > runs[-1].timestamp

    def test_get_test_runs_with_limit(self, storage):
        """Test getting test runs with limit."""
        project = "/test/project"
        
        for i in range(10):
            run = TestRun(
                id=str(uuid.uuid4()),
                project_path=project,
                timestamp=datetime.now(),
                status=TestRunStatus.PASSED,
                trigger="push",
            )
            storage.save_test_run(run)
        
        runs = storage.get_test_runs(project, limit=3)
        assert len(runs) == 3

    def test_save_and_get_coverage_trend(self, storage):
        """Test saving and retrieving coverage trends."""
        project = "/test/project"
        
        # Save trends
        for i in range(7):
            trend = CoverageTrend(
                timestamp=datetime.now() - timedelta(days=i),
                coverage_percent=80.0 + i,
                total_lines=1000,
                covered_lines=800 + i * 10,
            )
            storage.save_coverage_trend(project, trend)
        
        # Get trends
        trends = storage.get_coverage_trends(project, days=30)
        assert len(trends) == 7

    def test_get_stats(self, storage):
        """Test getting dashboard stats."""
        project = "/test/project"
        
        # Save some runs
        for status in [TestRunStatus.PASSED, TestRunStatus.PASSED, TestRunStatus.FAILED]:
            run = TestRun(
                id=str(uuid.uuid4()),
                project_path=project,
                timestamp=datetime.now(),
                status=status,
                trigger="push",
                duration_seconds=10.0,
                total_tests=10,
                passed_tests=8,
            )
            storage.save_test_run(run)
        
        # Save coverage trend
        trend = CoverageTrend(
            timestamp=datetime.now(),
            coverage_percent=85.0,
            total_lines=1000,
            covered_lines=850,
        )
        storage.save_coverage_trend(project, trend)
        
        # Get stats
        stats = storage.get_stats(project)
        assert stats.total_test_runs == 3
        assert stats.successful_runs == 2
        assert stats.failed_runs == 1
        assert stats.current_coverage == 85.0

    def test_cleanup_old_data(self, storage):
        """Test cleaning up old data."""
        project = "/test/project"
        
        # Save old runs
        old_run = TestRun(
            id=str(uuid.uuid4()),
            project_path=project,
            timestamp=datetime.now() - timedelta(days=100),
            status=TestRunStatus.PASSED,
            trigger="push",
        )
        storage.save_test_run(old_run)
        
        # Save recent run
        recent_run = TestRun(
            id=str(uuid.uuid4()),
            project_path=project,
            timestamp=datetime.now(),
            status=TestRunStatus.PASSED,
            trigger="push",
        )
        storage.save_test_run(recent_run)
        
        # Cleanup old data
        storage.cleanup_old_data(days=30)
        
        # Old run should be gone
        assert storage.get_test_run(old_run.id) is None
        
        # Recent run should still exist
        assert storage.get_test_run(recent_run.id) is not None

    def test_get_nonexistent_run(self, storage):
        """Test getting a non-existent test run."""
        run = storage.get_test_run("nonexistent-id")
        assert run is None

    def test_stats_empty_project(self, storage):
        """Test stats for project with no data."""
        stats = storage.get_stats("/empty/project")
        
        assert stats.total_test_runs == 0
        assert stats.successful_runs == 0
        assert stats.current_coverage == 0.0
