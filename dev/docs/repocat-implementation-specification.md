# repocat Implementation Specification

## 1. Purpose

`repocat` is a command-line file-to-prompt tool. It walks the current working directory, selects text files according to deterministic ignore/include rules, and renders the selected files into a prompt-friendly output format.

The tool is intended for repository capture and AI prompt construction. Its default behavior should be safe and predictable:

- operate from the current working directory;
- respect `.gitignore` files by default;
- allow repocat-specific rules to override `.gitignore`;
- produce deterministic output ordering;
- read and write text as UTF-8;
- avoid hidden timestamps or other nondeterministic metadata in generated output.

The most important design principle is that repocat has its own higher-precedence selection layer. `.repocatignore` and command-line `--include` / `--exclude` rules are not merely appended to `.gitignore`; they are evaluated as a separate override layer that decides before `.gitignore` is consulted.

---

## 2. Non-Goals for v1

The v1 implementation does not need to support:

- multiple root directories;
- reading `.repocatignore` from parent directories;
- JSON output for `check`;
- timestamped output headers;
- following directory symlinks;
- automatic token counting;
- binary file inclusion;
- custom encodings other than UTF-8;
- XML escaping in Claude XML output.

---

## 3. Terminology

### 3.1 Invocation Root

The invocation root is the current working directory at the time `repocat` starts.

All traversal is rooted at this directory. The tool does not capture files outside this directory.

### 3.2 Root-Relative Path

A root-relative path is a path from the invocation root to a file or directory, normalized to POSIX-style separators.

Examples:

```text
src/main.py
docs/design.md
.repocatignore
```

Even on Windows, internal matching and output paths use `/`, not `\`.

### 3.3 Captured File

A captured file is a regular text file that:

1. is discovered during traversal;
2. is not hard-excluded;
3. is selected by the final file-selection decision;
4. can be read as UTF-8.

Captured files are rendered in the requested output format.

### 3.4 Hard Exclusion

A hard exclusion is a path that repocat never captures, regardless of `.repocatignore`, CLI includes, or `.gitignore` behavior.

For v1, the hard exclusions are:

- `.git/` and all descendants;
- the output file specified by `--output`, if any.

Hard exclusions override even broad include rules such as `--include '*'`.

### 3.5 Repocat Layer

The repocat layer is the higher-precedence selection layer formed from:

1. the root `.repocatignore` file, if present;
2. command-line `--include` and `--exclude` rules, appended in exact command-line order.

This layer is evaluated before `.gitignore`.

If the repocat layer matches a file, it makes the final include/exclude decision for that file.

### 3.6 Gitignore Layer

The gitignore layer consists of `.gitignore` files discovered at the invocation root or below.

`.gitignore` files outside the invocation root are ignored.

The gitignore layer is consulted only when the repocat layer has no opinion for a file, and only when `--ignore-gitignore` is not set.

---

## 4. Command-Line Interface

## 4.1 Main Command

```bash
repocat [OPTIONS]
```

The main command captures files and renders them to stdout or to a file.

### 4.1.1 Format Options

```bash
-c, --cxml
```

Output in Claude XML-style format.

This is the default format.

```bash
-m, --markdown
```

Output in Markdown format using fenced code blocks.

`--cxml` and `--markdown` are mutually exclusive. If neither is provided, `--cxml` is used.

### 4.1.2 Output Option

```bash
-o, --output <file>
```

Write output to `<file>` instead of stdout.

The output file is always excluded from capture, regardless of ignore/include rules. This prevents accidental self-capture.

The output file path is resolved relative to the invocation root unless an absolute path is supplied. The resolved output file must be treated as a hard exclusion if it is inside the invocation root. If the output path is outside the invocation root, it is not traversable and therefore does not need to be excluded from traversal, but it still must be opened and written as UTF-8.

### 4.1.3 Ignore Behavior

```bash
--ignore-gitignore
```

Disable `.gitignore` handling entirely.

When this option is set:

- `.gitignore` files are not loaded;
- `.gitignore` files do not affect selection;
- the repocat layer and hard exclusions still apply.

### 4.1.4 Include and Exclude Rules

```bash
-i, --include <pattern>
-e, --exclude <pattern>
```

Both options are repeatable and order-sensitive.

`--exclude <pattern>` appends a normal gitignore-style pattern to the repocat layer.

`--include <pattern>` appends a negated gitignore-style pattern to the repocat layer. Internally, this is equivalent to prepending `!` to the supplied pattern.

Examples:

```bash
repocat -e tmp/
repocat -i tmp/keep.txt
repocat -e tmp/ -i tmp/keep.txt
repocat -i '*' -e secrets.env
```

Command-line rules are appended after `.repocatignore` in exact argv order. Later matching rules in the repocat layer override earlier matching rules in that same layer.

For example:

```bash
repocat -e tmp/ -i tmp/keep.txt -e tmp/keep.txt
```

The final `-e tmp/keep.txt` wins for `tmp/keep.txt`, so that file is excluded.

### 4.1.5 List Mode

```bash
--list-files
```

List the files that would be captured, one root-relative path per line, then exit without rendering file contents.

List mode uses the same traversal, hard exclusions, ignore handling, UTF-8 readability checks, symlink policy, and deterministic ordering as normal capture mode.

Unreadable or non-UTF-8 files that would otherwise be selected are not listed as captured files. They should produce warnings on stderr.

`--list-files` may be combined with selection options such as `--ignore-gitignore`, `-i`, and `-e`.

`--list-files` must not be combined with output format options or `--output`; if supplied together, the CLI should fail with a usage error.

## 4.2 Check Subcommand

```bash
repocat check [OPTIONS] FILE...
```

The `check` subcommand reports whether specific paths would be captured.

It is a diagnostic mode, not a rendering mode. It does not support `--cxml`, `--markdown`, or `--output`.

It should support the same selection-related options as the main command:

```bash
repocat check [--ignore-gitignore] [-i PATTERN] [-e PATTERN] FILE...
```

Each supplied file path is resolved relative to the invocation root unless absolute. The output uses normalized root-relative POSIX paths where possible.

Example output:

```text
INCLUDED  src/main.py
EXCLUDED  tmp/cache.db  matched .gitignore: tmp/
EXCLUDED  prompt.xml     hard-excluded: output file
EXCLUDED  image.png      non-utf-8 or unreadable
```

The exact wording can vary, but the output must clearly indicate:

- included vs excluded;
- normalized path;
- primary reason for the decision.

No JSON output mode is required for v1.

### 4.2.1 Check Exit Codes

`repocat check` should use script-friendly exit codes:

```text
0  all checked paths would be captured
1  one or more checked paths would not be captured
2  usage error or fatal runtime error
```

---

## 5. Configuration Files

## 5.1 `.repocatignore`

At startup, repocat looks for a file named `.repocatignore` in the invocation root only.

If present, it is read as UTF-8.

If absent, the repocat layer starts empty and may still receive command-line `--include` / `--exclude` rules.

`.repocatignore` uses gitignore-style pattern syntax as implemented through `pathspec.GitIgnoreSpec`.

`.repocatignore` is root-scoped. Its patterns are interpreted relative to the invocation root, not relative to nested directories.

Nested `.repocatignore` files are ignored in v1.

## 5.2 `.gitignore`

Unless `--ignore-gitignore` is specified, repocat discovers and applies `.gitignore` files at the invocation root and below.

`.gitignore` files above the invocation root are not considered.

Each `.gitignore` file is scoped to its own directory, matching normal gitignore semantics.

For a file at:

```text
src/pkg/module.py
```

The applicable `.gitignore` files are, if they exist:

```text
.gitignore
src/.gitignore
src/pkg/.gitignore
```

They are evaluated from root to leaf, with deeper `.gitignore` files taking precedence over shallower ones when both have matching rules.

## 5.3 Capturing Ignore Files Themselves

`.repocatignore` and `.gitignore` are not hard-excluded.

They may be captured if the final selection rules include them and they are readable as UTF-8.

Users who do not want these files captured can exclude them explicitly:

```gitignore
.repocatignore
.gitignore
```

---

## 6. File Selection Semantics

## 6.1 Decision Order

For every file, repocat makes the capture decision in this order:

```text
1. If the path is hard-excluded, exclude it.

2. Evaluate the repocat layer.
   If the repocat layer has a matching rule, that decision wins.

3. If --ignore-gitignore is not set, evaluate applicable .gitignore files.
   If .gitignore has a matching decision, use it.

4. Otherwise, include the file.
```

This can be represented as:

```python
def should_capture(path):
    if is_hard_excluded(path):
        return False

    repocat_decision = evaluate_repocat_layer(path)
    if repocat_decision is not None:
        return repocat_decision

    if not ignore_gitignore:
        gitignore_decision = evaluate_gitignore_layer(path)
        if gitignore_decision is not None:
            return gitignore_decision

    return True
```

## 6.2 Repocat Layer Precedence

The repocat layer has absolute precedence over `.gitignore`.

If `.repocatignore` or CLI rules match a file, `.gitignore` is not consulted for that file.

Example:

```gitignore
# .gitignore
tmp/
```

```bash
repocat -i tmp/keep.txt
```

Result:

```text
tmp/keep.txt is included.
Other files under tmp/ remain ignored unless another repocat rule includes them.
```

## 6.3 Broad Include Rules

A broad include rule such as:

```bash
repocat -i '*'
```

means:

```text
Include all traversable files under the invocation root, regardless of .gitignore, except hard-excluded files and files that cannot be read as UTF-8.
```

`.gitignore` is still conceptually part of the default policy, but it has no practical effect on files matched by `-i '*'`, because the repocat layer decides first.

## 6.4 `--ignore-gitignore`

`--ignore-gitignore` disables only the gitignore layer.

It does not disable:

- hard exclusions;
- `.repocatignore`;
- CLI `--include` / `--exclude` rules;
- UTF-8 decoding requirements;
- symlink policy.

## 6.5 Pathspec Polarity

The implementation should use `pathspec.GitIgnoreSpec` for gitignore-style matching.

For `GitIgnoreSpec.check_file(path)`, v1 should assume and test the following polarity:

```python
result.include is True   # matched a normal ignore/exclude pattern
result.include is False  # matched a negated include pattern
result.include is None   # no matching pattern
```

The implementation must include a unit test to lock this behavior:

```python
from pathspec import GitIgnoreSpec


def test_pathspec_gitignore_include_polarity():
    spec = GitIgnoreSpec.from_lines([
        "*.log",
        "!keep.log",
    ])

    assert spec.check_file("debug.log").include is True
    assert spec.check_file("keep.log").include is False
    assert spec.check_file("main.py").include is None
```

## 6.6 Repocat Layer Evaluation

Implementation rule:

```python
def evaluate_repocat_layer(root_relative_path: str) -> bool | None:
    result = repocat_spec.check_file(root_relative_path)

    if result.include is True:
        return False  # excluded by repocat layer

    if result.include is False:
        return True   # included by repocat layer

    return None       # no repocat opinion
```

The implementation should prefer `GitIgnoreSpec.check_file()` over manually iterating pattern objects in reverse. The reverse-order behavior is a useful conceptual model, but the implementation should allow `pathspec` to handle the matching details.

## 6.7 Gitignore Layer Evaluation

For a candidate file, evaluate all applicable `.gitignore` specs from root to leaf.

Each `.gitignore` spec must receive a path relative to the directory containing that `.gitignore` file.

Example:

```text
Invocation root: /repo
File:            /repo/src/pkg/module.py
Gitignore:       /repo/src/.gitignore
Path to check:   pkg/module.py
```

The root `.gitignore` case must be handled carefully. If the `.gitignore` directory is the invocation root, the path passed to that spec is simply the root-relative path.

Conceptual implementation:

```python
def evaluate_gitignore_layer(root_relative_path: str, active_gitignore_specs) -> bool | None:
    ignored = None

    for gitignore_dir_rel, spec in active_gitignore_specs:
        path_for_spec = relativize_to_gitignore_dir(
            root_relative_path,
            gitignore_dir_rel,
        )

        result = spec.check_file(path_for_spec)

        if result.include is True:
            ignored = True
        elif result.include is False:
            ignored = False

    if ignored is True:
        return False

    if ignored is False:
        return True

    return None
```

---

## 7. Traversal Semantics

## 7.1 Traversal Root

Traversal starts at the invocation root.

The tool must not traverse outside the invocation root.

## 7.2 Deterministic Traversal

File output order must be deterministic.

The required behavior is:

```text
All captured files are sorted lexicographically by normalized root-relative POSIX path before rendering.
```

Directory walk order may be implementation-specific internally, but the final captured file list must be sorted before output.

## 7.3 Directory Pruning

File classification and directory traversal must be treated as separate concerns.

Because repocat include rules can override `.gitignore`, the implementation must not blindly prune directories only because `.gitignore` ignores them.

Example:

```gitignore
# .gitignore
tmp/
```

```bash
repocat -i tmp/keep.txt
```

The tool must still be able to discover `tmp/keep.txt`.

Required v1 behavior:

```text
Do not prune directories based solely on .gitignore decisions.
```

The implementation may prune hard-excluded directories such as `.git/`.

Future optimized pruning is allowed only if it can prove that no higher-precedence repocat include rule could match descendants.

## 7.4 `.gitignore` Discovery During Traversal

When entering a directory, if `--ignore-gitignore` is not set and the directory contains `.gitignore`, compile it once and add it to the active `.gitignore` stack for that directory and its descendants.

The compiled spec must be cached per `.gitignore` file path. It must not be reparsed once per file.

A top-down traversal can maintain an active stack of:

```text
(gitignore_dir_rel, compiled_spec)
```

When traversal exits the directory, that directory's spec is removed from the active stack.

Implementation approaches:

1. recursive traversal that naturally pushes/pops specs;
2. iterative traversal with explicit stack frames carrying active specs.

Either is acceptable if behavior is identical.

## 7.5 Hidden Files

Hidden files are treated like any other files.

They are included or excluded only according to hard exclusions, repocat rules, `.gitignore`, UTF-8 readability, and symlink policy.

There is no special default exclusion for dotfiles other than `.git/`.

---

## 8. Symlink Policy

## 8.1 Directory Symlinks

Directory symlinks must not be followed.

This avoids cycles and accidental traversal outside the invocation root.

## 8.2 File Symlinks

For file symlinks:

- if the symlink is broken, skip it and warn;
- if the resolved target is outside the invocation root, skip it and warn;
- if the resolved target is inside the invocation root, read the target as UTF-8 and render the symlink path as the source path.

Example:

```text
docs/current.md -> docs/v2/current.md
```

If selected, the output source path is:

```text
docs/current.md
```

not:

```text
docs/v2/current.md
```

---

## 9. Text and Encoding Behavior

## 9.1 UTF-8 Only

All configuration files, captured files, and output files are read or written as UTF-8.

This includes:

- `.repocatignore`;
- `.gitignore`;
- captured file contents;
- `--output` target.

## 9.2 Decode Failures

If a selected file cannot be decoded as UTF-8, skip it and emit a warning to stderr.

The generated prompt output must remain valid according to the selected output mode and must not include partial replacement-character content from decode failures.

## 9.3 Read Failures

If a selected file cannot be read due to permissions or I/O errors, skip it and emit a warning to stderr.

## 9.4 Warning Behavior

Warnings are written to stderr.

Warnings must not be mixed into stdout prompt output.

When `--output` is used, warnings still go to stderr.

For normal capture mode, skipped files due to warnings do not make the command fail by default. The command should still exit `0` if it successfully produced output.

---

## 10. Output Rendering

## 10.1 Common Rendering Rules

Before rendering:

1. collect candidate files;
2. apply final selection rules;
3. discard files that cannot be read as UTF-8;
4. sort captured files lexicographically by normalized root-relative path;
5. render in the requested format.

Output must not include generation timestamps.

Output should be deterministic for a fixed file tree and fixed command-line invocation.

## 10.2 Claude XML-Style Output

Claude XML-style output is the default.

Example:

```xml
<documents>
<document index="1">
<source>src/main.py</source>
<document_content>
print("hello")
</document_content>
</document>
<document index="2">
<source>README.md</source>
<document_content>
# Project

Content here.
</document_content>
</document>
</documents>
```

Important v1 rule:

```text
Do not XML-escape paths or file contents.
```

This format is Claude-XML-style prompt markup, not a guarantee of formally valid XML for arbitrary file contents.

Consequences:

- file contents are inserted raw;
- `<`, `>`, `&`, and similar characters are not escaped;
- a file containing `</document_content>` may structurally confuse consumers;
- this is accepted for v1 by design.

The implementation may still normalize line endings in the generated wrapper, but file contents should be preserved as read, except that the renderer may ensure a newline before the closing `</document_content>` tag for readability.

## 10.3 Markdown Output

Markdown output is selected with:

```bash
repocat --markdown
```

or:

```bash
repocat -m
```

Example:

````markdown
## `src/main.py`

```python
print("hello")
```

## `README.md`

```markdown
# Project

Content here.
```
````

### 10.3.1 Language Label Inference

The Markdown renderer should infer common language labels from file extension.

Examples:

```text
.py    python
.js    javascript
.ts    typescript
.tsx   tsx
.jsx   jsx
.md    markdown
.json  json
.yaml  yaml
.yml   yaml
.toml  toml
.xml   xml
.html  html
.css   css
.sh    bash
.ps1   powershell
.sql   sql
.java  java
.cs    csharp
.cpp   cpp
.c     c
.h     c
.hpp   cpp
.rs    rust
.go    go
.rb    ruby
.php   php
```

If the extension is unknown, use an empty fence language.

### 10.3.2 Fence Safety

The Markdown renderer must handle file contents that contain triple backticks.

For each file, choose a fence length longer than any contiguous run of backticks found in that file.

For example, if the file contains:

````markdown
```text
example
```
````

then the renderer can wrap with four backticks:

`````markdown
````markdown
```text
example
```
````
`````

---

## 11. Output Destination

## 11.1 Stdout

If `--output` is not specified, prompt output is written to stdout as UTF-8 text.

Warnings are written to stderr.

## 11.2 File Output

If `--output <file>` is specified, prompt output is written to that file as UTF-8.

The output file's parent directory must exist. v1 does not need to create missing parent directories unless explicitly desired by the implementation.

If the output file already exists, it is overwritten.

The output file is hard-excluded from capture.

If the output file is inside a directory that would otherwise be captured, it must still be excluded.

Example:

```bash
repocat -i '*' -o prompt.xml
```

Captures all traversable UTF-8 files except:

- `.git/` descendants;
- `prompt.xml`;
- unreadable or non-UTF-8 files;
- disallowed symlinks.

---

## 12. Diagnostics

## 12.1 `--list-files`

`--list-files` reports the exact files that would be captured by normal mode, after all selection rules and UTF-8 checks.

Example:

```bash
repocat --list-files
```

Output:

```text
README.md
pyproject.toml
src/main.py
src/util.py
```

The list must be sorted in the same order files would be rendered.

## 12.2 `check FILE...`

`check` reports whether each named path would be captured.

It should evaluate:

- hard exclusions;
- repocat layer;
- gitignore layer unless disabled;
- symlink policy;
- existence;
- regular-file status;
- UTF-8 readability.

Possible result categories:

```text
INCLUDED
EXCLUDED
NOT_FOUND
NOT_A_FILE
```

The implementation may render `NOT_FOUND` and `NOT_A_FILE` as excluded results for exit-code purposes.

Example:

```bash
repocat check src/main.py tmp/cache.db missing.txt
```

Output:

```text
INCLUDED   src/main.py
EXCLUDED   tmp/cache.db   matched .gitignore: tmp/
NOT_FOUND  missing.txt
```

## 12.3 Decision Reasons

For diagnostics, the implementation should report the primary reason for inclusion/exclusion when practical.

Recommended reason examples:

```text
hard-excluded: .git directory
hard-excluded: output file
matched repocat include: !tmp/keep.txt
matched repocat exclude: tmp/
matched .gitignore: tmp/
default include
non-utf-8 or unreadable
external symlink target
broken symlink
not found
not a regular file
```

---

## 13. Exit Codes

## 13.1 Main Command

```text
0  success
1  usage error or fatal runtime error
```

Read warnings for individual files do not fail the command in v1.

## 13.2 `--list-files`

```text
0  success
1  usage error or fatal runtime error
```

## 13.3 `check`

```text
0  all checked paths would be captured
1  one or more checked paths would not be captured
2  usage error or fatal runtime error
```

---

## 14. Internal Architecture

## 14.1 Suggested Components

The implementation should be organized around these components:

```text
CliOptions
  Parsed command-line options.

SelectionConfig
  Invocation root, output file path, ignore-gitignore flag, compiled repocat spec.

IgnoreManager
  Loads and caches .gitignore files.
  Maintains active .gitignore specs during traversal.

FileWalker
  Traverses the invocation root.
  Applies hard directory exclusions and symlink policy.
  Produces candidate files with active gitignore context.

Selector
  Applies hard exclusions, repocat layer, and gitignore layer.
  Returns structured decisions with reasons.

Reader
  Reads selected files as UTF-8.
  Reports decode/read warnings.

Renderer
  Renders captured files as CXML or Markdown.

Diagnostics
  Implements --list-files and check.
```

## 14.2 Data Structures

Suggested decision model:

```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class DecisionKind(Enum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    NOT_FOUND = "not_found"
    NOT_A_FILE = "not_a_file"


@dataclass(frozen=True)
class SelectionDecision:
    kind: DecisionKind
    root_relative_path: str
    reason: str
    source: str | None = None
```

Suggested captured file model:

```python
@dataclass(frozen=True)
class CapturedFile:
    root_relative_path: str
    absolute_path: Path
    content: str
```

Suggested active gitignore model:

```python
@dataclass(frozen=True)
class ActiveGitignoreSpec:
    gitignore_dir_rel: str
    spec: GitIgnoreSpec
    source_path: Path
```

---

## 15. Implementation Algorithms

## 15.1 Startup

1. Record invocation root as `Path.cwd().resolve()`.
2. Parse CLI arguments.
3. Resolve `--output`, if present.
4. Build hard-exclusion context:
   - `.git/` under invocation root;
   - resolved output file if it is under invocation root.
5. Load `.repocatignore` from invocation root if present.
6. Append CLI `--include` / `--exclude` patterns in argv order.
7. Compile the combined repocat rule list using `GitIgnoreSpec.from_lines()`.
8. Execute requested mode:
   - normal render;
   - `--list-files`;
   - `check`.

## 15.2 Building Repocat Rules

Given:

```bash
repocat -e tmp/ -i tmp/keep.txt
```

The effective repocat rule list is:

```gitignore
# contents of .repocatignore first, if any

tmp/
!tmp/keep.txt
```

Implementation concept:

```python
repocat_lines = []

if root_repocatignore.exists():
    repocat_lines.extend(read_utf8_lines(root_repocatignore))

for cli_rule in cli_rules_in_argv_order:
    if cli_rule.kind == "exclude":
        repocat_lines.append(cli_rule.pattern)
    elif cli_rule.kind == "include":
        repocat_lines.append("!" + cli_rule.pattern)

repocat_spec = GitIgnoreSpec.from_lines(repocat_lines)
```

If the user passes an include pattern that already starts with `!`, the implementation should treat it as a literal user error rather than attempting to double-negate or reinterpret it.

Recommended behavior:

```text
-i/--include patterns must not start with '!'. Use -e/--exclude for exclusions.
```

## 15.3 Walking Files

Recommended recursive outline:

```python
def walk_dir(dir_path: Path, dir_rel: str, active_gitignores: list[ActiveGitignoreSpec]):
    if is_hard_excluded_dir(dir_path):
        return

    if not ignore_gitignore:
        gitignore_path = dir_path / ".gitignore"
        if gitignore_path.is_file():
            spec = load_cached_gitignore_spec(gitignore_path)
            active_gitignores = [
                *active_gitignores,
                ActiveGitignoreSpec(dir_rel, spec, gitignore_path),
            ]

    entries = sorted(dir_path.iterdir(), key=lambda p: normalize_rel_path(p))

    for entry in entries:
        if entry.is_dir() and not entry.is_symlink():
            walk_dir(entry, child_rel(dir_rel, entry.name), active_gitignores)
        elif entry.is_symlink():
            handle_symlink(entry, active_gitignores)
        elif entry.is_file():
            yield CandidateFile(entry, root_relative_path(entry), active_gitignores)
```

The implementation may avoid sorting during traversal if it sorts final captured files before rendering.

## 15.4 Selecting a Candidate File

```python
def select_candidate(candidate):
    path = candidate.root_relative_path

    if is_hard_excluded_file(candidate.absolute_path, path):
        return SelectionDecision(EXCLUDE, path, "hard-excluded")

    repocat_decision = evaluate_repocat_layer(path)
    if repocat_decision is True:
        return SelectionDecision(INCLUDE, path, "matched repocat include")
    if repocat_decision is False:
        return SelectionDecision(EXCLUDE, path, "matched repocat exclude")

    if not ignore_gitignore:
        git_decision = evaluate_gitignore_layer(path, candidate.active_gitignores)
        if git_decision is True:
            return SelectionDecision(INCLUDE, path, "matched .gitignore negation")
        if git_decision is False:
            return SelectionDecision(EXCLUDE, path, "matched .gitignore")

    return SelectionDecision(INCLUDE, path, "default include")
```

## 15.5 Reading Captured Files

For each included candidate:

```python
try:
    content = path.read_text(encoding="utf-8")
except UnicodeDecodeError:
    warn(f"Skipping non-UTF-8 file: {root_relative_path}")
    skip
except OSError as exc:
    warn(f"Skipping unreadable file: {root_relative_path}: {exc}")
    skip
```

The exact warning format may vary, but it must identify the skipped file.

---

## 16. Examples

## 16.1 Default Capture

```bash
repocat
```

Behavior:

- runs at cwd;
- reads `.repocatignore` from cwd if present;
- respects `.gitignore` files at cwd or below;
- outputs Claude XML-style content to stdout.

## 16.2 Markdown Output

```bash
repocat --markdown
```

Outputs selected files as Markdown fenced code blocks.

## 16.3 Write to File

```bash
repocat -o prompt.xml
```

Writes Claude XML-style output to `prompt.xml`.

`prompt.xml` is excluded from capture even if it already exists and even if `-i '*'` is supplied.

## 16.4 Ignore `.gitignore`

```bash
repocat --ignore-gitignore
```

Does not load or apply `.gitignore` files.

Still applies `.repocatignore`, CLI rules, hard exclusions, symlink policy, and UTF-8 checks.

## 16.5 Force Include a Gitignored File

```gitignore
# .gitignore
tmp/
```

```bash
repocat -i tmp/keep.txt
```

Result:

```text
tmp/keep.txt is captured if it exists and is UTF-8-readable.
Other files under tmp/ remain excluded by .gitignore.
```

## 16.6 Include Everything Traversable

```bash
repocat -i '*'
```

Result:

```text
All traversable UTF-8 files under cwd are captured, except hard exclusions and disallowed symlinks.
```

`.gitignore` has no practical effect on files matched by `*` because the repocat layer decides first.

## 16.7 Exclude After Include

```bash
repocat -i '*' -e secrets.env
```

Result:

```text
All traversable UTF-8 files are captured except secrets.env, hard exclusions, and disallowed symlinks.
```

The later `-e secrets.env` overrides the earlier `-i '*'` inside the repocat layer.

## 16.8 List Files

```bash
repocat --list-files
```

Result:

```text
README.md
pyproject.toml
src/main.py
```

No file contents are printed.

## 16.9 Check Files

```bash
repocat check README.md tmp/cache.db
```

Possible output:

```text
INCLUDED  README.md      default include
EXCLUDED  tmp/cache.db   matched .gitignore: tmp/
```

Exit code is `1` because at least one checked path would not be captured.

---

## 17. Testing Requirements

## 17.1 Core Selection Tests

Tests must cover:

- default include when no rules match;
- `.gitignore` exclusion;
- nested `.gitignore` exclusion;
- nested `.gitignore` negation;
- `.repocatignore` exclusion overriding default include;
- `.repocatignore` include overriding `.gitignore` exclusion;
- CLI include overriding `.gitignore` exclusion;
- CLI exclude overriding earlier CLI include;
- CLI include overriding earlier CLI exclude;
- `.repocatignore` followed by CLI rules, proving CLI rules are appended later;
- `--ignore-gitignore` disabling `.gitignore` behavior;
- `-i '*'` effectively bypassing `.gitignore` for traversable files;
- output file hard exclusion;
- `.git/` hard exclusion.

## 17.2 Traversal Tests

Tests must cover:

- files under a `.gitignore`-ignored directory can still be captured by repocat include;
- `.git/` is not traversed;
- hidden files are included by default unless ignored;
- final output order is lexicographic by root-relative POSIX path;
- `.gitignore` above invocation root is ignored;
- nested `.repocatignore` is ignored.

## 17.3 Encoding Tests

Tests must cover:

- UTF-8 file is captured;
- non-UTF-8 file is skipped with warning;
- unreadable file is skipped with warning where test environment supports permission manipulation;
- `.repocatignore` is read as UTF-8;
- `.gitignore` is read as UTF-8;
- output file is written as UTF-8.

## 17.4 Symlink Tests

Tests must cover:

- directory symlink is not followed;
- broken file symlink is skipped with warning;
- file symlink pointing outside invocation root is skipped with warning;
- file symlink pointing inside invocation root may be captured and rendered under the symlink path.

## 17.5 Renderer Tests

CXML tests:

- default output is CXML-style;
- files appear in sorted order;
- no timestamp appears;
- file contents are inserted raw without XML escaping;
- output file itself is excluded.

Markdown tests:

- fenced code blocks are produced;
- language labels are inferred for common extensions;
- unknown extensions use empty fence language;
- fence length expands when file contents contain triple backticks;
- no timestamp appears.

## 17.6 CLI Tests

Tests must cover:

- `repocat` default behavior;
- `repocat --cxml`;
- `repocat --markdown`;
- mutually exclusive format options;
- `repocat --output prompt.xml`;
- `repocat --list-files`;
- invalid combination of `--list-files` with render/output options;
- `repocat check FILE...`;
- `check` exit code `0` when all files included;
- `check` exit code `1` when any file excluded/missing/not a regular file;
- `check` exit code `2` for usage errors.

---

## 18. User-Facing Behavior Summary

The concise user-facing description should be:

```text
By default, repocat respects `.gitignore`, but `.repocatignore` and command-line `--include` / `--exclude` rules are stronger. If a repocat rule matches a file, that decision wins. `.gitignore` is only consulted for files that no repocat rule matched.
```

Additional explanation:

```text
`--include PATTERN` force-includes matching files, even if `.gitignore` would ignore them.

`--exclude PATTERN` excludes matching files from the prompt.

Rules are order-sensitive. Later repocat rules override earlier repocat rules.

`--ignore-gitignore` disables `.gitignore` entirely.
```

Example:

```bash
repocat -i '*' -e secrets.env
```

Meaning:

```text
Capture all traversable UTF-8 files under the current directory except secrets.env, the output file if one is specified, `.git/`, and disallowed symlinks.
```

---

## 19. Acceptance Criteria

A v1 implementation is complete when:

- `repocat` captures files from cwd and renders default CXML-style output;
- `--markdown` renders Markdown fenced code blocks;
- `--output` writes UTF-8 output to a file and excludes that file from capture;
- `.repocatignore` at cwd is honored;
- CLI `--include` and `--exclude` are repeatable and order-sensitive;
- repocat-layer rules override `.gitignore` rules;
- `.gitignore` files at cwd or lower are honored by default;
- `.gitignore` files above cwd are ignored;
- `--ignore-gitignore` disables `.gitignore` handling;
- hard exclusions are enforced;
- traversal does not allow `.gitignore` pruning to hide repocat-included descendants;
- selected files are read as UTF-8;
- non-UTF-8 or unreadable files are skipped with stderr warnings;
- captured file order is deterministic;
- `--list-files` reports exactly the files that would be captured;
- `check FILE...` reports capture decisions and uses the specified exit codes;
- symlink policy is implemented;
- test coverage exists for the precedence model, traversal behavior, renderers, diagnostics, and CLI validation.

