"""List and check diagnostics tests."""

from __future__ import annotations

from pathlib import Path

from conftest import invoke_repocat, listed_paths, write_bytes, write_text


def test_list_files_matches_render_membership_and_order(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".gitignore", "ignored.txt\n")
    write_text(tmp_path, "b.txt")
    write_text(tmp_path, "a.txt")
    write_text(tmp_path, "ignored.txt")

    listed = invoke_repocat(runner, monkeypatch, tmp_path, ["--list-files"])
    rendered = invoke_repocat(runner, monkeypatch, tmp_path, [])

    assert listed.exit_code == 0
    assert listed_paths(listed.stdout) == [".gitignore", "a.txt", "b.txt"]
    assert rendered.stdout.index("<source>.gitignore</source>") < rendered.stdout.index("<source>a.txt</source>")
    assert rendered.stdout.index("<source>a.txt</source>") < rendered.stdout.index("<source>b.txt</source>")
    assert "<source>ignored.txt</source>" not in rendered.stdout


def test_check_reports_categories_reasons_and_exit_codes(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".gitignore", "ignored.txt\n")
    write_text(tmp_path, "included.txt")
    write_text(tmp_path, "ignored.txt")
    write_text(tmp_path, "dir/file.txt")
    write_bytes(tmp_path, "bad.bin", b"\xff")

    included = invoke_repocat(runner, monkeypatch, tmp_path, ["check", "included.txt"])
    assert included.exit_code == 0
    assert "INCLUDED  included.txt  default include" in included.stdout

    mixed = invoke_repocat(
        runner,
        monkeypatch,
        tmp_path,
        ["check", "ignored.txt", "missing.txt", "dir", "bad.bin"],
    )
    assert mixed.exit_code == 1
    assert "EXCLUDED  ignored.txt  matched .gitignore: ignored.txt" in mixed.stdout
    assert "NOT_FOUND  missing.txt  not found" in mixed.stdout
    assert "NOT_A_FILE  dir  not a regular file" in mixed.stdout
    assert "EXCLUDED  bad.bin  non-utf-8 or unreadable" in mixed.stdout


def test_check_repocat_include_overrides_gitignore(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".gitignore", "tmp/\n")
    write_text(tmp_path, "tmp/keep.txt")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["check", "--include", "tmp/keep.txt", "tmp/keep.txt"])

    assert result.exit_code == 0
    assert "INCLUDED  tmp/keep.txt  matched repocat include: !tmp/keep.txt" in result.stdout


def test_blank_lines_do_not_shift_repocat_diagnostic_pattern(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".repocatignore", "\n\nsecret.txt\n")
    write_text(tmp_path, "secret.txt")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["check", "secret.txt"])

    assert result.exit_code == 1
    assert "matched repocat exclude: secret.txt" in result.stdout


def test_blank_lines_do_not_shift_gitignore_diagnostic_pattern(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".gitignore", "\n\nignored.txt\n")
    write_text(tmp_path, "ignored.txt")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["check", "ignored.txt"])

    assert result.exit_code == 1
    assert "matched .gitignore: ignored.txt" in result.stdout


def test_comment_lines_do_not_shift_gitignore_diagnostic_pattern(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".gitignore", "# comment\nignored.txt\n")
    write_text(tmp_path, "ignored.txt")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["check", "ignored.txt"])

    assert result.exit_code == 1
    assert "matched .gitignore: ignored.txt" in result.stdout


def test_check_reports_gitignore_filter_exclusion(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, ".gitignore", "tests/ignored.txt\n")
    write_text(tmp_path, "tests/ignored.txt")

    result = invoke_repocat(
        runner,
        monkeypatch,
        tmp_path,
        ["check", "-e", "*", "-i", "tests/**", "-g", "tests/ignored.txt"],
    )

    assert result.exit_code == 1
    assert "EXCLUDED  tests/ignored.txt  matched gitignore filter: tests/ignored.txt" in result.stdout


def test_check_absolute_path_outside_root_is_excluded(runner, monkeypatch, tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    try:
        result = invoke_repocat(runner, monkeypatch, tmp_path, ["check", str(outside)])
    finally:
        outside.unlink(missing_ok=True)

    assert result.exit_code == 1
    assert "outside invocation root" in result.stdout
