"""Typer-based command-line entrypoint with deterministic rule parsing."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import typer

from repocat.diagnostics import check_paths, format_check_result
from repocat.models import CheckOptions, CliOptions, CliRule, OutputFormat
from repocat.paths import resolve_output_path
from repocat.reading import capture_repository
from repocat.rendering import render_cxml, render_markdown
from repocat.selection import RepocatError, build_selection_config

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
)


class UsageError(Exception):
    """A command-line usage error."""


@app.command(
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
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
            output_path.write_text(output, encoding="utf-8")
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
            output = token.split("=", 1)[1]
        elif token == "--ignore-gitignore":
            ignore_gitignore = True
        elif token in ("-i", "--include"):
            index += 1
            rules.append(CliRule("include", _validate_include(_require_value(argv, index, token))))
        elif token.startswith("--include="):
            rules.append(CliRule("include", _validate_include(token.split("=", 1)[1])))
        elif token in ("-e", "--exclude"):
            index += 1
            rules.append(CliRule("exclude", _require_value(argv, index, token)))
        elif token.startswith("--exclude="):
            rules.append(CliRule("exclude", token.split("=", 1)[1]))
        elif token == "--list-files":
            list_files = True
        elif token in ("-h", "--help"):
            typer.echo(main_help())
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
        if token == "--ignore-gitignore":
            ignore_gitignore = True
        elif token in ("-i", "--include"):
            index += 1
            rules.append(CliRule("include", _validate_include(_require_value(argv, index, token))))
        elif token.startswith("--include="):
            rules.append(CliRule("include", _validate_include(token.split("=", 1)[1])))
        elif token in ("-e", "--exclude"):
            index += 1
            rules.append(CliRule("exclude", _require_value(argv, index, token)))
        elif token.startswith("--exclude="):
            rules.append(CliRule("exclude", token.split("=", 1)[1]))
        elif token in ("-c", "--cxml", "-m", "--markdown", "-o", "--output", "--list-files"):
            raise UsageError(f"Unsupported check option: {token}")
        elif token in ("-h", "--help"):
            typer.echo(check_help())
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


def _validate_include(pattern: str) -> str:
    """Validate an include pattern."""
    if pattern.startswith("!"):
        raise UsageError("-i/--include patterns must not start with '!'")
    return pattern


def main_help() -> str:
    """Return concise manual help for the raw parser."""
    return (
        "Usage: repocat [OPTIONS]\n\n"
        "Options:\n"
        "  -c, --cxml              Render Claude XML-style output (default).\n"
        "  -m, --markdown          Render Markdown fenced code blocks.\n"
        "  -o, --output FILE       Write output to FILE.\n"
        "      --ignore-gitignore  Disable .gitignore handling.\n"
        "  -i, --include PATTERN   Force-include a gitignore-style pattern.\n"
        "  -e, --exclude PATTERN   Exclude a gitignore-style pattern.\n"
        "      --list-files        List captured files only.\n"
        "\nCommands:\n"
        "  check [OPTIONS] FILE...  Report whether paths would be captured."
    )


def check_help() -> str:
    """Return concise manual help for check mode."""
    return (
        "Usage: repocat check [OPTIONS] FILE...\n\n"
        "Options:\n"
        "      --ignore-gitignore  Disable .gitignore handling.\n"
        "  -i, --include PATTERN   Force-include a gitignore-style pattern.\n"
        "  -e, --exclude PATTERN   Exclude a gitignore-style pattern."
    )
