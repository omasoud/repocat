"""CLI parsing and command behavior tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import invoke_repocat, listed_paths, write_text


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
    ],
)
def test_main_usage_errors(runner, monkeypatch, tmp_path: Path, args: list[str], message: str) -> None:
    result = invoke_repocat(runner, monkeypatch, tmp_path, args)

    assert result.exit_code == 1
    assert message in result.output


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


def test_check_usage_errors_exit_2(runner, monkeypatch, tmp_path: Path) -> None:
    result = invoke_repocat(runner, monkeypatch, tmp_path, ["check", "--markdown", "README.md"])

    assert result.exit_code == 2
    assert "Unsupported check option" in result.output


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
