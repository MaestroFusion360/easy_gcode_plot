"""Small public facade for the native FANUC CNC kernel."""

from __future__ import annotations

from dataclasses import replace

from ..compensation.milling import apply_milling_cutter_compensation_with_owners
from ..frontend.model import Motion, Point2, Program
from ..frontend.program import eval_words, parse_program, try_wcs_from_gcode, x_delta_to_diameter, x_value_to_diameter
from ..geometry import resolve_arc
from ..geometry.coordinates import WcsOffset, WcsOffsets  # noqa: F401 - compatibility re-export
from ..geometry.coordinates import milling_wcs_offsets as _mill_wcs_offsets
from ..geometry.coordinates import published_wcs_offsets as _result_wcs_offsets
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
from ..runtime.trace import build_source_motion_trace_with_steps as _build_source_motion_trace_with_steps
from ..runtime.trace_metadata import threading_step_flags as _threading_step_flags
from .conversion import semantic_instructions as _semantic_instructions
from .conversion import trace_motion as _trace_motion
from .resources import ExecutionBudget, ExecutionLimits, SemanticError, active_budget
from .types import (
    Diagnostic,
    ExecutionResult,
    ExecutionStep,
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
    emulate_g28_home: bool = False,
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
        return replace(
            execute_milling(
                source,
                skip_optional_blocks=skip_optional_blocks,
                default_unit_scale=default_unit_scale,
                home=(home_x, home_y, home_z),
                wcs_offsets=mill_offsets,
            ),
            wcs_offsets=_result_wcs_offsets(mill_offsets),
        )

    program: Program | None = None
    unsupported: tuple[Diagnostic, ...] = ()
    turn_offsets = _turn_wcs_offsets(wcs_offsets)
    try:
        program = parse_program(source.splitlines())
        unsupported = _unsupported_g_diagnostics(program)
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
            eval_words_fn=eval_words,
            try_wcs_from_gcode_fn=try_wcs_from_gcode,
            x_value_to_diameter_fn=x_value_to_diameter,
            x_delta_to_diameter_fn=x_delta_to_diameter,
            motion_ctor=Motion,
            point_ctor=Point2,
            tools=tools,
        )
        unsupported += _fractional_code_diagnostics(program, trace_steps)
    except Exception as exc:
        return ExecutionResult(
            ok=False,
            program=program,
            instructions=_semantic_instructions(program),
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
        instructions=_semantic_instructions(program),
        motions=tuple(_trace_motion(motion) for motion in native_motions),
        diagnostics=unsupported,
        executed_blocks=tuple(
            dict.fromkeys(motion.source_block for motion in native_motions if motion.source_block is not None)
        ),
        signals=signals,
        program_end=program_end_code(events),
        execution_steps=tuple(
            ExecutionStep(
                source_block=step.source_block,
                emitted_count=step.emitted_count,
                unit_scale=step.unit_scale,
                x_is_diameter=step.x_is_diameter,
                contour_definition=step.contour_definition,
                stop=step.stop,
                words=step.words,
                signals=step.signals,
                occurrence=occurrence,
                events=step.events,
                active_wcs=step.active_wcs,
                position=(step.modal_x, 0.0, step.modal_z),
                feed_mode=step.feed_mode,
                spindle_rpm=step.spindle_rpm,
                spindle_mode=step.spindle_mode,
                surface_speed_m_min=step.surface_speed_m_min,
                spindle_limit_rpm=step.spindle_limit_rpm,
                spindle_running=step.spindle_running,
            )
            for occurrence, step in enumerate(trace_steps)
        ),
        events=events,
        wcs_offsets=_result_wcs_offsets(turn_offsets),
    )


def execute(source, language="fanuc_turn", *, limits=None, cancelled=None, source_arc_type=1, **options):
    """Execute once; resolve geometry and publish a self-contained immutable result."""
    budget = ExecutionBudget(limits or ExecutionLimits(), cancelled)
    token = active_budget.set(budget)
    milling_tools = options.pop("milling_tools", None)
    try:
        result = _execute_impl(source, language, **options)
        motions = []
        motion_step_owners: list[int] = []
        geometry_diagnostics: list[Diagnostic] = []
        cursor = 0
        try:
            threading_steps = (
                _threading_step_flags(result.execution_steps)
                if language == "fanuc_turn"
                else (False,) * len(result.execution_steps)
            )
            for step_index, step in enumerate(result.execution_steps):
                for motion in result.motions[cursor : cursor + step.emitted_count]:
                    motion = replace(
                        motion,
                        x_scale=0.5 if language == "fanuc_turn" else 1.0,
                        feed_mode=step.feed_mode,
                        spindle_rpm=step.spindle_rpm,
                        spindle_mode=step.spindle_mode,
                        surface_speed_m_min=step.surface_speed_m_min,
                        spindle_limit_rpm=step.spindle_limit_rpm,
                        spindle_running=step.spindle_running,
                        compensation_status="APPLIED"
                        if motion.compensation_applied
                        else ("UNVERIFIED" if motion.compensation_mode in (41, 42) else "NOT_APPLIED"),
                        threading=threading_steps[step_index] and motion.move == 1,
                    )
                    try:
                        resolved = resolve_arc(motion, source_arc_type=source_arc_type)
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
                execution_steps=tuple(
                    replace(step, emitted_count=emitted_counts[index])
                    for index, step in enumerate(result.execution_steps)
                ),
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
                execution_steps=tuple(
                    replace(step, emitted_count=emitted_counts[index])
                    for index, step in enumerate(result.execution_steps)
                ),
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
