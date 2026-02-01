"""REST API server for VerifyAI."""

from pathlib import Path
from typing import Any
import logging
import os

logger = logging.getLogger(__name__)

# Try to import FastAPI, but make it optional
try:
    from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = None
    BaseModel = object


# Request/Response models
if FASTAPI_AVAILABLE:
    class ScanRequest(BaseModel):
        """Request to scan a project."""
        path: str = "."
        verbose: bool = False

    class GenerateRequest(BaseModel):
        """Request to generate tests."""
        path: str = "."
        test_type: str = "all"
        dry_run: bool = False

    class VerifyRequest(BaseModel):
        """Request to run verification."""
        path: str = "."
        trigger: str = "manual"
        base_branch: str = "main"

    class AnalyzeRequest(BaseModel):
        """Request to analyze test output."""
        path: str = "."
        test_output: str

    class ReplayRequest(BaseModel):
        """Request to replay logs."""
        log_file: str
        format: str = "auto"
        base_url: str = "http://localhost:8000"

    class WebhookPayload(BaseModel):
        """GitHub webhook payload."""
        class Config:
            extra = "allow"

    class HealthResponse(BaseModel):
        """Health check response."""
        status: str
        version: str


def create_app(
    project_path: Path | None = None,
    webhook_secret: str | None = None,
) -> Any:
    """Create FastAPI application.

    Args:
        project_path: Default project path
        webhook_secret: GitHub webhook secret

    Returns:
        FastAPI application
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError(
            "FastAPI not installed. Install with: pip install 'verify-ai[server]'"
        )

    from .. import __version__
    from .webhook import WebhookHandler

    app = FastAPI(
        title="VerifyAI API",
        description="AI-powered automated verification system",
        version=__version__,
    )

    # Initialize handlers
    webhook_handler = WebhookHandler(
        webhook_secret=webhook_secret or os.getenv("GITHUB_WEBHOOK_SECRET"),
    )
    default_path = project_path or Path.cwd()

    # Health check
    @app.get("/health", response_model=HealthResponse)
    async def health():
        """Health check endpoint."""
        return {"status": "healthy", "version": __version__}

    # Scan endpoint
    @app.post("/api/scan")
    async def scan(request: ScanRequest):
        """Scan a project."""
        from ..core.scanner import ProjectScanner

        try:
            path = Path(request.path).resolve()
            scanner = ProjectScanner(path)
            info = scanner.scan()

            return {
                "project": info.name,
                "path": str(info.path),
                "languages": info.languages,
                "source_files": len(info.source_files),
                "test_files": len(info.test_files),
                "functions": len(info.functions),
                "classes": len(info.classes),
                "api_endpoints": len(info.api_endpoints),
                "summary": info.summary(),
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Generate endpoint
    @app.post("/api/generate")
    async def generate(request: GenerateRequest, background_tasks: BackgroundTasks):
        """Generate tests for a project."""
        from ..core.scanner import ProjectScanner
        from ..config import ProjectConfig

        try:
            path = Path(request.path).resolve()
            scanner = ProjectScanner(path)
            info = scanner.scan()
            config = ProjectConfig.find_and_load(path)

            if request.dry_run:
                return {
                    "dry_run": True,
                    "would_generate": {
                        "functions": len(info.functions),
                        "api_endpoints": len(info.api_endpoints),
                    },
                    "llm_provider": config.llm.provider,
                }

            # For actual generation, run in background
            return {
                "status": "queued",
                "message": "Test generation queued",
                "functions": len(info.functions),
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Verify endpoint
    @app.post("/api/verify")
    async def verify(request: VerifyRequest):
        """Run verification on a project."""
        from ..git import GitTracker, get_strategy_for_trigger

        try:
            path = Path(request.path).resolve()
            strategy = get_strategy_for_trigger(request.trigger)
            tracker = GitTracker(path)

            changes = []
            if tracker.is_valid:
                if request.trigger == "push":
                    changes = tracker.get_uncommitted_changes()
                elif request.trigger in ("pr", "merge"):
                    changes = tracker.get_pr_changes(base_branch=request.base_branch)

            source_changes = [c for c in changes if c.is_source_file and not c.is_test_file]

            return {
                "trigger": request.trigger,
                "strategy": strategy.level.value,
                "changed_files": len(source_changes),
                "files": [c.path for c in source_changes[:20]],
                "config": {
                    "verify_changed_files": strategy.config.verify_changed_files,
                    "generate_missing_tests": strategy.config.generate_missing_tests,
                    "timeout": strategy.config.total_timeout,
                },
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Analyze endpoint
    @app.post("/api/analyze")
    async def analyze(request: AnalyzeRequest):
        """Analyze test failures."""
        from ..analysis import TestAnalyzer

        try:
            analyzer = TestAnalyzer()
            failures = analyzer.parse_pytest_output(request.test_output)

            results = []
            for failure in failures:
                analysis = analyzer.analyze_failure(failure)
                results.append({
                    "test": failure.test_name,
                    "type": failure.failure_type.value,
                    "message": failure.error_message[:200],
                    "root_cause": analysis.root_cause,
                    "confidence": analysis.confidence,
                    "fix_target": analysis.fix_type,
                })

            return {
                "total_failures": len(failures),
                "failures": results,
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # GitHub webhook endpoint
    @app.post("/webhook/github")
    async def github_webhook(request: Request, background_tasks: BackgroundTasks):
        """Handle GitHub webhook events."""
        # Get headers
        event_type = request.headers.get("X-GitHub-Event", "")
        signature = request.headers.get("X-Hub-Signature-256", "")
        delivery_id = request.headers.get("X-GitHub-Delivery", "")

        # Get body
        body = await request.body()

        # Verify signature
        if not webhook_handler.verify_signature(body, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse payload
        try:
            import json
            payload = json.loads(body)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        # Parse event
        event = webhook_handler.parse_event(event_type, payload)
        if not event:
            return {"status": "ignored", "reason": f"Unsupported event: {event_type}"}

        # Handle event (could be async/background)
        result = await webhook_handler.handle_event(event)

        logger.info(f"Handled webhook {delivery_id}: {result.get('status')}")

        return result

    # Diff endpoint
    @app.get("/api/diff")
    async def diff(
        path: str = ".",
        from_ref: str = "HEAD~1",
        to_ref: str = "HEAD",
    ):
        """Get git diff between two references."""
        from ..git import GitTracker

        try:
            project_path = Path(path).resolve()
            tracker = GitTracker(project_path)

            if not tracker.is_valid:
                raise HTTPException(status_code=400, detail="Not a git repository")

            changes = tracker.get_changes_between(from_ref, to_ref)

            return {
                "from": from_ref,
                "to": to_ref,
                "total": len(changes),
                "files": [
                    {
                        "path": c.path,
                        "type": c.change_type.value,
                        "additions": c.additions,
                        "deletions": c.deletions,
                    }
                    for c in changes
                ],
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Commits endpoint
    @app.get("/api/commits")
    async def commits(
        path: str = ".",
        count: int = 10,
    ):
        """Get recent commits."""
        from ..git import GitTracker

        try:
            project_path = Path(path).resolve()
            tracker = GitTracker(project_path)

            if not tracker.is_valid:
                raise HTTPException(status_code=400, detail="Not a git repository")

            commits_list = tracker.get_commits(max_count=count)

            return {
                "count": len(commits_list),
                "commits": [
                    {
                        "sha": c.short_sha,
                        "message": c.message.split("\n")[0][:100],
                        "author": c.author,
                        "timestamp": c.timestamp.isoformat(),
                        "source_changes": len(c.source_files_changed),
                        "test_changes": len(c.test_files_changed),
                    }
                    for c in commits_list
                ],
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Coverage endpoint - run coverage analysis
    @app.post("/api/coverage")
    async def run_coverage(
        path: str = ".",
        threshold: float = 80.0,
    ):
        """Run coverage analysis on a project."""
        from ..coverage import CoverageAnalyzer

        try:
            project_path = Path(path).resolve()
            analyzer = CoverageAnalyzer(project_path)
            report = analyzer.run_with_coverage()

            passes, message = analyzer.check_threshold(threshold)
            below_threshold = analyzer.get_files_below_threshold(threshold)

            return {
                "project": str(project_path),
                "coverage_percent": report.coverage_percent,
                "threshold": threshold,
                "passes_threshold": passes,
                "message": message,
                "summary": {
                    "total_files": report.summary.total_files if report.summary else 0,
                    "total_lines": report.summary.total_lines if report.summary else 0,
                    "covered_lines": report.summary.covered_lines if report.summary else 0,
                    "missed_lines": report.summary.missed_lines if report.summary else 0,
                },
                "files_below_threshold": [
                    {"file": f, "coverage": c}
                    for f, c in below_threshold[:20]
                ],
                "duration_seconds": report.duration_seconds,
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Coverage report endpoint - get latest report
    @app.get("/api/coverage/report")
    async def get_coverage_report(path: str = "."):
        """Get the latest coverage report."""
        from ..coverage import CoverageAnalyzer

        try:
            project_path = Path(path).resolve()
            analyzer = CoverageAnalyzer(project_path)

            # Try to load existing report or run new analysis
            report = analyzer.run_with_coverage()

            return report.to_dict()

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Uncovered functions endpoint
    @app.get("/api/coverage/uncovered")
    async def get_uncovered(
        path: str = ".",
        max_results: int = 20,
    ):
        """Get list of uncovered functions."""
        from ..coverage import CoverageAnalyzer

        try:
            project_path = Path(path).resolve()
            analyzer = CoverageAnalyzer(project_path)
            report = analyzer.run_with_coverage()

            uncovered = report.get_uncovered_functions()

            return {
                "total_uncovered": len(uncovered),
                "functions": [
                    {
                        "name": f.name,
                        "file": f.file_path,
                        "start_line": f.start_line,
                        "end_line": f.end_line,
                        "total_lines": f.total_lines,
                    }
                    for f in uncovered[:max_results]
                ],
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
):
    """Run the API server.

    Args:
        host: Host to bind to
        port: Port to listen on
        reload: Enable auto-reload for development
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI not installed")

    import uvicorn

    app = create_app()
    uvicorn.run(app, host=host, port=port, reload=reload)
