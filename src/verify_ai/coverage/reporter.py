"""Coverage report generators."""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text

from verify_ai.coverage.models import CoverageReport, FileMetrics


class CoverageReporter(ABC):
    """Abstract base class for coverage reporters."""
    
    @abstractmethod
    def generate(self, report: CoverageReport, output_path: Optional[Path] = None) -> str:
        """Generate coverage report.
        
        Args:
            report: Coverage report data
            output_path: Optional path to save report
            
        Returns:
            Report content as string
        """
        pass


class ConsoleReporter(CoverageReporter):
    """Generate coverage report for console output."""
    
    def __init__(self, show_details: bool = False, threshold: float = 80.0):
        """Initialize console reporter.
        
        Args:
            show_details: Show detailed line coverage
            threshold: Coverage threshold for highlighting
        """
        self.show_details = show_details
        self.threshold = threshold
        self.console = Console()
    
    def generate(self, report: CoverageReport, output_path: Optional[Path] = None) -> str:
        """Generate and display console report.
        
        Args:
            report: Coverage report data
            output_path: Ignored for console output
            
        Returns:
            Empty string (output is printed directly)
        """
        # Summary panel
        summary = report.summary
        if summary:
            coverage_pct = summary.line_coverage_percent
            status = "✓" if coverage_pct >= self.threshold else "✗"
            color = "green" if coverage_pct >= self.threshold else "red"
            
            summary_text = Text()
            summary_text.append(f"\n  Line Coverage: ", style="bold")
            summary_text.append(f"{coverage_pct:.1f}%", style=f"bold {color}")
            summary_text.append(f" {status}\n", style=color)
            summary_text.append(f"  Lines: {summary.covered_lines}/{summary.total_lines}\n")
            summary_text.append(f"  Files: {summary.total_files}\n")
            if summary.total_branches > 0:
                summary_text.append(f"  Branches: {summary.covered_branches}/{summary.total_branches} ")
                summary_text.append(f"({summary.branch_coverage_percent:.1f}%)\n")
            if summary.total_functions > 0:
                summary_text.append(f"  Functions: {summary.covered_functions}/{summary.total_functions} ")
                summary_text.append(f"({summary.function_coverage_percent:.1f}%)\n")
            
            self.console.print(Panel(
                summary_text,
                title="Coverage Summary",
                border_style="blue",
            ))
        
        # File coverage table
        if report.file_reports:
            table = Table(title="File Coverage", show_header=True, header_style="bold")
            table.add_column("File", style="cyan", no_wrap=True)
            table.add_column("Lines", justify="right")
            table.add_column("Covered", justify="right")
            table.add_column("Missed", justify="right")
            table.add_column("Coverage", justify="right")
            table.add_column("Status", justify="center")
            
            for file_report in sorted(report.file_reports, key=lambda f: f.coverage_percent):
                pct = file_report.coverage_percent
                status = "✓" if pct >= self.threshold else "✗"
                color = "green" if pct >= self.threshold else "red" if pct < 50 else "yellow"
                
                # Shorten file path for display
                file_path = file_report.file_path
                if len(file_path) > 50:
                    file_path = "..." + file_path[-47:]
                
                table.add_row(
                    file_path,
                    str(file_report.total_lines),
                    str(file_report.covered_lines),
                    str(file_report.missed_lines),
                    f"[{color}]{pct:.1f}%[/{color}]",
                    f"[{color}]{status}[/{color}]",
                )
            
            self.console.print(table)
        
        # Show uncovered functions if details enabled
        if self.show_details:
            uncovered = report.get_uncovered_functions()
            if uncovered:
                self.console.print("\n[bold]Uncovered Functions:[/bold]")
                for func in uncovered[:10]:
                    self.console.print(
                        f"  • [cyan]{func.name}[/cyan] "
                        f"({func.file_path}:{func.start_line}-{func.end_line})"
                    )
                if len(uncovered) > 10:
                    self.console.print(f"  ... and {len(uncovered) - 10} more")
        
        return ""
    
    def print_progress(self, report: CoverageReport):
        """Print coverage as progress bar.
        
        Args:
            report: Coverage report data
        """
        if report.summary:
            pct = report.summary.line_coverage_percent
            color = "green" if pct >= self.threshold else "red" if pct < 50 else "yellow"
            
            with Progress(
                TextColumn("[bold blue]Coverage"),
                BarColumn(complete_style=color),
                TextColumn(f"[{color}]{pct:.1f}%[/{color}]"),
            ) as progress:
                task = progress.add_task("coverage", total=100)
                progress.update(task, completed=pct)


class JSONReporter(CoverageReporter):
    """Generate coverage report in JSON format."""
    
    def __init__(self, pretty: bool = True):
        """Initialize JSON reporter.
        
        Args:
            pretty: Use pretty formatting
        """
        self.pretty = pretty
    
    def generate(self, report: CoverageReport, output_path: Optional[Path] = None) -> str:
        """Generate JSON report.
        
        Args:
            report: Coverage report data
            output_path: Optional path to save report
            
        Returns:
            JSON string
        """
        data = report.to_dict()
        
        if self.pretty:
            content = json.dumps(data, indent=2, ensure_ascii=False)
        else:
            content = json.dumps(data, ensure_ascii=False)
        
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content)
        
        return content


class HTMLReporter(CoverageReporter):
    """Generate coverage report in HTML format."""
    
    def __init__(self, title: str = "Coverage Report"):
        """Initialize HTML reporter.
        
        Args:
            title: Report title
        """
        self.title = title
    
    def generate(self, report: CoverageReport, output_path: Optional[Path] = None) -> str:
        """Generate HTML report.
        
        Args:
            report: Coverage report data
            output_path: Optional path to save report
            
        Returns:
            HTML string
        """
        summary = report.summary
        coverage_pct = summary.line_coverage_percent if summary else 0
        
        # Generate file rows
        file_rows = []
        for file_report in sorted(report.file_reports, key=lambda f: f.coverage_percent):
            pct = file_report.coverage_percent
            color = "#28a745" if pct >= 80 else "#dc3545" if pct < 50 else "#ffc107"
            
            file_rows.append(f"""
            <tr>
                <td><code>{file_report.file_path}</code></td>
                <td class="text-right">{file_report.total_lines}</td>
                <td class="text-right">{file_report.covered_lines}</td>
                <td class="text-right">{file_report.missed_lines}</td>
                <td class="text-right">
                    <div class="progress-bar" style="--pct: {pct}%">
                        <span style="color: {color}">{pct:.1f}%</span>
                    </div>
                </td>
            </tr>
            """)
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.title}</title>
    <style>
        :root {{
            --bg-color: #f5f5f5;
            --card-bg: #ffffff;
            --text-color: #333333;
            --border-color: #e0e0e0;
            --success-color: #28a745;
            --warning-color: #ffc107;
            --danger-color: #dc3545;
        }}
        
        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg-color: #1a1a2e;
                --card-bg: #16213e;
                --text-color: #e0e0e0;
                --border-color: #2a3a5a;
            }}
        }}
        
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            padding: 2rem;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        h1 {{
            margin-bottom: 2rem;
            font-size: 2rem;
        }}
        
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        
        .summary-card {{
            background: var(--card-bg);
            border-radius: 8px;
            padding: 1.5rem;
            border: 1px solid var(--border-color);
        }}
        
        .summary-card h3 {{
            font-size: 0.875rem;
            color: #888;
            margin-bottom: 0.5rem;
        }}
        
        .summary-card .value {{
            font-size: 2rem;
            font-weight: bold;
        }}
        
        .coverage-circle {{
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: conic-gradient(
                {"var(--success-color)" if coverage_pct >= 80 else "var(--danger-color)" if coverage_pct < 50 else "var(--warning-color)"} {coverage_pct}%,
                var(--border-color) {coverage_pct}%
            );
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto;
        }}
        
        .coverage-circle-inner {{
            width: 100px;
            height: 100px;
            border-radius: 50%;
            background: var(--card-bg);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            font-weight: bold;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--card-bg);
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid var(--border-color);
        }}
        
        th, td {{
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        
        th {{
            background: var(--bg-color);
            font-weight: 600;
        }}
        
        tr:hover {{
            background: var(--bg-color);
        }}
        
        .text-right {{
            text-align: right;
        }}
        
        .progress-bar {{
            width: 100px;
            height: 20px;
            background: var(--border-color);
            border-radius: 10px;
            overflow: hidden;
            position: relative;
        }}
        
        .progress-bar::before {{
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            height: 100%;
            width: var(--pct);
            background: currentColor;
            opacity: 0.3;
        }}
        
        .progress-bar span {{
            position: relative;
            z-index: 1;
            padding: 0 8px;
            font-size: 0.875rem;
            font-weight: 600;
        }}
        
        code {{
            font-family: 'Fira Code', Consolas, monospace;
            font-size: 0.875rem;
        }}
        
        .timestamp {{
            color: #888;
            font-size: 0.875rem;
            margin-top: 2rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{self.title}</h1>
        
        <div class="summary">
            <div class="summary-card">
                <div class="coverage-circle">
                    <div class="coverage-circle-inner">
                        {coverage_pct:.1f}%
                    </div>
                </div>
            </div>
            <div class="summary-card">
                <h3>Total Lines</h3>
                <div class="value">{summary.total_lines if summary else 0}</div>
            </div>
            <div class="summary-card">
                <h3>Covered Lines</h3>
                <div class="value" style="color: var(--success-color)">{summary.covered_lines if summary else 0}</div>
            </div>
            <div class="summary-card">
                <h3>Missed Lines</h3>
                <div class="value" style="color: var(--danger-color)">{summary.missed_lines if summary else 0}</div>
            </div>
            <div class="summary-card">
                <h3>Files</h3>
                <div class="value">{summary.total_files if summary else 0}</div>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>File</th>
                    <th class="text-right">Lines</th>
                    <th class="text-right">Covered</th>
                    <th class="text-right">Missed</th>
                    <th class="text-right">Coverage</th>
                </tr>
            </thead>
            <tbody>
                {"".join(file_rows)}
            </tbody>
        </table>
        
        <p class="timestamp">
            Generated: {report.timestamp.strftime("%Y-%m-%d %H:%M:%S")}
            | Duration: {report.duration_seconds:.2f}s
        </p>
    </div>
</body>
</html>
"""
        
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html)
        
        return html


def create_reporter(format: str, **kwargs) -> CoverageReporter:
    """Factory function to create appropriate reporter.
    
    Args:
        format: Report format ('console', 'json', 'html')
        **kwargs: Additional arguments for reporter
        
    Returns:
        CoverageReporter instance
    """
    reporters = {
        "console": ConsoleReporter,
        "text": ConsoleReporter,
        "json": JSONReporter,
        "html": HTMLReporter,
    }
    
    reporter_class = reporters.get(format.lower())
    if reporter_class is None:
        raise ValueError(f"Unknown report format: {format}. Available: {list(reporters.keys())}")
    
    return reporter_class(**kwargs)
