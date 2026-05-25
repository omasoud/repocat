"""Traversal, symlink, and UTF-8 behavior tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from conftest import (
    can_make_unreadable,
    invoke_repocat,
    listed_paths,
    make_symlink,
    write_bytes,
    write_text,
)


def test_gitignored_directory_is_still_traversed_for_repocat_include(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".gitignore", "tmp/\n")
    write_text(tmp_path, "tmp/keep.txt")
    write_text(tmp_path, "tmp/drop.txt")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--include", "tmp/keep.txt", "--list-files"])

    assert result.exit_code == 0
    assert listed_paths(result.stdout) == [".gitignore", "tmp/keep.txt"]


def test_hidden_files_parent_gitignore_and_nested_repocatignore(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".gitignore", "parent-ignored.txt\n")
    child = tmp_path / "child"
    write_text(child, ".hidden", "hidden\n")
    write_text(child, "nested/.repocatignore", "ignored-by-nested.txt\n")
    write_text(child, "nested/ignored-by-nested.txt")
    write_text(child, "parent-ignored.txt")
    write_text(child, "regular.txt")

    result = invoke_repocat(runner, monkeypatch, child, ["--list-files"])

    assert result.exit_code == 0
    assert listed_paths(result.stdout) == [
        ".hidden",
        "nested/.repocatignore",
        "nested/ignored-by-nested.txt",
        "parent-ignored.txt",
        "regular.txt",
    ]


def test_deterministic_sorted_output_order(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "z.txt")
    write_text(tmp_path, "a/b.txt")
    write_text(tmp_path, "a/a.txt")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--list-files"])

    assert result.exit_code == 0
    assert listed_paths(result.stdout) == ["a/a.txt", "a/b.txt", "z.txt"]


def test_non_utf8_file_is_skipped_with_stderr_warning(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "ok.txt", "ok\n")
    write_bytes(tmp_path, "bad.bin", b"\xff\xfe\x00")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--include", "*", "--list-files"])

    assert result.exit_code == 0
    assert listed_paths(result.stdout) == ["ok.txt"]
    assert "skipping non-UTF-8 file: bad.bin" in result.output


def test_unreadable_file_is_skipped_where_supported(runner, monkeypatch, tmp_path: Path) -> None:
    if not can_make_unreadable():
        pytest.skip("chmod unreadable files are not reliable on this platform")

    write_text(tmp_path, "ok.txt")
    unreadable = write_text(tmp_path, "locked.txt")
    unreadable.chmod(0)
    try:
        result = invoke_repocat(runner, monkeypatch, tmp_path, ["--include", "*", "--list-files"])
    finally:
        unreadable.chmod(0o600)

    assert result.exit_code == 0
    assert listed_paths(result.stdout) == ["ok.txt"]
    assert "skipping unreadable file: locked.txt" in result.output


def test_symlink_policy_cases(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "target.txt", "target contents\n")
    make_symlink(tmp_path / "inside-link.txt", tmp_path / "target.txt")

    external = tmp_path.parent / f"{tmp_path.name}-external.txt"
    external.write_text("external\n", encoding="utf-8")
    make_symlink(tmp_path / "external-link.txt", external)

    make_symlink(tmp_path / "broken-link.txt", tmp_path / "missing.txt")

    real_dir = tmp_path / "real-dir"
    real_dir.mkdir()
    write_text(real_dir, "nested.txt")
    make_symlink(tmp_path / "dir-link", real_dir, directory=True)

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--include", "*", "--list-files"])

    assert result.exit_code == 0
    assert listed_paths(result.stdout) == ["inside-link.txt", "real-dir/nested.txt", "target.txt"]
    assert "broken symlink: broken-link.txt" in result.output
    assert "external target: external-link.txt" in result.output
    assert "dir-link/nested.txt" not in result.stdout

    rendered = invoke_repocat(runner, monkeypatch, tmp_path, ["--include", "inside-link.txt"])
    assert '<source>inside-link.txt</source>' in rendered.stdout
    assert "target contents" in rendered.stdout

    try:
        external.unlink()
    except OSError:
        pass


def test_git_directory_is_not_traversed(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".git/config", "secret\n")
    write_text(tmp_path, "vendor/project/.git/config", "nested secret\n")
    write_text(tmp_path, "visible.txt")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--include", "*", "--list-files"])

    assert result.exit_code == 0
    assert listed_paths(result.stdout) == ["visible.txt"]
    assert os.name


def test_malformed_gitignore_reports_clean_error(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".gitignore", "\\\n")
    write_text(tmp_path, "visible.txt")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--list-files"])

    assert result.exit_code == 1
    assert "Invalid ignore pattern in" in result.output


def test_non_utf8_repocatignore_is_fatal(runner, monkeypatch, tmp_path: Path) -> None:
    write_bytes(tmp_path, ".repocatignore", b"\xff")
    write_text(tmp_path, "visible.txt")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--list-files"])

    assert result.exit_code == 1
    assert ".repocatignore must be valid UTF-8" in result.output
