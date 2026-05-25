"""Path normalization and containment helpers."""

from __future__ import annotations

import os
from pathlib import Path


def normalize_rel_parts(parts: tuple[str, ...]) -> str:
    """Return a POSIX path from relative path parts."""
    return "/".join(part for part in parts if part and part != ".")


def normalize_root_relative(root: Path, path: Path) -> str:
    """Return ``path`` relative to ``root`` with POSIX separators."""
    rel = path.relative_to(root)
    return normalize_rel_parts(rel.parts)


def normalize_user_path(path: str) -> str:
    """Normalize a user-supplied path for diagnostics."""
    return Path(path).as_posix()


def is_relative_to(path: Path, parent: Path) -> bool:
    """Return whether ``path`` is contained by ``parent``."""
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def resolve_output_path(root: Path, output: str | None) -> Path | None:
    """Resolve an output path relative to the invocation root."""
    if output is None:
        return None

    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = root / output_path
    return output_path.resolve(strict=False)


def resolved_inside_root(root: Path, path: Path) -> bool:
    """Return whether a resolved path is inside the invocation root."""
    return is_relative_to(path.resolve(strict=False), root)


def hard_git_path(root_relative_path: str) -> bool:
    """Return whether a root-relative path is inside any ``.git`` directory."""
    return ".git" in root_relative_path.split("/")


def child_rel(parent_rel: str, name: str) -> str:
    """Return a child root-relative path."""
    if not parent_rel:
        return name
    return f"{parent_rel}/{name}"


def path_for_gitignore(root_relative_path: str, gitignore_dir_rel: str) -> str:
    """Relativize a root-relative file path to a gitignore directory."""
    if not gitignore_dir_rel:
        return root_relative_path

    prefix = f"{gitignore_dir_rel}/"
    if root_relative_path.startswith(prefix):
        return root_relative_path[len(prefix) :]
    return root_relative_path


def display_path_for(root: Path, raw_path: str) -> tuple[Path, str, bool]:
    """Resolve a CLI path and return absolute path, display path, root containment."""
    user_path = Path(raw_path)
    lexical_path = user_path if user_path.is_absolute() else root / user_path
    lexical_path = Path(os.path.abspath(lexical_path))
    inside = is_relative_to(lexical_path, root)

    if inside:
        try:
            display = normalize_root_relative(root, lexical_path)
        except ValueError:
            display = normalize_user_path(raw_path)
    else:
        display = normalize_user_path(raw_path)

    return lexical_path, display, inside
