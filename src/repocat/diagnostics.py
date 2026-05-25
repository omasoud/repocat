"""Diagnostic modes for listing and checking capture membership."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from repocat.models import (
    CandidateFile,
    CheckResult,
    DecisionKind,
    SelectionConfig,
    SelectionDecision,
)
from repocat.paths import display_path_for, hard_git_path, normalize_root_relative
from repocat.reading import read_utf8
from repocat.selection import IgnoreManager, hard_exclusion_decision, select_candidate
from repocat.traversal import active_gitignores_for_path

Warn = Callable[[str], None]


def format_check_result(result: CheckResult) -> str:
    """Format one check result as a human-readable diagnostic line."""
    decision = result.decision
    label = _label(decision.kind)
    if decision.reason:
        return f"{label}  {decision.root_relative_path}  {decision.reason}"
    return f"{label}  {decision.root_relative_path}"


def check_paths(config: SelectionConfig, files: tuple[str, ...], warn: Warn) -> list[CheckResult]:
    """Check whether specific paths would be captured."""
    ignore_manager = IgnoreManager(warn)
    return [_check_one(config, ignore_manager, raw_path, warn) for raw_path in files]


def _check_one(
    config: SelectionConfig,
    ignore_manager: IgnoreManager,
    raw_path: str,
    warn: Warn,
) -> CheckResult:
    lexical_path, display_path, inside_root = display_path_for(config.root, raw_path)

    if not inside_root:
        decision = SelectionDecision(DecisionKind.EXCLUDE, display_path, "outside invocation root")
        return CheckResult(decision, False)

    if hard_git_path(display_path):
        decision = SelectionDecision(DecisionKind.EXCLUDE, display_path, "hard-excluded: .git directory")
        return CheckResult(decision, False)

    read_path = lexical_path
    if lexical_path.is_symlink():
        try:
            target = lexical_path.resolve(strict=True)
        except OSError:
            decision = SelectionDecision(DecisionKind.EXCLUDE, display_path, "broken symlink")
            return CheckResult(decision, False)

        if target.is_dir():
            decision = SelectionDecision(DecisionKind.NOT_A_FILE, display_path, "directory symlink not followed")
            return CheckResult(decision, False)

        if not target.is_relative_to(config.root):
            decision = SelectionDecision(DecisionKind.EXCLUDE, display_path, "external symlink target")
            return CheckResult(decision, False)

        if not target.is_file():
            decision = SelectionDecision(DecisionKind.NOT_A_FILE, display_path, "not a regular file")
            return CheckResult(decision, False)

        read_path = target
    elif not lexical_path.exists():
        decision = SelectionDecision(DecisionKind.NOT_FOUND, display_path, "not found")
        return CheckResult(decision, False)
    elif not lexical_path.is_file():
        decision = SelectionDecision(DecisionKind.NOT_A_FILE, display_path, "not a regular file")
        return CheckResult(decision, False)

    try:
        root_relative_path = normalize_root_relative(config.root, lexical_path)
    except ValueError:
        root_relative_path = display_path

    active_gitignores = active_gitignores_for_path(config, ignore_manager, root_relative_path)
    candidate = CandidateFile(
        root_relative_path=root_relative_path,
        absolute_path=lexical_path,
        read_path=read_path,
        active_gitignores=active_gitignores,
    )

    hard_decision = hard_exclusion_decision(config, lexical_path, read_path, root_relative_path)
    if hard_decision is not None:
        return CheckResult(hard_decision, False)

    decision = select_candidate(config, candidate)
    if decision.kind is not DecisionKind.INCLUDE:
        return CheckResult(decision, False)

    if read_utf8(read_path, root_relative_path, warn) is None:
        failed = SelectionDecision(DecisionKind.EXCLUDE, root_relative_path, "non-utf-8 or unreadable")
        return CheckResult(failed, False)

    return CheckResult(decision, True)


def _label(kind: DecisionKind) -> str:
    if kind is DecisionKind.INCLUDE:
        return "INCLUDED"
    if kind is DecisionKind.NOT_FOUND:
        return "NOT_FOUND"
    if kind is DecisionKind.NOT_A_FILE:
        return "NOT_A_FILE"
    return "EXCLUDED"
