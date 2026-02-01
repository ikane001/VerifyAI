"""Coverage analysis module for VerifyAI."""

from verify_ai.coverage.models import (
    CoverageReport,
    FileMetrics,
    FunctionCoverage,
    LineCoverage,
    CoverageSummary,
)
from verify_ai.coverage.analyzer import CoverageAnalyzer
from verify_ai.coverage.collectors import PytestCoverageCollector
from verify_ai.coverage.reporter import (
    CoverageReporter,
    HTMLReporter,
    JSONReporter,
    ConsoleReporter,
)

__all__ = [
    "CoverageReport",
    "FileMetrics",
    "FunctionCoverage",
    "LineCoverage",
    "CoverageSummary",
    "CoverageAnalyzer",
    "PytestCoverageCollector",
    "CoverageReporter",
    "HTMLReporter",
    "JSONReporter",
    "ConsoleReporter",
]
