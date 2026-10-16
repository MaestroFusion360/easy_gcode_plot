"""Small public facade for the native FANUC CNC kernel."""

from __future__ import annotations

from dataclasses import replace

from ..geometry.coordinates import WcsOffset, WcsOffsets
from ..runtime.diagnostics import (
    SUPPORTED_TURNING_G_CODES as SUPPORTED_G_CODES,
)
from ..runtime.diagnostics import (
    diagnostic_from_exception as _diagnostic_from_exception,
)
from ..runtime.events import program_end_code
from ..runtime.trace_metadata import threading_step_flags as _threading_step_flags
from ..turning.dialect import validate_system
from .arc_source import _effective_arc_type, _invalid_turning_profile_cycles
from .execution_request import SUPPORTED_LANGUAGES, SUPPORTED_SOURCE_DIALECTS, _execute_impl
from .resources import ExecutionBudget, ExecutionLimits, active_budget
from .trace_geometry import (
    ResolvedTrace,
    _motion_with_step_metadata,
    _partial_steps_after_geometry_failure,
    _resolve_geometry_motion,
    _resolve_milling_compensation,
    _steps_with_emitted_counts,
)
from .types import Diagnostic, ExecutionResult, SemanticInstruction, TraceMotion

__all__ = [
    "Diagnostic",
    "ExecutionResult",
    "SUPPORTED_G_CODES",
    "SUPPORTED_LANGUAGES",
    "SemanticInstruction",
    "TraceMotion",
    "WcsOffset",
    "WcsOffsets",
    "execute",
    "SUPPORTED_SOURCE_DIALECTS",
]


def _capture_tool_resolver(resolver, resolved_tools):
    if resolver is None:
        return None

    def resolve(program):
        tools = resolver(program)
        resolved_tools["milling_tools"] = tools
        return tools

    return resolve


def _execution_arc_tolerance(value, language):
    if value is not None:
        return value
    return 0.01 if language == "fanuc_mill" else 0.001


def execute(
    source,
    language="fanuc_turn",
    *,
    limits=None,
    cancelled=None,
    source_arc_type=1,
    autodetect_arc_type=False,
    arc_tolerance=None,
    **options,
):
    """Execute once; resolve geometry and publish a self-contained immutable result.

    An optional tool_resolver receives the parsed Program once, before motion
    execution, and returns the tool geometry used by execution/compensation.
    Parsing and tool preparation share execution cancellation checkpoints.
    """
    arc_tolerance = _execution_arc_tolerance(arc_tolerance, language)
    token = active_budget.set(ExecutionBudget(limits or ExecutionLimits(), cancelled))
    resolved_tools = {"milling_tools": options.pop("milling_tools", None)}
    milling_correction_enabled = bool(options.pop("milling_correction_enabled", True))
    options["tool_resolver"] = _capture_tool_resolver(options.pop("tool_resolver", None), resolved_tools)
    try:
        result = _execute_impl(source, language, geometry_tolerance=arc_tolerance, **options)
        result = replace(
            result,
            source_dialect=options.get("source_dialect", "fanuc"),
            lathe_gcode_system=validate_system(options.get("lathe_gcode_system", "A")),
            sinumerik_840d_sl=options.get("sinumerik_840d_sl", True),
        )
        effective_arc_type = _effective_arc_type(result, language, autodetect_arc_type, arc_tolerance, source_arc_type)
        trace = ResolvedTrace()
        motions, motion_step_owners = trace.motions, trace.owners
        geometry_diagnostics, cursor = [], 0
        invalid_cycles = (
            _invalid_turning_profile_cycles(
                result, effective_arc_type, arc_tolerance, options.get("lathe_gcode_system", "A")
            )
            if language == "fanuc_turn"
            else {}
        )
        geometry_diagnostics.extend(invalid_cycles.values())
        step_index = 0
        try:
            threading_steps = (
                _threading_step_flags(result.execution_steps)
                if language == "fanuc_turn" and result.source_dialect != "sinumerik"
                else (False,) * len(result.execution_steps)
            )
            for step_index, step in enumerate(result.execution_steps):
                if step_index in invalid_cycles:
                    cursor += step.emitted_count
                    continue
                for motion in result.motions[cursor : cursor + step.emitted_count]:
                    threading = threading_steps[step_index] and motion.move == 1
                    motion = _motion_with_step_metadata(motion, step, language, threading)
                    resolved, diagnostic = _resolve_geometry_motion(
                        motion, result.program, language, effective_arc_type, arc_tolerance
                    )
                    if diagnostic is not None:
                        geometry_diagnostics.append(diagnostic)
                        continue
                    trace.append(resolved, step_index)
                cursor += step.emitted_count
        except Exception as exc:
            diagnostic = _diagnostic_from_exception(exc, result.program)
            partial_steps = _partial_steps_after_geometry_failure(
                result.execution_steps, motion_step_owners, step_index
            )
            partial_events = tuple(event for step in partial_steps for event in step.events)
            partial_signals = tuple(signal for step in partial_steps for signal in step.signals)
            return replace(
                result,
                ok=False,
                motions=tuple(motions),
                diagnostics=result.diagnostics + (diagnostic,),
                executed_blocks=tuple(step.source_block for step in partial_steps),
                execution_steps=tuple(partial_steps),
                signals=partial_signals,
                program_end=program_end_code(partial_events),
                events=partial_events,
                complete=False,
                language=language,
            )
        if not result.execution_steps:
            motions = list(result.motions)
        if result.execution_steps:
            emitted_counts = trace.emitted_counts(result.execution_steps)
            result = replace(
                result,
                execution_steps=_steps_with_emitted_counts(result.execution_steps, emitted_counts),
            )
        diagnostics = result.diagnostics + tuple(geometry_diagnostics)
        if language == "fanuc_mill" and milling_correction_enabled:
            result, motions, compensation_diagnostics = _resolve_milling_compensation(
                result, motions, motion_step_owners, resolved_tools["milling_tools"], options.get("kinematics")
            )
            diagnostics += compensation_diagnostics
        return replace(
            result,
            motions=tuple(motions),
            diagnostics=diagnostics,
            ok=result.ok and not any(item.severity == "error" for item in geometry_diagnostics),
            complete=result.complete,
            language=language,
            executed_blocks=tuple(step.source_block for step in result.execution_steps),
        )
    except Exception as exc:
        diagnostic = _diagnostic_from_exception(exc, None)
        return ExecutionResult(
            False,
            None,
            (),
            (),
            (diagnostic,),
            (),
            complete=False,
            language=language,
            source_dialect=options.get("source_dialect", "fanuc"),
        )
    finally:
        active_budget.reset(token)
