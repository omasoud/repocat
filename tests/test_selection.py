"""Selection precedence tests."""

from __future__ import annotations

from pathlib import Path

from pathspec import GitIgnoreSpec

from conftest import invoke_repocat, listed_paths, write_text


def test_pathspec_gitignore_include_polarity() -> None:
    spec = GitIgnoreSpec.from_lines(
        [
            "*.log",
            "!keep.log",
        ]
    )

    assert spec.check_file("debug.log").include is True
    assert spec.check_file("keep.log").include is False
    assert spec.check_file("main.py").include is None


def test_default_include_when_no_rules_match(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "README.md")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--list-files"])

    assert result.exit_code == 0
    assert listed_paths(result.stdout) == ["README.md"]


def test_root_and_nested_gitignore_with_nested_negation(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".gitignore", "*.log\n")
    write_text(tmp_path, "debug.log")
    write_text(tmp_path, "src/.gitignore", "*.tmp\n!important.tmp\n")
    write_text(tmp_path, "src/cache.tmp")
    write_text(tmp_path, "src/important.tmp")
    write_text(tmp_path, "src/main.py")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--list-files"])

    assert result.exit_code == 0
    assert listed_paths(result.stdout) == [
        ".gitignore",
        "src/.gitignore",
        "src/important.tmp",
        "src/main.py",
    ]


def test_repocatignore_excludes_and_cli_can_override_it(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".repocatignore", "tmp/\n")
    write_text(tmp_path, "tmp/keep.txt")
    write_text(tmp_path, "tmp/drop.txt")

    excluded = invoke_repocat(runner, monkeypatch, tmp_path, ["--list-files"])
    assert excluded.exit_code == 0
    assert listed_paths(excluded.stdout) == [".repocatignore"]

    included = invoke_repocat(runner, monkeypatch, tmp_path, ["--include", "tmp/keep.txt", "--list-files"])
    assert included.exit_code == 0
    assert listed_paths(included.stdout) == [".repocatignore", "tmp/keep.txt"]


def test_repocat_layer_overrides_gitignore(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".gitignore", "tmp/\n")
    write_text(tmp_path, ".repocatignore", "!tmp/from-repocat.txt\n")
    write_text(tmp_path, "tmp/from-repocat.txt")
    write_text(tmp_path, "tmp/from-cli.txt")
    write_text(tmp_path, "tmp/ignored.txt")

    result = invoke_repocat(
        runner,
        monkeypatch,
        tmp_path,
        ["--include", "tmp/from-cli.txt", "--list-files"],
    )

    assert result.exit_code == 0
    assert listed_paths(result.stdout) == [
        ".gitignore",
        ".repocatignore",
        "tmp/from-cli.txt",
        "tmp/from-repocat.txt",
    ]


def test_cli_later_rules_win(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "tmp/keep.txt")

    include_last = invoke_repocat(
        runner,
        monkeypatch,
        tmp_path,
        ["--exclude", "tmp/", "--include", "tmp/keep.txt", "--list-files"],
    )
    assert include_last.exit_code == 0
    assert listed_paths(include_last.stdout) == ["tmp/keep.txt"]

    exclude_last = invoke_repocat(
        runner,
        monkeypatch,
        tmp_path,
        ["--include", "*", "--exclude", "tmp/keep.txt", "--list-files"],
    )
    assert exclude_last.exit_code == 0
    assert listed_paths(exclude_last.stdout) == []


def test_ignore_gitignore_disables_only_gitignore_layer(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".gitignore", "ignored.txt\n")
    write_text(tmp_path, ".repocatignore", "repocat-ignored.txt\n")
    write_text(tmp_path, "ignored.txt")
    write_text(tmp_path, "repocat-ignored.txt")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--ignore-gitignore", "--list-files"])

    assert result.exit_code == 0
    assert listed_paths(result.stdout) == [".gitignore", ".repocatignore", "ignored.txt"]


def test_broad_include_cannot_override_hard_exclusions(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".git/config", "secret\n")
    write_text(tmp_path, "prompt.xml", "old\n")
    write_text(tmp_path, "src/main.py")

    result = invoke_repocat(
        runner,
        monkeypatch,
        tmp_path,
        ["--include", "*", "--output", "prompt.xml"],
    )

    assert result.exit_code == 0
    output = (tmp_path / "prompt.xml").read_text(encoding="utf-8")
    assert "<source>src/main.py</source>" in output
    assert "<source>.git/config</source>" not in output
    assert "<source>prompt.xml</source>" not in output
