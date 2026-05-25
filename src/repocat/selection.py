"""Ignore loading and file selection semantics."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from pathspec import GitIgnoreSpec

from repocat.models import (
    ActiveGitignoreSpec,
    CandidateFile,
    CliRule,
    DecisionKind,
    RuleSource,
    SelectionConfig,
    SelectionDecision,
)
from repocat.paths import hard_git_path, path_for_gitignore, resolved_inside_root

Warn = Callable[[str], None]


class RepocatError(Exception):
    """A fatal repocat runtime or usage error."""


class IgnoreManager:
    """Load and cache nested ``.gitignore`` files."""

    def __init__(self, warn: Warn | None = None) -> None:
        self._cache: dict[Path, tuple[GitIgnoreSpec, tuple[RuleSource, ...]]] = {}
        self._warn = warn

    def load(self, gitignore_path: Path) -> tuple[GitIgnoreSpec, tuple[RuleSource, ...]] | None:
        """Return a compiled gitignore spec for ``gitignore_path``."""
        cached = self._cache.get(gitignore_path)
        if cached is not None:
            return cached

        try:
            text = gitignore_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            if self._warn is not None:
                self._warn(f"Warning: skipping non-UTF-8 .gitignore: {gitignore_path}")
            return None
        except OSError as exc:
            if self._warn is not None:
                self._warn(f"Warning: skipping unreadable .gitignore: {gitignore_path}: {exc}")
            return None

        sources = tuple(RuleSource(line, str(gitignore_path)) for line in text.splitlines())
        compiled = (GitIgnoreSpec.from_lines([source.pattern for source in sources]), sources)
        self._cache[gitignore_path] = compiled
        return compiled


def build_selection_config(
    root: Path,
    output_path: Path | None,
    ignore_gitignore: bool,
    cli_rules: tuple[CliRule, ...],
) -> SelectionConfig:
    """Build a selection configuration from root files and CLI rules."""
    sources: list[RuleSource] = []
    repocatignore_path = root / ".repocatignore"

    if repocatignore_path.is_file():
        try:
            text = repocatignore_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise RepocatError(".repocatignore must be valid UTF-8") from exc
        except OSError as exc:
            raise RepocatError(f"Unable to read .repocatignore: {exc}") from exc
        sources.extend(RuleSource(line, ".repocatignore") for line in text.splitlines())

    for rule in cli_rules:
        if rule.kind == "include":
            sources.append(RuleSource(f"!{rule.pattern}", "command line"))
        else:
            sources.append(RuleSource(rule.pattern, "command line"))

    spec = GitIgnoreSpec.from_lines([source.pattern for source in sources])
    return SelectionConfig(
        root=root,
        output_path=output_path,
        ignore_gitignore=ignore_gitignore,
        repocat_spec=spec,
        repocat_sources=tuple(sources),
    )


def select_candidate(config: SelectionConfig, candidate: CandidateFile) -> SelectionDecision:
    """Select or reject a candidate file according to v1 precedence."""
    path = candidate.root_relative_path

    hard_decision = hard_exclusion_decision(config, candidate.absolute_path, candidate.read_path, path)
    if hard_decision is not None:
        return hard_decision

    repocat_decision = evaluate_repocat_layer(config, path)
    if repocat_decision is not None:
        return repocat_decision

    if not config.ignore_gitignore:
        gitignore_decision = evaluate_gitignore_layer(path, candidate.active_gitignores)
        if gitignore_decision is not None:
            return gitignore_decision

    return SelectionDecision(DecisionKind.INCLUDE, path, "default include")


def hard_exclusion_decision(
    config: SelectionConfig,
    absolute_path: Path,
    read_path: Path,
    root_relative_path: str,
) -> SelectionDecision | None:
    """Return a hard-exclusion decision when one applies."""
    if hard_git_path(root_relative_path):
        return SelectionDecision(
            DecisionKind.EXCLUDE,
            root_relative_path,
            "hard-excluded: .git directory",
        )

    if config.output_path is not None and resolved_inside_root(config.root, config.output_path):
        output_path = config.output_path.resolve(strict=False)
        if absolute_path.resolve(strict=False) == output_path or read_path.resolve(strict=False) == output_path:
            return SelectionDecision(
                DecisionKind.EXCLUDE,
                root_relative_path,
                "hard-excluded: output file",
            )

    return None


def evaluate_repocat_layer(config: SelectionConfig, root_relative_path: str) -> SelectionDecision | None:
    """Evaluate the higher-precedence repocat layer."""
    result = config.repocat_spec.check_file(root_relative_path)
    if result.include is None:
        return None

    source = _source_at(config.repocat_sources, result.index)
    if result.include is True:
        return SelectionDecision(
            DecisionKind.EXCLUDE,
            root_relative_path,
            f"matched repocat exclude: {source.pattern}",
            source.origin,
        )

    return SelectionDecision(
        DecisionKind.INCLUDE,
        root_relative_path,
        f"matched repocat include: {source.pattern}",
        source.origin,
    )


def evaluate_gitignore_layer(
    root_relative_path: str,
    active_gitignores: tuple[ActiveGitignoreSpec, ...],
) -> SelectionDecision | None:
    """Evaluate applicable gitignore files from root to leaf."""
    included: bool | None = None
    matched_source: RuleSource | None = None

    for active in active_gitignores:
        path = path_for_gitignore(root_relative_path, active.gitignore_dir_rel)
        result = active.spec.check_file(path)
        if result.include is True:
            included = False
            matched_source = _source_at(active.sources, result.index)
        elif result.include is False:
            included = True
            matched_source = _source_at(active.sources, result.index)

    if included is None or matched_source is None:
        return None

    if included:
        return SelectionDecision(
            DecisionKind.INCLUDE,
            root_relative_path,
            f"matched .gitignore include: {matched_source.pattern}",
            matched_source.origin,
        )

    return SelectionDecision(
        DecisionKind.EXCLUDE,
        root_relative_path,
        f"matched .gitignore: {matched_source.pattern}",
        matched_source.origin,
    )


def _source_at(sources: tuple[RuleSource, ...], index: int | None) -> RuleSource:
    """Return pattern source metadata for a pathspec result index."""
    if index is None or index < 0 or index >= len(sources):
        return RuleSource("<unknown>", "<unknown>")
    return sources[index]
