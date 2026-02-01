"""Data models for Dashboard."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TestRunStatus(Enum):
    """Status of a test run."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


@dataclass
class TestRun:
    """Record of a test execution."""
    
    id: str
    project_path: str
    timestamp: datetime
    status: TestRunStatus
    trigger: str  # push, pr, merge, manual, scheduled
    
    # Test results
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    
    # Coverage data
    coverage_percent: Optional[float] = None
    covered_lines: int = 0
    total_lines: int = 0
    
    # Git info
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    
    # Execution details
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    
    @property
    def pass_rate(self) -> float:
        """Calculate test pass rate."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "project_path": self.project_path,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "trigger": self.trigger,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "skipped_tests": self.skipped_tests,
            "coverage_percent": self.coverage_percent,
            "covered_lines": self.covered_lines,
            "total_lines": self.total_lines,
            "commit_sha": self.commit_sha,
            "branch": self.branch,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "pass_rate": self.pass_rate,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TestRun":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            project_path=data["project_path"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            status=TestRunStatus(data["status"]),
            trigger=data["trigger"],
            total_tests=data.get("total_tests", 0),
            passed_tests=data.get("passed_tests", 0),
            failed_tests=data.get("failed_tests", 0),
            skipped_tests=data.get("skipped_tests", 0),
            coverage_percent=data.get("coverage_percent"),
            covered_lines=data.get("covered_lines", 0),
            total_lines=data.get("total_lines", 0),
            commit_sha=data.get("commit_sha"),
            branch=data.get("branch"),
            duration_seconds=data.get("duration_seconds", 0.0),
            error_message=data.get("error_message"),
        )


@dataclass
class CoverageTrend:
    """Coverage trend data point."""
    
    timestamp: datetime
    coverage_percent: float
    total_lines: int
    covered_lines: int
    commit_sha: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "coverage_percent": self.coverage_percent,
            "total_lines": self.total_lines,
            "covered_lines": self.covered_lines,
            "commit_sha": self.commit_sha,
        }


@dataclass
class DashboardStats:
    """Dashboard statistics summary."""
    
    project_path: str
    last_updated: datetime = field(default_factory=datetime.now)
    
    # Test stats
    total_test_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    
    # Current coverage
    current_coverage: float = 0.0
    coverage_trend: str = "stable"  # up, down, stable
    
    # Recent activity
    last_run_timestamp: Optional[datetime] = None
    last_run_status: Optional[TestRunStatus] = None
    
    # Averages
    avg_duration_seconds: float = 0.0
    avg_pass_rate: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "project_path": self.project_path,
            "last_updated": self.last_updated.isoformat(),
            "total_test_runs": self.total_test_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "success_rate": (
                (self.successful_runs / self.total_test_runs * 100)
                if self.total_test_runs > 0 else 0.0
            ),
            "current_coverage": self.current_coverage,
            "coverage_trend": self.coverage_trend,
            "last_run_timestamp": (
                self.last_run_timestamp.isoformat()
                if self.last_run_timestamp else None
            ),
            "last_run_status": (
                self.last_run_status.value
                if self.last_run_status else None
            ),
            "avg_duration_seconds": self.avg_duration_seconds,
            "avg_pass_rate": self.avg_pass_rate,
        }


@dataclass
class CommitTestResult:
    """Test result associated with a commit."""
    
    commit_sha: str
    commit_message: str
    author: str
    timestamp: datetime
    
    test_status: TestRunStatus
    coverage_percent: Optional[float] = None
    passed_tests: int = 0
    failed_tests: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "commit_sha": self.commit_sha,
            "commit_message": self.commit_message,
            "author": self.author,
            "timestamp": self.timestamp.isoformat(),
            "test_status": self.test_status.value,
            "coverage_percent": self.coverage_percent,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
        }


@dataclass 
class FileTestInfo:
    """Test information for a file."""
    
    file_path: str
    has_tests: bool
    test_count: int = 0
    coverage_percent: Optional[float] = None
    last_tested: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "has_tests": self.has_tests,
            "test_count": self.test_count,
            "coverage_percent": self.coverage_percent,
            "last_tested": self.last_tested.isoformat() if self.last_tested else None,
        }
