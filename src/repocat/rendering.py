"""Prompt output renderers."""

from __future__ import annotations

import re
from pathlib import Path

from repocat.models import CapturedFile

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
    ".sh": "bash",
    ".ps1": "powershell",
    ".sql": "sql",
    ".java": "java",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".rs": "rust",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
}


def render_cxml(files: list[CapturedFile]) -> str:
    """Render captured files in Claude XML-style prompt markup."""
    parts = ["<documents>\n"]
    for index, captured in enumerate(files, start=1):
        parts.append(f'<document index="{index}">\n')
        parts.append(f"<source>{captured.root_relative_path}</source>\n")
        parts.append("<document_content>\n")
        parts.append(captured.content)
        if not captured.content.endswith("\n"):
            parts.append("\n")
        parts.append("</document_content>\n")
        parts.append("</document>\n\n")
    parts.append("</documents>\n")
    return "".join(parts)


def render_markdown(files: list[CapturedFile]) -> str:
    """Render captured files as Markdown fenced code blocks."""
    parts: list[str] = []
    for captured in files:
        fence = markdown_fence(captured.content)
        language = infer_markdown_language(captured.root_relative_path)
        parts.append(f"## `{captured.root_relative_path}`\n\n")
        parts.append(f"{fence}{language}\n")
        parts.append(captured.content)
        if not captured.content.endswith("\n"):
            parts.append("\n")
        parts.append(f"{fence}\n\n")
    return "".join(parts)


def infer_markdown_language(root_relative_path: str) -> str:
    """Infer a Markdown fence language from a file extension."""
    return LANGUAGE_BY_SUFFIX.get(Path(root_relative_path).suffix.lower(), "")


def markdown_fence(content: str) -> str:
    """Return a fence longer than any contiguous backtick run in content."""
    longest = 0
    for match in re.finditer(r"`+", content):
        longest = max(longest, len(match.group(0)))
    return "`" * max(3, longest + 1)
