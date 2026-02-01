"""Coverage analyzer for VerifyAI."""

from pathlib import Path
from typing import Optional

from verify_ai.coverage.collectors import PytestCoverageCollector
from verify_ai.coverage.models import (
    CoverageReport,
    FunctionCoverage,
    UncoveredSuggestion,
)


class CoverageAnalyzer:
    """Main coverage analyzer class.
    
    Provides high-level interface for running coverage analysis,
    identifying uncovered code, and suggesting tests.
    """
    
    def __init__(
        self,
        project_path: Optional[Path] = None,
        config: Optional[dict] = None,
    ):
        """Initialize coverage analyzer.
        
        Args:
            project_path: Path to project root
            config: Coverage configuration
        """
        self.project_path = Path(project_path or ".").resolve()
        self.config = config or {}
        self.collector = PytestCoverageCollector(self.config)
        self._latest_report: Optional[CoverageReport] = None
    
    def run_with_coverage(
        self,
        test_path: Optional[Path] = None,
        source_path: Optional[Path] = None,
        test_args: Optional[list[str]] = None,
    ) -> CoverageReport:
        """Run tests with coverage collection.
        
        Args:
            test_path: Path to test files (auto-detected if not provided)
            source_path: Path to source files (auto-detected if not provided)
            test_args: Additional test arguments
            
        Returns:
            CoverageReport with results
        """
        # Auto-detect paths if not provided
        if test_path is None:
            test_path = self._detect_test_path()
        if source_path is None:
            source_path = self._detect_source_path()
        
        # Run coverage collection
        self._latest_report = self.collector.run(
            test_path=test_path,
            source_path=source_path,
            test_args=test_args,
        )
        
        return self._latest_report
    
    def analyze_uncovered(
        self,
        report: Optional[CoverageReport] = None,
        threshold: float = 0.0,
    ) -> list[FunctionCoverage]:
        """Analyze and return uncovered functions.
        
        Args:
            report: Coverage report to analyze (uses latest if not provided)
            threshold: Minimum coverage threshold (0-100)
            
        Returns:
            List of uncovered functions
        """
        if report is None:
            report = self._latest_report
        
        if report is None:
            raise ValueError("No coverage report available. Run coverage first.")
        
        uncovered = []
        
        for file_report in report.file_reports:
            # Skip files above threshold
            if file_report.coverage_percent >= threshold:
                continue
            
            # Add uncovered functions
            for func in file_report.functions:
                if not func.is_covered or func.coverage_percent < threshold:
                    uncovered.append(func)
        
        # Sort by priority (larger functions first)
        uncovered.sort(key=lambda f: f.total_lines, reverse=True)
        
        return uncovered
    
    def suggest_tests_for_uncovered(
        self,
        report: Optional[CoverageReport] = None,
        max_suggestions: int = 10,
    ) -> list[UncoveredSuggestion]:
        """Generate test suggestions for uncovered code.
        
        Args:
            report: Coverage report to analyze
            max_suggestions: Maximum number of suggestions to return
            
        Returns:
            List of test suggestions
        """
        uncovered = self.analyze_uncovered(report)
        
        suggestions = []
        for func in uncovered[:max_suggestions]:
            suggestion = UncoveredSuggestion.from_function(func)
            suggestions.append(suggestion)
        
        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda s: priority_order.get(s.priority, 3))
        
        return suggestions
    
    def check_threshold(
        self,
        threshold: float,
        report: Optional[CoverageReport] = None,
    ) -> tuple[bool, str]:
        """Check if coverage meets threshold.
        
        Args:
            threshold: Required coverage percentage (0-100)
            report: Coverage report to check
            
        Returns:
            Tuple of (passes, message)
        """
        if report is None:
            report = self._latest_report
        
        if report is None:
            return False, "No coverage report available"
        
        coverage = report.coverage_percent
        
        if coverage >= threshold:
            return True, f"Coverage {coverage:.1f}% meets threshold {threshold:.1f}%"
        else:
            return False, f"Coverage {coverage:.1f}% is below threshold {threshold:.1f}%"
    
    def get_files_below_threshold(
        self,
        threshold: float,
        report: Optional[CoverageReport] = None,
    ) -> list[tuple[str, float]]:
        """Get files with coverage below threshold.
        
        Args:
            threshold: Coverage threshold percentage
            report: Coverage report to analyze
            
        Returns:
            List of (file_path, coverage_percent) tuples
        """
        if report is None:
            report = self._latest_report
        
        if report is None:
            return []
        
        below_threshold = []
        for file_report in report.file_reports:
            if file_report.coverage_percent < threshold:
                below_threshold.append((
                    file_report.file_path,
                    file_report.coverage_percent,
                ))
        
        # Sort by coverage (lowest first)
        below_threshold.sort(key=lambda x: x[1])
        
        return below_threshold
    
    def _detect_test_path(self) -> Path:
        """Auto-detect test directory."""
        candidates = [
            self.project_path / "tests",
            self.project_path / "test",
        ]
        
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate
        
        return self.project_path
    
    def _detect_source_path(self) -> Path:
        """Auto-detect source directory."""
        candidates = [
            self.project_path / "src",
            self.project_path / "lib",
        ]
        
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate
        
        return self.project_path
    
    @property
    def latest_report(self) -> Optional[CoverageReport]:
        """Get the latest coverage report."""
        return self._latest_report
    
    def get_summary(self, report: Optional[CoverageReport] = None) -> dict:
        """Get coverage summary as dictionary.
        
        Args:
            report: Coverage report (uses latest if not provided)
            
        Returns:
            Summary dictionary
        """
        if report is None:
            report = self._latest_report
        
        if report is None:
            return {
                "has_data": False,
                "message": "No coverage data available",
            }
        
        return {
            "has_data": True,
            "project_path": report.project_path,
            "total_files": report.summary.total_files if report.summary else 0,
            "total_lines": report.summary.total_lines if report.summary else 0,
            "covered_lines": report.summary.covered_lines if report.summary else 0,
            "coverage_percent": report.coverage_percent,
            "duration_seconds": report.duration_seconds,
        }
