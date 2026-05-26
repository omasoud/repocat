"""Shared data models for repository capture."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal

from pathspec import GitIgnoreSpec


RuleKind = Literal["include", "exclude", "gitignore_filter"]
OutputFormat = Literal["cxml", "markdown"]


@dataclass(frozen=True, slots=True)
class CliRule:
    """A command-line repocat rule in original argv order."""

    kind: RuleKind
    pattern: str | None = None


@dataclass(frozen=True, slots=True)
class CliOptions:
    """Parsed command-line options for the main capture command."""

    output_format: OutputFormat
    output_path: Path | None
    ignore_gitignore: bool
    cli_rules: tuple[CliRule, ...]
    list_files: bool


@dataclass(frozen=True, slots=True)
class CheckOptions:
    """Parsed command-line options for the check diagnostic command."""

    ignore_gitignore: bool
    cli_rules: tuple[CliRule, ...]
    files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuleSource:
    """Source metadata for a compiled ignore pattern."""

    pattern: str
    origin: str


@dataclass(frozen=True, slots=True)
class SelectionConfig:
    """Selection settings shared by traversal, diagnostics, and capture."""

    root: Path
    output_path: Path | None
    ignore_gitignore: bool
    repocat_actions: tuple["RepocatAction", ...]


@dataclass(frozen=True, slots=True)
class RepocatPatternAction:
    """A contiguous compiled chunk of repocat include/exclude patterns."""

    spec: GitIgnoreSpec
    sources: tuple[RuleSource, ...]


@dataclass(frozen=True, slots=True)
class RepocatGitignoreFilterAction:
    """An ordered exclusion-only gitignore filter action."""

    origin: str = "command line"


RepocatAction = RepocatPatternAction | RepocatGitignoreFilterAction


class DecisionKind(Enum):
    """Possible selection decision categories."""

    INCLUDE = "include"
    EXCLUDE = "exclude"
    NOT_FOUND = "not_found"
    NOT_A_FILE = "not_a_file"


@dataclass(frozen=True, slots=True)
class SelectionDecision:
    """Structured selection result with a human-readable reason."""

    kind: DecisionKind
    root_relative_path: str
    reason: str
    source: str | None = None


@dataclass(frozen=True, slots=True)
class ActiveGitignoreSpec:
    """A gitignore spec that applies to a candidate file."""

    gitignore_dir_rel: str
    spec: GitIgnoreSpec
    source_path: Path
    sources: tuple[RuleSource, ...]


@dataclass(frozen=True, slots=True)
class CandidateFile:
    """A traversed file path plus selection context."""

    root_relative_path: str
    absolute_path: Path
    read_path: Path
    active_gitignores: tuple[ActiveGitignoreSpec, ...]


@dataclass(frozen=True, slots=True)
class CapturedFile:
    """A selected UTF-8 file ready for rendering."""

    root_relative_path: str
    absolute_path: Path
    content: str


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Diagnostic result for one check path."""

    decision: SelectionDecision
    would_capture: bool
