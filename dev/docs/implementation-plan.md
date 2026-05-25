# repocat Implementation Plan

## Overview

Implement `repocat` v1 as specified in [repocat-implementation-specification.md](repocat-implementation-specification.md).

The v1 goal is a deterministic CLI repository capture tool that:

- walks the current working directory only;
- applies hard exclusions before all other rules;
- evaluates `.repocatignore` and CLI include/exclude rules before `.gitignore`;
- respects nested `.gitignore` files by default;
- reads and writes UTF-8 only;
- renders Claude XML-style output by default, with Markdown as an option;
- supports `--list-files` and `check FILE...` diagnostics;
- has focused unit and CLI coverage for selection precedence, traversal, rendering, and diagnostics.

Follow the project guidance in `AGENT.md`: use Python, Typer for the CLI, `uv` for dependency management, type hints, docstrings, and test-driven implementation slices.

## Phase 1: Project Foundation

- [x] PROJ-01 Add runtime dependencies for `typer` and `pathspec` using `uv`.
- [x] PROJ-02 Add a package entry module layout under `src/repocat/` that separates CLI, models, selection, traversal, reading, rendering, and diagnostics.
- [x] PROJ-03 Replace the placeholder `main()` in `src/repocat/__init__.py` with a stable package entrypoint that dispatches to the CLI app.
- [x] PROJ-04 Add shared test helpers for temporary repository trees, command invocation, file creation, binary/non-UTF-8 files, and normalized path assertions.
- [x] PROJ-05 Add a smoke test proving the installed `repocat` command enters the real CLI rather than the placeholder output.

## Phase 2: Core Models and Path Handling

- [x] CORE-01 Define `CliOptions`, `SelectionConfig`, `SelectionDecision`, `DecisionKind`, `CandidateFile`, `CapturedFile`, and `ActiveGitignoreSpec` data structures.
- [x] CORE-02 Implement root-relative POSIX path normalization for files and directories on Windows and POSIX.
- [x] CORE-03 Implement invocation-root containment checks for absolute paths, resolved symlink targets, and output-file hard exclusions.
- [x] CORE-04 Implement output-path resolution relative to the invocation root, preserving support for absolute output paths outside the root.
- [x] CORE-05 Test normalized root-relative paths use `/` separators and never escape the invocation root.
- [x] CORE-06 Test output-file hard exclusion resolution for relative, absolute-inside-root, and absolute-outside-root paths.

## Phase 3: CLI Parsing and Validation

- [x] CLI-01 Implement Typer main command options: `--cxml`, `--markdown`, `--output`, `--ignore-gitignore`, `--include`, `--exclude`, and `--list-files`.
- [x] CLI-02 Implement the `check FILE...` subcommand with the same selection-related options as the main command.
- [x] CLI-03 Preserve exact argv order for repeated `--include` and `--exclude` options when building repocat-layer rules.
- [x] CLI-04 Validate `--cxml` and `--markdown` as mutually exclusive, defaulting to CXML when neither is supplied.
- [x] CLI-05 Validate `--list-files` cannot be combined with output format options or `--output`.
- [x] CLI-06 Validate `--include` patterns must not start with `!`, returning a usage error.
- [x] CLI-07 Test main command parsing for defaults, explicit CXML, Markdown, output, and ignore-gitignore.
- [x] CLI-08 Test CLI usage errors for invalid option combinations and invalid include patterns.
- [x] CLI-09 Test `check` exit code `2` for usage errors.

## Phase 4: Ignore Rule Loading and Selection Semantics

- [x] SEL-01 Load root `.repocatignore` as UTF-8 when present and ignore nested `.repocatignore` files.
- [x] SEL-02 Build repocat-layer rules from `.repocatignore` first, then CLI rules in exact argv order.
- [x] SEL-03 Compile repocat rules with `pathspec.GitIgnoreSpec.from_lines()`.
- [x] SEL-04 Add the required pathspec polarity unit test for `GitIgnoreSpec.check_file().include`.
- [x] SEL-05 Implement repocat-layer evaluation where normal patterns exclude and negated patterns include.
- [x] SEL-06 Implement cached `.gitignore` loading for root and nested `.gitignore` files as UTF-8.
- [x] SEL-07 Implement gitignore-layer evaluation from root to leaf, passing each spec a path relative to its `.gitignore` directory.
- [x] SEL-08 Implement selector decision order: hard exclusion, repocat layer, gitignore layer unless disabled, default include.
- [x] SEL-09 Include structured diagnostic reasons for hard exclusions, repocat include/exclude, gitignore include/exclude, and default include.
- [x] SEL-10 Test default include when no rules match.
- [x] SEL-11 Test `.gitignore` root exclusion, nested exclusion, and nested negation.
- [x] SEL-12 Test `.repocatignore` exclusion overriding default include.
- [x] SEL-13 Test `.repocatignore` and CLI includes overriding `.gitignore` exclusions.
- [x] SEL-14 Test CLI include/exclude order where later rules win.
- [x] SEL-15 Test CLI rules appended after `.repocatignore` can override `.repocatignore`.
- [x] SEL-16 Test `--ignore-gitignore` disables only the gitignore layer.
- [x] SEL-17 Test `-i '*'` includes traversable UTF-8 files regardless of `.gitignore`, except hard exclusions.
- [x] SEL-18 Test `.git/` and output file hard exclusions cannot be overridden by broad includes.

## Phase 5: Traversal and Symlink Policy

- [x] WALK-01 Implement recursive or stack-based traversal starting at `Path.cwd().resolve()`.
- [x] WALK-02 Prune `.git/` and descendants as hard-excluded traversal paths.
- [x] WALK-03 Do not prune directories based solely on `.gitignore` decisions.
- [x] WALK-04 Maintain active `.gitignore` specs while entering and exiting directories.
- [x] WALK-05 Produce candidate files with their active gitignore context and normalized root-relative path.
- [x] WALK-06 Treat hidden files as ordinary files except for `.git/`.
- [x] WALK-07 Skip directory symlinks without following them.
- [x] WALK-08 For file symlinks, warn and skip broken links.
- [x] WALK-09 For file symlinks, warn and skip targets outside the invocation root.
- [x] WALK-10 For file symlinks targeting files inside the invocation root, read the target but render the symlink path.
- [x] WALK-11 Sort captured files lexicographically by normalized root-relative path before list or render output.
- [x] WALK-12 Test repocat include can capture a file under a `.gitignore`-ignored directory.
- [x] WALK-13 Test `.git/` is not traversed.
- [x] WALK-14 Test hidden files are included by default.
- [x] WALK-15 Test `.gitignore` above the invocation root is ignored.
- [x] WALK-16 Test nested `.repocatignore` is ignored.
- [x] WALK-17 Test deterministic sorted output order.
- [x] WALK-18 Test all required symlink policy cases where the platform supports them.

## Phase 6: UTF-8 Reading, Warnings, and Output Writing

- [x] IO-01 Implement UTF-8 reading for `.repocatignore`, `.gitignore`, and captured files.
- [x] IO-02 Skip selected files that fail UTF-8 decoding and emit warnings to stderr.
- [x] IO-03 Skip selected files that fail with read `OSError` and emit warnings to stderr.
- [x] IO-04 Ensure warnings never mix into stdout prompt output.
- [x] IO-05 Implement UTF-8 output writing for `--output`, overwriting an existing file and requiring the parent directory to already exist.
- [x] IO-06 Keep normal capture and list mode exit code `0` when individual selected files are skipped due to read/decode warnings.
- [x] IO-07 Test UTF-8 files are captured.
- [x] IO-08 Test non-UTF-8 files are skipped with stderr warnings and omitted from `--list-files`.
- [x] IO-09 Test unreadable files are skipped with warnings where permission manipulation is supported.
- [x] IO-10 Test output files are written as UTF-8 and excluded from capture.

## Phase 7: Renderers

- [x] REND-01 Implement default Claude XML-style renderer with `<documents>`, indexed `<document>` entries, `<source>`, and raw `<document_content>`.
- [x] REND-02 Preserve file contents as read and do not XML-escape paths or contents.
- [x] REND-03 Avoid timestamps and nondeterministic metadata in all renderers.
- [x] REND-04 Implement Markdown renderer with `## \`path\`` headings and fenced code blocks.
- [x] REND-05 Infer Markdown fence language labels for the extensions listed in the specification.
- [x] REND-06 Use an empty Markdown fence language for unknown extensions.
- [x] REND-07 Choose a Markdown fence length longer than any contiguous backtick run in each file.
- [x] REND-08 Test CXML default output, sorted document order, raw content insertion, no escaping, and no timestamp.
- [x] REND-09 Test Markdown output, language inference, unknown extensions, expanded fence length, sorted order, and no timestamp.

## Phase 8: Diagnostics and Exit Codes

- [x] DIAG-01 Implement `--list-files` using the same traversal, selection, symlink, UTF-8 readability, and sorting behavior as normal capture.
- [x] DIAG-02 Implement `check FILE...` for included, excluded, not found, and not a regular file outcomes.
- [x] DIAG-03 Resolve checked paths relative to the invocation root unless absolute, and display normalized root-relative paths where possible.
- [x] DIAG-04 Report primary decision reasons for `check` output.
- [x] DIAG-05 Return `0` from `check` only when every checked path would be captured.
- [x] DIAG-06 Return `1` from `check` when any checked path is excluded, missing, unreadable, non-UTF-8, or not a regular file.
- [x] DIAG-07 Return `2` from `check` for usage errors or fatal runtime errors.
- [x] DIAG-08 Test `--list-files` output exactly matches render capture membership and order.
- [x] DIAG-09 Test `check` output categories and reason text for representative cases.
- [x] DIAG-10 Test `check` exit codes `0`, `1`, and `2`.

## Phase 9: User Documentation and Final Acceptance

- [x] DOC-01 Update `README.md` with install/use examples for default capture, Markdown output, file output, ignore-gitignore, includes/excludes, list mode, and check mode.
- [x] DOC-02 Add concise user-facing explanation of precedence: repocat rules win, gitignore is consulted only when repocat has no opinion.
- [x] DOC-03 Document hard exclusions, UTF-8 behavior, symlink policy, and warning behavior.
- [x] DOC-04 Add or update developer docs with architecture notes if the implementation differs materially from the suggested components.
- [x] ACC-01 Run the full test suite with `uv run pytest`.
- [x] ACC-02 Manually smoke test `repocat`, `repocat --markdown`, `repocat --list-files`, and `repocat check README.md` from the repository root.
- [x] ACC-03 Confirm all acceptance criteria in the specification are represented by completed tasks or tests.

