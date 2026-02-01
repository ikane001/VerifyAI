"""Coverage collectors for different test frameworks."""

import json
import subprocess
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from verify_ai.coverage.models import (
    CoverageReport,
    FileMetrics,
    FunctionCoverage,
    LineCoverage,
)


class BaseCoverageCollector(ABC):
    """Abstract base class for coverage collectors."""
    
    @abstractmethod
    def run(
        self,
        test_path: Path,
        source_path: Path,
        test_args: Optional[list[str]] = None,
    ) -> CoverageReport:
        """Run tests and collect coverage data.
        
        Args:
            test_path: Path to test files or directory
            source_path: Path to source files to measure coverage for
            test_args: Additional arguments to pass to test runner
            
        Returns:
            CoverageReport with collected data
        """
        pass


class PytestCoverageCollector(BaseCoverageCollector):
    """Collect coverage using pytest and coverage.py."""
    
    def __init__(self, coverage_config: Optional[dict] = None):
        """Initialize collector.
        
        Args:
            coverage_config: Optional coverage configuration
        """
        self.config = coverage_config or {}
        self.exclude_patterns = self.config.get("exclude", [
            "*/test_*.py",
            "*/__pycache__/*",
            "*/tests/*",
        ])
    
    def run(
        self,
        test_path: Path,
        source_path: Path,
        test_args: Optional[list[str]] = None,
    ) -> CoverageReport:
        """Run pytest with coverage and return report.
        
        Args:
            test_path: Path to test files
            source_path: Path to source files
            test_args: Additional pytest arguments
            
        Returns:
            CoverageReport with coverage data
        """
        start_time = time.time()
        
        # Create temp directory for coverage data
        with tempfile.TemporaryDirectory() as tmpdir:
            coverage_file = Path(tmpdir) / ".coverage"
            json_report = Path(tmpdir) / "coverage.json"
            
            # Build pytest command with coverage
            cmd = [
                sys.executable, "-m", "pytest",
                str(test_path),
                f"--cov={source_path}",
                "--cov-report=json:" + str(json_report),
                "--cov-report=",  # Suppress terminal output
                "-q",  # Quiet mode
            ]
            
            # Add exclude patterns
            for pattern in self.exclude_patterns:
                cmd.append(f"--cov-config=.coveragerc")
            
            if test_args:
                cmd.extend(test_args)
            
            # Set coverage data file location
            env = {
                **subprocess.os.environ,
                "COVERAGE_FILE": str(coverage_file),
            }
            
            # Run pytest with coverage
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    cwd=str(source_path.parent) if source_path.is_file() else str(source_path),
                )
            except FileNotFoundError:
                # pytest-cov not installed, try alternative approach
                return self._run_with_coverage_py(
                    test_path, source_path, test_args, start_time
                )
            
            duration = time.time() - start_time
            
            # Parse JSON report
            if json_report.exists():
                report = self._parse_json_report(
                    json_report,
                    source_path,
                    duration,
                    " ".join(cmd),
                )
                return report
            
            # If JSON report doesn't exist, return empty report
            return CoverageReport(
                project_path=str(source_path),
                duration_seconds=duration,
                test_command=" ".join(cmd),
            )
    
    def _run_with_coverage_py(
        self,
        test_path: Path,
        source_path: Path,
        test_args: Optional[list[str]],
        start_time: float,
    ) -> CoverageReport:
        """Fallback: run with coverage.py directly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_report = Path(tmpdir) / "coverage.json"
            
            # Run coverage
            cmd = [
                sys.executable, "-m", "coverage", "run",
                "--source", str(source_path),
                "-m", "pytest", str(test_path), "-q",
            ]
            
            if test_args:
                cmd.extend(test_args)
            
            subprocess.run(cmd, capture_output=True, text=True)
            
            # Generate JSON report
            report_cmd = [
                sys.executable, "-m", "coverage", "json",
                "-o", str(json_report),
            ]
            subprocess.run(report_cmd, capture_output=True, text=True)
            
            duration = time.time() - start_time
            
            if json_report.exists():
                return self._parse_json_report(
                    json_report, source_path, duration, " ".join(cmd)
                )
            
            return CoverageReport(
                project_path=str(source_path),
                duration_seconds=duration,
                test_command=" ".join(cmd),
            )
    
    def _parse_json_report(
        self,
        json_path: Path,
        source_path: Path,
        duration: float,
        command: str,
    ) -> CoverageReport:
        """Parse coverage.py JSON report.
        
        Args:
            json_path: Path to JSON report file
            source_path: Path to source directory
            duration: Test duration in seconds
            command: Command used to run tests
            
        Returns:
            CoverageReport with parsed data
        """
        with open(json_path) as f:
            data = json.load(f)
        
        file_reports = []
        
        for file_path, file_data in data.get("files", {}).items():
            # Get line coverage data
            executed_lines = set(file_data.get("executed_lines", []))
            missing_lines = set(file_data.get("missing_lines", []))
            all_lines = executed_lines | missing_lines
            
            # Create line coverage entries
            line_coverage = []
            for line_num in sorted(all_lines):
                is_covered = line_num in executed_lines
                line_coverage.append(LineCoverage(
                    line_number=line_num,
                    is_covered=is_covered,
                    hit_count=1 if is_covered else 0,
                ))
            
            # Get summary data
            summary = file_data.get("summary", {})
            total_lines = summary.get("num_statements", len(all_lines))
            covered_lines = summary.get("covered_lines", len(executed_lines))
            missed_lines = summary.get("missing_lines", len(missing_lines))
            
            # Get branch data if available
            total_branches = summary.get("num_branches", 0)
            covered_branches = summary.get("covered_branches", 0)
            
            file_metrics = FileMetrics(
                file_path=file_path,
                total_lines=total_lines,
                covered_lines=covered_lines,
                missed_lines=missed_lines,
                total_branches=total_branches,
                covered_branches=covered_branches,
                line_coverage=line_coverage,
            )
            
            file_reports.append(file_metrics)
        
        return CoverageReport(
            project_path=str(source_path),
            file_reports=file_reports,
            duration_seconds=duration,
            test_command=command,
        )
    
    def run_quick(self, project_path: Path) -> CoverageReport:
        """Run quick coverage analysis for a project.
        
        Automatically detects test and source directories.
        
        Args:
            project_path: Path to project root
            
        Returns:
            CoverageReport with coverage data
        """
        # Detect test directory
        test_paths = [
            project_path / "tests",
            project_path / "test",
            project_path,
        ]
        test_path = next(
            (p for p in test_paths if p.exists() and (p.is_dir() or p.suffix == ".py")),
            project_path,
        )
        
        # Detect source directory
        source_paths = [
            project_path / "src",
            project_path / "lib",
            project_path,
        ]
        source_path = next(
            (p for p in source_paths if p.exists() and p.is_dir()),
            project_path,
        )
        
        return self.run(test_path, source_path)


class CoverageDataLoader:
    """Load existing coverage data from files."""
    
    @staticmethod
    def load_from_json(json_path: Path) -> CoverageReport:
        """Load coverage report from JSON file.
        
        Args:
            json_path: Path to coverage JSON file
            
        Returns:
            CoverageReport with loaded data
        """
        with open(json_path) as f:
            data = json.load(f)
        
        file_reports = []
        
        for file_data in data.get("files", []):
            line_coverage = [
                LineCoverage(
                    line_number=lc["line_number"],
                    is_covered=lc["is_covered"],
                    hit_count=lc.get("hit_count", 0),
                )
                for lc in file_data.get("line_coverage", [])
            ]
            
            functions = [
                FunctionCoverage(
                    name=fn["name"],
                    file_path=file_data["file_path"],
                    start_line=fn["start_line"],
                    end_line=fn["end_line"],
                    is_covered=fn["is_covered"],
                    total_lines=fn.get("total_lines", 0),
                    covered_lines=fn.get("covered_lines", 0),
                )
                for fn in file_data.get("functions", [])
            ]
            
            file_reports.append(FileMetrics(
                file_path=file_data["file_path"],
                total_lines=file_data["total_lines"],
                covered_lines=file_data["covered_lines"],
                missed_lines=file_data["missed_lines"],
                total_branches=file_data.get("total_branches", 0),
                covered_branches=file_data.get("covered_branches", 0),
                line_coverage=line_coverage,
                functions=functions,
            ))
        
        return CoverageReport(
            project_path=data.get("project_path", ""),
            file_reports=file_reports,
            duration_seconds=data.get("duration_seconds", 0.0),
            test_command=data.get("test_command", ""),
        )
    
    @staticmethod
    def load_from_coverage_file(coverage_path: Path) -> CoverageReport:
        """Load coverage from .coverage SQLite database.
        
        Args:
            coverage_path: Path to .coverage file
            
        Returns:
            CoverageReport with loaded data
        """
        try:
            import coverage
            
            cov = coverage.Coverage(data_file=str(coverage_path))
            cov.load()
            
            file_reports = []
            
            for filename in cov.get_data().measured_files():
                analysis = cov.analysis2(filename)
                
                # analysis2 returns: (filename, executable, excluded, missing, formatted_missing)
                _, executable, excluded, missing, _ = analysis
                
                executed = set(executable) - set(missing)
                
                line_coverage = []
                for line_num in sorted(set(executable)):
                    is_covered = line_num in executed
                    line_coverage.append(LineCoverage(
                        line_number=line_num,
                        is_covered=is_covered,
                        hit_count=1 if is_covered else 0,
                    ))
                
                file_reports.append(FileMetrics(
                    file_path=filename,
                    total_lines=len(executable),
                    covered_lines=len(executed),
                    missed_lines=len(missing),
                    line_coverage=line_coverage,
                ))
            
            return CoverageReport(
                project_path=str(coverage_path.parent),
                file_reports=file_reports,
            )
            
        except ImportError:
            raise ImportError("coverage package is required to load .coverage files")
