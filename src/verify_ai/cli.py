"""CLI for VerifyAI."""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.tree import Tree

from . import __version__
from .config import ProjectConfig, settings
from .core.generator import GeneratedTest, TestGenerator, TestWriter
from .core.scanner import ProjectInfo, ProjectScanner
from .git import GitTracker, get_strategy_for_trigger, VerificationLevel
from .analysis import TestAnalyzer, FixGenerator, FixSuggestion
from .scenario import APILogParser, HARParser, ErrorLogParser, generate_tests_from_har
from .llm import create_llm_client

app = typer.Typer(
    name="vai",
    help="VerifyAI - AI-powered automated verification system",
    add_completion=False,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"VerifyAI v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version and exit"
    ),
):
    """VerifyAI - AI-powered automated verification system."""
    pass


@app.command()
def init(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the project to initialize",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Overwrite existing configuration",
    ),
):
    """Initialize VerifyAI for a project.

    Creates a verify-ai.yaml configuration file in the project root.
    """
    project_path = path.resolve()

    if not project_path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {project_path}")
        raise typer.Exit(1)

    config_file = project_path / "verify-ai.yaml"

    if config_file.exists() and not force:
        console.print(
            f"[yellow]Warning:[/yellow] Configuration already exists at {config_file}"
        )
        console.print("Use --force to overwrite")
        raise typer.Exit(1)

    # Scan project to detect languages
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Scanning project...", total=None)
        scanner = ProjectScanner(project_path)
        info = scanner.scan()

    # Create default configuration
    config_content = f"""# VerifyAI Configuration
# Generated for: {info.name}

project:
  name: {info.name}
  languages: {info.languages}
  test_output: ./tests/generated

llm:
  provider: claude  # claude | openai | ollama
  model: claude-sonnet-4-20250514
  fallback: ollama/codellama  # Fallback to local model if API fails

triggers:
  push:
    - lint
    - affected_unit_tests
  pull_request:
    - unit_tests
    - integration_tests
    - ai_review
  merge_to_main:
    - regression_tests
    - e2e_tests
  scheduled:
    cron: "0 2 * * *"
    jobs:
      - full_regression
      - test_regeneration

fix:
  auto_fix_tests: true      # Auto-fix test code issues
  auto_fix_source: false    # Source fixes require approval
  require_approval: true    # Show diff before applying fixes
"""

    config_file.write_text(config_content)

    console.print(Panel.fit(
        f"[green]✓[/green] VerifyAI initialized for [bold]{info.name}[/bold]\n\n"
        f"Configuration saved to: {config_file}\n\n"
        f"Detected languages: {', '.join(info.languages) or 'None'}\n"
        f"Source files: {len(info.source_files)}\n"
        f"Existing tests: {len(info.test_files)}",
        title="Initialization Complete",
    ))


@app.command()
def scan(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the project to scan",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-V",
        help="Show detailed output",
    ),
):
    """Scan a project and show its structure.

    Analyzes the project to find source files, test files,
    API specifications, and code structure.
    """
    project_path = path.resolve()

    if not project_path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {project_path}")
        raise typer.Exit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning project...", total=None)
        scanner = ProjectScanner(project_path)
        info = scanner.scan()

    # Display results
    console.print()
    console.print(Panel.fit(
        f"[bold]{info.name}[/bold]\n{info.path}",
        title="Project",
    ))

    # Summary table
    table = Table(title="Project Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Languages", ", ".join(info.languages) or "None")
    table.add_row("Source Files", str(len(info.source_files)))
    table.add_row("Test Files", str(len(info.test_files)))
    table.add_row("Functions", str(len(info.functions)))
    table.add_row("Classes", str(len(info.classes)))
    table.add_row("API Endpoints", str(len(info.api_endpoints)))

    if info.git_info.is_repo:
        table.add_row("Git Branch", info.git_info.current_branch)
        table.add_row("Changed Files", str(len(info.git_info.changed_files)))

    console.print(table)

    if verbose:
        # Show file tree
        if info.source_files:
            tree = Tree("[bold]Source Files[/bold]")
            for f in info.source_files[:20]:  # Limit to 20
                tree.add(str(f.relative_to(project_path)))
            if len(info.source_files) > 20:
                tree.add(f"... and {len(info.source_files) - 20} more")
            console.print(tree)

        # Show API endpoints
        if info.api_endpoints:
            console.print()
            ep_table = Table(title="API Endpoints")
            ep_table.add_column("Method", style="cyan")
            ep_table.add_column("Path", style="green")
            ep_table.add_column("Summary")

            for ep in info.api_endpoints[:10]:  # Limit to 10
                ep_table.add_row(ep.method.upper(), ep.path, ep.summary[:50] if ep.summary else "")

            if len(info.api_endpoints) > 10:
                ep_table.add_row("...", f"and {len(info.api_endpoints) - 10} more", "")

            console.print(ep_table)

        # Show functions
        if info.functions:
            console.print()
            func_table = Table(title="Functions")
            func_table.add_column("Name", style="cyan")
            func_table.add_column("File")
            func_table.add_column("Line", justify="right")

            for func in info.functions[:15]:  # Limit to 15
                rel_path = Path(func.file_path).relative_to(project_path)
                func_table.add_row(func.name, str(rel_path), str(func.line_number))

            if len(info.functions) > 15:
                func_table.add_row("...", f"and {len(info.functions) - 15} more", "")

            console.print(func_table)


@app.command()
def generate(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the project",
    ),
    output: Path = typer.Option(
        None, "--output", "-o",
        help="Output directory for generated tests",
    ),
    test_type: str = typer.Option(
        "all", "--type", "-t",
        help="Type of tests to generate: api, unit, all",
    ),
    llm: str = typer.Option(
        None, "--llm", "-l",
        help="LLM provider to use: claude, openai, ollama",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Show what would be generated without writing files",
    ),
):
    """Generate tests for a project.

    Uses LLM to analyze code and generate comprehensive test cases.
    """
    project_path = path.resolve()

    if not project_path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {project_path}")
        raise typer.Exit(1)

    # Load configuration
    config = ProjectConfig.find_and_load(project_path)

    # Override LLM provider if specified
    if llm:
        config.llm.provider = llm  # type: ignore

    # Determine output directory
    if output is None:
        output = project_path / config.test_output
    output = output.resolve()

    # Scan project
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning project...", total=None)
        scanner = ProjectScanner(project_path)
        info = scanner.scan()
        progress.update(task, completed=True)

    # Check what to generate
    generate_api = test_type in ("api", "all") and info.api_endpoints
    generate_unit = test_type in ("unit", "all") and (info.functions or info.classes)

    if not generate_api and not generate_unit:
        console.print("[yellow]Nothing to generate.[/yellow]")
        console.print("No API endpoints or functions found.")
        raise typer.Exit(0)

    # Show what will be generated
    console.print()
    console.print(Panel.fit(
        f"[bold]Test Generation Plan[/bold]\n\n"
        f"LLM Provider: {config.llm.provider}\n"
        f"Model: {config.llm.model}\n"
        f"Output: {output}\n\n"
        f"API Tests: {len(info.api_endpoints) if generate_api else 0}\n"
        f"Unit Tests: {len(info.functions) + sum(len(c.methods) for c in info.classes) if generate_unit else 0}",
        title="Generation Plan",
    ))

    if dry_run:
        console.print("\n[yellow]Dry run - no files will be written[/yellow]")
        raise typer.Exit(0)

    # Confirm
    if not typer.confirm("\nProceed with generation?"):
        raise typer.Exit(0)

    # Generate tests
    async def run_generation():
        try:
            generator = TestGenerator(config=config)
            all_tests: list[GeneratedTest] = []

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                # Generate API tests
                if generate_api:
                    task = progress.add_task(
                        f"Generating API tests ({len(info.api_endpoints)} endpoints)...",
                        total=None
                    )
                    api_tests = await generator.generate_api_tests_batch(
                        info.api_endpoints,
                        base_url=info.config.llm.model if info.config else "http://localhost:8000",
                    )
                    all_tests.extend(api_tests)
                    progress.update(task, completed=True)

                # Generate unit tests
                if generate_unit:
                    task = progress.add_task(
                        f"Generating unit tests ({len(info.functions)} functions)...",
                        total=None
                    )
                    for func in info.functions:
                        if not func.name.startswith("_"):
                            test = await generator.generate_unit_test(func)
                            all_tests.append(test)
                    progress.update(task, completed=True)

            return all_tests

        except ValueError as e:
            console.print(f"\n[red]Error:[/red] {e}")
            console.print("\nMake sure you have set the appropriate API key:")
            console.print("  - For Claude: VAI_CLAUDE_API_KEY")
            console.print("  - For OpenAI: VAI_OPENAI_API_KEY")
            raise typer.Exit(1)

    tests = asyncio.run(run_generation())

    # Write tests
    if not dry_run and tests:
        writer = TestWriter(output)
        paths = writer.write_all(tests)

        console.print()
        console.print(Panel.fit(
            f"[green]✓[/green] Generated {len(tests)} test(s)\n\n"
            f"Output directory: {output}\n"
            f"Files written: {len(set(paths))}",
            title="Generation Complete",
        ))

        # List generated files
        console.print("\n[bold]Generated Files:[/bold]")
        for p in sorted(set(paths)):
            console.print(f"  • {p.relative_to(project_path)}")


@app.command()
def verify(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the project",
    ),
    trigger: str = typer.Option(
        "manual", "--trigger", "-t",
        help="Trigger type: push, pr, merge, scheduled, manual",
    ),
    base_branch: str = typer.Option(
        "main", "--base", "-b",
        help="Base branch for comparison (PR/merge)",
    ),
    generate: bool = typer.Option(
        True, "--generate/--no-generate",
        help="Generate missing tests",
    ),
):
    """Run verification on a project.

    Executes the appropriate tests based on the trigger type and strategy.
    Uses Git to detect changed files for incremental verification.
    """
    project_path = path.resolve()

    if not project_path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {project_path}")
        raise typer.Exit(1)

    # Get verification strategy
    strategy = get_strategy_for_trigger(trigger)  # type: ignore

    console.print(Panel.fit(
        f"[bold]Verification Strategy[/bold]\n\n"
        f"Trigger: {trigger}\n"
        f"Level: {strategy.level.value}\n"
        f"Description: {strategy.description}",
        title="Verification",
    ))

    # Initialize git tracker
    tracker = GitTracker(project_path)

    if not tracker.is_valid:
        console.print("[yellow]Warning:[/yellow] Not a git repository, will verify all files")

    # Get changes based on trigger type
    changes = []
    if tracker.is_valid:
        if trigger == "push":
            # Get uncommitted changes
            changes = tracker.get_uncommitted_changes()
        elif trigger in ("pr", "merge"):
            # Get changes compared to base branch
            changes = tracker.get_pr_changes(base_branch=base_branch)
        else:
            # Manual/scheduled - get recent changes
            changes = tracker.get_changes_in_commit("HEAD")

    # Filter to source files
    source_changes = [c for c in changes if c.is_source_file and not c.is_test_file]

    # Display changes
    if source_changes:
        console.print()
        changes_table = Table(title="Changed Files")
        changes_table.add_column("Type", style="cyan", width=8)
        changes_table.add_column("File")
        changes_table.add_column("+", style="green", justify="right", width=6)
        changes_table.add_column("-", style="red", justify="right", width=6)

        for change in source_changes[:20]:
            changes_table.add_row(
                change.change_type.value,
                change.path,
                str(change.additions) if change.additions else "",
                str(change.deletions) if change.deletions else "",
            )

        if len(source_changes) > 20:
            changes_table.add_row("...", f"and {len(source_changes) - 20} more", "", "")

        console.print(changes_table)
    else:
        console.print("\n[dim]No source file changes detected[/dim]")

    # Show strategy config
    console.print()
    config_table = Table(title="Verification Config")
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value")

    cfg = strategy.config
    config_table.add_row("Verify changed files", str(cfg.verify_changed_files))
    config_table.add_row("Verify affected files", str(cfg.verify_affected_files))
    config_table.add_row("Generate missing tests", str(cfg.generate_missing_tests))
    config_table.add_row("Run existing tests", str(cfg.run_existing_tests))
    config_table.add_row("Fail fast", str(cfg.fail_fast))
    config_table.add_row("Block on failure", str(cfg.block_on_failure))
    config_table.add_row("Timeout", f"{cfg.total_timeout}s")

    console.print(config_table)

    # Show what would be verified
    console.print()
    if source_changes and cfg.verify_changed_files:
        console.print(f"[bold]Files to verify:[/bold] {len(source_changes)}")

        # Scan project to find affected files
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning project...", total=None)
            scanner = ProjectScanner(project_path)
            info = scanner.scan()

        if cfg.verify_affected_files and info.dependencies:
            from .git.strategy import ImpactAnalyzer
            analyzer = ImpactAnalyzer(info)
            affected = analyzer.get_affected_files([c.path for c in source_changes])
            if affected:
                console.print(f"[bold]Affected files:[/bold] {len(affected)}")
                for f in affected[:5]:
                    console.print(f"  • {f}")
                if len(affected) > 5:
                    console.print(f"  ... and {len(affected) - 5} more")

    # For now, show the plan
    console.print()
    console.print(Panel.fit(
        "[green]✓[/green] Verification analysis complete\n\n"
        "Next steps would be:\n"
        "1. Run existing tests for changed files\n"
        "2. Generate missing tests if enabled\n"
        "3. Execute generated tests\n"
        "4. Report results",
        title="Summary",
    ))


@app.command()
def diff(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the project",
    ),
    from_ref: str = typer.Option(
        "HEAD~1", "--from", "-f",
        help="Starting reference (older)",
    ),
    to_ref: str = typer.Option(
        "HEAD", "--to", "-t",
        help="Ending reference (newer)",
    ),
    show_functions: bool = typer.Option(
        False, "--functions",
        help="Show changed functions",
    ),
):
    """Show git changes between two references.

    Useful for understanding what changed and what needs verification.
    """
    project_path = path.resolve()

    tracker = GitTracker(project_path)

    if not tracker.is_valid:
        console.print("[red]Error:[/red] Not a git repository")
        raise typer.Exit(1)

    # Get changes
    changes = tracker.get_changes_between(from_ref, to_ref)

    if not changes:
        console.print(f"[dim]No changes between {from_ref} and {to_ref}[/dim]")
        raise typer.Exit(0)

    # Show changes
    console.print(Panel.fit(
        f"[bold]Changes[/bold] from {from_ref} to {to_ref}",
        title="Git Diff",
    ))

    # Summary
    source_files = [c for c in changes if c.is_source_file]
    test_files = [c for c in changes if c.is_test_file]
    other_files = [c for c in changes if not c.is_source_file and not c.is_test_file]

    summary_table = Table(title="Summary")
    summary_table.add_column("Category", style="cyan")
    summary_table.add_column("Count", justify="right")
    summary_table.add_column("Additions", style="green", justify="right")
    summary_table.add_column("Deletions", style="red", justify="right")

    for category, files in [("Source", source_files), ("Tests", test_files), ("Other", other_files)]:
        if files:
            total_add = sum(f.additions for f in files)
            total_del = sum(f.deletions for f in files)
            summary_table.add_row(category, str(len(files)), f"+{total_add}", f"-{total_del}")

    console.print(summary_table)

    # File list
    console.print()
    file_table = Table(title="Changed Files")
    file_table.add_column("Type", style="cyan", width=4)
    file_table.add_column("File")
    file_table.add_column("+", style="green", justify="right", width=6)
    file_table.add_column("-", style="red", justify="right", width=6)

    for change in changes:
        type_emoji = {
            "A": "[green]A[/green]",
            "M": "[yellow]M[/yellow]",
            "D": "[red]D[/red]",
            "R": "[blue]R[/blue]",
        }.get(change.change_type.value, change.change_type.value)

        file_table.add_row(
            type_emoji,
            change.path,
            str(change.additions) if change.additions else "",
            str(change.deletions) if change.deletions else "",
        )

    console.print(file_table)

    # Show changed functions
    if show_functions:
        console.print()
        changed_funcs = tracker.get_changed_functions(from_ref, to_ref)

        if changed_funcs:
            func_table = Table(title="Changed Functions")
            func_table.add_column("Function", style="cyan")
            func_table.add_column("File")
            func_table.add_column("Change", style="yellow")

            for func in changed_funcs:
                func_table.add_row(func["name"], func["file"], func["change"])

            console.print(func_table)
        else:
            console.print("[dim]No function changes detected[/dim]")


@app.command()
def commits(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the project",
    ),
    count: int = typer.Option(
        10, "--count", "-n",
        help="Number of commits to show",
    ),
    since: str = typer.Option(
        None, "--since", "-s",
        help="Show commits since date (e.g., '2024-01-01')",
    ),
):
    """Show recent commit history.

    Lists commits with their changed files.
    """
    project_path = path.resolve()

    tracker = GitTracker(project_path)

    if not tracker.is_valid:
        console.print("[red]Error:[/red] Not a git repository")
        raise typer.Exit(1)

    commits_list = tracker.get_commits(max_count=count, since=since)

    if not commits_list:
        console.print("[dim]No commits found[/dim]")
        raise typer.Exit(0)

    console.print(Panel.fit(
        f"[bold]Recent Commits[/bold] (showing {len(commits_list)})",
        title="Git History",
    ))

    for commit in commits_list:
        source_changes = len(commit.source_files_changed)
        test_changes = len(commit.test_files_changed)

        console.print()
        console.print(
            f"[yellow]{commit.short_sha}[/yellow] "
            f"[bold]{commit.message.split(chr(10))[0][:60]}[/bold]"
        )
        console.print(
            f"  [dim]{commit.author} • {commit.timestamp.strftime('%Y-%m-%d %H:%M')} • "
            f"{source_changes} source, {test_changes} test files[/dim]"
        )


@app.command()
def analyze(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the project",
    ),
    pytest_output: str = typer.Option(
        None, "--output", "-o",
        help="Path to pytest output file, or '-' to read from stdin",
    ),
    suggest_fixes: bool = typer.Option(
        True, "--fixes/--no-fixes",
        help="Generate fix suggestions",
    ),
):
    """Analyze test failures and suggest fixes.

    Parses pytest output to identify failures and generate fix suggestions.
    """
    project_path = path.resolve()

    # Read pytest output
    output_text = ""
    if pytest_output:
        if pytest_output == "-":
            import sys
            output_text = sys.stdin.read()
        else:
            output_text = Path(pytest_output).read_text()
    else:
        # Run pytest and capture output
        console.print("[yellow]No pytest output provided. Running pytest...[/yellow]")
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "pytest", "-v", "--tb=short"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )
        output_text = result.stdout + result.stderr

        if result.returncode == 0:
            console.print("[green]All tests passed![/green]")
            raise typer.Exit(0)

    # Parse failures
    analyzer = TestAnalyzer()
    failures = analyzer.parse_pytest_output(output_text)

    if not failures:
        console.print("[yellow]No test failures found in output[/yellow]")
        raise typer.Exit(0)

    console.print(Panel.fit(
        f"[bold]Test Failures Analysis[/bold]\n\n"
        f"Found {len(failures)} failure(s)",
        title="Analysis",
    ))

    # Group failures
    groups = analyzer.group_failures(failures)
    console.print(f"\n[bold]Grouped into {len(groups)} pattern(s)[/bold]")

    # Analyze each failure
    fix_generator = FixGenerator(project_path=project_path)
    all_fixes: list[FixSuggestion] = []

    for i, failure in enumerate(failures, 1):
        console.print()
        console.print(f"[bold cyan]Failure {i}:[/bold cyan] {failure.test_name}")

        analysis = analyzer.analyze_failure(failure)

        # Display analysis
        analysis_table = Table(show_header=False, box=None)
        analysis_table.add_column("Key", style="dim")
        analysis_table.add_column("Value")

        analysis_table.add_row("Type", failure.failure_type.value)
        analysis_table.add_row("File", failure.test_file)
        if failure.line_number:
            analysis_table.add_row("Line", str(failure.line_number))
        analysis_table.add_row("Error", failure.error_message[:80])
        analysis_table.add_row("Root Cause", analysis.root_cause[:80])
        analysis_table.add_row("Confidence", f"{analysis.confidence:.0%}")
        analysis_table.add_row("Fix Target", analysis.fix_type or "unknown")

        console.print(analysis_table)

        # Generate fix suggestion
        if suggest_fixes:
            fix = fix_generator._generate_rule_based_fix(analysis, "", "")
            if fix:
                all_fixes.append(fix)
                console.print()
                console.print("[bold green]Suggested Fix:[/bold green]")
                console.print(f"  {fix.description}")
                if fix.new_code:
                    console.print(f"  [dim]Code:[/dim] {fix.new_code[:60]}...")

    # Summary
    if all_fixes:
        console.print()
        console.print(Panel.fit(
            f"[bold]Fix Summary[/bold]\n\n"
            f"Generated {len(all_fixes)} fix suggestion(s)\n"
            f"Auto-fixable: {sum(1 for f in all_fixes if f.is_auto_fixable)}\n"
            f"Requires approval: {sum(1 for f in all_fixes if f.requires_approval)}",
            title="Summary",
        ))


@app.command()
def analyze(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the project",
    ),
    test_output: str = typer.Option(
        None, "--output", "-o",
        help="Path to pytest output file (or will run tests)",
    ),
    suggest_fixes: bool = typer.Option(
        True, "--fix/--no-fix",
        help="Generate fix suggestions",
    ),
):
    """Analyze test failures and suggest fixes.

    Parses pytest output to identify failures, analyzes root causes,
    and generates fix suggestions.
    """
    project_path = path.resolve()

    if not project_path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {project_path}")
        raise typer.Exit(1)

    # Get test output
    if test_output:
        test_output_path = Path(test_output)
        if not test_output_path.exists():
            console.print(f"[red]Error:[/red] Output file not found: {test_output}")
            raise typer.Exit(1)
        output = test_output_path.read_text()
    else:
        # Run pytest and capture output
        import subprocess
        console.print("[dim]Running pytest...[/dim]")
        result = subprocess.run(
            ["python3", "-m", "pytest", "-v", "--tb=short"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )
        output = result.stdout + result.stderr

        if result.returncode == 0:
            console.print("[green]All tests passed![/green]")
            raise typer.Exit(0)

    # Analyze failures
    analyzer = TestAnalyzer()
    failures = analyzer.parse_pytest_output(output)

    if not failures:
        console.print("[yellow]No failures found in output[/yellow]")
        raise typer.Exit(0)

    console.print(Panel.fit(
        f"[bold]Found {len(failures)} test failure(s)[/bold]",
        title="Analysis",
    ))

    # Display failures
    for i, failure in enumerate(failures, 1):
        console.print()
        console.print(f"[bold red]Failure #{i}:[/bold red] {failure.test_name}")
        console.print(f"  File: {failure.test_file}")
        console.print(f"  Type: {failure.failure_type.value}")
        console.print(f"  Error: {failure.error_message[:100]}")

        if failure.expected_value and failure.actual_value:
            console.print(f"  Expected: [green]{failure.expected_value}[/green]")
            console.print(f"  Actual: [red]{failure.actual_value}[/red]")

        # Analyze
        analysis = analyzer.analyze_failure(failure)
        console.print(f"\n  [cyan]Root Cause:[/cyan] {analysis.root_cause}")
        console.print(f"  [cyan]Confidence:[/cyan] {analysis.confidence:.0%}")
        console.print(f"  [cyan]Fix Target:[/cyan] {analysis.fix_type}")

        # Generate fix suggestion
        if suggest_fixes:
            generator = FixGenerator(project_path=project_path)
            fix = generator._generate_rule_based_fix(analysis, "", "")

            if fix:
                console.print(f"\n  [yellow]Suggested Fix:[/yellow]")
                console.print(f"    File: {fix.file_path}")
                console.print(f"    Action: {fix.fix_type.value}")
                console.print(f"    Description: {fix.description}")

                if fix.new_code:
                    console.print(f"    New code:")
                    for line in fix.new_code.split("\n")[:5]:
                        console.print(f"      [dim]{line}[/dim]")

    # Group related failures
    groups = analyzer.group_failures(failures)
    if len(groups) < len(failures):
        console.print()
        console.print(f"[dim]Failures grouped into {len(groups)} categories[/dim]")


@app.command()
def replay(
    log_file: Path = typer.Argument(
        ...,
        help="Path to log file (HAR, JSON logs, or access logs)",
    ),
    output: Path = typer.Option(
        None, "--output", "-o",
        help="Output file for generated tests",
    ),
    log_format: str = typer.Option(
        "auto", "--format", "-f",
        help="Log format: auto, har, json, nginx",
    ),
    base_url: str = typer.Option(
        "http://localhost:8000", "--base-url", "-b",
        help="Base URL for generated tests",
    ),
):
    """Generate tests from logs (HAR, API logs, error logs).

    Replay user scenarios by converting logs into executable tests.
    Supports:
    - HAR files (browser recordings)
    - JSON API logs
    - Nginx/Apache access logs
    - Error logs (for reproduction tests)
    """
    if not log_file.exists():
        console.print(f"[red]Error:[/red] File not found: {log_file}")
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"[bold]Parsing log file[/bold]\n\n"
        f"File: {log_file.name}\n"
        f"Format: {log_format}\n"
        f"Base URL: {base_url}",
        title="Scenario Replay",
    ))

    # Detect format if auto
    file_ext = log_file.suffix.lower()
    if log_format == "auto":
        if file_ext == ".har":
            log_format = "har"
        elif file_ext == ".json":
            # Could be HAR or JSON logs, try to detect
            content = log_file.read_text()[:1000]
            if '"log"' in content and '"entries"' in content:
                log_format = "har"
            else:
                log_format = "json"
        else:
            log_format = "nginx"

    # Parse based on format
    test_code = ""
    entry_count = 0

    if log_format == "har":
        parser = HARParser(filter_api_only=True)
        entries = parser.parse_file(log_file)
        entry_count = len(entries)

        if entries:
            test_code = generate_tests_from_har(log_file, base_url=base_url)

    elif log_format == "json":
        parser = APILogParser(log_format="json")
        entries = parser.parse_file(log_file)
        entry_count = len(entries)

        if entries:
            from .scenario.api_logs import generate_tests_from_logs
            test_code = generate_tests_from_logs(entries, base_url=base_url)

    elif log_format == "nginx":
        parser = APILogParser(log_format="nginx")
        entries = parser.parse_file(log_file)
        entry_count = len(entries)

        if entries:
            from .scenario.api_logs import generate_tests_from_logs
            test_code = generate_tests_from_logs(entries, base_url=base_url)

    elif log_format == "error":
        parser = ErrorLogParser()
        errors = parser.parse_file(log_file)
        entry_count = len(errors)

        if errors:
            from .scenario.error_replay import generate_reproduction_tests
            test_code = generate_reproduction_tests(errors, base_url=base_url)

    if not test_code:
        console.print("[yellow]No entries found in log file[/yellow]")
        raise typer.Exit(0)

    # Output results
    console.print(f"\n[green]✓[/green] Parsed {entry_count} entries")

    if output:
        output.write_text(test_code)
        console.print(f"[green]✓[/green] Tests written to {output}")
    else:
        # Show preview
        console.print("\n[bold]Generated Test Preview:[/bold]")
        lines = test_code.split("\n")[:30]
        for line in lines:
            console.print(f"  [dim]{line}[/dim]")
        if len(test_code.split("\n")) > 30:
            console.print(f"  [dim]... ({len(test_code.split(chr(10))) - 30} more lines)[/dim]")

        console.print("\n[yellow]Use --output to save to file[/yellow]")


@app.command()
def report(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the project",
    ),
    format: str = typer.Option(
        "console", "--format", "-f",
        help="Output format: console, html, json",
    ),
):
    """Generate a verification report.

    Creates a summary of the project's test coverage and quality.
    """
    project_path = path.resolve()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing project...", total=None)
        scanner = ProjectScanner(project_path)
        info = scanner.scan()

    console.print(Panel.fit(
        f"[bold]Verification Report[/bold]\n"
        f"Project: {info.name}\n\n"
        f"Source Files: {len(info.source_files)}\n"
        f"Test Files: {len(info.test_files)}\n"
        f"Functions: {len(info.functions)}\n"
        f"Classes: {len(info.classes)}\n"
        f"API Endpoints: {len(info.api_endpoints)}\n\n"
        f"[yellow]Full reporting will be implemented in later phases[/yellow]",
        title="Report",
    ))


@app.command()
def coverage(
    path: Path = typer.Argument(
        Path("."),
        help="Path to the project",
    ),
    threshold: float = typer.Option(
        80.0, "--threshold", "-t",
        help="Coverage threshold percentage (0-100)",
    ),
    format: str = typer.Option(
        "console", "--format", "-f",
        help="Output format: console, html, json",
    ),
    output: Path = typer.Option(
        None, "--output", "-o",
        help="Output file for report (html/json only)",
    ),
    suggest: bool = typer.Option(
        False, "--suggest", "-s",
        help="Suggest tests for uncovered code",
    ),
):
    """Analyze code coverage.

    Runs tests with coverage collection and generates a report.
    Shows which files and functions lack test coverage.
    """
    from verify_ai.coverage import CoverageAnalyzer
    from verify_ai.coverage.reporter import create_reporter

    project_path = path.resolve()

    if not project_path.exists():
        console.print(f"[red]Error:[/red] Path does not exist: {project_path}")
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"[bold]Coverage Analysis[/bold]\n\n"
        f"Project: {project_path.name}\n"
        f"Threshold: {threshold}%\n"
        f"Format: {format}",
        title="Coverage",
    ))

    # Run coverage analysis
    analyzer = CoverageAnalyzer(project_path)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running tests with coverage...", total=None)
        try:
            report_data = analyzer.run_with_coverage()
        except Exception as e:
            console.print(f"\n[red]Error running coverage:[/red] {e}")
            console.print("\n[dim]Make sure pytest and pytest-cov are installed:[/dim]")
            console.print("  pip install pytest pytest-cov")
            raise typer.Exit(1)

    # Generate report
    reporter = create_reporter(format, threshold=threshold)
    
    output_path = None
    if output:
        output_path = output.resolve()
    elif format == "html":
        output_path = project_path / "coverage_report.html"
    elif format == "json":
        output_path = project_path / "coverage_report.json"

    reporter.generate(report_data, output_path)

    if output_path and format in ("html", "json"):
        console.print(f"\n[green]✓[/green] Report saved to: {output_path}")

    # Check threshold
    passes, message = analyzer.check_threshold(threshold)
    console.print()
    if passes:
        console.print(f"[green]✓[/green] {message}")
    else:
        console.print(f"[red]✗[/red] {message}")

    # Show files below threshold
    below = analyzer.get_files_below_threshold(threshold)
    if below:
        console.print(f"\n[yellow]Files below {threshold}% coverage:[/yellow]")
        for file_path, pct in below[:10]:
            console.print(f"  • {file_path}: {pct:.1f}%")
        if len(below) > 10:
            console.print(f"  ... and {len(below) - 10} more")

    # Suggest tests for uncovered code
    if suggest:
        suggestions = analyzer.suggest_tests_for_uncovered(max_suggestions=5)
        if suggestions:
            console.print("\n[bold]Suggested Tests for Uncovered Code:[/bold]")
            for i, sugg in enumerate(suggestions, 1):
                console.print(f"\n  [{sugg.priority.upper()}] {sugg.function.name}")
                console.print(f"      File: {sugg.function.file_path}:{sugg.function.start_line}")
                console.print(f"      Reason: {sugg.reason}")
                for test_case in sugg.suggested_test_cases[:2]:
                    console.print(f"      • {test_case}")

    # Exit with error if below threshold
    if not passes:
        raise typer.Exit(1)


@app.command()
def dashboard(
    host: str = typer.Option(
        "127.0.0.1", "--host", "-h",
        help="Host to bind to",
    ),
    port: int = typer.Option(
        8080, "--port", "-p",
        help="Port to listen on",
    ),
    no_browser: bool = typer.Option(
        False, "--no-browser",
        help="Don't open browser automatically",
    ),
    path: Path = typer.Argument(
        Path("."),
        help="Path to the project",
    ),
):
    """Start the VerifyAI web dashboard.

    Opens a web interface to monitor test coverage, execution history,
    and project health metrics.
    """
    try:
        from .dashboard.app import run_dashboard
    except ImportError:
        console.print("[red]Error:[/red] Dashboard dependencies not installed")
        console.print("Install with: pip install 'verify-ai[server]'")
        raise typer.Exit(1)

    project_path = path.resolve()

    console.print(Panel.fit(
        f"[bold]VerifyAI Dashboard[/bold]\n\n"
        f"URL: http://{host}:{port}\n"
        f"Project: {project_path.name}\n\n"
        f"Press Ctrl+C to stop",
        title="Starting Dashboard",
    ))

    run_dashboard(
        host=host,
        port=port,
        project_path=project_path,
        open_browser=not no_browser,
    )


@app.command()
def mcp_server():
    """Start MCP server for AI assistant integration.

    Runs the Model Context Protocol server in stdio mode,
    allowing AI assistants to interact with VerifyAI.
    """
    from .mcp.server import run_mcp_server

    console.print("[dim]Starting MCP server...[/dim]", err=True)
    asyncio.run(run_mcp_server())


@app.command()
def server(
    host: str = typer.Option(
        "0.0.0.0", "--host", "-h",
        help="Host to bind to",
    ),
    port: int = typer.Option(
        8000, "--port", "-p",
        help="Port to listen on",
    ),
    reload: bool = typer.Option(
        False, "--reload",
        help="Enable auto-reload for development",
    ),
):
    """Start the VerifyAI API server.

    Runs a REST API server with GitHub webhook support.
    Requires: pip install 'verify-ai[server]'
    """
    try:
        from .server.api import run_server
    except ImportError:
        console.print("[red]Error:[/red] Server dependencies not installed")
        console.print("Install with: pip install 'verify-ai[server]'")
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"[bold]VerifyAI API Server[/bold]\n\n"
        f"Host: {host}\n"
        f"Port: {port}\n"
        f"Reload: {reload}\n\n"
        f"Endpoints:\n"
        f"  POST /api/scan\n"
        f"  POST /api/generate\n"
        f"  POST /api/verify\n"
        f"  POST /api/analyze\n"
        f"  POST /webhook/github\n"
        f"  GET  /health",
        title="Starting Server",
    ))

    run_server(host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
