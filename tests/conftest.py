"""Shared test helpers for repocat."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

import pytest
from typer.testing import CliRunner

from repocat.cli import app

TOTAL_FILES_PREFIX = "Total files: "


@pytest.fixture
def runner() -> CliRunner:
    """Return a Typer CLI runner."""
    return CliRunner()


def invoke_repocat(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    cwd: Path,
    args: Sequence[str],
):
    """Invoke repocat from ``cwd``."""
    monkeypatch.chdir(cwd)
    return runner.invoke(app, list(args), catch_exceptions=False)


def write_text(root: Path, relative: str, content: str = "content\n") -> Path:
    """Create a UTF-8 text file under ``root``."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return path


def write_bytes(root: Path, relative: str, content: bytes) -> Path:
    """Create a binary file under ``root``."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def listed_paths(output: str) -> list[str]:
    """Return path lines from ``--list-files`` output."""
    return [line for line in output.splitlines() if line and not line.startswith(TOTAL_FILES_PREFIX)]


def listed_total(output: str) -> int:
    """Return the total count from ``--list-files`` output."""
    for line in reversed(output.splitlines()):
        if line.startswith(TOTAL_FILES_PREFIX):
            return int(line.removeprefix(TOTAL_FILES_PREFIX))
    raise AssertionError("missing total files line")


def make_symlink(link: Path, target: Path, *, directory: bool = False) -> None:
    """Create a symlink or skip when the platform disallows it."""
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlinks are not available: {exc}")


def can_make_unreadable() -> bool:
    """Return whether chmod-based unreadable-file tests are meaningful."""
    return os.name != "nt"
