"""Ignore loading and file selection semantics."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from pathspec import GitIgnoreSpec
from pathspec.patterns.gitignore import GitIgnorePatternError
from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern

from repocat.models import (
    ActiveGitignoreSpec,
    CandidateFile,
    CliRule,
    DecisionKind,
    RepocatAction,
    RepocatGitignoreFilterAction,
    RepocatPatternAction,
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
            text = gitignore_path.read_text(encoding="utf-8", newline="")
        except UnicodeDecodeError:
            if self._warn is not None:
                self._warn(f"Warning: skipping non-UTF-8 .gitignore: {gitignore_path}")
            return None
        except OSError as exc:
            if self._warn is not None:
                self._warn(f"Warning: skipping unreadable .gitignore: {gitignore_path}: {exc}")
            return None

        sources = tuple(RuleSource(line, str(gitignore_path)) for line in text.splitlines())
        compiled = _compile_gitignore_sources(sources, str(gitignore_path))
        self._cache[gitignore_path] = compiled
        return compiled


def build_selection_config(
    root: Path,
    output_path: Path | None,
    ignore_gitignore: bool,
    cli_rules: tuple[CliRule, ...],
) -> SelectionConfig:
    """Build a selection configuration from root files and CLI rules."""
    actions: list[RepocatAction] = []
    sources: list[RuleSource] = []
    repocatignore_path = root / ".repocatignore"

    if repocatignore_path.is_file():
        try:
            text = repocatignore_path.read_text(encoding="utf-8", newline="")
        except UnicodeDecodeError as exc:
            raise RepocatError(".repocatignore must be valid UTF-8") from exc
        except OSError as exc:
            raise RepocatError(f"Unable to read .repocatignore: {exc}") from exc
        sources.extend(RuleSource(line, ".repocatignore") for line in text.splitlines())

    root_action = _make_pattern_action(tuple(sources), "repocat rules")
    if root_action is not None:
        actions.append(root_action)

    cli_sources: list[RuleSource] = []
    for rule in cli_rules:
        if rule.kind == "include":
            cli_sources.append(RuleSource(f"!{rule.pattern}", "command line"))
        elif rule.kind == "exclude":
            cli_sources.append(RuleSource(rule.pattern or "", "command line"))
        elif rule.kind == "gitignore_filter":
            cli_action = _make_pattern_action(tuple(cli_sources), "repocat rules")
            if cli_action is not None:
                actions.append(cli_action)
            cli_sources = []
            actions.append(RepocatGitignoreFilterAction())

    cli_action = _make_pattern_action(tuple(cli_sources), "repocat rules")
    if cli_action is not None:
        actions.append(cli_action)

    return SelectionConfig(
        root=root,
        output_path=output_path,
        ignore_gitignore=ignore_gitignore,
        repocat_actions=tuple(actions),
    )


def select_candidate(config: SelectionConfig, candidate: CandidateFile) -> SelectionDecision:
    """Select or reject a candidate file according to v1 precedence."""
    path = candidate.root_relative_path

    hard_decision = hard_exclusion_decision(config, candidate.absolute_path, candidate.read_path, path)
    if hard_decision is not None:
        return hard_decision

    repocat_decision = evaluate_repocat_layer(config, path, candidate.active_gitignores)
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


def evaluate_repocat_layer(
    config: SelectionConfig,
    root_relative_path: str,
    active_gitignores: tuple[ActiveGitignoreSpec, ...],
) -> SelectionDecision | None:
    """Evaluate the ordered higher-precedence repocat layer."""
    decision: SelectionDecision | None = None

    for action in config.repocat_actions:
        if isinstance(action, RepocatPatternAction):
            pattern_decision = evaluate_repocat_pattern_action(action, root_relative_path)
            if pattern_decision is not None:
                decision = pattern_decision
        elif isinstance(action, RepocatGitignoreFilterAction):
            filter_decision = evaluate_gitignore_filter(root_relative_path, active_gitignores)
            if filter_decision is not None:
                decision = filter_decision

    return decision


def evaluate_repocat_pattern_action(
    action: RepocatPatternAction,
    root_relative_path: str,
) -> SelectionDecision | None:
    """Evaluate one contiguous repocat pattern chunk."""
    result = action.spec.check_file(root_relative_path)
    if result.include is None:
        return None

    source = _source_at(action.sources, result.index)
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


def evaluate_gitignore_filter(
    root_relative_path: str,
    active_gitignores: tuple[ActiveGitignoreSpec, ...],
) -> SelectionDecision | None:
    """Apply .gitignore as an exclusion-only ordered repocat action."""
    decision = evaluate_gitignore_layer(root_relative_path, active_gitignores)
    if decision is None or decision.kind is not DecisionKind.EXCLUDE:
        return None

    return SelectionDecision(
        DecisionKind.EXCLUDE,
        root_relative_path,
        decision.reason.replace("matched .gitignore:", "matched gitignore filter:", 1),
        decision.source,
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


def _make_pattern_action(
    sources: tuple[RuleSource, ...],
    description: str,
) -> RepocatPatternAction | None:
    """Compile sources into a repocat pattern action if any source is effective."""
    spec, effective_sources = _compile_gitignore_sources(sources, description)
    if not effective_sources:
        return None
    return RepocatPatternAction(spec=spec, sources=effective_sources)


def _compile_gitignore_sources(
    sources: tuple[RuleSource, ...],
    description: str,
) -> tuple[GitIgnoreSpec, tuple[RuleSource, ...]]:
    """Compile effective gitignore patterns and aligned source metadata."""
    patterns: list[GitIgnoreSpecPattern] = []
    effective_sources: list[RuleSource] = []

    try:
        for source in sources:
            if source.pattern == "":
                continue
            pattern = GitIgnoreSpecPattern(source.pattern)
            if pattern.include is None:
                continue
            patterns.append(pattern)
            effective_sources.append(source)
    except GitIgnorePatternError as exc:
        raise RepocatError(f"Invalid ignore pattern in {description}: {exc}") from exc

    return GitIgnoreSpec(patterns), tuple(effective_sources)
