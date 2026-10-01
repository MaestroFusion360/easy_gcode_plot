"""FANUC-style 3-axis milling resolver producing logical trace motions."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum, auto

from ..api.types import Diagnostic, ExecutionEvent, ExecutionResult, ExecutionStep, MachineSignal, TraceMotion
from ..frontend.program import EvaluatedWords, parse_program
from ..runtime.diagnostics import modal_conflict_diagnostics
from ..runtime.events import home_return_event, main_program_location, program_end_code, program_start_event
from ..runtime.execution import ProgramRuntime, semantic_instructions
from .diagnostics import _apply_milling_tool_change, _execution_diagnostic
from .kinematics import TCP_TABLE_PROFILES, MachineKinematics, effective_orientation
from .motion import _emit_milling_motions, _g53_home_axes
from .sinumerik_iso import (
    SINUMERIK_MODE_ISO,
    SINUMERIK_MODE_SIEMENS,
    is_siemens_metadata_block,
    mode_switch_code,
    mode_switch_diagnostic,
    unsupported_iso_macro_diagnostic,
    unsupported_siemens_mode_diagnostic,
    validate_and_normalize_iso_block,
)
from .state import (
    MillState,
    _activate_tcp,
    _apply_pre_flow_modal_state,
    _execution_step,
    _wcs_offset,
)

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
        43.4,
        49,
        50,
        51,
        52,
        53,
        53.1,
        54.1,
        54,
        55,
        56,
        57,
        58,
        59,
        65,
        68,
        68.2,
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
MILLING_RECOGNIZED_M_CODES = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 19, 29, 30, 98, 99})


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


@dataclass(frozen=True)
class _PreparedMillingBlock:
    """State-phase output consumed by geometric execution."""

    words: EvaluatedWords
    evaluated: tuple
    gcodes: tuple
    rotary_start_angles: dict[str, float]
    signals: tuple
    diagnostics: tuple[Diagnostic, ...]


@dataclass
class _MillingExecutionContext:
    program: object
    state: MillState
    runtime: ProgramRuntime
    home: tuple[float, float, float]
    wcs_offsets: dict[int, tuple[float, float, float]] | None
    program_start_block: int
    program_number: int | None
    source_dialect: str = "fanuc"
    controller_mode: str = "fanuc"
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
        if m not in recognized_m:
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


def _milling_spindle_signals(block, words, mcodes) -> tuple[MachineSignal, ...]:
    signals = []
    for code, kind in ((19, "spindle_orient"), (29, "rigid_tapping_prepare")):
        if code in mcodes:
            signals.append(MachineSignal(kind, block.index, f"M{code}", words.get("S")))
    return tuple(signals)


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


def _apply_sinumerik_mode_switch(ctx, block, evaluated_block, occurrence_events):
    switch_diagnostic = mode_switch_diagnostic(block, evaluated_block)
    if switch_diagnostic is not None:
        return evaluated_block, _BlockOutcome(
            action=_BlockAction.STOP,
            events=tuple(occurrence_events),
            diagnostics=(switch_diagnostic,),
            words=evaluated_block.values,
        )

    switch = mode_switch_code(evaluated_block)
    if switch is None:
        return None
    ctx.controller_mode = SINUMERIK_MODE_ISO if switch == 291 else SINUMERIK_MODE_SIEMENS
    occurrence_events.append(
        ExecutionEvent(
            "SINUMERIK_ISO_MODE" if switch == 291 else "SINUMERIK_SIEMENS_MODE",
            block.index,
            code=f"G{switch}",
        )
    )
    return evaluated_block, _BlockOutcome(
        events=tuple(occurrence_events),
        words=evaluated_block.values,
    )


def _prepare_siemens_block(block, evaluated_block, occurrence_events):
    if is_siemens_metadata_block(block, evaluated_block):
        return evaluated_block, _BlockOutcome(
            events=tuple(occurrence_events),
            words=evaluated_block.values,
        )
    return evaluated_block, _BlockOutcome(
        action=_BlockAction.STOP,
        events=tuple(occurrence_events),
        diagnostics=(unsupported_siemens_mode_diagnostic(block),),
        words=evaluated_block.values,
    )


def _prepare_source_dialect_block(ctx, block, evaluated_block, occurrence_events):
    """Apply SINUMERIK G290/G291 mode semantics before FANUC-style dispatch."""
    if ctx.source_dialect != "sinumerik":
        return evaluated_block, None

    switch_result = _apply_sinumerik_mode_switch(ctx, block, evaluated_block, occurrence_events)
    if switch_result is not None:
        return switch_result
    if ctx.controller_mode == SINUMERIK_MODE_SIEMENS:
        return _prepare_siemens_block(block, evaluated_block, occurrence_events)

    gcodes = evaluated_block.codes.all_g
    absolute_mode = next((g == 90 for g in reversed(gcodes) if g in (90, 91)), ctx.state.absolute)
    active_plane = next((int(g) for g in reversed(gcodes) if g in (17, 18, 19)), ctx.state.plane)
    normalized, diagnostic = validate_and_normalize_iso_block(
        block, evaluated_block, absolute_mode=absolute_mode, active_plane=active_plane
    )
    if diagnostic is None:
        # The common milling state phase applies modal changes exactly once.
        return normalized, None
    return normalized, _BlockOutcome(
        action=_BlockAction.STOP,
        events=tuple(occurrence_events),
        diagnostics=(diagnostic,),
        words=normalized.values,
    )


def _reject_unsupported_sinumerik_flow(ctx, block, occurrence_events):
    if ctx.source_dialect != "sinumerik" or block.flow_node is None:
        return None
    diagnostic = (
        unsupported_siemens_mode_diagnostic(block)
        if ctx.controller_mode == SINUMERIK_MODE_SIEMENS
        else unsupported_iso_macro_diagnostic(block)
    )
    return _BlockOutcome(
        action=_BlockAction.STOP,
        events=tuple(occurrence_events),
        diagnostics=(diagnostic,),
    )


def _finish_milling_block(ctx, block, prepared: _PreparedMillingBlock, occurrence_events):
    if 43.4 in prepared.gcodes:
        _activate_tcp(ctx.state)

    emitted: list[TraceMotion] = []
    cycle_signals = _emit_milling_motions(
        block,
        ctx.state,
        prepared.words,
        prepared.gcodes,
        emitted,
        ctx.home,
        ctx.wcs_offsets,
        rotary_start_angles=prepared.rotary_start_angles,
    )
    if ctx.state.kinematics is not None:
        tool_orientation = effective_orientation(ctx.state.kinematics, ctx.state.rotary_angles)
        emitted = [replace(motion, tool_orientation=tool_orientation) for motion in emitted]
    elif ctx.state.twp.active and ctx.state.twp.tool_axis_control:
        emitted = [replace(motion, tool_orientation=ctx.state.twp.orientation) for motion in emitted]
    return _BlockOutcome(
        motions=tuple(emitted),
        events=tuple(occurrence_events),
        signals=prepared.signals + cycle_signals,
        diagnostics=prepared.diagnostics,
        words=prepared.evaluated,
    )


def _prepare_milling_block_state(ctx, block, evaluated_block, occurrence_events):
    words = evaluated_block.words
    early_outcome = _validate_milling_block(ctx, block, evaluated_block, occurrence_events)
    if early_outcome is not None:
        return early_outcome, None

    gcodes = evaluated_block.codes.all_g
    evaluated = evaluated_block.values
    signals = evaluated_block.signals + _milling_spindle_signals(block, words, evaluated_block.codes.all_m)
    diagnostics: list[Diagnostic] = []
    early_outcome = _diagnose_unknown_milling_codes(ctx, block, evaluated_block, occurrence_events, diagnostics)
    if early_outcome is not None:
        return early_outcome, None

    rotary_start_angles = dict(ctx.state.rotary_angles)
    early_outcome = _apply_rotary_index(ctx, block, evaluated_block, occurrence_events)
    if early_outcome is None:
        early_outcome = _apply_milling_block_state(ctx, block, evaluated_block, occurrence_events, diagnostics)
    if early_outcome is not None:
        return early_outcome, None
    _append_milling_reference_events(ctx, block, gcodes, words, occurrence_events)

    early_outcome = _dispatch_milling_program_flow(ctx, block, evaluated_block, occurrence_events, diagnostics)
    if early_outcome is not None:
        return early_outcome, None
    return None, _PreparedMillingBlock(words, evaluated, gcodes, rotary_start_angles, signals, tuple(diagnostics))


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

    twp_requested = 68.2 in codes.all_g
    orient_requested = 53.1 in codes.all_g
    tcp_requested = 43.4 in codes.all_g
    rotary_requested = any(axis in words for axis in ("A", "B", "C"))
    error = None
    if tcp_requested and (ctx.state.kinematics is None or ctx.state.kinematics.id not in TCP_TABLE_PROFILES):
        error = (
            "TCP_KINEMATICS_REQUIRED",
            "G43.4 requires the 5ax_table_ac_angled or 5ax_table_bc_angled kinematics profile",
        )
    elif tcp_requested and (ctx.state.twp.active or twp_requested):
        error = ("UNSUPPORTED_TCP_TWP_COMPOSITION", "G43.4 cannot combine with G68.2 tilted-work-plane mode")
    elif tcp_requested and rotary_requested:
        error = ("UNSUPPORTED_G43_4_START_ROTARY", "Rotary addresses in the G43.4 activation block are not modeled")
    elif (ctx.state.twp.active or twp_requested) and rotary_requested:
        error = ("UNSUPPORTED_TWP_EXPLICIT_ROTARY", "G68.2 does not support explicit A/B/C rotary addresses")
    elif orient_requested and (
        codes.all_g != (53.1,) or codes.all_m or any(key not in ("G", "N") for key, _ in evaluated)
    ):
        error = ("G53_1_MUST_BE_STANDALONE", "G53.1 must be a standalone block")
    elif orient_requested and (not ctx.state.twp.active or ctx.state.twp.start_block != block.index - 1):
        error = ("G53_1_REQUIRES_G68_2", "G53.1 must immediately follow G68.2")
    if error is not None:
        return _BlockOutcome(
            action=_BlockAction.STOP,
            events=tuple(occurrence_events),
            diagnostics=(Diagnostic(error[0], error[1], "error", "unsupported", block.index + 1, block.raw),),
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
    position_words = any(letter in words for letter in ("X", "Y", "Z", "A", "B", "C"))
    _report_unknown_g_codes(block_diagnostics, unknown_g, position_words, block)
    _report_unknown_m_codes(block_diagnostics, codes.all_m, MILLING_RECOGNIZED_M_CODES, block)
    if not (unknown_g and position_words):
        return None
    _apply_pre_flow_modal_state(
        ctx.state, codes.all_g, codes.all_m, words, wcs_offsets=ctx.wcs_offsets, block_index=block.index
    )
    ctx.state.unknown_axes.update(letter for letter in ("X", "Y", "Z") if letter in words)
    return _BlockOutcome(
        action=_BlockAction.STOP if any(axis in words for axis in ("A", "B", "C")) else _BlockAction.ADVANCE,
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
    was_twp_active = ctx.state.twp.active
    old_rotary_angles = tuple(ctx.state.rotary_angles[axis] for axis in ("A", "B", "C"))
    _apply_pre_flow_modal_state(
        ctx.state, codes.all_g, codes.all_m, words, wcs_offsets=ctx.wcs_offsets, block_index=block.index
    )
    if 68.2 in codes.all_g:
        occurrence_events.append(
            ExecutionEvent(
                "TILTED_WORK_PLANE_ON",
                block.index,
                twp_origin=ctx.state.twp.origin,
                twp_angles=ctx.state.twp.angles,
                twp_orientation=ctx.state.twp.orientation,
            )
        )
    if 53.1 in codes.all_g:
        occurrence_events.append(
            ExecutionEvent(
                "TOOL_AXIS_ORIENT",
                block.index,
                twp_origin=ctx.state.twp.origin,
                twp_angles=ctx.state.twp.angles,
                twp_orientation=ctx.state.twp.orientation,
                old_abc=old_rotary_angles,
                new_abc=tuple(ctx.state.rotary_angles[axis] for axis in ("A", "B", "C")),
                kinematics_profile=ctx.state.kinematics.id,
            )
        )
    if 69 in codes.all_g and was_twp_active:
        occurrence_events.append(ExecutionEvent("TILTED_WORK_PLANE_OFF", block.index))
    if 43.4 in codes.all_g:
        occurrence_events.append(
            ExecutionEvent(
                "TCP_CONTROL_ON",
                block.index,
                kinematics_profile=ctx.state.kinematics.id if ctx.state.kinematics else None,
            )
        )
    if 49 in codes.all_g:
        occurrence_events.append(ExecutionEvent("TCP_CONTROL_OFF", block.index))
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
                tuple(axis for axis in ("X", "Y", "Z", "A", "B", "C") if axis in words),
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


def _apply_rotary_index(ctx, block, evaluated_block, occurrence_events) -> _BlockOutcome | None:
    words = evaluated_block.words
    codes = evaluated_block.codes
    gcodes = codes.all_g
    rotary = tuple(axis for axis in ("A", "B", "C") if axis in words)
    if not rotary or 65 in gcodes:
        return None
    state = ctx.state
    absolute = next((g == 90 for g in reversed(gcodes) if g in (90, 91)), state.absolute)
    targets = {
        axis: 0.0
        if 28 in gcodes
        else float(words[axis])
        if absolute
        else state.rotary_angles[axis] + float(words[axis])
        for axis in rotary
    }
    changed = tuple(axis for axis in rotary if targets[axis] != state.rotary_angles[axis])
    if not changed:
        return None
    move = next((g for g in reversed(gcodes) if g in (0, 1, 2, 3)), state.move)
    continuous_c = (
        state.kinematics is not None
        and state.kinematics.id == "4ax_table_c"
        and changed == ("C",)
        and 28 not in gcodes
        and 53 not in gcodes
        and move in (0, 1)
    )
    tcp_motion = (
        state.tcp_control
        and state.kinematics is not None
        and state.kinematics.id in TCP_TABLE_PROFILES
        and 28 not in gcodes
        and 53 not in gcodes
        and move in (0, 1)
    )
    message = ""
    if state.kinematics is None:
        code = "ROTARY_KINEMATICS_REQUIRED"
        message = f"Select a kinematics profile to resolve rotary address {', '.join(changed)}"
    elif any(axis not in state.kinematics.addresses for axis in changed):
        code = "UNCONFIGURED_ROTARY_AXIS"
        message = f"Rotary address {', '.join(changed)} is not configured in profile {state.kinematics.id}"
    elif state.tcp_control and move in (2, 3):
        code = "UNSUPPORTED_TCP_ROTARY_ARC"
        message = "G43.4 rotary interpolation with G2/G3 is not modeled; use G0/G1 TCP motion"
    elif any(axis in words for axis in ("X", "Y", "Z")) and not (continuous_c or tcp_motion):
        code = "UNSUPPORTED_SIMULTANEOUS_ROTARY_MOTION"
        message = "Rotary and linear motion in one block is not supported"
    elif 28 not in gcodes and move != 0 and not (continuous_c and move == 1) and not tcp_motion:
        code = "UNSUPPORTED_ROTARY_INTERPOLATION"
        message = "Rotary motion requires rapid G0 indexing"
    else:
        code = None
    if code is not None:
        return _BlockOutcome(
            action=_BlockAction.STOP,
            events=tuple(occurrence_events),
            diagnostics=(Diagnostic(code, message, "error", "unsupported", block.index + 1, block.raw),),
            words=evaluated_block.values,
        )
    old = tuple(state.rotary_angles[axis] for axis in ("A", "B", "C"))
    # Indexed tables retain programmed XYZ, as in 1.7.0, including
    # five-axis profiles with TCP off. Rebasing to the previous display
    # point puts the next approach on the opposite side of the workpiece.
    # Active TCP keeps its existing fixed-tip semantics in _machine.
    for axis in changed:
        state.rotary_angles[axis] = targets[axis]
    new = tuple(state.rotary_angles[axis] for axis in ("A", "B", "C"))
    occurrence_events.append(
        ExecutionEvent(
            "ROTARY_MOTION" if (continuous_c or tcp_motion) else "ROTARY_INDEX",
            block.index,
            axes=changed,
            old_abc=old,
            new_abc=new,
            kinematics_profile=state.kinematics.id,
        )
    )
    return None


def _execute_milling_block(ctx: _MillingExecutionContext, block) -> _BlockOutcome:
    """Run the named milling phases without committing PC or ExecutionStep."""
    occurrence_events: list[ExecutionEvent] = []
    if not ctx.program_started and block.index == ctx.program_start_block:
        occurrence_events.append(program_start_event(block, ctx.program_number))
        ctx.program_started = True

    # Phase 1: control flow that must run before CNC word evaluation.
    early_outcome = _reject_unsupported_sinumerik_flow(ctx, block, occurrence_events)
    if early_outcome is not None:
        return early_outcome
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

    evaluated_block, early_outcome = _prepare_source_dialect_block(ctx, block, evaluated_block, occurrence_events)
    if early_outcome is not None:
        return early_outcome

    # Phases 3–5 validate and apply state before program-flow transfer.
    early_outcome, prepared = _prepare_milling_block_state(ctx, block, evaluated_block, occurrence_events)
    if early_outcome is not None:
        return early_outcome
    assert prepared is not None

    # Phase 6: execute geometric semantics and return everything for one commit.
    return _finish_milling_block(ctx, block, prepared, occurrence_events)


def execute_milling(
    source: str,
    *,
    skip_optional_blocks: bool = False,
    default_unit_scale: float = 1.0,
    home: tuple[float, float, float] = (0.0, 0.0, 0.0),
    wcs_offsets: dict[int, tuple[float, float, float]] | None = None,
    g73_retract_distance: float = 1.0,
    include_instructions: bool = True,
    kinematics: MachineKinematics | None = None,
    source_dialect: str = "fanuc",
):

    program = parse_program(source)
    program_start_block, program_number = main_program_location(program)
    ox, oy, oz = _wcs_offset(wcs_offsets, 54)
    state = MillState(
        kinematics=kinematics,
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
        source_dialect=source_dialect,
        controller_mode=SINUMERIK_MODE_SIEMENS if source_dialect == "sinumerik" else "fanuc",
    )
    contains_rotary = any(
        any(token.letter in ("A", "B", "C") for token in block.parsed_words) for block in program.blocks
    )
    stopped_due_error = False

    try:
        _validate_g73_retract_distance(state.g73_retract_distance)
        while 0 <= runtime.pc < len(program.blocks):
            simple_blocks_available = (
                not contains_rotary
                and not state.twp.active
                and not state.tcp_control
                and kinematics is None
                and source_dialect == "fanuc"
                and _execute_simple_blocks is not None
                and (ctx.program_started or runtime.pc != ctx.program_start_block)
            )
            if simple_blocks_available and _execute_simple_blocks(
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
                stopped_due_error = any(d.severity == "error" for d in outcome.diagnostics)
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
            rotary_angles=tuple(state.rotary_angles.items()),
            kinematics_profile=kinematics.id if kinematics else None,
            rotary_axes=tuple(sorted(kinematics.addresses)) if kinematics else (),
        )

    signals = tuple(signals)
    event_tuple = tuple(events)
    return ExecutionResult(
        ok=not any(d.severity == "error" for d in diagnostics),
        complete=not stopped_due_error,
        program=program,
        instructions=instructions,
        motions=tuple(motions),
        diagnostics=tuple(diagnostics),
        executed_blocks=tuple(executed),
        signals=signals,
        program_end=program_end_code(event_tuple),
        execution_steps=tuple(steps),
        events=event_tuple,
        rotary_angles=tuple(state.rotary_angles.items()),
        kinematics_profile=kinematics.id if kinematics else None,
        rotary_axes=tuple(sorted(kinematics.addresses)) if kinematics else (),
    )
