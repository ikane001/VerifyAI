"""Tests for server and webhook modules."""

import json
from pathlib import Path

import pytest

from verify_ai.server.webhook import (
    WebhookHandler,
    GitHubEvent,
    GitHubEventType,
    handle_push_event,
    handle_pull_request_event,
)


@pytest.fixture
def webhook_handler():
    """Create webhook handler."""
    return WebhookHandler(webhook_secret="test_secret")


class TestWebhookHandler:
    """Tests for WebhookHandler."""

    def test_create_handler(self, webhook_handler):
        """Test handler creation."""
        assert webhook_handler is not None
        assert webhook_handler.webhook_secret == "test_secret"

    def test_verify_signature_valid(self, webhook_handler):
        """Test valid signature verification."""
        import hmac
        import hashlib

        payload = b'{"test": "data"}'
        signature = "sha256=" + hmac.new(
            b"test_secret",
            payload,
            hashlib.sha256,
        ).hexdigest()

        assert webhook_handler.verify_signature(payload, signature)

    def test_verify_signature_invalid(self, webhook_handler):
        """Test invalid signature verification."""
        payload = b'{"test": "data"}'
        signature = "sha256=invalid"

        assert not webhook_handler.verify_signature(payload, signature)

    def test_parse_push_event(self, webhook_handler):
        """Test parsing push event."""
        payload = {
            "ref": "refs/heads/main",
            "after": "abc123def456",
            "before": "000000000000",
            "commits": [
                {
                    "id": "abc123",
                    "message": "Test commit",
                    "added": ["new_file.py"],
                    "modified": ["existing.py"],
                }
            ],
            "repository": {"full_name": "owner/repo"},
            "sender": {"login": "testuser", "id": 123},
        }

        event = webhook_handler.parse_event("push", payload)

        assert event is not None
        assert event.event_type == GitHubEventType.PUSH
        assert event.branch == "main"
        assert event.commit_sha == "abc123def456"
        assert event.repository == "owner/repo"
        assert len(event.commits) == 1

    def test_parse_pr_event(self, webhook_handler):
        """Test parsing pull request event."""
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 42,
                "title": "Test PR",
                "state": "open",
                "base": {"ref": "main"},
                "head": {"ref": "feature", "sha": "abc123"},
            },
            "repository": {"full_name": "owner/repo"},
            "sender": {"login": "testuser", "id": 123},
        }

        event = webhook_handler.parse_event("pull_request", payload)

        assert event is not None
        assert event.event_type == GitHubEventType.PULL_REQUEST
        assert event.action == "opened"
        assert event.pr_number == 42
        assert event.pr_title == "Test PR"
        assert event.pr_base_branch == "main"
        assert event.pr_head_branch == "feature"

    def test_parse_unsupported_event(self, webhook_handler):
        """Test parsing unsupported event."""
        event = webhook_handler.parse_event("fork", {})
        assert event is None


class TestGitHubEvent:
    """Tests for GitHubEvent."""

    def test_trigger_type_push(self):
        """Test trigger type for push event."""
        event = GitHubEvent(
            event_type=GitHubEventType.PUSH,
            branch="feature",
        )
        assert event.trigger_type == "push"

    def test_trigger_type_push_main(self):
        """Test trigger type for push to main."""
        event = GitHubEvent(
            event_type=GitHubEventType.PUSH,
            branch="main",
        )
        assert event.trigger_type == "merge"

    def test_trigger_type_pr(self):
        """Test trigger type for PR event."""
        event = GitHubEvent(
            event_type=GitHubEventType.PULL_REQUEST,
            action="opened",
        )
        assert event.trigger_type == "pr"

    def test_changed_files(self):
        """Test getting changed files."""
        event = GitHubEvent(
            event_type=GitHubEventType.PUSH,
            commits=[
                {"added": ["a.py"], "modified": ["b.py"]},
                {"added": ["c.py"], "modified": ["a.py"]},  # Duplicate
            ],
        )
        changed = event.changed_files

        assert "a.py" in changed
        assert "b.py" in changed
        assert "c.py" in changed
        assert len(changed) == 3  # No duplicates


class TestEventHandlers:
    """Tests for event handlers."""

    @pytest.mark.asyncio
    async def test_handle_push_event(self):
        """Test handling push event."""
        event = GitHubEvent(
            event_type=GitHubEventType.PUSH,
            repository="owner/repo",
            branch="feature",
            commit_sha="abc123def456",
            commits=[
                {"added": ["new.py"], "modified": ["old.py"]},
            ],
        )

        result = await handle_push_event(event)

        assert result["status"] == "processing"
        assert result["event"] == "push"
        assert result["repository"] == "owner/repo"
        assert result["changed_files"] == 2

    @pytest.mark.asyncio
    async def test_handle_push_event_no_source(self):
        """Test handling push with no source files."""
        event = GitHubEvent(
            event_type=GitHubEventType.PUSH,
            repository="owner/repo",
            branch="feature",
            commits=[
                {"added": ["README.md"], "modified": []},
            ],
        )

        result = await handle_push_event(event)

        assert result["status"] == "skipped"
        assert "No source files" in result["reason"]

    @pytest.mark.asyncio
    async def test_handle_pr_event(self):
        """Test handling PR event."""
        event = GitHubEvent(
            event_type=GitHubEventType.PULL_REQUEST,
            action="opened",
            repository="owner/repo",
            pr_number=42,
            pr_title="Test PR",
            pr_base_branch="main",
            pr_head_branch="feature",
            commit_sha="abc123",
        )

        result = await handle_pull_request_event(event)

        assert result["status"] == "processing"
        assert result["event"] == "pull_request"
        assert result["pr_number"] == 42

    @pytest.mark.asyncio
    async def test_handle_pr_event_ignored(self):
        """Test ignoring certain PR actions."""
        event = GitHubEvent(
            event_type=GitHubEventType.PULL_REQUEST,
            action="labeled",  # Not handled
            repository="owner/repo",
            pr_number=42,
        )

        result = await handle_pull_request_event(event)

        assert result["status"] == "ignored"
