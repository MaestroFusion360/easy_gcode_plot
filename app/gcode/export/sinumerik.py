"""Source-preserving SINUMERIK ISO-M and FANUC milling dialect conversion."""

from __future__ import annotations

import re

from app.gcode.kernel import ExecutionResult
from app.gcode.program_execution import execute_program
from app.gcode.source_mode import SINUMERIK_MODE_SIEMENS, sinumerik_initial_mode

from .native_full import normalize_native_full_program
from .options import ExportOptions
from .source_formatting import format_full_program_source
from .validation import (
    validate_full_program_dialect_conversion,
    validate_native_to_fanuc_export,
    validate_sinumerik_iso_export,
    validate_sinumerik_iso_source,
)

_G291_BLOCK_RE = re.compile(r"^\s*(?:N\d+\s*)?G\s*291(?:\s*;.*)?\s*$", re.IGNORECASE)
_PROGRAM_NUMBER_RE = re.compile(r"^(\s*)(O\d+)(?=\s|\(|;|$)", re.IGNORECASE)


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
    lines = [_PROGRAM_NUMBER_RE.sub(r"\1(\2)", line, count=1) for line in lines if line.strip() != "%"]
    newline = "\r\n" if "\r\n" in source else "\n"
    if has_iso_mode:
        mode_index = next(index for index, line in enumerate(lines) if _is_g291_block(line))
        mode_line = lines.pop(mode_index).rstrip("\r\n") + newline
    else:
        mode_line = f"G291{newline}"
    lines.insert(_full_program_mode_insertion(lines), mode_line)
    converted = "".join(lines)
    validate_full_program_dialect_conversion(
        source_result,
        converted,
        "fanuc_mill",
        source_dialect="sinumerik",
        execution_options=execution_options,
    )
    return converted


def convert_full_program_to_fanuc(
    source: str, *, source_result=None, execution_options=None, export_options=None
) -> str:
    """Normalize native semantics before emission; retain ISO-M source structure."""
    if source_result is None:
        options = {**(execution_options or {}), "source_dialect": "sinumerik"}
        source_result, _tools, _inferred = execute_program(source, language="fanuc_mill", **options)
    if (
        not source_result.ok
        or not source_result.complete
        or any(d.severity == "error" for d in source_result.diagnostics)
    ):
        raise ValueError("Full Program dialect conversion requires successful complete source execution")
    validate_native_to_fanuc_export(source_result)
    has_native = sinumerik_initial_mode(source) == SINUMERIK_MODE_SIEMENS or any(
        event.kind == "SINUMERIK_SIEMENS_MODE" for event in source_result.events
    )
    if has_native:
        converted = normalize_native_full_program(source, source_result)
        header = re.search(r"(?im)^\s*;?\s*%_N_(\d+)_MPF\s*$", source)
        if header:
            converted = re.sub(r"(?im)^\s*;?\s*%_N_\d+_MPF\s*$", "", converted)
            converted = f"%\nO{int(header[1])}\n" + converted.strip("\r\n") + "\n%\n"
        converted = format_full_program_source(
            converted, export_options or ExportOptions(delimiter=True), uppercase_comments=True
        )
    else:
        lines = source.splitlines(keepends=True)
        converted = "".join(line for line in lines if not _is_g291_block(line))
        if export_options is not None:
            converted = format_full_program_source(converted, export_options, uppercase_comments=True)
    validate_full_program_dialect_conversion(
        source_result,
        converted,
        "fanuc_mill",
        source_dialect="fanuc",
        execution_options=execution_options,
    )
    return converted


def _is_g291_block(line: str) -> bool:
    return _G291_BLOCK_RE.fullmatch(line.rstrip("\r\n")) is not None


def _full_program_mode_insertion(_lines: list[str]) -> int:
    """Activate ISO before any header, blank line or ISO-style comment."""
    return 0
