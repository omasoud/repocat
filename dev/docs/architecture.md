# repocat Architecture Notes

The v1 implementation follows the component layout from the implementation
specification:

- `repocat.models` defines CLI, selection, candidate, captured-file, and
  diagnostic data structures.
- `repocat.paths` owns root-relative POSIX normalization, output path
  resolution, containment checks, and gitignore-relative path conversion.
- `repocat.selection` loads `.repocatignore`, caches `.gitignore` files, and
  evaluates hard exclusions, ordered repocat actions, and gitignore rules in
  precedence order.
- `repocat.traversal` walks the invocation root, prunes any directory named
  `.git`, maintains active nested `.gitignore` specs, and applies symlink
  traversal policy.
- `repocat.reading` reads selected files as UTF-8 and emits skip warnings.
- `repocat.rendering` renders Claude XML-style output and Markdown output.
- `repocat.diagnostics` implements `--list-files` membership reuse and
  `check FILE...` result formatting.
- `repocat.cli` provides the Typer entrypoint and validation.

The CLI uses a single Typer command with manual dispatch for the `check` command
token. This keeps the public syntax as `repocat check FILE...` while preserving
the exact argv order of repeated `--include`, `--exclude`, and
`--gitignore-filter` options before building the repocat rule layer.

The repocat layer is represented as ordered actions. `.repocatignore` is compiled
as the first pattern chunk, contiguous CLI include/exclude rules are compiled as
additional chunks, and `-g` / `--gitignore-filter` inserts an exclusion-only
gitignore filter action between those chunks.

Hard exclusion policy treats every directory named `.git` under the invocation
root as non-capturable, including nested repositories such as
`vendor/project/.git/`.
