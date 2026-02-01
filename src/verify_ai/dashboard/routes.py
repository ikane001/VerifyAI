"""Dashboard API routes."""

from pathlib import Path
from typing import Optional

# Try to import FastAPI, but make it optional
try:
    from fastapi import APIRouter, HTTPException, Query
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    APIRouter = None

from verify_ai.dashboard.models import TestRunStatus
from verify_ai.dashboard.storage import DashboardStorage


def create_dashboard_router(
    storage: Optional[DashboardStorage] = None,
    default_project: Optional[str] = None,
) -> "APIRouter":
    """Create FastAPI router for dashboard endpoints.
    
    Args:
        storage: DashboardStorage instance
        default_project: Default project path
        
    Returns:
        FastAPI APIRouter
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI not installed")
    
    router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
    
    _storage = storage or DashboardStorage()
    _default_project = default_project or str(Path.cwd())
    
    @router.get("/stats")
    async def get_stats(project: str = Query(default=None)):
        """Get dashboard statistics for a project."""
        project_path = project or _default_project
        
        try:
            stats = _storage.get_stats(project_path)
            return stats.to_dict()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/coverage/trend")
    async def get_coverage_trend(
        project: str = Query(default=None),
        days: int = Query(default=30, ge=1, le=365),
    ):
        """Get coverage trend data."""
        project_path = project or _default_project
        
        try:
            trends = _storage.get_coverage_trends(project_path, days=days)
            return {
                "project": project_path,
                "days": days,
                "data_points": len(trends),
                "trends": [t.to_dict() for t in trends],
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/tests/history")
    async def get_test_history(
        project: str = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ):
        """Get test execution history."""
        project_path = project or _default_project
        
        try:
            runs = _storage.get_test_runs(project_path, limit=limit, offset=offset)
            return {
                "project": project_path,
                "total": len(runs),
                "runs": [r.to_dict() for r in runs],
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/tests/{run_id}")
    async def get_test_run(run_id: str):
        """Get details of a specific test run."""
        try:
            run = _storage.get_test_run(run_id)
            if run is None:
                raise HTTPException(status_code=404, detail="Test run not found")
            return run.to_dict()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/commits")
    async def get_commits_with_tests(
        project: str = Query(default=None),
        limit: int = Query(default=20, ge=1, le=100),
    ):
        """Get commits with their associated test results."""
        project_path = project or _default_project
        
        try:
            # Get test runs grouped by commit
            runs = _storage.get_test_runs(project_path, limit=limit * 2)
            
            # Group by commit
            commits = {}
            for run in runs:
                if run.commit_sha and run.commit_sha not in commits:
                    commits[run.commit_sha] = {
                        "commit_sha": run.commit_sha,
                        "branch": run.branch,
                        "timestamp": run.timestamp.isoformat(),
                        "test_status": run.status.value,
                        "coverage_percent": run.coverage_percent,
                        "passed_tests": run.passed_tests,
                        "failed_tests": run.failed_tests,
                    }
            
            return {
                "project": project_path,
                "commits": list(commits.values())[:limit],
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/summary")
    async def get_summary(project: str = Query(default=None)):
        """Get a quick summary for the dashboard home."""
        project_path = project or _default_project
        
        try:
            stats = _storage.get_stats(project_path)
            trends = _storage.get_coverage_trends(project_path, days=7)
            recent_runs = _storage.get_test_runs(project_path, limit=5)
            
            return {
                "project": project_path,
                "stats": stats.to_dict(),
                "recent_coverage": [t.to_dict() for t in trends[-7:]],
                "recent_runs": [r.to_dict() for r in recent_runs],
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return router
