"""Project scanner for analyzing code structure."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
import logging

import git

from ..config import ProjectConfig
from ..parsers.code_parser import ClassInfo, CodeParser, FunctionInfo, detect_language
from ..parsers.openapi import APIEndpoint, OpenAPIParser, find_openapi_spec
from ..parsers.tree_sitter_parser import (
    TreeSitterParser,
    DependencyInfo,
    create_parser,
    TREE_SITTER_AVAILABLE,
)

logger = logging.getLogger(__name__)


@dataclass
class GitInfo:
    """Git repository information."""

    is_repo: bool = False
    current_branch: str = ""
    recent_commits: list[dict] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)


@dataclass
class ProjectInfo:
    """Comprehensive project information."""

    path: Path
    name: str
    languages: list[str] = field(default_factory=list)
    config: ProjectConfig | None = None

    # Code structure
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)

    # API information
    api_endpoints: list[APIEndpoint] = field(default_factory=list)
    api_spec_path: Path | None = None

    # Git information
    git_info: GitInfo = field(default_factory=GitInfo)

    # File statistics
    source_files: list[Path] = field(default_factory=list)
    test_files: list[Path] = field(default_factory=list)

    # Dependency information (Phase 2)
    dependencies: dict[str, DependencyInfo] = field(default_factory=dict)
    uses_tree_sitter: bool = False

    def summary(self) -> str:
        """Generate a summary for LLM context."""
        lines = [
            f"Project: {self.name}",
            f"Path: {self.path}",
            f"Languages: {', '.join(self.languages)}",
            f"Source files: {len(self.source_files)}",
            f"Test files: {len(self.test_files)}",
            f"Functions: {len(self.functions)}",
            f"Classes: {len(self.classes)}",
            f"API Endpoints: {len(self.api_endpoints)}",
        ]

        if self.uses_tree_sitter:
            lines.append("Parser: tree-sitter (multi-language)")
        else:
            lines.append("Parser: Python AST (fallback)")

        if self.git_info.is_repo:
            lines.append(f"Git branch: {self.git_info.current_branch}")
            if self.git_info.changed_files:
                lines.append(f"Changed files: {len(self.git_info.changed_files)}")

        # Dependency summary
        if self.dependencies:
            all_deps = set()
            for dep_info in self.dependencies.values():
                all_deps.update(dep_info.dependencies)
            lines.append(f"External dependencies: {len(all_deps)}")

        return "\n".join(lines)

    def get_dependency_graph(self) -> dict[str, list[str]]:
        """Get dependency graph for the project.

        Returns:
            Dictionary mapping file paths to their dependencies.
        """
        graph = {}
        for file_path, dep_info in self.dependencies.items():
            graph[file_path] = dep_info.dependencies
        return graph


class ProjectScanner:
    """Scanner for analyzing project structure."""

    # Common patterns to ignore
    IGNORE_DIRS = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".eggs",
        "*.egg-info",
    }

    IGNORE_FILES = {
        ".DS_Store",
        "Thumbs.db",
        ".gitignore",
        ".env",
    }

    SOURCE_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".java": "java",
        ".rs": "rust",
        ".rb": "ruby",
    }

    TEST_PATTERNS = [
        "**/test_*.py",
        "**/*_test.py",
        "**/tests/*.py",
        "**/*.test.js",
        "**/*.test.ts",
        "**/*.spec.js",
        "**/*.spec.ts",
        "**/test/*.go",
        "**/*_test.go",
    ]

    def __init__(self, project_path: Path, use_tree_sitter: bool = True):
        """Initialize scanner with project path.

        Args:
            project_path: Path to the project root
            use_tree_sitter: Whether to use tree-sitter for parsing (if available)
        """
        self.project_path = project_path.resolve()
        self.config = ProjectConfig.find_and_load(self.project_path)
        self._use_tree_sitter = use_tree_sitter and TREE_SITTER_AVAILABLE
        self._ts_parser: TreeSitterParser | None = None

        if self._use_tree_sitter:
            self._ts_parser = create_parser()
            if self._ts_parser:
                logger.info("Using tree-sitter parser for multi-language support")
            else:
                logger.warning("tree-sitter initialization failed, falling back to Python AST")
                self._use_tree_sitter = False

    def scan(self) -> ProjectInfo:
        """Perform full project scan.

        Returns:
            ProjectInfo with all collected information
        """
        info = ProjectInfo(
            path=self.project_path,
            name=self.project_path.name,
            config=self.config,
            uses_tree_sitter=self._use_tree_sitter and self._ts_parser is not None,
        )

        # Scan source files
        info.source_files = self._find_source_files()
        info.test_files = self._find_test_files()

        # Detect languages
        info.languages = self._detect_languages(info.source_files)

        # Parse code structure (using tree-sitter if available)
        all_functions, all_classes = self._parse_code_structure(info.source_files, info.languages)
        info.functions = all_functions
        info.classes = all_classes

        # Parse dependencies (Phase 2)
        if self._ts_parser:
            info.dependencies = self._parse_dependencies(info.source_files)

        # Find and parse OpenAPI spec
        spec_path = find_openapi_spec(self.project_path)
        if spec_path:
            info.api_spec_path = spec_path
            parser = OpenAPIParser(spec_path)
            info.api_endpoints = parser.get_endpoints()

        # Get git information
        info.git_info = self._get_git_info()

        return info

    def _find_source_files(self) -> list[Path]:
        """Find all source files in the project."""
        source_files = []

        for ext in self.SOURCE_EXTENSIONS:
            for file_path in self.project_path.rglob(f"*{ext}"):
                if self._should_include(file_path):
                    source_files.append(file_path)

        return sorted(source_files)

    def _find_test_files(self) -> list[Path]:
        """Find all test files in the project."""
        test_files = set()

        for pattern in self.TEST_PATTERNS:
            for file_path in self.project_path.glob(pattern):
                if self._should_include(file_path):
                    test_files.add(file_path)

        return sorted(test_files)

    def _should_include(self, file_path: Path) -> bool:
        """Check if file should be included in scan."""
        # Check if any parent is in ignore list
        for parent in file_path.parents:
            if parent.name in self.IGNORE_DIRS:
                return False

        # Check if file is in ignore list
        if file_path.name in self.IGNORE_FILES:
            return False

        return True

    def _detect_languages(self, source_files: list[Path]) -> list[str]:
        """Detect languages from source files."""
        languages = set()
        for file_path in source_files:
            lang = detect_language(file_path)
            if lang:
                languages.add(lang)
        return sorted(languages)

    def _parse_code_structure(
        self, source_files: list[Path], languages: list[str]
    ) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        """Parse code structure from source files.

        Uses tree-sitter if available for multi-language support,
        otherwise falls back to Python AST parser.
        """
        all_functions = []
        all_classes = []

        for file_path in source_files:
            lang = detect_language(file_path)
            if not lang:
                continue

            try:
                # Try tree-sitter first if available
                if self._ts_parser and lang in ("python", "javascript", "typescript", "go", "java"):
                    functions, classes = self._ts_parser.parse_file(file_path)
                    all_functions.extend(functions)
                    all_classes.extend(classes)
                # Fall back to Python AST for Python files
                elif lang == "python":
                    parser = CodeParser(language=lang)
                    functions, classes = parser.parse_file(file_path)
                    all_functions.extend(functions)
                    all_classes.extend(classes)
                # Use simple regex parser for JS/TS when tree-sitter not available
                elif lang in ("javascript", "typescript"):
                    parser = CodeParser(language=lang)
                    functions, classes = parser.parse_file(file_path)
                    all_functions.extend(functions)
                    all_classes.extend(classes)

            except Exception as e:
                logger.debug(f"Error parsing {file_path}: {e}")
                continue

        return all_functions, all_classes

    def _parse_dependencies(self, source_files: list[Path]) -> dict[str, DependencyInfo]:
        """Parse dependencies from source files using tree-sitter.

        Args:
            source_files: List of source files to parse

        Returns:
            Dictionary mapping file paths to their dependency info
        """
        dependencies = {}

        if not self._ts_parser:
            return dependencies

        for file_path in source_files:
            try:
                dep_info = self._ts_parser.parse_imports(file_path)
                rel_path = str(file_path.relative_to(self.project_path))
                dependencies[rel_path] = dep_info
            except Exception as e:
                logger.debug(f"Error parsing dependencies from {file_path}: {e}")
                continue

        return dependencies

    def _get_git_info(self) -> GitInfo:
        """Get git repository information."""
        git_info = GitInfo()

        try:
            repo = git.Repo(self.project_path, search_parent_directories=True)
            git_info.is_repo = True
            git_info.current_branch = repo.active_branch.name

            # Get recent commits
            commits = list(repo.iter_commits(max_count=10))
            git_info.recent_commits = [
                {
                    "sha": c.hexsha[:8],
                    "message": c.message.strip().split("\n")[0],
                    "author": str(c.author),
                    "date": c.committed_datetime.isoformat(),
                }
                for c in commits
            ]

            # Get changed files (uncommitted)
            changed = repo.index.diff(None)
            git_info.changed_files = [d.a_path for d in changed]

            # Add untracked files
            git_info.changed_files.extend(repo.untracked_files)

        except (git.InvalidGitRepositoryError, git.GitCommandNotFound):
            pass

        return git_info

    def get_files_for_testing(self) -> list[Path]:
        """Get source files that need test generation.

        Excludes files that already have tests.
        """
        tested_modules = set()
        for test_file in self.test_files:
            # Extract module name from test file
            name = test_file.stem
            if name.startswith("test_"):
                tested_modules.add(name[5:])
            elif name.endswith("_test"):
                tested_modules.add(name[:-5])

        # Find source files without tests
        files_needing_tests = []
        for source_file in self.source_files:
            module_name = source_file.stem
            if module_name not in tested_modules and not module_name.startswith("_"):
                files_needing_tests.append(source_file)

        return files_needing_tests

    @property
    def test_files(self) -> list[Path]:
        """Lazy load test files."""
        if not hasattr(self, "_test_files"):
            self._test_files = self._find_test_files()
        return self._test_files
