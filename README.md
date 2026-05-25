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

Capture the current directory as Claude XML-style prompt markup:

```bash
repocat
```

Render Markdown fenced code blocks instead:

```bash
repocat --markdown
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
```

`--include` and `--exclude` are repeatable and order-sensitive. Later repocat
rules override earlier repocat rules.

## Rule Precedence

By default, repocat respects `.gitignore`, but `.repocatignore` and command-line
`--include` / `--exclude` rules are stronger. If a repocat rule matches a file,
that decision wins. `.gitignore` is only consulted for files that no repocat rule
matched.

Precedence:

1. Hard exclusions always win.
2. Root `.repocatignore` and CLI rules decide next.
3. `.gitignore` decides only when repocat has no matching rule.
4. Files are included by default.

Hard exclusions are:

- `.git/` and all descendants.
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
