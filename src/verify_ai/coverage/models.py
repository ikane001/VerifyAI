"""Data models for coverage analysis."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class LineCoverage:
    """Coverage information for a single line."""
    
    line_number: int
    is_covered: bool
    hit_count: int = 0
    is_branch: bool = False
    branch_covered: Optional[bool] = None


@dataclass
class FunctionCoverage:
    """Coverage information for a function."""
    
    name: str
    file_path: str
    start_line: int
    end_line: int
    is_covered: bool
    total_lines: int = 0
    covered_lines: int = 0
    
    @property
    def coverage_percent(self) -> float:
        """Calculate coverage percentage for this function."""
        if self.total_lines == 0:
            return 0.0
        return (self.covered_lines / self.total_lines) * 100


@dataclass
class FileMetrics:
    """Coverage metrics for a single file."""
    
    file_path: str
    total_lines: int
    covered_lines: int
    missed_lines: int
    total_branches: int = 0
    covered_branches: int = 0
    line_coverage: list[LineCoverage] = field(default_factory=list)
    functions: list[FunctionCoverage] = field(default_factory=list)
    
    @property
    def coverage_percent(self) -> float:
        """Calculate line coverage percentage."""
        if self.total_lines == 0:
            return 0.0
        return (self.covered_lines / self.total_lines) * 100
    
    @property
    def branch_coverage_percent(self) -> float:
        """Calculate branch coverage percentage."""
        if self.total_branches == 0:
            return 0.0
        return (self.covered_branches / self.total_branches) * 100
    
    @property
    def uncovered_lines(self) -> list[int]:
        """Get list of uncovered line numbers."""
        return [lc.line_number for lc in self.line_coverage if not lc.is_covered]
    
    @property
    def uncovered_functions(self) -> list[FunctionCoverage]:
        """Get list of uncovered functions."""
        return [f for f in self.functions if not f.is_covered]


@dataclass
class CoverageSummary:
    """Summary of coverage metrics."""
    
    total_files: int
    total_lines: int
    covered_lines: int
    missed_lines: int
    total_branches: int = 0
    covered_branches: int = 0
    total_functions: int = 0
    covered_functions: int = 0
    
    @property
    def line_coverage_percent(self) -> float:
        """Calculate overall line coverage percentage."""
        if self.total_lines == 0:
            return 0.0
        return (self.covered_lines / self.total_lines) * 100
    
    @property
    def branch_coverage_percent(self) -> float:
        """Calculate overall branch coverage percentage."""
        if self.total_branches == 0:
            return 0.0
        return (self.covered_branches / self.total_branches) * 100
    
    @property
    def function_coverage_percent(self) -> float:
        """Calculate overall function coverage percentage."""
        if self.total_functions == 0:
            return 0.0
        return (self.covered_functions / self.total_functions) * 100


@dataclass
class CoverageReport:
    """Complete coverage report for a project."""
    
    project_path: str
    timestamp: datetime = field(default_factory=datetime.now)
    file_reports: list[FileMetrics] = field(default_factory=list)
    summary: Optional[CoverageSummary] = None
    test_command: str = ""
    duration_seconds: float = 0.0
    
    def __post_init__(self):
        """Calculate summary if not provided."""
        if self.summary is None:
            self.summary = self._calculate_summary()
    
    def _calculate_summary(self) -> CoverageSummary:
        """Calculate summary from file reports."""
        total_files = len(self.file_reports)
        total_lines = sum(f.total_lines for f in self.file_reports)
        covered_lines = sum(f.covered_lines for f in self.file_reports)
        missed_lines = sum(f.missed_lines for f in self.file_reports)
        total_branches = sum(f.total_branches for f in self.file_reports)
        covered_branches = sum(f.covered_branches for f in self.file_reports)
        total_functions = sum(len(f.functions) for f in self.file_reports)
        covered_functions = sum(
            len([fn for fn in f.functions if fn.is_covered])
            for f in self.file_reports
        )
        
        return CoverageSummary(
            total_files=total_files,
            total_lines=total_lines,
            covered_lines=covered_lines,
            missed_lines=missed_lines,
            total_branches=total_branches,
            covered_branches=covered_branches,
            total_functions=total_functions,
            covered_functions=covered_functions,
        )
    
    @property
    def coverage_percent(self) -> float:
        """Get overall coverage percentage."""
        if self.summary:
            return self.summary.line_coverage_percent
        return 0.0
    
    def get_uncovered_files(self, threshold: float = 100.0) -> list[FileMetrics]:
        """Get files with coverage below threshold."""
        return [
            f for f in self.file_reports
            if f.coverage_percent < threshold
        ]
    
    def get_uncovered_functions(self) -> list[FunctionCoverage]:
        """Get all uncovered functions across all files."""
        uncovered = []
        for file_report in self.file_reports:
            uncovered.extend(file_report.uncovered_functions)
        return uncovered
    
    def to_dict(self) -> dict:
        """Convert report to dictionary for serialization."""
        return {
            "project_path": self.project_path,
            "timestamp": self.timestamp.isoformat(),
            "duration_seconds": self.duration_seconds,
            "test_command": self.test_command,
            "summary": {
                "total_files": self.summary.total_files if self.summary else 0,
                "total_lines": self.summary.total_lines if self.summary else 0,
                "covered_lines": self.summary.covered_lines if self.summary else 0,
                "missed_lines": self.summary.missed_lines if self.summary else 0,
                "line_coverage_percent": self.summary.line_coverage_percent if self.summary else 0.0,
                "total_branches": self.summary.total_branches if self.summary else 0,
                "covered_branches": self.summary.covered_branches if self.summary else 0,
                "branch_coverage_percent": self.summary.branch_coverage_percent if self.summary else 0.0,
                "total_functions": self.summary.total_functions if self.summary else 0,
                "covered_functions": self.summary.covered_functions if self.summary else 0,
                "function_coverage_percent": self.summary.function_coverage_percent if self.summary else 0.0,
            },
            "files": [
                {
                    "file_path": f.file_path,
                    "total_lines": f.total_lines,
                    "covered_lines": f.covered_lines,
                    "missed_lines": f.missed_lines,
                    "coverage_percent": f.coverage_percent,
                    "uncovered_lines": f.uncovered_lines,
                    "functions": [
                        {
                            "name": fn.name,
                            "start_line": fn.start_line,
                            "end_line": fn.end_line,
                            "is_covered": fn.is_covered,
                            "coverage_percent": fn.coverage_percent,
                        }
                        for fn in f.functions
                    ],
                }
                for f in self.file_reports
            ],
        }


@dataclass
class UncoveredSuggestion:
    """Suggestion for adding tests to uncovered code."""
    
    function: FunctionCoverage
    priority: str  # "high", "medium", "low"
    reason: str
    suggested_test_cases: list[str] = field(default_factory=list)
    
    @classmethod
    def from_function(cls, func: FunctionCoverage) -> "UncoveredSuggestion":
        """Create suggestion from uncovered function."""
        # Determine priority based on function characteristics
        if func.total_lines > 20:
            priority = "high"
            reason = f"Large function ({func.total_lines} lines) with no test coverage"
        elif func.total_lines > 10:
            priority = "medium"
            reason = f"Medium function ({func.total_lines} lines) needs test coverage"
        else:
            priority = "low"
            reason = f"Small function ({func.total_lines} lines) could use test coverage"
        
        return cls(
            function=func,
            priority=priority,
            reason=reason,
            suggested_test_cases=[
                f"Test basic functionality of {func.name}",
                f"Test edge cases for {func.name}",
                f"Test error handling in {func.name}",
            ],
        )
