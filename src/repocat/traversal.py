"""Repository traversal and symlink handling."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterator

from repocat.models import ActiveGitignoreSpec, CandidateFile, SelectionConfig
from repocat.paths import child_rel, normalize_root_relative, resolved_inside_root
from repocat.selection import IgnoreManager

Warn = Callable[[str], None]


def walk_files(
    config: SelectionConfig,
    ignore_manager: IgnoreManager,
    warn: Warn,
) -> Iterator[CandidateFile]:
    """Yield candidate files under the invocation root."""
    yield from _walk_dir(config, ignore_manager, warn, config.root, "", ())


def active_gitignores_for_path(
    config: SelectionConfig,
    ignore_manager: IgnoreManager,
    root_relative_path: str,
) -> tuple[ActiveGitignoreSpec, ...]:
    """Load applicable gitignore specs for one root-relative path."""
    if config.ignore_gitignore:
        return ()

    active: list[ActiveGitignoreSpec] = []
    current_dir = config.root
    parent_rel = ""
    parent_parts = Path(root_relative_path).parent.parts

    _append_gitignore(config, ignore_manager, current_dir, parent_rel, active)
    for part in parent_parts:
        if part in ("", "."):
            continue
        current_dir = current_dir / part
        parent_rel = child_rel(parent_rel, part)
        _append_gitignore(config, ignore_manager, current_dir, parent_rel, active)

    return tuple(active)


def _walk_dir(
    config: SelectionConfig,
    ignore_manager: IgnoreManager,
    warn: Warn,
    dir_path: Path,
    dir_rel: str,
    active_gitignores: tuple[ActiveGitignoreSpec, ...],
) -> Iterator[CandidateFile]:
    if dir_path.name == ".git" and dir_rel == ".git":
        return

    active = list(active_gitignores)
    _append_gitignore(config, ignore_manager, dir_path, dir_rel, active)
    active_tuple = tuple(active)

    try:
        entries = sorted(dir_path.iterdir(), key=lambda entry: entry.name)
    except OSError as exc:
        warn(f"Warning: skipping unreadable directory: {dir_rel or '.'}: {exc}")
        return

    for entry in entries:
        entry_rel = child_rel(dir_rel, entry.name)
        if entry_rel == ".git":
            continue

        if entry.is_symlink():
            yield from _handle_symlink(config, warn, entry, entry_rel, active_tuple)
            continue

        if entry.is_dir():
            yield from _walk_dir(config, ignore_manager, warn, entry, entry_rel, active_tuple)
            continue

        if entry.is_file():
            yield CandidateFile(
                root_relative_path=normalize_root_relative(config.root, entry),
                absolute_path=entry,
                read_path=entry,
                active_gitignores=active_tuple,
            )


def _append_gitignore(
    config: SelectionConfig,
    ignore_manager: IgnoreManager,
    dir_path: Path,
    dir_rel: str,
    active: list[ActiveGitignoreSpec],
) -> None:
    if config.ignore_gitignore:
        return

    gitignore_path = dir_path / ".gitignore"
    if not gitignore_path.is_file():
        return

    loaded = ignore_manager.load(gitignore_path)
    if loaded is None:
        return

    spec, sources = loaded
    active.append(
        ActiveGitignoreSpec(
            gitignore_dir_rel=dir_rel,
            spec=spec,
            source_path=gitignore_path,
            sources=sources,
        )
    )


def _handle_symlink(
    config: SelectionConfig,
    warn: Warn,
    entry: Path,
    entry_rel: str,
    active_gitignores: tuple[ActiveGitignoreSpec, ...],
) -> Iterator[CandidateFile]:
    try:
        target = entry.resolve(strict=True)
    except OSError:
        warn(f"Warning: skipping broken symlink: {entry_rel}")
        return

    if target.is_dir():
        return

    if not resolved_inside_root(config.root, target):
        warn(f"Warning: skipping symlink with external target: {entry_rel}")
        return

    if not target.is_file():
        warn(f"Warning: skipping symlink to non-file target: {entry_rel}")
        return

    yield CandidateFile(
        root_relative_path=entry_rel,
        absolute_path=entry,
        read_path=target,
        active_gitignores=active_gitignores,
    )
