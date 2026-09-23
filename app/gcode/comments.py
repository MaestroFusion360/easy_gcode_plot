"""Shared G-code comment syntax policy."""

from __future__ import annotations

import re

PARENTHESES = "parentheses"
SEMICOLON = "semicolon"
DEFAULT_COMMENT_STYLE = PARENTHESES
COMMENT_STYLES = (PARENTHESES, SEMICOLON)


def normalize_comment_style(value: object) -> str:
    """Return a supported persisted comment style."""
    style = str(value or "").strip().lower()
    return style if style in COMMENT_STYLES else DEFAULT_COMMENT_STYLE


def comment_markers(style: object = DEFAULT_COMMENT_STYLE) -> tuple[str, str]:
    """Return the opening and closing text for *style*."""
    return (";", "") if normalize_comment_style(style) == SEMICOLON else ("(", ")")


def format_comment(text: object, style: object = DEFAULT_COMMENT_STYLE) -> str:
    """Format one comment using the selected project-wide syntax."""
    body = str(text).strip()
    if not body:
        return ""
    start, end = comment_markers(style)
    return f"{start}{body}{end}"


def strip_comments(line: str, style: object | None = None) -> str:
    """Remove comments from a source line.

    With no explicit style both common CNC syntaxes are accepted for backwards
    compatibility by the parser. UI consumers pass the configured style.
    """
    selected = normalize_comment_style(style) if style is not None else None
    out = line
    if selected in (None, PARENTHESES):
        out = re.sub(r"\([^()]*\)", "", out)
    if selected in (None, SEMICOLON):
        out = out.split(";", 1)[0]
    return out.strip()


def extract_comments(line: str) -> list[str]:
    """Extract comments from either supported input syntax."""
    comments = [match.group(1).strip() for match in re.finditer(r"\((.*?)\)", line) if match.group(1).strip()]
    _code, separator, comment = line.partition(";")
    if separator and comment.strip():
        comments.append(comment.strip())
    return comments
