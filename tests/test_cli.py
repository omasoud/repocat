"""CLI parsing and command behavior tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from repocat.cli import get_version, main as cli_main
from conftest import invoke_repocat, listed_paths, listed_total, write_text


def test_default_and_explicit_formats(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "main.py", "print('hi')\n")

    default = invoke_repocat(runner, monkeypatch, tmp_path, [])
    assert default.exit_code == 0
    assert default.stdout.startswith("<documents>\n")
    assert "<source>main.py</source>" in default.stdout

    cxml = invoke_repocat(runner, monkeypatch, tmp_path, ["--cxml"])
    assert cxml.exit_code == 0
    assert cxml.stdout.startswith("<documents>\n")

    markdown = invoke_repocat(runner, monkeypatch, tmp_path, ["--markdown"])
    assert markdown.exit_code == 0
    assert "## `main.py`" in markdown.stdout
    assert "```python" in markdown.stdout


def test_output_file_is_written_and_excluded(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "a.txt", "alpha\n")
    write_text(tmp_path, "prompt.xml", "old\n")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["-i", "*", "--output", "prompt.xml"])

    assert result.exit_code == 0
    assert result.stdout == ""
    output = (tmp_path / "prompt.xml").read_text(encoding="utf-8")
    assert "<source>a.txt</source>" in output
    assert "<source>prompt.xml</source>" not in output


def test_output_paths_support_absolute_inside_and_outside_root(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "a.txt", "alpha\n")
    inside_output = tmp_path / "inside.xml"
    inside_output.write_text("old\n", encoding="utf-8")

    inside = invoke_repocat(
        runner,
        monkeypatch,
        tmp_path,
        ["--include", "*", "--output", str(inside_output)],
    )
    assert inside.exit_code == 0
    inside_text = inside_output.read_text(encoding="utf-8")
    assert "<source>a.txt</source>" in inside_text
    assert "<source>inside.xml</source>" not in inside_text

    outside_output = tmp_path.parent / f"{tmp_path.name}-outside.xml"
    try:
        outside = invoke_repocat(
            runner,
            monkeypatch,
            tmp_path,
            ["--include", "*", "--output", str(outside_output)],
        )
        assert outside.exit_code == 0
        outside_text = outside_output.read_text(encoding="utf-8")
        assert "<source>a.txt</source>" in outside_text
        assert "<source>inside.xml</source>" in outside_text
    finally:
        outside_output.unlink(missing_ok=True)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--cxml", "--markdown"], "mutually exclusive"),
        (["--list-files", "--markdown"], "--list-files cannot be combined"),
        (["--list-files", "--output", "prompt.xml"], "--list-files cannot be combined"),
        (["--include", "!secret.txt"], "must not start with '!'"),
        (["--include="], "--include requires a non-empty value"),
        (["--exclude="], "--exclude requires a non-empty value"),
        (["--output="], "--output requires a non-empty value"),
        (["--exclude", "!secret.txt"], "--exclude patterns must not start with '!'"),
        (["--stdout", "--output", "prompt.xml"], "--stdout cannot be combined with --output"),
    ],
)
def test_main_usage_errors(runner, monkeypatch, tmp_path: Path, args: list[str], message: str) -> None:
    result = invoke_repocat(runner, monkeypatch, tmp_path, args)

    assert result.exit_code == 1
    assert message in result.output


def test_interactive_stdout_requires_explicit_stdout(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "main.py", "print('hi')\n")
    monkeypatch.setattr("repocat.cli._stdout_is_interactive", lambda: True)

    result = invoke_repocat(runner, monkeypatch, tmp_path, [])

    assert result.exit_code == 1
    assert f"repocat {get_version()}" in result.stdout
    assert "repocat captures the current directory and writes prompt output to stdout." in result.stdout
    assert "repocat --stdout" in result.stdout
    assert "To see help:" in result.stdout
    assert "repocat -h" in result.stdout
    assert "<documents>" not in result.stdout


def test_stdout_flag_allows_interactive_stdout_capture(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "main.py", "print('hi')\n")
    monkeypatch.setattr("repocat.cli._stdout_is_interactive", lambda: True)

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--stdout"])

    assert result.exit_code == 0
    assert result.stdout.startswith("<documents>\n")
    assert "<source>main.py</source>" in result.stdout


def test_non_interactive_stdout_allows_bare_capture(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "main.py", "print('hi')\n")
    monkeypatch.setattr("repocat.cli._stdout_is_interactive", lambda: False)

    result = invoke_repocat(runner, monkeypatch, tmp_path, [])

    assert result.exit_code == 0
    assert result.stdout.startswith("<documents>\n")
    assert "<source>main.py</source>" in result.stdout


def test_interactive_stdout_guard_does_not_block_list_files(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "main.py", "print('hi')\n")
    monkeypatch.setattr("repocat.cli._stdout_is_interactive", lambda: True)

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--list-files"])

    assert result.exit_code == 0
    assert listed_paths(result.stdout) == ["main.py"]
    assert listed_total(result.stdout) == 1


def test_list_files_prints_total_at_end(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "b.txt")
    write_text(tmp_path, "a.txt")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--list-files"])

    assert result.exit_code == 0
    assert result.stdout.splitlines() == ["a.txt", "b.txt", "Total files: 2"]


def test_repeated_include_exclude_order_is_preserved(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "keep.txt")
    write_text(tmp_path, "secret.txt")

    result = invoke_repocat(
        runner,
        monkeypatch,
        tmp_path,
        ["--include", "*", "--exclude", "secret.txt", "--list-files"],
    )

    assert result.exit_code == 0
    assert listed_paths(result.stdout) == ["keep.txt"]
    assert listed_total(result.stdout) == 1


def test_gitignore_filter_is_available_in_main_and_check_help(runner, monkeypatch, tmp_path: Path) -> None:
    main_help = invoke_repocat(runner, monkeypatch, tmp_path, ["--help"])
    check_help = invoke_repocat(runner, monkeypatch, tmp_path, ["check", "--help"])

    assert main_help.exit_code == 0
    assert f"repocat {get_version()}" in main_help.stdout
    assert "-g, --gitignore-filter" in main_help.stdout
    assert "Rule Order" in main_help.stdout
    assert "Selection rules run in the exact order supplied" in main_help.stdout
    assert "repocat -e '*' -i 'tests/**' -g --list-files" in main_help.stdout
    assert "https://github.com/omasoud/repocat" in main_help.stdout
    assert check_help.exit_code == 0
    assert "-g, --gitignore-filter" in check_help.stdout
    assert "Use `--` before a dash-prefixed filename." in check_help.stdout


def test_check_usage_errors_exit_2(runner, monkeypatch, tmp_path: Path) -> None:
    result = invoke_repocat(runner, monkeypatch, tmp_path, ["check", "--markdown", "README.md"])

    assert result.exit_code == 2
    assert "Unsupported check option" in result.output


def test_main_rejects_unknown_option(runner, monkeypatch, tmp_path: Path) -> None:
    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--not-real"])

    assert result.exit_code == 1
    assert "Unknown argument" in result.output


def test_check_rejects_unknown_dash_option(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "README.md")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["check", "--not-real", "README.md"])

    assert result.exit_code == 2
    assert "Unknown argument" in result.output


def test_direct_entrypoint_check_usage_errors_exit_2(monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "README.md")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli_main(["check", "--not-real", "README.md"])

    assert exc_info.value.code == 2


def test_check_supports_end_of_options_for_dash_paths(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "-weird.txt")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["check", "--", "-weird.txt"])

    assert result.exit_code == 0
    assert "INCLUDED  -weird.txt  default include" in result.stdout


def test_malformed_cli_pattern_reports_usage_error(runner, monkeypatch, tmp_path: Path) -> None:
    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--include", "\\"])

    assert result.exit_code == 1
    assert "Invalid ignore pattern in repocat rules" in result.output


def test_installed_command_enters_real_cli() -> None:
    project_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        ["uv", "run", "repocat", "--list-files"],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Hello from repocat!" not in result.stdout
    assert "pyproject.toml" in result.stdout
    assert sys.executable
