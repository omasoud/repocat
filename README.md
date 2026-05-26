# repocat

`repocat` captures the current repository into prompt-friendly text. It walks the
current working directory, selects UTF-8 files with deterministic ignore rules,
and renders Claude XML-style output by default.

## Install

```bash
uv sync
uv run repocat --list-files
```

The package also exposes the `repocat` console script when installed from this
project.

## Usage

By default, `repocat` writes prompt output to stdout when stdout is redirected
or piped:

```bash
repocat > prompt.xml
repocat | pbcopy
```

When stdout is an interactive terminal, bare `repocat` prints guidance instead
of dumping file contents. To print directly to the terminal anyway:

```bash
repocat --stdout
```

Render Markdown fenced code blocks instead:

```bash
repocat --markdown > prompt.md
```

Write output to a UTF-8 file. The output file is excluded from capture:

```bash
repocat --output prompt.xml
```

List the files that would be captured without rendering contents:

```bash
repocat --list-files
```

Check why specific files would or would not be captured:

```bash
repocat check README.md src/main.py
```

Disable `.gitignore` handling:

```bash
repocat --ignore-gitignore
```

Use repocat-specific include and exclude rules:

```bash
repocat --include "tmp/keep.txt"
repocat --exclude "secrets.env"
repocat --include "*" --exclude "secrets.env"
repocat --exclude "*" --include "tests/**" --gitignore-filter --list-files
```

`--include`, `--exclude`, and `--gitignore-filter` are repeatable and
order-sensitive. Later repocat rules override earlier repocat rules.

## Rule Precedence

By default, repocat respects `.gitignore`, but `.repocatignore` and command-line
rules are evaluated in a higher-precedence repocat layer.

Most repocat rules decide directly:

- `--exclude PATTERN` excludes matching files.
- `--include PATTERN` force-includes matching files, even if `.gitignore` would
  otherwise ignore them.

`--gitignore-filter` is the exception: it applies `.gitignore` as an
exclusion-only filter at that point in the ordered CLI rule sequence. It can
remove ignored files from a previous include, but it never includes files by
itself.

If the ordered repocat layer makes no decision for a file, normal `.gitignore`
handling is applied. If `.gitignore` also makes no decision, the file is
included.

Precedence:

1. Hard exclusions always win.
2. Root `.repocatignore` and ordered CLI rules decide next.
3. `.gitignore` decides only when repocat has no matching rule.
4. Files are included by default.

When `--ignore-gitignore` is set, `--gitignore-filter` has no effect because no
`.gitignore` files are loaded.

Hard exclusions are:

- Any `.git/` directory and all descendants.
- The `--output` file when it is inside the invocation root.

Nested `.repocatignore` files are ignored. Nested `.gitignore` files are honored
by default and scoped to their own directories.

## Text, Symlinks, and Warnings

All configuration files, captured files, and output files use UTF-8. Selected
files that cannot be read as UTF-8, or cannot be read due to an I/O error, are
skipped with warnings on stderr. Warnings are never mixed into stdout prompt
output.

Directory symlinks are not followed. File symlinks are captured only when their
targets resolve to regular files inside the invocation root; the rendered source
path remains the symlink path. Broken file symlinks and external symlink targets
are skipped with stderr warnings.
