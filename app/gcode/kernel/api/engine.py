"""Small public facade for the native FANUC CNC kernel."""

from __future__ import annotations

import gc
import math
from dataclasses import replace

from ..compensation.milling import apply_milling_cutter_compensation_with_owners
from ..frontend.model import Motion, Point2, Program
from ..frontend.program import parse_program, try_wcs_from_gcode, x_delta_to_diameter, x_value_to_diameter
from ..geometry import resolve_arc
from ..geometry.coordinates import WcsOffset, WcsOffsets  # noqa: F401 - compatibility re-export
from ..geometry.coordinates import milling_extended_wcs_offsets as _mill_extended_wcs_offsets
from ..geometry.coordinates import milling_wcs_offsets as _mill_wcs_offsets
from ..geometry.coordinates import published_extended_wcs_offsets as _result_extended_wcs_offsets
from ..geometry.coordinates import published_wcs_offsets as _result_wcs_offsets
from ..geometry.coordinates import turning_extended_wcs_offsets as _turn_extended_wcs_offsets
from ..geometry.coordinates import turning_wcs_offsets as _turn_wcs_offsets
from ..milling import execute_milling
from ..runtime.diagnostics import SUPPORTED_TURNING_G_CODES as SUPPORTED_G_CODES  # noqa: F401
from ..runtime.diagnostics import (
    diagnostic_from_exception as _diagnostic_from_exception,
)
from ..runtime.diagnostics import (
    fractional_code_diagnostics as _fractional_code_diagnostics,
)
from ..runtime.diagnostics import (
    unsupported_turning_g_diagnostics as _unsupported_g_diagnostics,
)
from ..runtime.events import program_end_code
from ..runtime.execution import semantic_instructions as _semantic_instructions
from ..runtime.trace import build_source_motion_trace_with_steps as _build_source_motion_trace_with_steps
from ..runtime.trace_metadata import threading_step_flags as _threading_step_flags
from .conversion import trace_motion as _trace_motion
from .resources import ExecutionBudget, ExecutionLimits, SemanticError, active_budget
from .types import (
    Diagnostic,
    ExecutionResult,
    SemanticInstruction,  # noqa: F401 - compatibility re-export
    TraceMotion,  # noqa: F401 - compatibility re-export
)

__all__ = (
    "Diagnostic",
    "ExecutionResult",
    "SUPPORTED_G_CODES",
    "SUPPORTED_LANGUAGES",
    "SemanticInstruction",
    "TraceMotion",
    "WcsOffset",
    "WcsOffsets",
    "execute",
)

SUPPORTED_LANGUAGES = frozenset({"fanuc_turn", "fanuc_mill"})


def _ijk_radius_mismatch(motion: TraceMotion, source_arc_type: int) -> float | None:
    axes = {17: (0, 1), 18: (0, 2), 19: (1, 2)}
    plane_axes = axes.get(motion.plane)
    if motion.move not in (2, 3) or plane_axes is None:
        return None
    start = (motion.start_x * motion.x_scale, motion.start_y, motion.start_z)
    end = (motion.end_x * motion.x_scale, motion.end_y, motion.end_z)
    offsets = (None if motion.i is None else motion.i * motion.x_scale, motion.j, motion.k)
    first_axis, second_axis = plane_axes
    if offsets[first_axis] is None and offsets[second_axis] is None:
        return None
    center_first = offsets[first_axis] or 0.0
    center_second = offsets[second_axis] or 0.0
    if source_arc_type == 1:
        center_first += start[first_axis]
        center_second += start[second_axis]
    start_radius = math.hypot(start[first_axis] - center_first, start[second_axis] - center_second)
    if start_radius <= 1e-10:
        return None
    end_radius = math.hypot(end[first_axis] - center_first, end[second_axis] - center_second)
    return abs(start_radius - end_radius)


def _autodetect_milling_arc_type(motions: tuple[TraceMotion, ...], *, tolerance: float, fallback: int) -> int:
    tolerance = max(0.0, float(tolerance))
    for motion in motions:
        relative_error = _ijk_radius_mismatch(motion, 1)
        absolute_error = _ijk_radius_mismatch(motion, 2)
        if relative_error is None and absolute_error is None:
            continue
        relative_valid = relative_error is not None and relative_error <= tolerance
        absolute_valid = absolute_error is not None and absolute_error <= tolerance
        if relative_valid != absolute_valid:
            return 1 if relative_valid else 2
    return fallback


def _effective_arc_type(result, language, autodetect_arc_type, arc_tolerance, source_arc_type):
    if language != "fanuc_mill" or not autodetect_arc_type:
        return source_arc_type
    return _autodetect_milling_arc_type(result.motions, tolerance=arc_tolerance, fallback=source_arc_type)


def _motion_with_step_metadata(motion, step, language, threading):
    x_scale = 0.5 if language == "fanuc_turn" else 1.0
    compensation_status = (
        "APPLIED"
        if motion.compensation_applied
        else ("UNVERIFIED" if motion.compensation_mode in (41, 42) else "NOT_APPLIED")
    )
    current_metadata = (
        motion.x_scale,
        motion.feed_mode,
        motion.spindle_rpm,
        motion.spindle_mode,
        motion.surface_speed_m_min,
        motion.spindle_limit_rpm,
        motion.spindle_running,
        motion.compensation_status,
        motion.threading,
    )
    expected_metadata = (
        x_scale,
        step.feed_mode,
        step.spindle_rpm,
        step.spindle_mode,
        step.surface_speed_m_min,
        step.spindle_limit_rpm,
        step.spindle_running,
        compensation_status,
        threading,
    )
    if current_metadata == expected_metadata:
        return motion
    return replace(
        motion,
        x_scale=x_scale,
        feed_mode=step.feed_mode,
        spindle_rpm=step.spindle_rpm,
        spindle_mode=step.spindle_mode,
        surface_speed_m_min=step.surface_speed_m_min,
        spindle_limit_rpm=step.spindle_limit_rpm,
        spindle_running=step.spindle_running,
        compensation_status=compensation_status,
        threading=threading,
    )


def _defer_gc() -> bool:
    was_enabled = gc.isenabled()
    if was_enabled:
        gc.disable()
    return was_enabled


def _restore_gc(was_enabled: bool) -> None:
    if was_enabled:
        gc.enable()


def _steps_with_emitted_counts(steps, emitted_counts):
    return tuple(
        step if step.emitted_count == emitted_counts[index] else replace(step, emitted_count=emitted_counts[index])
        for index, step in enumerate(steps)
    )


def _execute_impl(
    source: str,
    language: str = "fanuc_turn",
    *,
    x_is_diameter: bool = True,
    skip_optional_blocks: bool = False,
    supplementary_angles: bool = False,
    pq_mm_for_g74758384: bool = False,
    default_unit_scale: float = 1.0,
    tools: dict[str, dict[str, object]] | None = None,
    home_x: float = 0.0,
    home_y: float = 0.0,
    home_z: float = 0.0,
    wcs_offsets: WcsOffsets | None = None,
    extended_wcs_offsets: WcsOffsets | None = None,
    milling_g73_retract_distance: float = 1.0,
    emulate_g28_home: bool = False,
    include_instructions: bool = True,
) -> ExecutionResult:
    """Parse, compile, and trace a FANUC turning program.

    Unsupported position-changing commands fail closed at that block while
    preserving every trustworthy motion produced before it.
    """
    if language not in SUPPORTED_LANGUAGES:
        return ExecutionResult(
            ok=False,
            program=None,
            instructions=(),
            motions=(),
            diagnostics=(
                Diagnostic(
                    code="UNSUPPORTED_LANGUAGE",
                    message=f"Unsupported G-code language: {language}",
                ),
            ),
            executed_blocks=(),
            complete=False,
        )

    if language == "fanuc_mill":
        mill_offsets = _mill_wcs_offsets(wcs_offsets)
        mill_offsets.update(_mill_extended_wcs_offsets(extended_wcs_offsets))
        return replace(
            execute_milling(
                source,
                skip_optional_blocks=skip_optional_blocks,
                default_unit_scale=default_unit_scale,
                home=(home_x, home_y, home_z),
                wcs_offsets=mill_offsets,
                g73_retract_distance=milling_g73_retract_distance,
                include_instructions=include_instructions,
            ),
            wcs_offsets=_result_wcs_offsets(mill_offsets),
            extended_wcs_offsets=_result_extended_wcs_offsets(mill_offsets),
        )

    program: Program | None = None
    unsupported: tuple[Diagnostic, ...] = ()
    turn_offsets = _turn_wcs_offsets(wcs_offsets)
    turn_offsets.update(_turn_extended_wcs_offsets(extended_wcs_offsets))
    try:
        program = parse_program(source)
        unsupported = _unsupported_g_diagnostics(program)
        execution_diagnostics: list[Diagnostic] = []
        rough, finish = [], []
        native_motions, trace_steps = _build_source_motion_trace_with_steps(
            program,
            rough,
            finish,
            x_is_diameter=x_is_diameter,
            pq_mm_for_g74758384=pq_mm_for_g74758384,
            supplementary_angles=supplementary_angles,
            default_unit_scale=default_unit_scale,
            skip_optional_blocks=skip_optional_blocks,
            home_x=home_x,
            home_z=home_z,
            wcs_offsets=turn_offsets,
            emulate_g28_home=emulate_g28_home,
            try_wcs_from_gcode_fn=try_wcs_from_gcode,
            x_value_to_diameter_fn=x_value_to_diameter,
            x_delta_to_diameter_fn=x_delta_to_diameter,
            motion_ctor=Motion,
            point_ctor=Point2,
            tools=tools,
            diagnostics=execution_diagnostics,
        )
        unsupported += tuple(execution_diagnostics)
        unsupported += _fractional_code_diagnostics(program, trace_steps)
    except Exception as exc:
        return ExecutionResult(
            ok=False,
            program=program,
            instructions=_semantic_instructions(program) if include_instructions else (),
            motions=(),
            diagnostics=unsupported + (_diagnostic_from_exception(exc, program),),
            executed_blocks=(),
            complete=False,
        )

    signals = tuple(signal for step in trace_steps for signal in step.signals)
    events = tuple(event for step in trace_steps for event in step.events)
    return ExecutionResult(
        ok=not any(item.severity == "error" for item in unsupported),
        program=program,
        instructions=_semantic_instructions(program) if include_instructions else (),
        motions=tuple(_trace_motion(motion) for motion in native_motions),
        diagnostics=unsupported,
        executed_blocks=tuple(
            dict.fromkeys(motion.source_block for motion in native_motions if motion.source_block is not None)
        ),
        signals=signals,
        program_end=program_end_code(events),
        execution_steps=tuple(trace_steps),
        events=events,
        wcs_offsets=_result_wcs_offsets(turn_offsets),
        extended_wcs_offsets=_result_extended_wcs_offsets(turn_offsets),
    )


def execute(
    source,
    language="fanuc_turn",
    *,
    limits=None,
    cancelled=None,
    source_arc_type=1,
    autodetect_arc_type=False,
    arc_tolerance=0.001,
    **options,
):
    """Execute once; resolve geometry and publish a self-contained immutable result."""
    token = active_budget.set(ExecutionBudget(limits or ExecutionLimits(), cancelled))
    milling_tools = options.pop("milling_tools", None)
    gc_was_enabled = _defer_gc()
    try:
        result = _execute_impl(source, language, **options)
        effective_arc_type = _effective_arc_type(result, language, autodetect_arc_type, arc_tolerance, source_arc_type)
        motions, motion_step_owners, geometry_diagnostics, cursor = [], [], [], 0
        try:
            threading_steps = (
                _threading_step_flags(result.execution_steps)
                if language == "fanuc_turn"
                else (False,) * len(result.execution_steps)
            )
            for step_index, step in enumerate(result.execution_steps):
                for motion in result.motions[cursor : cursor + step.emitted_count]:
                    threading = threading_steps[step_index] and motion.move == 1
                    motion = _motion_with_step_metadata(motion, step, language, threading)
                    try:
                        resolved = resolve_arc(motion, source_arc_type=effective_arc_type)
                    except SemanticError as exc:
                        diagnostic = _diagnostic_from_exception(exc, result.program)
                        if diagnostic.line is None and motion.source_block is not None:
                            block = result.program.blocks[motion.source_block] if result.program is not None else None
                            diagnostic = replace(
                                diagnostic,
                                line=motion.source_block + 1,
                                raw=None if block is None else block.raw,
                            )
                        geometry_diagnostics.append(diagnostic)
                        continue
                    motions.append(resolved)
                    motion_step_owners.append(step_index)
                cursor += step.emitted_count
        except Exception as exc:
            emitted_counts = [0] * len(result.execution_steps)
            for owner in motion_step_owners:
                emitted_counts[owner] += 1
            diagnostic = _diagnostic_from_exception(exc, result.program)
            partial_steps = []
            for index, step in enumerate(result.execution_steps):
                if index > step_index:
                    break
                partial_steps.append(
                    replace(
                        step,
                        emitted_count=emitted_counts[index],
                        stop=(step.stop or index == step_index),
                    )
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
            emitted_counts = [0] * len(result.execution_steps)
            for owner in motion_step_owners:
                emitted_counts[owner] += 1
            result = replace(
                result,
                execution_steps=_steps_with_emitted_counts(result.execution_steps, emitted_counts),
            )
        diagnostics = result.diagnostics + tuple(geometry_diagnostics)
        if language == "fanuc_mill":
            motions, motion_step_owners = apply_milling_cutter_compensation_with_owners(
                motions,
                milling_tools or {},
                motion_step_owners,
            )
            emitted_counts = [0] * len(result.execution_steps)
            for owner in motion_step_owners:
                emitted_counts[owner] += 1
            result = replace(
                result,
                execution_steps=_steps_with_emitted_counts(result.execution_steps, emitted_counts),
            )
            if any(m.compensation_mode in (41, 42) and not m.compensation_applied for m in motions):
                diagnostics = diagnostics + (
                    Diagnostic(
                        "UNVERIFIED_CUTTER_COMPENSATION",
                        "G41/G42 requires a configured T1-T99 milling cutter and supported "
                        "resolved line/arc/helix geometry",
                        "warning",
                        "unverified",
                    ),
                )
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
        return ExecutionResult(False, None, (), (), (diagnostic,), (), complete=False, language=language)
    finally:
        active_budget.reset(token)
        _restore_gc(gc_was_enabled)
