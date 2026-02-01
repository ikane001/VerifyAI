"""Git integration for change tracking and incremental verification."""

from .tracker import (
    GitTracker,
    CommitInfo,
    FileChange,
    ChangeType,
    DiffChunk,
)
from .strategy import (
    VerificationLevel,
    VerificationStrategy,
    VerificationConfig,
    get_strategy_for_trigger,
)

__all__ = [
    "GitTracker",
    "CommitInfo",
    "FileChange",
    "ChangeType",
    "DiffChunk",
    "VerificationLevel",
    "VerificationStrategy",
    "VerificationConfig",
    "get_strategy_for_trigger",
]
