"""UTF-8 file reading and capture collection."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from repocat.models import CapturedFile, DecisionKind, SelectionConfig
from repocat.selection import IgnoreManager, select_candidate
from repocat.traversal import walk_files

Warn = Callable[[str], None]


def capture_repository(config: SelectionConfig, warn: Warn) -> list[CapturedFile]:
    """Collect selected UTF-8 files, sorted by root-relative path."""
    ignore_manager = IgnoreManager(warn)
    captured: list[CapturedFile] = []

    for candidate in walk_files(config, ignore_manager, warn):
        decision = select_candidate(config, candidate)
        if decision.kind is not DecisionKind.INCLUDE:
            continue

        content = read_utf8(candidate.read_path, candidate.root_relative_path, warn)
        if content is None:
            continue

        captured.append(
            CapturedFile(
                root_relative_path=candidate.root_relative_path,
                absolute_path=candidate.absolute_path,
                content=content,
            )
        )

    return sorted(captured, key=lambda captured_file: captured_file.root_relative_path)


def read_utf8(path: Path, root_relative_path: str, warn: Warn) -> str | None:
    """Read a file as UTF-8, warning and returning ``None`` on failure."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        warn(f"Warning: skipping non-UTF-8 file: {root_relative_path}")
    except OSError as exc:
        warn(f"Warning: skipping unreadable file: {root_relative_path}: {exc}")
    return None
