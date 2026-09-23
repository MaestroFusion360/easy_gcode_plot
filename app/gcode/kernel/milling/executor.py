"""FANUC-style 3-axis milling resolver producing logical trace motions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto

from ..api.types import Diagnostic, ExecutionEvent, ExecutionResult, ExecutionStep, TraceMotion
from ..frontend.program import parse_program
from ..runtime.diagnostics import modal_conflict_diagnostics
from ..runtime.events import home_return_event, main_program_location, program_end_code, program_start_event
from ..runtime.execution import ProgramRuntime, semantic_instructions
from .diagnostics import _apply_milling_tool_change, _execution_diagnostic
from .motion import _emit_milling_motions, _g53_home_axes
from .state import MillState, _apply_pre_flow_modal_state, _execution_step, _wcs_offset

try:
    from ._native_executor import execute_simple_blocks as _execute_simple_blocks
except ImportError:
    _execute_simple_blocks = None


MILLING_RECOGNIZED_G_CODES = frozenset(
    {
        0,
        1,
        2,
        3,
        4,
        10,
        15,
        16,
        17,
        18,
        19,
        20,
        21,
        28,
        40,
        41,
        42,
        43,
        49,
        50,
        51,
        52,
        53,
        54.1,
        54,
        55,
        56,
        57,
        58,
        59,
        65,
        68,
        69,
        73,
        80,
        81,
        82,
        83,
        84,
        85,
        86,
        90,
        91,
        94,
        95,
        98,
        99,
    }
)
MILLING_RECOGNIZED_M_CODES = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 30, 98, 99})


class _BlockAction(Enum):
    ADVANCE = auto()
    JUMP = auto()
    STOP = auto()


@dataclass(frozen=True)
class _BlockOutcome:
    """Complete result of one interpreted block, finalized by the caller."""

    action: _BlockAction = _BlockAction.ADVANCE
    next_pc: int | None = None
    motions: tuple[TraceMotion, ...] = ()
    events: tuple[ExecutionEvent, ...] = ()
    signals: tuple = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    words: tuple = ()


@dataclass
class _MillingExecutionContext:
    program: object
    state: MillState
    runtime: ProgramRuntime
    home: tuple[float, float, float]
    wcs_offsets: dict[int, tuple[float, float, float]] | None
    program_start_block: int
    program_number: int | None
    program_started: bool = False


def _report_unknown_g_codes(diagnostics, unknown_g, position_words, block) -> None:
    for g in unknown_g:
        diagnostics.append(
            Diagnostic(
                "UNSUPPORTED_G_CODE",
                (
                    f"G{g} is not modeled for fanuc_mill; execution stops before this position block"
                    if position_words
                    else f"G{g} is not modeled for fanuc_mill; ignored for trace execution"
                ),
                "error" if position_words else "warning",
                "unsupported" if position_words else "unverified",
                block.index + 1,
                block.raw,
            )
        )


def _report_unknown_m_codes(diagnostics, mcodes, recognized_m, block) -> None:
    for m in mcodes:
        if 0 <= m <= 199 and m not in recognized_m:
            diagnostics.append(
                Diagnostic(
                    "UNSUPPORTED_M_CODE",
                    f"M{m} is not modeled for fanuc_mill; ignored for trace execution",
                    "warning",
                    "unverified",
                    block.index + 1,
                    block.raw,
                )
            )


def _validate_g73_retract_distance(value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError("G73 retract distance must be finite and non-negative")


def _unsupported_polar_arc(state: MillState, gcodes, words) -> bool:
    """Return whether this block requests an unverified polar arc form."""
    polar_active = state.polar_active
    for g in gcodes:
        if g == 15:
            polar_active = False
        elif g == 16:
            polar_active = True
    if not polar_active or any(g in gcodes for g in (4, 10, 51, 52, 53, 68)):
        return False

    explicit_motion = next((g for g in reversed(gcodes) if g in (0, 1, 2, 3)), None)
    if explicit_motion is None:
        if state.cycle != 80:
            return False
        motion_mode = state.move
    else:
        motion_mode = explicit_motion
    if motion_mode not in (2, 3):
        return False
    is_motion_block = explicit_motion in (2, 3) or any(axis in words for axis in ("X", "Y", "Z", "I", "J", "K", "R"))
    return is_motion_block and (any(axis in words for axis in ("I", "J", "K")) or "R" not in words)


def _finalize_milling_block(
    ctx,
    block,
    outcome,
    motions,
    diagnostics,
    executed,
    steps,
    signals,
    events,
) -> bool:
    """Commit one block exactly once and apply its control-flow action."""
    diagnostics.extend(outcome.diagnostics)
    motions.extend(outcome.motions)
    signals.extend(outcome.signals)
    events.extend(outcome.events)
    if outcome.motions and (not executed or executed[-1] != block.index):
        executed.append(block.index)
    steps.append(
        _execution_step(
            ctx.state,
            block,
            len(outcome.motions),
            len(steps),
            words=outcome.words,
            signals=outcome.signals,
            events=outcome.events,
            stop=outcome.action is _BlockAction.STOP,
            wcs_offsets=ctx.wcs_offsets,
            variables=ctx.runtime.variable_snapshot(),
        )
    )
    if outcome.action is _BlockAction.STOP:
        return True
    if outcome.action is _BlockAction.JUMP:
        if outcome.next_pc is None:
            raise RuntimeError("Jump outcome requires a destination")
        ctx.runtime.jump(outcome.next_pc)
    else:
        ctx.runtime.advance()
    return False


def _validate_milling_block(ctx, block, evaluated_block, occurrence_events):
    """Return an early outcome for validation/dispatch, otherwise ``None``."""
    words = evaluated_block.words
    codes = evaluated_block.codes
    evaluated = evaluated_block.values
    conflict_diagnostics = modal_conflict_diagnostics(codes.all_g, "fanuc_mill", block)
    if conflict_diagnostics:
        return _BlockOutcome(
            events=tuple(occurrence_events),
            diagnostics=tuple(conflict_diagnostics),
            words=evaluated,
        )

    g65_flow = ctx.runtime.dispatch_g65(
        block=block,
        words=words,
        codes=codes,
        pc=ctx.runtime.pc,
        program=ctx.program,
    )
    if g65_flow.dispatch.handled:
        occurrence_events.extend(g65_flow.events)
        return _BlockOutcome(
            action=_BlockAction.JUMP,
            next_pc=g65_flow.dispatch.next_pc,
            events=tuple(occurrence_events),
            words=evaluated,
        )

    if not _unsupported_polar_arc(ctx.state, codes.all_g, words):
        return None
    return _BlockOutcome(
        events=tuple(occurrence_events),
        diagnostics=(
            Diagnostic(
                "UNSUPPORTED_POLAR_ARC_CENTER",
                "Polar G2/G3 requires R-format circular interpolation; I/J/K is not modeled",
                "error",
                "unsupported",
                block.index + 1,
                block.raw,
            ),
        ),
        words=evaluated,
    )


def _diagnose_unknown_milling_codes(ctx, block, evaluated_block, occurrence_events, block_diagnostics):
    """Report unknown codes and fail closed for position-bearing G codes."""
    words = evaluated_block.words
    codes = evaluated_block.codes
    unknown_g = tuple(g for g in codes.all_g if g not in MILLING_RECOGNIZED_G_CODES)
    position_words = any(letter in words for letter in ("X", "Y", "Z"))
    _report_unknown_g_codes(block_diagnostics, unknown_g, position_words, block)
    _report_unknown_m_codes(block_diagnostics, codes.all_m, MILLING_RECOGNIZED_M_CODES, block)
    if not (unknown_g and position_words):
        return None
    _apply_pre_flow_modal_state(ctx.state, codes.all_g, codes.all_m, words, wcs_offsets=ctx.wcs_offsets)
    ctx.state.unknown_axes.update(letter for letter in ("X", "Y", "Z") if letter in words)
    return _BlockOutcome(
        events=tuple(occurrence_events),
        signals=evaluated_block.signals,
        diagnostics=tuple(block_diagnostics),
        words=evaluated_block.values,
    )


def _apply_milling_block_state(ctx, block, evaluated_block, occurrence_events, block_diagnostics):
    """Apply tool/modal state and return early while position remains unknown."""
    words = evaluated_block.words
    codes = evaluated_block.codes
    _apply_milling_tool_change(
        block,
        ctx.state,
        words,
        codes,
        block_diagnostics,
        occurrence_events,
        ctx.runtime.call_stack,
    )
    _apply_pre_flow_modal_state(ctx.state, codes.all_g, codes.all_m, words, wcs_offsets=ctx.wcs_offsets)
    if not ctx.state.unknown_axes:
        return None
    if ctx.state.absolute:
        for letter in tuple(ctx.state.unknown_axes):
            if letter in words:
                setattr(ctx.state, letter.lower(), words[letter] * ctx.state.unit_scale)
                ctx.state.unknown_axes.remove(letter)
    return _BlockOutcome(
        events=tuple(occurrence_events),
        signals=evaluated_block.signals,
        diagnostics=tuple(block_diagnostics),
        words=evaluated_block.values,
    )


def _append_milling_reference_events(ctx, block, gcodes, words, occurrence_events) -> None:
    if 28 in gcodes:
        occurrence_events.append(
            home_return_event(
                block,
                "G28",
                tuple(axis for axis in ("X", "Y", "Z") if axis in words),
                len(ctx.runtime.call_stack),
            )
        )
    if 53 in gcodes:
        home_axes = _g53_home_axes(ctx.state, words, ctx.home, wcs_offsets=ctx.wcs_offsets)
        if home_axes:
            occurrence_events.append(home_return_event(block, "G53", home_axes, len(ctx.runtime.call_stack)))


def _dispatch_milling_program_flow(ctx, block, evaluated_block, occurrence_events, block_diagnostics):
    codes = evaluated_block.codes
    program_flow = ctx.runtime.dispatch_program_flow(
        codes=codes,
        words=evaluated_block.words,
        pc=ctx.runtime.pc,
        program=ctx.program,
        block=block,
        program_number=ctx.program_number,
    )
    occurrence_events.extend(program_flow.events)
    if not program_flow.dispatch.handled:
        return None
    action = _BlockAction.STOP if program_flow.dispatch.stop else _BlockAction.JUMP
    return _BlockOutcome(
        action=action,
        next_pc=program_flow.dispatch.next_pc,
        events=tuple(occurrence_events),
        signals=evaluated_block.signals,
        diagnostics=tuple(block_diagnostics),
        words=evaluated_block.values,
    )


def _execute_milling_block(ctx: _MillingExecutionContext, block) -> _BlockOutcome:
    """Run the named milling phases without committing PC or ExecutionStep."""
    occurrence_events: list[ExecutionEvent] = []
    if not ctx.program_started and block.index == ctx.program_start_block:
        occurrence_events.append(program_start_event(block, ctx.program_number))
        ctx.program_started = True

    # Phase 1: control flow that must run before CNC word evaluation.
    flow = ctx.runtime.dispatch_macro(block, ctx.runtime.pc, ctx.program.blocks)
    if flow.handled:
        return _BlockOutcome(
            action=_BlockAction.JUMP,
            next_pc=flow.next_pc,
            events=tuple(occurrence_events),
        )

    # Phase 2: evaluate the block once and establish its modal codes.
    evaluated_block = ctx.runtime.evaluate_block(block)
    words = evaluated_block.words
    if words.errors:
        token, error = words.errors[0]
        raise ValueError(f"{error} at line {block.index + 1}: {block.raw} ({token.letter}{token.expr})") from error
    codes = evaluated_block.codes
    gcodes = codes.all_g
    evaluated = evaluated_block.values

    # Phase 3: reject ambiguous or unsupported semantics before applying state.
    early_outcome = _validate_milling_block(ctx, block, evaluated_block, occurrence_events)
    if early_outcome is not None:
        return early_outcome

    occurrence_signals = evaluated_block.signals
    block_diagnostics: list[Diagnostic] = []
    early_outcome = _diagnose_unknown_milling_codes(ctx, block, evaluated_block, occurrence_events, block_diagnostics)
    if early_outcome is not None:
        return early_outcome

    # Phase 4: apply tool and modal state before any program-flow transfer.
    early_outcome = _apply_milling_block_state(ctx, block, evaluated_block, occurrence_events, block_diagnostics)
    if early_outcome is not None:
        return early_outcome
    _append_milling_reference_events(ctx, block, gcodes, words, occurrence_events)

    # Phase 5: transfer program flow only after state changes are visible.
    early_outcome = _dispatch_milling_program_flow(ctx, block, evaluated_block, occurrence_events, block_diagnostics)
    if early_outcome is not None:
        return early_outcome

    # Phase 6: execute geometric semantics and return everything for one commit.
    emitted: list[TraceMotion] = []
    cycle_signals = _emit_milling_motions(block, ctx.state, words, gcodes, emitted, ctx.home, ctx.wcs_offsets)
    occurrence_signals += cycle_signals
    return _BlockOutcome(
        motions=tuple(emitted),
        events=tuple(occurrence_events),
        signals=occurrence_signals,
        diagnostics=tuple(block_diagnostics),
        words=evaluated,
    )


def execute_milling(
    source: str,
    *,
    skip_optional_blocks: bool = False,
    default_unit_scale: float = 1.0,
    home: tuple[float, float, float] = (0.0, 0.0, 0.0),
    wcs_offsets: dict[int, tuple[float, float, float]] | None = None,
    g73_retract_distance: float = 1.0,
    include_instructions: bool = True,
):

    program = parse_program(source)
    program_start_block, program_number = main_program_location(program)
    ox, oy, oz = _wcs_offset(wcs_offsets, 54)
    state = MillState(
        x=home[0] - ox,
        y=home[1] - oy,
        z=home[2] - oz,
        unit_scale=float(default_unit_scale),
        g73_retract_distance=float(g73_retract_distance),
    )
    motions: list[TraceMotion] = []
    diagnostics: list[Diagnostic] = []
    executed: list[int] = []
    steps: list[ExecutionStep] = []
    signals = []
    events: list[ExecutionEvent] = []
    runtime = ProgramRuntime.create(program)
    instructions = semantic_instructions(program) if include_instructions else ()
    ctx = _MillingExecutionContext(
        program=program,
        state=state,
        runtime=runtime,
        home=home,
        wcs_offsets=wcs_offsets,
        program_start_block=program_start_block,
        program_number=program_number,
    )

    try:
        _validate_g73_retract_distance(state.g73_retract_distance)
        while 0 <= runtime.pc < len(program.blocks):
            if _execute_simple_blocks is not None and _execute_simple_blocks(
                program, runtime, state, motions, executed, steps, wcs_offsets
            ):
                continue
            block = runtime.next_block(program.blocks)
            if block.optional_skip and skip_optional_blocks:
                runtime.advance()
                continue
            outcome = _execute_milling_block(ctx, block)
            if _finalize_milling_block(
                ctx,
                block,
                outcome,
                motions,
                diagnostics,
                executed,
                steps,
                signals,
                events,
            ):
                break
    except Exception as exc:
        diagnostics.append(_execution_diagnostic(exc, program))
        return ExecutionResult(
            False,
            program,
            instructions,
            tuple(motions),
            tuple(diagnostics),
            tuple(executed),
            signals=tuple(signals),
            execution_steps=tuple(steps),
            complete=False,
            events=tuple(events),
        )

    signals = tuple(signals)
    event_tuple = tuple(events)
    return ExecutionResult(
        ok=not any(d.severity == "error" for d in diagnostics),
        program=program,
        instructions=instructions,
        motions=tuple(motions),
        diagnostics=tuple(diagnostics),
        executed_blocks=tuple(executed),
        signals=signals,
        program_end=program_end_code(event_tuple),
        execution_steps=tuple(steps),
        events=event_tuple,
    )
