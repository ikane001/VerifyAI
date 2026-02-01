"""GitHub webhook handling for automated verification."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal
import hashlib
import hmac
import logging
import os

logger = logging.getLogger(__name__)


class GitHubEventType(Enum):
    """Types of GitHub events we handle."""

    PUSH = "push"
    PULL_REQUEST = "pull_request"
    PULL_REQUEST_REVIEW = "pull_request_review"
    CHECK_SUITE = "check_suite"
    CHECK_RUN = "check_run"
    WORKFLOW_RUN = "workflow_run"


@dataclass
class GitHubEvent:
    """Parsed GitHub webhook event."""

    event_type: GitHubEventType
    action: str | None = None
    repository: str = ""
    branch: str = ""
    commit_sha: str = ""

    # For push events
    before_sha: str = ""
    commits: list[dict] = field(default_factory=list)

    # For PR events
    pr_number: int | None = None
    pr_title: str = ""
    pr_base_branch: str = ""
    pr_head_branch: str = ""
    pr_state: str = ""

    # Sender info
    sender: str = ""
    sender_id: int | None = None

    # Timestamps
    timestamp: datetime | None = None

    # Raw payload
    raw: dict = field(default_factory=dict)

    @property
    def trigger_type(self) -> Literal["push", "pr", "merge", "manual"]:
        """Get verification trigger type for this event."""
        if self.event_type == GitHubEventType.PUSH:
            if self.branch in ("main", "master"):
                return "merge"
            return "push"
        elif self.event_type == GitHubEventType.PULL_REQUEST:
            if self.action == "closed" and self.raw.get("pull_request", {}).get("merged"):
                return "merge"
            return "pr"
        return "manual"

    @property
    def changed_files(self) -> list[str]:
        """Get list of changed files from event."""
        files = []

        if self.event_type == GitHubEventType.PUSH:
            for commit in self.commits:
                files.extend(commit.get("added", []))
                files.extend(commit.get("modified", []))

        return list(set(files))


class WebhookHandler:
    """Handle GitHub webhook events."""

    def __init__(
        self,
        webhook_secret: str | None = None,
        work_dir: Path | None = None,
    ):
        """Initialize webhook handler.

        Args:
            webhook_secret: GitHub webhook secret for signature verification
            work_dir: Working directory for cloning repos
        """
        self.webhook_secret = webhook_secret or os.getenv("GITHUB_WEBHOOK_SECRET")
        self.work_dir = work_dir or Path("/tmp/verify-ai")
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature.

        Args:
            payload: Raw request body
            signature: X-Hub-Signature-256 header value

        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            logger.warning("No webhook secret configured, skipping verification")
            return True

        if not signature:
            return False

        # GitHub sends: sha256=<hex_digest>
        if signature.startswith("sha256="):
            signature = signature[7:]

        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    def parse_event(self, event_type: str, payload: dict) -> GitHubEvent | None:
        """Parse a GitHub webhook payload.

        Args:
            event_type: X-GitHub-Event header value
            payload: Parsed JSON payload

        Returns:
            GitHubEvent or None if event type is not supported
        """
        try:
            event_enum = GitHubEventType(event_type)
        except ValueError:
            logger.debug(f"Unsupported event type: {event_type}")
            return None

        repo = payload.get("repository", {})
        sender = payload.get("sender", {})

        event = GitHubEvent(
            event_type=event_enum,
            repository=repo.get("full_name", ""),
            sender=sender.get("login", ""),
            sender_id=sender.get("id"),
            raw=payload,
        )

        if event_enum == GitHubEventType.PUSH:
            event.branch = payload.get("ref", "").replace("refs/heads/", "")
            event.commit_sha = payload.get("after", "")
            event.before_sha = payload.get("before", "")
            event.commits = payload.get("commits", [])

        elif event_enum == GitHubEventType.PULL_REQUEST:
            pr = payload.get("pull_request", {})
            event.action = payload.get("action")
            event.pr_number = pr.get("number")
            event.pr_title = pr.get("title", "")
            event.pr_state = pr.get("state", "")
            event.pr_base_branch = pr.get("base", {}).get("ref", "")
            event.pr_head_branch = pr.get("head", {}).get("ref", "")
            event.commit_sha = pr.get("head", {}).get("sha", "")
            event.branch = event.pr_head_branch

        return event

    async def handle_event(self, event: GitHubEvent) -> dict:
        """Handle a parsed GitHub event.

        Args:
            event: Parsed GitHubEvent

        Returns:
            Result of handling the event
        """
        if event.event_type == GitHubEventType.PUSH:
            return await handle_push_event(event)

        elif event.event_type == GitHubEventType.PULL_REQUEST:
            return await handle_pull_request_event(event)

        return {"status": "ignored", "reason": f"Unhandled event type: {event.event_type.value}"}


async def handle_push_event(event: GitHubEvent) -> dict:
    """Handle a push event.

    Args:
        event: Push event

    Returns:
        Result dictionary
    """
    logger.info(f"Handling push to {event.repository}/{event.branch}")

    # Skip if no code changes
    changed_files = event.changed_files
    source_files = [f for f in changed_files if _is_source_file(f)]

    if not source_files:
        return {
            "status": "skipped",
            "reason": "No source files changed",
        }

    # Determine verification strategy
    from ..git import get_strategy_for_trigger
    trigger = event.trigger_type
    strategy = get_strategy_for_trigger(trigger)

    result = {
        "status": "processing",
        "event": "push",
        "repository": event.repository,
        "branch": event.branch,
        "commit": event.commit_sha[:7],
        "trigger": trigger,
        "strategy": strategy.level.value,
        "changed_files": len(source_files),
        "files": source_files[:20],  # Limit for response
    }

    # In a real implementation, this would:
    # 1. Clone/pull the repository
    # 2. Run verification based on strategy
    # 3. Report results back to GitHub

    return result


async def handle_pull_request_event(event: GitHubEvent) -> dict:
    """Handle a pull request event.

    Args:
        event: Pull request event

    Returns:
        Result dictionary
    """
    logger.info(f"Handling PR #{event.pr_number} ({event.action}) in {event.repository}")

    # Only handle certain actions
    handled_actions = {"opened", "synchronize", "reopened"}
    if event.action not in handled_actions:
        return {
            "status": "ignored",
            "reason": f"Action '{event.action}' not handled",
        }

    # Get verification strategy
    from ..git import get_strategy_for_trigger
    strategy = get_strategy_for_trigger("pr")

    result = {
        "status": "processing",
        "event": "pull_request",
        "action": event.action,
        "repository": event.repository,
        "pr_number": event.pr_number,
        "pr_title": event.pr_title,
        "base_branch": event.pr_base_branch,
        "head_branch": event.pr_head_branch,
        "commit": event.commit_sha[:7],
        "strategy": strategy.level.value,
        "config": {
            "generate_missing_tests": strategy.config.generate_missing_tests,
            "block_on_failure": strategy.config.block_on_failure,
            "timeout": strategy.config.total_timeout,
        },
    }

    # In a real implementation, this would:
    # 1. Clone/pull the repository
    # 2. Checkout the PR branch
    # 3. Run verification
    # 4. Create/update PR comment with results
    # 5. Set commit status

    return result


def _is_source_file(path: str) -> bool:
    """Check if a file path is a source file."""
    source_extensions = {
        ".py", ".js", ".ts", ".tsx", ".jsx",
        ".go", ".java", ".rs", ".rb", ".php",
    }
    return Path(path).suffix.lower() in source_extensions


# GitHub API helpers

@dataclass
class GitHubStatus:
    """GitHub commit status."""

    state: Literal["pending", "success", "failure", "error"]
    target_url: str | None = None
    description: str = ""
    context: str = "verify-ai"


async def set_commit_status(
    repo: str,
    commit_sha: str,
    status: GitHubStatus,
    token: str | None = None,
) -> bool:
    """Set commit status on GitHub.

    Args:
        repo: Repository full name (owner/repo)
        commit_sha: Commit SHA
        status: Status to set
        token: GitHub token

    Returns:
        True if successful
    """
    token = token or os.getenv("GITHUB_TOKEN")
    if not token:
        logger.error("No GitHub token available")
        return False

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.github.com/repos/{repo}/statuses/{commit_sha}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json={
                    "state": status.state,
                    "target_url": status.target_url,
                    "description": status.description[:140],  # GitHub limit
                    "context": status.context,
                },
            )
            return response.status_code == 201

    except Exception as e:
        logger.error(f"Failed to set commit status: {e}")
        return False


async def create_pr_comment(
    repo: str,
    pr_number: int,
    body: str,
    token: str | None = None,
) -> bool:
    """Create a comment on a pull request.

    Args:
        repo: Repository full name
        pr_number: PR number
        body: Comment body (markdown)
        token: GitHub token

    Returns:
        True if successful
    """
    token = token or os.getenv("GITHUB_TOKEN")
    if not token:
        logger.error("No GitHub token available")
        return False

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json={"body": body},
            )
            return response.status_code == 201

    except Exception as e:
        logger.error(f"Failed to create PR comment: {e}")
        return False
