"""Renderer tests."""

from __future__ import annotations

from pathlib import Path

from conftest import invoke_repocat, write_text


def test_cxml_default_sorted_raw_and_without_timestamp(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "b.txt", "<raw>&content\n")
    write_text(tmp_path, "a.txt", "alpha")

    result = invoke_repocat(runner, monkeypatch, tmp_path, [])

    assert result.exit_code == 0
    assert result.stdout.index("<source>a.txt</source>") < result.stdout.index("<source>b.txt</source>")
    assert "<raw>&content" in result.stdout
    assert "&lt;raw&gt;" not in result.stdout
    assert "timestamp" not in result.stdout.lower()


def test_markdown_languages_unknown_extension_and_expanded_fence(runner, monkeypatch, tmp_path: Path) -> None:
    write_text(tmp_path, "script.py", "print('hi')\n")
    write_text(tmp_path, "notes.unknown", "plain\n")
    write_text(tmp_path, "nested.md", "```text\ninside\n```\n")

    result = invoke_repocat(runner, monkeypatch, tmp_path, ["--markdown"])

    assert result.exit_code == 0
    assert "## `script.py`\n\n```python\n" in result.stdout
    assert "## `notes.unknown`\n\n```\n" in result.stdout
    assert "## `nested.md`\n\n````markdown\n```text\ninside\n```\n````" in result.stdout
    assert "timestamp" not in result.stdout.lower()
