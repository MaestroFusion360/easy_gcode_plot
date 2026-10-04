"""Formatting-only edits for source-preserving Full Program exports."""

from __future__ import annotations

import re

from app.gcode.source_mode import SINUMERIK_MODE_SIEMENS, sinumerik_initial_mode

from ..comments import SEMICOLON, format_comment, normalize_comment_style
from .formatting import _ADDRESS_BOUNDARY_RE, _without_sequence_number
from .options import ExportOptions


def is_native_full_program(result):
    return result.source_dialect == "sinumerik" and (
        sinumerik_initial_mode("\n".join(block.raw for block in result.program.blocks)) == SINUMERIK_MODE_SIEMENS
        or any(event.kind == "SINUMERIK_NATIVE_OPERATION" for event in result.events)
    )


def format_full_program_source(
    source: str, options: ExportOptions, *, native: bool = False, uppercase_comments: bool = False
) -> str:
    """Apply formatting-only options to source blocks without rebuilding geometry."""
    source = _apply_full_program_text_options(source, options, native=native)
    has_jump_flow = re.search(r"\bGOTO[FB]?\b", source, flags=re.IGNORECASE) is not None
    has_sequence_labels = re.search(r"(?im)^\s*/?\s*N\d+\b", source) is not None
    if has_jump_flow and (options.sequence_numbers or has_sequence_labels):
        raise ValueError("Sequence numbers cannot be changed in a program that uses GOTO labels")

    output: list[str] = []
    sequence = options.sequence_start
    for raw_line in source.splitlines(keepends=True):
        raw_line = _format_source_comments(raw_line, options, native=native, uppercase_comments=uppercase_comments)
        line_ending = _line_ending(raw_line)
        line = raw_line[: -len(line_ending)] if line_ending else raw_line
        code, comment = _split_full_program_comment(line, native=native)
        if not code.strip():
            output.append(raw_line)
            continue

        comment_separator = " " if comment and code and code[-1].isspace() else ""
        indentation = code[: len(code) - len(code.lstrip())]
        body = code.strip()
        block_skip = ""
        if body.startswith("/"):
            body = body[1:].lstrip()
            block_skip = "/"
        body = _without_sequence_number(body)
        if not body:
            output.append(indentation + block_skip + comment + line_ending)
            continue
        if body.startswith("%") or re.match(r"^O\d+\b", body, flags=re.IGNORECASE):
            output.append(indentation + block_skip + body + comment_separator + comment + line_ending)
            continue

        body = _format_source_addresses(body, options)
        if options.sequence_numbers:
            spacer = " " if options.sequence_spacing or options.delimiter else ""
            body = f"N{sequence}{spacer}{body}"
            sequence += options.sequence_increment
        output.append(indentation + block_skip + body + comment_separator + comment + line_ending)
    return "".join(output)


def _format_source_addresses(body, options):
    fragments = re.split(r'("(?:[^"]|"")*")', body)
    for index in range(0, len(fragments), 2):
        code = _format_leading_zero_addresses(fragments[index], options.leading_zero)
        if options.delimiter:
            code = _ADDRESS_BOUNDARY_RE.sub(" ", code)
        else:
            code = re.sub(r"(?<=[0-9.\]#])\s+(?=[A-Z](?=[+\-]?(?:\d|\.|#|\[)))", "", code, flags=re.IGNORECASE)
        fragments[index] = code
    return "".join(fragments)


def _format_source_comments(line: str, options: ExportOptions, *, native=False, uppercase_comments=False) -> str:
    ending = _line_ending(line)
    body = line[: -len(ending)] if ending else line
    if native:
        code, _comment = _split_full_program_comment(body, native=True)
        return line if options.include_comments else code.rstrip() + ending
    code, separator, tail = body.partition(";")
    comments = []

    def remove(match):
        comments.append(match.group(1))
        return " "

    code = re.sub(r"\(([^()]*)\)", remove, code)
    if separator:
        comments.append(tail.strip())
    if not comments:
        return line
    if not options.include_comments:
        return code.rstrip() + ending
    if uppercase_comments:
        comments = [comment.upper() for comment in comments]
    if normalize_comment_style(options.comment_style) == SEMICOLON:
        comment = format_comment(" | ".join(comments), SEMICOLON)
    else:
        comment = " ".join(
            format_comment(c.replace("(", "[").replace(")", "]"), options.comment_style) for c in comments
        )
    return code.rstrip() + (" " if code.strip() and comment else "") + comment + ending


def _line_ending(line: str) -> str:
    return "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""


def _program_header_index(lines: list[str]) -> int | None:
    return next(
        (
            index
            for index, line in enumerate(lines)
            if re.match(r"^\s*(?:O\d+\b|;?\s*%_N_[A-Z0-9_]+_(?:MPF|SPF)\b)", line, re.IGNORECASE)
        ),
        None,
    )


def _replace_program_header(lines: list[str], header: list[str], newline: str) -> None:
    index = _program_header_index(lines)
    if index is None:
        index = next((i + 1 for i, line in enumerate(lines) if line.strip() == "%"), 0)
        lines[index:index] = [line + newline for line in header]
        return
    ending = _line_ending(lines[index])
    lines[index : index + 1] = [line + (newline if i < len(header) - 1 else ending) for i, line in enumerate(header)]


def _insert_safety_line(lines: list[str], newline: str, *, native=False) -> None:
    mode_index = next(
        (index for index, line in enumerate(lines) if re.match(r"^\s*(?:N\d+\s*)?G\s*291\b", line, re.IGNORECASE)),
        None,
    )
    preceding_header = max((i for i in (mode_index, _program_header_index(lines)) if i is not None), default=-1)
    if preceding_header >= 0 and not _line_ending(lines[preceding_header]):
        lines[preceding_header] += newline
    safety = ["G17 G40 G90"] if native else ["G80", "G0 G17 G40 G49 G90"]
    lines[preceding_header + 1 : preceding_header + 1] = [line + newline for line in safety]


def _replace_program_end(lines: list[str], end: list[str], newline: str) -> None:
    index = next(
        (i for i in range(len(lines) - 1, -1, -1) if re.match(r"^\s*(?:N\d+\s*)?M(?:2|30)\b", lines[i], re.IGNORECASE)),
        None,
    )
    if index is not None:
        ending = _line_ending(lines[index])
        lines[index : index + 1] = [line + (newline if i < len(end) - 1 else ending) for i, line in enumerate(end)]
        return
    index = len(lines) - 1 if lines and lines[-1].strip() == "%" else len(lines)
    if index and not _line_ending(lines[index - 1]):
        lines[index - 1] += newline
    lines[index:index] = [line + newline for line in end]


def _apply_full_program_text_options(source: str, options: ExportOptions, *, native=False) -> str:
    """Apply editable program wrappers to a source-preserving full program."""
    lines = source.splitlines(keepends=True)
    newline = "\r\n" if "\r\n" in source else "\n"
    header = [line for line in options.start_program.strip().splitlines() if line.strip()]
    if header:
        _replace_program_header(lines, header, newline)
    if options.safety_line:
        _insert_safety_line(lines, newline, native=native)
    end = [line for line in options.end_program.strip().splitlines() if line.strip()]
    if end:
        _replace_program_end(lines, end, newline)
    return "".join(lines)


def _split_full_program_comment(line: str, *, native=False) -> tuple[str, str]:
    if native:
        for match in re.finditer(r'"(?:[^"]|"")*"|;', line):
            if match[0] == ";":
                return line[: match.start()], line[match.start() :]
        return line, ""
    for index, character in enumerate(line):
        if character in "(;":
            return line[:index], line[index:]
    return line, ""


def _format_leading_zero_addresses(line: str, enabled: bool) -> str:
    def replace(match: re.Match[str]) -> str:
        letter, integer, fraction = match.groups()
        number = int(integer)
        if enabled and 0 <= number < 10:
            formatted = f"{number:02d}"
        else:
            formatted = str(number)
        return f"{letter}{formatted}{fraction or ''}"

    return re.sub(r"(?<![A-Z0-9_])([GMTHD])(\d+)(\.\d*)?", replace, line, flags=re.IGNORECASE)
