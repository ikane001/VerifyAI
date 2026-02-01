"""Git change tracking for incremental verification."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Iterator
import logging
import re

import git
from git import Repo, Commit, Diff

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Type of file change."""

    ADDED = "A"
    MODIFIED = "M"
    DELETED = "D"
    RENAMED = "R"
    COPIED = "C"
    UNTRACKED = "?"


@dataclass
class DiffChunk:
    """A chunk of diff showing specific changes."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    content: str
    added_lines: list[tuple[int, str]] = field(default_factory=list)
    removed_lines: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class FileChange:
    """Information about a changed file."""

    path: str
    change_type: ChangeType
    old_path: str | None = None  # For renames
    diff_chunks: list[DiffChunk] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0

    @property
    def is_source_file(self) -> bool:
        """Check if this is a source code file."""
        source_extensions = {
            ".py", ".js", ".ts", ".tsx", ".jsx",
            ".go", ".java", ".rs", ".rb", ".php",
            ".c", ".cpp", ".h", ".hpp", ".cs",
        }
        return Path(self.path).suffix.lower() in source_extensions

    @property
    def is_test_file(self) -> bool:
        """Check if this is a test file."""
        path_lower = self.path.lower()
        return (
            "test" in path_lower
            or "spec" in path_lower
            or path_lower.startswith("tests/")
            or "/tests/" in path_lower
        )


@dataclass
class CommitInfo:
    """Information about a git commit."""

    sha: str
    short_sha: str
    message: str
    author: str
    author_email: str
    timestamp: datetime
    files_changed: list[FileChange] = field(default_factory=list)
    parent_sha: str | None = None

    @property
    def source_files_changed(self) -> list[FileChange]:
        """Get only source file changes."""
        return [f for f in self.files_changed if f.is_source_file and not f.is_test_file]

    @property
    def test_files_changed(self) -> list[FileChange]:
        """Get only test file changes."""
        return [f for f in self.files_changed if f.is_test_file]


class GitTracker:
    """Track git changes for incremental verification."""

    def __init__(self, repo_path: Path):
        """Initialize git tracker.

        Args:
            repo_path: Path to the git repository
        """
        self.repo_path = repo_path.resolve()
        try:
            self.repo = Repo(self.repo_path)
            self._is_valid = True
        except git.InvalidGitRepositoryError:
            self._is_valid = False
            logger.warning(f"Not a git repository: {repo_path}")
        except Exception as e:
            self._is_valid = False
            logger.error(f"Error opening git repository: {e}")

    @property
    def is_valid(self) -> bool:
        """Check if this is a valid git repository."""
        return self._is_valid

    @property
    def current_branch(self) -> str | None:
        """Get current branch name."""
        if not self._is_valid:
            return None
        try:
            return self.repo.active_branch.name
        except TypeError:
            # Detached HEAD
            return None

    @property
    def head_commit(self) -> CommitInfo | None:
        """Get HEAD commit info."""
        if not self._is_valid:
            return None
        try:
            return self._commit_to_info(self.repo.head.commit)
        except Exception:
            return None

    def get_uncommitted_changes(self) -> list[FileChange]:
        """Get all uncommitted changes (staged + unstaged + untracked).

        Returns:
            List of file changes
        """
        if not self._is_valid:
            return []

        changes = []

        # Staged changes
        try:
            staged = self.repo.index.diff("HEAD")
            for diff in staged:
                changes.append(self._diff_to_file_change(diff))
        except Exception:
            pass

        # Unstaged changes
        try:
            unstaged = self.repo.index.diff(None)
            for diff in unstaged:
                change = self._diff_to_file_change(diff)
                # Avoid duplicates
                if not any(c.path == change.path for c in changes):
                    changes.append(change)
        except Exception:
            pass

        # Untracked files
        try:
            for path in self.repo.untracked_files:
                if not any(c.path == path for c in changes):
                    changes.append(FileChange(
                        path=path,
                        change_type=ChangeType.UNTRACKED,
                    ))
        except Exception:
            pass

        return changes

    def get_changes_between(
        self,
        from_ref: str = "HEAD~1",
        to_ref: str = "HEAD",
    ) -> list[FileChange]:
        """Get changes between two refs (commits, branches, tags).

        Args:
            from_ref: Starting reference (older)
            to_ref: Ending reference (newer)

        Returns:
            List of file changes
        """
        if not self._is_valid:
            return []

        try:
            from_commit = self.repo.commit(from_ref)
            to_commit = self.repo.commit(to_ref)

            diffs = from_commit.diff(to_commit)
            return [self._diff_to_file_change(d, with_chunks=True) for d in diffs]

        except Exception as e:
            logger.error(f"Error getting changes between {from_ref} and {to_ref}: {e}")
            return []

    def get_changes_in_commit(self, commit_ref: str = "HEAD") -> list[FileChange]:
        """Get changes introduced in a specific commit.

        Args:
            commit_ref: Commit reference (SHA, branch, tag)

        Returns:
            List of file changes
        """
        if not self._is_valid:
            return []

        try:
            commit = self.repo.commit(commit_ref)
            if commit.parents:
                diffs = commit.parents[0].diff(commit)
            else:
                # Initial commit - compare with empty tree
                diffs = commit.diff(git.NULL_TREE)

            return [self._diff_to_file_change(d, with_chunks=True) for d in diffs]

        except Exception as e:
            logger.error(f"Error getting changes in commit {commit_ref}: {e}")
            return []

    def get_commits(
        self,
        since: str | None = None,
        until: str | None = None,
        max_count: int = 50,
        branch: str | None = None,
    ) -> list[CommitInfo]:
        """Get commit history.

        Args:
            since: Start date/ref
            until: End date/ref
            max_count: Maximum number of commits
            branch: Branch to get commits from

        Returns:
            List of commit info
        """
        if not self._is_valid:
            return []

        try:
            kwargs = {"max_count": max_count}

            if since:
                kwargs["since"] = since
            if until:
                kwargs["until"] = until

            if branch:
                commits = self.repo.iter_commits(branch, **kwargs)
            else:
                commits = self.repo.iter_commits(**kwargs)

            return [self._commit_to_info(c) for c in commits]

        except Exception as e:
            logger.error(f"Error getting commits: {e}")
            return []

    def get_changed_functions(
        self,
        from_ref: str = "HEAD~1",
        to_ref: str = "HEAD",
    ) -> list[dict]:
        """Analyze diff to find changed functions/methods.

        Args:
            from_ref: Starting reference
            to_ref: Ending reference

        Returns:
            List of dicts with function change info
        """
        changes = self.get_changes_between(from_ref, to_ref)
        changed_functions = []

        for change in changes:
            if not change.is_source_file or change.change_type == ChangeType.DELETED:
                continue

            for chunk in change.diff_chunks:
                # Parse chunk header for function context
                # Git diff headers often contain function names
                funcs = self._extract_functions_from_chunk(chunk, change.path)
                changed_functions.extend(funcs)

        return changed_functions

    def get_pr_changes(
        self,
        base_branch: str = "main",
        head_branch: str | None = None,
    ) -> list[FileChange]:
        """Get changes between PR base and head.

        Args:
            base_branch: Base branch (e.g., main, master)
            head_branch: Head branch (current branch if None)

        Returns:
            List of file changes
        """
        if not self._is_valid:
            return []

        head = head_branch or self.current_branch
        if not head:
            return []

        try:
            # Find merge base
            merge_base = self.repo.merge_base(base_branch, head)
            if not merge_base:
                return []

            return self.get_changes_between(merge_base[0].hexsha, head)

        except Exception as e:
            logger.error(f"Error getting PR changes: {e}")
            return []

    def _diff_to_file_change(self, diff: Diff, with_chunks: bool = False) -> FileChange:
        """Convert git diff to FileChange."""
        # Determine change type
        if diff.new_file:
            change_type = ChangeType.ADDED
        elif diff.deleted_file:
            change_type = ChangeType.DELETED
        elif diff.renamed_file:
            change_type = ChangeType.RENAMED
        elif diff.copied_file:
            change_type = ChangeType.COPIED
        else:
            change_type = ChangeType.MODIFIED

        # Get file path
        path = diff.b_path or diff.a_path

        # Get old path for renames
        old_path = diff.a_path if diff.renamed_file else None

        # Parse diff chunks
        chunks = []
        additions = 0
        deletions = 0

        if with_chunks:
            try:
                diff_text = diff.diff.decode("utf-8", errors="replace") if diff.diff else ""
                chunks, additions, deletions = self._parse_diff_chunks(diff_text)
            except Exception:
                pass

        return FileChange(
            path=path,
            change_type=change_type,
            old_path=old_path,
            diff_chunks=chunks,
            additions=additions,
            deletions=deletions,
        )

    def _parse_diff_chunks(self, diff_text: str) -> tuple[list[DiffChunk], int, int]:
        """Parse diff text into chunks."""
        chunks = []
        total_additions = 0
        total_deletions = 0

        # Regex to match chunk headers: @@ -old_start,old_count +new_start,new_count @@
        chunk_pattern = re.compile(
            r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)"
        )

        current_chunk = None
        current_lines = []

        for line in diff_text.split("\n"):
            match = chunk_pattern.match(line)
            if match:
                # Save previous chunk
                if current_chunk:
                    current_chunk.content = "\n".join(current_lines)
                    chunks.append(current_chunk)

                # Start new chunk
                old_start = int(match.group(1))
                old_count = int(match.group(2) or 1)
                new_start = int(match.group(3))
                new_count = int(match.group(4) or 1)

                current_chunk = DiffChunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    content="",
                )
                current_lines = [match.group(5).strip()]  # Function context

            elif current_chunk:
                current_lines.append(line)

                if line.startswith("+") and not line.startswith("+++"):
                    total_additions += 1
                    current_chunk.added_lines.append(
                        (len(current_chunk.added_lines) + current_chunk.new_start, line[1:])
                    )
                elif line.startswith("-") and not line.startswith("---"):
                    total_deletions += 1
                    current_chunk.removed_lines.append(
                        (len(current_chunk.removed_lines) + current_chunk.old_start, line[1:])
                    )

        # Save last chunk
        if current_chunk:
            current_chunk.content = "\n".join(current_lines)
            chunks.append(current_chunk)

        return chunks, total_additions, total_deletions

    def _commit_to_info(self, commit: Commit) -> CommitInfo:
        """Convert git commit to CommitInfo."""
        # Get file changes
        file_changes = []
        if commit.parents:
            for diff in commit.parents[0].diff(commit):
                file_changes.append(self._diff_to_file_change(diff))

        return CommitInfo(
            sha=commit.hexsha,
            short_sha=commit.hexsha[:7],
            message=commit.message.strip(),
            author=commit.author.name,
            author_email=commit.author.email,
            timestamp=datetime.fromtimestamp(commit.committed_date),
            files_changed=file_changes,
            parent_sha=commit.parents[0].hexsha if commit.parents else None,
        )

    def _extract_functions_from_chunk(
        self, chunk: DiffChunk, file_path: str
    ) -> list[dict]:
        """Extract function names from diff chunk."""
        functions = []

        # Try to find function definitions in added lines
        # This is a simple heuristic - could be improved with AST
        patterns = {
            ".py": r"^\s*(?:async\s+)?def\s+(\w+)",
            ".js": r"(?:function\s+(\w+)|(\w+)\s*[=:]\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))",
            ".ts": r"(?:function\s+(\w+)|(\w+)\s*[=:]\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))",
            ".go": r"func\s+(?:\([^)]+\)\s+)?(\w+)",
            ".java": r"(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(",
        }

        suffix = Path(file_path).suffix.lower()
        pattern = patterns.get(suffix)

        if not pattern:
            return functions

        for line_num, line in chunk.added_lines:
            match = re.search(pattern, line)
            if match:
                func_name = next(g for g in match.groups() if g)
                functions.append({
                    "name": func_name,
                    "file": file_path,
                    "line": line_num,
                    "change": "added",
                })

        for line_num, line in chunk.removed_lines:
            match = re.search(pattern, line)
            if match:
                func_name = next(g for g in match.groups() if g)
                functions.append({
                    "name": func_name,
                    "file": file_path,
                    "line": line_num,
                    "change": "removed",
                })

        return functions
