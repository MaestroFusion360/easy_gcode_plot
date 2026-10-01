"""Source-preserving SINUMERIK ISO-M and FANUC milling dialect conversion."""

from __future__ import annotations

import re

from app.gcode.kernel import ExecutionResult
from app.gcode.program_execution import execute_program

from .validation import (
    validate_full_program_dialect_conversion,
    validate_sinumerik_iso_export,
    validate_sinumerik_iso_source,
)

_G291_BLOCK_RE = re.compile(r"^\s*(?:N\d+\s*)?G\s*291(?:\s*;.*)?\s*$", re.IGNORECASE)


def convert_full_program_to_sinumerik(
    source: str,
    *,
    source_result: ExecutionResult | None = None,
    execution_options: dict | None = None,
) -> str:
    """Convert only the verified ISO-M subset; never synthesize Siemens commands."""
    validate_sinumerik_iso_source(source)
    lines = source.splitlines(keepends=True)
    has_iso_mode = any(_is_g291_block(line) for line in lines)
    if source_result is None:
        options = dict(execution_options or {})
        options.setdefault("autodetect_arc_type", True)
        options["source_dialect"] = "sinumerik" if has_iso_mode else "fanuc"
        source_result, _tools, _inferred = execute_program(source, language="fanuc_mill", **options)
    validate_sinumerik_iso_export(source_result)
    if not source_result.ok or not source_result.complete:
        raise ValueError("Full Program dialect conversion requires successful complete source execution")
    if not has_iso_mode:
        newline = "\r\n" if "\r\n" in source else "\n"
        lines.insert(_full_program_mode_insertion(lines), f"G291{newline}")
    converted = "".join(lines)
    validate_full_program_dialect_conversion(
        source_result,
        converted,
        "fanuc_mill",
        source_dialect="sinumerik",
        execution_options=execution_options,
    )
    return converted


def convert_full_program_to_fanuc(source: str) -> str:
    """Remove the standalone SINUMERIK ISO-mode block, preserving other text."""
    lines = source.splitlines(keepends=True)
    return "".join(line for line in lines if not _is_g291_block(line))


def _is_g291_block(line: str) -> bool:
    return _G291_BLOCK_RE.fullmatch(line.rstrip("\r\n")) is not None


def _full_program_mode_insertion(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        code = line.strip()
        if not code or code.startswith(("%", ";", "(")):
            continue
        return index
    return len(lines)
