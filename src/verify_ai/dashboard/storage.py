"""SQLite storage for Dashboard data."""

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from verify_ai.dashboard.models import (
    CoverageTrend,
    DashboardStats,
    TestRun,
    TestRunStatus,
)


class DashboardStorage:
    """SQLite-based storage for dashboard data."""
    
    DEFAULT_DB_PATH = Path.home() / ".verify-ai" / "dashboard.db"
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize storage.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path or self.DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_runs (
                    id TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    total_tests INTEGER DEFAULT 0,
                    passed_tests INTEGER DEFAULT 0,
                    failed_tests INTEGER DEFAULT 0,
                    skipped_tests INTEGER DEFAULT 0,
                    coverage_percent REAL,
                    covered_lines INTEGER DEFAULT 0,
                    total_lines INTEGER DEFAULT 0,
                    commit_sha TEXT,
                    branch TEXT,
                    duration_seconds REAL DEFAULT 0,
                    error_message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS coverage_trends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_path TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    coverage_percent REAL NOT NULL,
                    total_lines INTEGER NOT NULL,
                    covered_lines INTEGER NOT NULL,
                    commit_sha TEXT
                )
            """)
            
            # Create indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_test_runs_project
                ON test_runs(project_path, timestamp DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_coverage_trends_project
                ON coverage_trends(project_path, timestamp DESC)
            """)
            
            conn.commit()
    
    def save_test_run(self, run: TestRun) -> str:
        """Save a test run record.
        
        Args:
            run: TestRun to save
            
        Returns:
            ID of saved record
        """
        if not run.id:
            run.id = str(uuid.uuid4())
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO test_runs (
                    id, project_path, timestamp, status, trigger,
                    total_tests, passed_tests, failed_tests, skipped_tests,
                    coverage_percent, covered_lines, total_lines,
                    commit_sha, branch, duration_seconds, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run.id,
                run.project_path,
                run.timestamp.isoformat(),
                run.status.value,
                run.trigger,
                run.total_tests,
                run.passed_tests,
                run.failed_tests,
                run.skipped_tests,
                run.coverage_percent,
                run.covered_lines,
                run.total_lines,
                run.commit_sha,
                run.branch,
                run.duration_seconds,
                run.error_message,
            ))
            conn.commit()
        
        return run.id
    
    def get_test_runs(
        self,
        project_path: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TestRun]:
        """Get test runs for a project.
        
        Args:
            project_path: Project path to filter by
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of TestRun records
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM test_runs
                WHERE project_path = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """, (project_path, limit, offset))
            
            runs = []
            for row in cursor:
                runs.append(TestRun(
                    id=row["id"],
                    project_path=row["project_path"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    status=TestRunStatus(row["status"]),
                    trigger=row["trigger"],
                    total_tests=row["total_tests"],
                    passed_tests=row["passed_tests"],
                    failed_tests=row["failed_tests"],
                    skipped_tests=row["skipped_tests"],
                    coverage_percent=row["coverage_percent"],
                    covered_lines=row["covered_lines"],
                    total_lines=row["total_lines"],
                    commit_sha=row["commit_sha"],
                    branch=row["branch"],
                    duration_seconds=row["duration_seconds"],
                    error_message=row["error_message"],
                ))
            
            return runs
    
    def get_test_run(self, run_id: str) -> Optional[TestRun]:
        """Get a specific test run by ID.
        
        Args:
            run_id: Test run ID
            
        Returns:
            TestRun or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM test_runs WHERE id = ?",
                (run_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return TestRun(
                    id=row["id"],
                    project_path=row["project_path"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    status=TestRunStatus(row["status"]),
                    trigger=row["trigger"],
                    total_tests=row["total_tests"],
                    passed_tests=row["passed_tests"],
                    failed_tests=row["failed_tests"],
                    skipped_tests=row["skipped_tests"],
                    coverage_percent=row["coverage_percent"],
                    covered_lines=row["covered_lines"],
                    total_lines=row["total_lines"],
                    commit_sha=row["commit_sha"],
                    branch=row["branch"],
                    duration_seconds=row["duration_seconds"],
                    error_message=row["error_message"],
                )
            return None
    
    def save_coverage_trend(self, project_path: str, trend: CoverageTrend):
        """Save a coverage trend data point.
        
        Args:
            project_path: Project path
            trend: Coverage trend data
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO coverage_trends (
                    project_path, timestamp, coverage_percent,
                    total_lines, covered_lines, commit_sha
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                project_path,
                trend.timestamp.isoformat(),
                trend.coverage_percent,
                trend.total_lines,
                trend.covered_lines,
                trend.commit_sha,
            ))
            conn.commit()
    
    def get_coverage_trends(
        self,
        project_path: str,
        days: int = 30,
    ) -> list[CoverageTrend]:
        """Get coverage trend data.
        
        Args:
            project_path: Project path to filter by
            days: Number of days of history
            
        Returns:
            List of CoverageTrend records
        """
        since = datetime.now() - timedelta(days=days)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM coverage_trends
                WHERE project_path = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            """, (project_path, since.isoformat()))
            
            trends = []
            for row in cursor:
                trends.append(CoverageTrend(
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    coverage_percent=row["coverage_percent"],
                    total_lines=row["total_lines"],
                    covered_lines=row["covered_lines"],
                    commit_sha=row["commit_sha"],
                ))
            
            return trends
    
    def get_stats(self, project_path: str) -> DashboardStats:
        """Get dashboard statistics for a project.
        
        Args:
            project_path: Project path
            
        Returns:
            DashboardStats
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Get total runs and status counts
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) as passed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    AVG(duration_seconds) as avg_duration,
                    AVG(CASE WHEN total_tests > 0 
                        THEN (passed_tests * 100.0 / total_tests) 
                        ELSE 0 END) as avg_pass_rate
                FROM test_runs
                WHERE project_path = ?
            """, (project_path,))
            
            stats_row = cursor.fetchone()
            
            # Get latest run
            cursor = conn.execute("""
                SELECT timestamp, status, coverage_percent
                FROM test_runs
                WHERE project_path = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (project_path,))
            
            last_run_row = cursor.fetchone()
            
            # Get coverage trend
            cursor = conn.execute("""
                SELECT coverage_percent
                FROM coverage_trends
                WHERE project_path = ?
                ORDER BY timestamp DESC
                LIMIT 2
            """, (project_path,))
            
            coverage_rows = cursor.fetchall()
            
            # Determine trend direction
            coverage_trend = "stable"
            current_coverage = 0.0
            
            if coverage_rows:
                current_coverage = coverage_rows[0]["coverage_percent"]
                if len(coverage_rows) > 1:
                    prev_coverage = coverage_rows[1]["coverage_percent"]
                    if current_coverage > prev_coverage + 1:
                        coverage_trend = "up"
                    elif current_coverage < prev_coverage - 1:
                        coverage_trend = "down"
            
            return DashboardStats(
                project_path=project_path,
                total_test_runs=stats_row["total"] or 0,
                successful_runs=stats_row["passed"] or 0,
                failed_runs=stats_row["failed"] or 0,
                current_coverage=current_coverage,
                coverage_trend=coverage_trend,
                last_run_timestamp=(
                    datetime.fromisoformat(last_run_row["timestamp"])
                    if last_run_row else None
                ),
                last_run_status=(
                    TestRunStatus(last_run_row["status"])
                    if last_run_row else None
                ),
                avg_duration_seconds=stats_row["avg_duration"] or 0.0,
                avg_pass_rate=stats_row["avg_pass_rate"] or 0.0,
            )
    
    def cleanup_old_data(self, days: int = 90):
        """Remove data older than specified days.
        
        Args:
            days: Number of days to retain
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM test_runs WHERE timestamp < ?",
                (cutoff.isoformat(),)
            )
            conn.execute(
                "DELETE FROM coverage_trends WHERE timestamp < ?",
                (cutoff.isoformat(),)
            )
            conn.commit()
