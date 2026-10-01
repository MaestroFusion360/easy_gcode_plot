"""Geometry and machine-signal checks shared by GUI and CLI conversions."""

from __future__ import annotations

import re

from app.gcode.comments import strip_comments
from app.gcode.kernel import Diagnostic, ExecutionResult
from app.gcode.program_execution import execute_program

_NATIVE_TRANSFORM_RE = re.compile(r"(?<![A-Z0-9_])(?:TRAORI|TRAFOOF|CYCLE800)(?![A-Z0-9_])", re.IGNORECASE)


def validate_full_program_dialect_conversion(
    source_result: ExecutionResult,
    converted_source: str,
    language: str,
    *,
    source_dialect: str,
    execution_options: dict | None = None,
) -> None:
    if source_dialect == "sinumerik":
        validate_sinumerik_iso_export(source_result)
        validate_sinumerik_iso_source(converted_source)
    options = dict(execution_options or {})
    options["source_dialect"] = source_dialect
    options.setdefault("autodetect_arc_type", True)
    converted_result, _tools, _inferred = execute_program(
        converted_source,
        language=language,
        **options,
    )
    if source_dialect == "sinumerik":
        validate_sinumerik_iso_export(converted_result)
    if not converted_result.ok or not converted_result.complete or converted_result.diagnostics:
        diagnostic = converted_result.diagnostics[0] if converted_result.diagnostics else None
        detail = f": {diagnostic.code}: {diagnostic.message}" if diagnostic else ""
        raise ValueError(f"Full Program dialect conversion failed validation{detail}")
    if _motion_trace_signature(source_result) != _motion_trace_signature(converted_result):
        raise ValueError("Full Program dialect conversion changes resolved motion geometry")
    if _machine_signal_signature(source_result) != _machine_signal_signature(converted_result):
        raise ValueError("Full Program dialect conversion changes machine signals")


def _machine_signal_signature(result: ExecutionResult) -> tuple:
    return tuple((signal.kind, signal.code, signal.value) for signal in result.signals)


def _motion_trace_signature(result: ExecutionResult) -> tuple:
    return tuple(
        (
            motion.move,
            motion.plane,
            *(
                round(value, 8)
                for value in (
                    motion.start_x,
                    motion.start_y,
                    motion.start_z,
                    motion.end_x,
                    motion.end_y,
                    motion.end_z,
                    motion.i or 0.0,
                    motion.j or 0.0,
                    motion.k or 0.0,
                    motion.feed or 0.0,
                )
            ),
            None
            if motion.arc is None
            else (
                *(round(value, 8) for value in motion.arc.center),
                round(motion.arc.radius, 8),
                round(motion.arc.sweep, 8),
            ),
        )
        for motion in result.motions
    )


def sinumerik_iso_export_diagnostic(result: ExecutionResult) -> Diagnostic | None:
    """Reject unverified rotary/TCP conversion using authoritative kernel facts.

    Selected multi-axis profiles and executed rotary/TCP state are unsupported.
    Use the existing kernel profile/axis facts, including rejected blocks.
    No rotary or native Siemens command equivalences are implemented here.
    """
    words = tuple(word for step in result.execution_steps for word in step.words)
    used_rotary = {letter for letter, _value in words if letter in {"A", "B", "C"}}
    tcp_or_twp = any(letter == "G" and value in {43.4, 68.2, 53.1} for letter, value in words) or any(
        event.kind in {"TCP_CONTROL_ON", "TILTED_WORK_PLANE_ON", "TOOL_AXIS_ORIENT"} for event in result.events
    )
    tcp_or_twp = tcp_or_twp or any(diagnostic.code == "TWP_KINEMATICS_REQUIRED" for diagnostic in result.diagnostics)
    if result.program is not None:
        tcp_or_twp = tcp_or_twp or any(
            _NATIVE_TRANSFORM_RE.search(strip_comments(block.raw)) for block in result.program.blocks
        )
    rotary_events = any(event.kind in {"ROTARY_INDEX", "ROTARY_MOTION"} for event in result.events)
    if tcp_or_twp or len(result.rotary_axes) > 1 or len(used_rotary) > 1:
        return Diagnostic(
            "UNSUPPORTED_SINUMERIK_ISO_5AX_EXPORT",
            "SINUMERIK ISO export for 5-axis / TCP programs is not supported yet",
            "error",
            "unsupported",
        )
    if result.rotary_axes or used_rotary or rotary_events:
        return Diagnostic(
            "UNSUPPORTED_SINUMERIK_ISO_4AX_EXPORT",
            "SINUMERIK ISO export for 4-axis programs is not supported yet",
            "error",
            "unsupported",
        )
    return None


def validate_sinumerik_iso_export(result: ExecutionResult) -> None:
    """Fail before generating NC when ISO equivalence is not implemented."""
    diagnostic = sinumerik_iso_export_diagnostic(result)
    if diagnostic is not None:
        raise ValueError(diagnostic.message)


def validate_sinumerik_iso_source(source: str) -> None:
    """Reject explicitly programmed native transforms, never infer or emit them.

    The ISO-M kernel does not execute these commands; a FANUC surrogate cannot
    establish their equivalence. Comments are not executable commands.
    """
    if any(_NATIVE_TRANSFORM_RE.search(strip_comments(line)) for line in source.splitlines()):
        raise ValueError("SINUMERIK ISO export for 5-axis / TCP programs is not supported yet")
