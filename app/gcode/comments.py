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
    """Extract comments without mistaking SINUMERIK AC(...) expressions for comments.

    A ``;`` that appears inside a parenthesized comment is part of that comment,
    not a second semicolon comment, so it must not be extracted twice.
    """
    comments: list[str] = []
    depth = 0
    body_start = -1
    skip_body = False
    for index, character in enumerate(str(line)):
        if character == "(":
            if depth == 0:
                skip_body = line[:index].rstrip().upper().endswith("AC")
                body_start = index + 1
            depth += 1
        elif character == ")" and depth:
            depth -= 1
            if depth == 0 and not skip_body:
                body = line[body_start:index].strip()
                if body:
                    comments.append(body)
        elif character == ";" and depth == 0:
            comment = line[index + 1 :].strip()
            if comment:
                comments.append(comment)
            break
    return comments
