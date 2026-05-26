"""Typer-based command-line entrypoint with deterministic rule parsing."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

import typer
from rich.console import Console
from rich.highlighter import RegexHighlighter
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from repocat.diagnostics import check_paths, format_check_result
from repocat.models import CheckOptions, CliOptions, CliRule, OutputFormat
from repocat.paths import resolve_output_path
from repocat.reading import capture_repository
from repocat.rendering import render_cxml, render_markdown
from repocat.selection import RepocatError, build_selection_config

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    rich_markup_mode="rich",
)


class UsageError(Exception):
    """A command-line usage error."""


class OptionHighlighter(RegexHighlighter):
    """Highlight CLI options and metavars in help text."""

    highlights = [
        r"(^|\W)(?P<option>\-\-[\w\-]+)(?![a-zA-Z0-9])",
        r"(^|\W)(?P<switch>\-\w+)(?![a-zA-Z0-9])",
        r"(?P<metavar>\b[A-Z][A-Z0-9_]*\b)",
    ]


def main(argv: Sequence[str] | None = None) -> None:
    """Run the CLI from raw process arguments."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "check":
        try:
            raise SystemExit(run_check(args[1:]))
        except typer.Exit as exc:
            raise SystemExit(exc.exit_code) from exc
        except UsageError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise SystemExit(2) from exc
        except RepocatError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise SystemExit(2) from exc

    try:
        raise SystemExit(run_main(args))
    except typer.Exit as exc:
        raise SystemExit(exc.exit_code) from exc
    except UsageError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc
    except RepocatError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc


@app.command(
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
def main_command(ctx: typer.Context) -> None:
    """Capture the current working directory."""
    args = list(ctx.args)
    if args and args[0] == "check":
        try:
            exit_code = run_check(args[1:])
        except UsageError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(2) from exc
        except RepocatError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(2) from exc
        raise typer.Exit(exit_code)

    try:
        exit_code = run_main(args)
    except UsageError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    except RepocatError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    raise typer.Exit(exit_code)


def run_main(argv: Sequence[str]) -> int:
    """Run the main capture mode with already-parsed raw arguments."""
    options = parse_main_args(argv)
    root = Path.cwd().resolve()
    output_path = resolve_output_path(root, str(options.output_path) if options.output_path else None)
    config = build_selection_config(root, output_path, options.ignore_gitignore, options.cli_rules)

    def warn(message: str) -> None:
        typer.echo(message, err=True)

    captured = capture_repository(config, warn)

    if options.list_files:
        for captured_file in captured:
            typer.echo(captured_file.root_relative_path)
        return 0

    output = render_markdown(captured) if options.output_format == "markdown" else render_cxml(captured)
    if output_path is not None:
        try:
            output_path.write_text(output, encoding="utf-8", newline="\n")
        except OSError as exc:
            raise RepocatError(f"Unable to write output file: {exc}") from exc
    else:
        typer.echo(output, nl=False)
    return 0


def run_check(argv: Sequence[str]) -> int:
    """Run check diagnostics with already-parsed raw arguments."""
    options = parse_check_args(argv)
    root = Path.cwd().resolve()
    config = build_selection_config(root, None, options.ignore_gitignore, options.cli_rules)

    def warn(message: str) -> None:
        typer.echo(message, err=True)

    results = check_paths(config, options.files, warn)
    for result in results:
        typer.echo(format_check_result(result))
    return 0 if all(result.would_capture for result in results) else 1


def parse_main_args(argv: Sequence[str]) -> CliOptions:
    """Parse main command arguments while preserving CLI rule order."""
    cxml = False
    markdown = False
    output: str | None = None
    ignore_gitignore = False
    list_files = False
    rules: list[CliRule] = []

    index = 0
    while index < len(argv):
        token = argv[index]
        if token in ("-c", "--cxml"):
            cxml = True
        elif token in ("-m", "--markdown"):
            markdown = True
        elif token in ("-o", "--output"):
            index += 1
            output = _require_value(argv, index, token)
        elif token.startswith("--output="):
            output = _require_equals_value(token, "--output")
        elif token == "--ignore-gitignore":
            ignore_gitignore = True
        elif token in ("-g", "--gitignore-filter"):
            rules.append(CliRule("gitignore_filter"))
        elif token in ("-i", "--include"):
            index += 1
            rules.append(CliRule("include", _validate_include(_require_value(argv, index, token))))
        elif token.startswith("--include="):
            rules.append(CliRule("include", _validate_include(_require_equals_value(token, "--include"))))
        elif token in ("-e", "--exclude"):
            index += 1
            rules.append(CliRule("exclude", _validate_exclude(_require_value(argv, index, token))))
        elif token.startswith("--exclude="):
            rules.append(CliRule("exclude", _validate_exclude(_require_equals_value(token, "--exclude"))))
        elif token == "--list-files":
            list_files = True
        elif token in ("-h", "--help"):
            print_main_help()
            raise typer.Exit(0)
        else:
            raise UsageError(f"Unknown argument: {token}")
        index += 1

    if cxml and markdown:
        raise UsageError("--cxml and --markdown are mutually exclusive")
    if list_files and (cxml or markdown or output is not None):
        raise UsageError("--list-files cannot be combined with output format options or --output")

    output_format: OutputFormat = "markdown" if markdown else "cxml"
    return CliOptions(
        output_format=output_format,
        output_path=Path(output) if output is not None else None,
        ignore_gitignore=ignore_gitignore,
        cli_rules=tuple(rules),
        list_files=list_files,
    )


def parse_check_args(argv: Sequence[str]) -> CheckOptions:
    """Parse check command arguments while preserving CLI rule order."""
    ignore_gitignore = False
    rules: list[CliRule] = []
    files: list[str] = []

    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--":
            files.extend(argv[index + 1 :])
            break
        if token == "--ignore-gitignore":
            ignore_gitignore = True
        elif token in ("-g", "--gitignore-filter"):
            rules.append(CliRule("gitignore_filter"))
        elif token in ("-i", "--include"):
            index += 1
            rules.append(CliRule("include", _validate_include(_require_value(argv, index, token))))
        elif token.startswith("--include="):
            rules.append(CliRule("include", _validate_include(_require_equals_value(token, "--include"))))
        elif token in ("-e", "--exclude"):
            index += 1
            rules.append(CliRule("exclude", _validate_exclude(_require_value(argv, index, token))))
        elif token.startswith("--exclude="):
            rules.append(CliRule("exclude", _validate_exclude(_require_equals_value(token, "--exclude"))))
        elif token in ("-c", "--cxml", "-m", "--markdown", "-o", "--output", "--list-files"):
            raise UsageError(f"Unsupported check option: {token}")
        elif token in ("-h", "--help"):
            print_check_help()
            raise typer.Exit(0)
        elif token.startswith("-"):
            raise UsageError(f"Unknown argument: {token}")
        else:
            files.append(token)
        index += 1

    if not files:
        raise UsageError("check requires at least one file")

    return CheckOptions(
        ignore_gitignore=ignore_gitignore,
        cli_rules=tuple(rules),
        files=tuple(files),
    )


def _require_value(argv: Sequence[str], index: int, option_name: str) -> str:
    """Return the next argv value or raise a usage error."""
    if index >= len(argv):
        raise UsageError(f"{option_name} requires a value")
    value = argv[index]
    if value == "":
        raise UsageError(f"{option_name} requires a non-empty value")
    return value


def _require_equals_value(token: str, option_name: str) -> str:
    """Return a non-empty ``--option=value`` value."""
    value = token.split("=", 1)[1]
    if value == "":
        raise UsageError(f"{option_name} requires a non-empty value")
    return value


def _validate_include(pattern: str) -> str:
    """Validate an include pattern."""
    if pattern == "":
        raise UsageError("-i/--include requires a non-empty value")
    if pattern.startswith("!"):
        raise UsageError("-i/--include patterns must not start with '!'")
    return pattern


def _validate_exclude(pattern: str) -> str:
    """Validate an exclude pattern."""
    if pattern == "":
        raise UsageError("-e/--exclude requires a non-empty value")
    if pattern.startswith("!"):
        raise UsageError("-e/--exclude patterns must not start with '!'")
    return pattern


def print_main_help() -> None:
    """Print rich-formatted main help."""
    _print_rich_help(
        usage="Usage: repocat [OPTIONS]",
        description="Capture the current working directory.",
        options=[
            ("-c, --cxml", "Render Claude XML-style output (default)."),
            ("-m, --markdown", "Render Markdown fenced code blocks."),
            ("-o, --output FILE", "Write output to FILE."),
            ("--ignore-gitignore", "Disable .gitignore handling."),
            ("-i, --include PATTERN", "Force-include a gitignore-style pattern."),
            ("-e, --exclude PATTERN", "Exclude a gitignore-style pattern."),
            ("-g, --gitignore-filter", "Apply .gitignore as an ordered exclusion-only filter."),
            ("--list-files", "List captured files only."),
        ],
        commands=[("check [OPTIONS] FILE...", "Report whether paths would be captured.")],
    )


def print_check_help() -> None:
    """Print rich-formatted check help."""
    _print_rich_help(
        usage="Usage: repocat check [OPTIONS] FILE...",
        description="Report whether paths would be captured.",
        options=[
            ("--ignore-gitignore", "Disable .gitignore handling."),
            ("-i, --include PATTERN", "Force-include a gitignore-style pattern."),
            ("-e, --exclude PATTERN", "Exclude a gitignore-style pattern."),
            ("-g, --gitignore-filter", "Apply .gitignore as an ordered exclusion-only filter."),
        ],
        commands=[],
    )


def _print_rich_help(
    usage: str,
    description: str,
    options: list[tuple[str, str]],
    commands: list[tuple[str, str]],
) -> None:
    """Print help using Rich formatting."""
    option_highlighter = OptionHighlighter()
    console = Console(highlighter=option_highlighter)
    console.print(option_highlighter(usage), style="bold yellow")
    console.print(Text(description))

    options_table = Table(show_header=False, box=None, padding=(0, 1), pad_edge=False)
    options_table.add_column("Option", style="bold cyan", no_wrap=True)
    options_table.add_column("Description")
    for option, help_text in options:
        options_table.add_row(option_highlighter(option), help_text)
    console.print(Panel(options_table, title="Options", title_align="left", border_style="dim"))

    if commands:
        commands_table = Table(show_header=False, box=None, padding=(0, 1), pad_edge=False)
        commands_table.add_column("Command", style="bold cyan", no_wrap=True)
        commands_table.add_column("Description")
        for command, help_text in commands:
            commands_table.add_row(command, help_text)
        console.print(Panel(commands_table, title="Commands", title_align="left", border_style="dim"))
