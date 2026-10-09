"""FANUC-style 3-axis milling resolver producing logical trace motions."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum, auto

from app.native import native_symbol

from ..api.resources import SemanticError
from ..api.types import Diagnostic, ExecutionEvent, ExecutionResult, ExecutionStep, MachineSignal, TraceMotion
from ..frontend.ast import SinumerikFlowAstNode
from ..frontend.program import EvaluatedWords, parse_program
from ..frontend.sinumerik import parse_sinumerik_program
from ..runtime.capabilities import COMMON_ISO_M_CODES, controller_capability_gate
from ..runtime.cycles import CycleContext, apply_cycle_outcome
from ..runtime.diagnostics import modal_conflict_diagnostics
from ..runtime.events import main_program_location, program_end_code, program_start_event
from ..runtime.execution import ProgramRuntime, resolve_program_tools, semantic_instructions
from .cycles.sinumerik import execute_native_cycle
from .diagnostics import _apply_milling_tool_change, _execution_diagnostic
from .kinematics import TCP_TABLE_PROFILES, MachineKinematics, effective_orientation, kinematics_snapshot
from .motion import _emit_milling_motions
from .sinumerik_flow import build_native_loop_maps, native_flow_destination
from .sinumerik_native import (
    apply_native_declaration,
    apply_native_tcp_edge,
    evaluate_native_block,
    native_dc_diagnostics,
    native_edge_diagnostics,
    native_ignored_mode_warnings,
    native_operation_code,
)
from .state import (
    MillState,
    _activate_tcp,
    _apply_pre_flow_modal_state,
    _cancel_tcp,
    _execution_step,
    _wcs_offset,
)

_execute_simple_blocks = native_symbol("executor", "execute_simple_blocks")


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
        74,
        76,
        80,
        81,
        82,
        83,
        84,
        85,
        86,
        87,
        89,
        90,
        91,
        92.1,
        93,
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
    program_started: bool = False


def _report_unknown_g_codes(diagnostics, unknown_g, position_words, block) -> None:
    for g in unknown_g:
        diagnostics.append(
            Diagnostic(
                "UNSUPPORTED_G_CODE",
                (
                    f"G{g} is not modeled for fanuc_mill; this position block is skipped and its XYZ state "
                    "is unknown until absolute positions are restored; rotary position blocks stop execution"
                    if position_words
                    else f"G{g} is not modeled for fanuc_mill; ignored for trace execution"
                ),
                "error" if position_words else "warning",
                "unsupported" if position_words else "unverified",
                block.index + 1,
                block.raw,
            )
        )


def _report_unknown_m_codes(diagnostics, mcodes, recognized_m, block, controller="fanuc_mill") -> None:
    for m in mcodes:
        if m not in recognized_m:
            diagnostics.append(
                Diagnostic(
                    "UNSUPPORTED_M_CODE",
                    f"M{m:g} is not modeled for {controller}; ignored for trace execution",
                    "warning",
                    "unverified",
                    block.index + 1,
                    block.raw,
                    cnc_codes=(f"M{m:g}",),
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


def _validate_g83_clearance(value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError("G83 reentry clearance must be finite and non-negative")


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


def _gate_milling_block(ctx, block, occurrence_events, evaluated_block=None):
    normalized, diagnostic, switch = controller_capability_gate(ctx.runtime, block, evaluated_block, state=ctx.state)
    if ctx.source_dialect == "sinumerik":
        ctx.state.source_arc_type = 1
    if diagnostic is not None:
        return normalized, _BlockOutcome(
            action=_BlockAction.STOP,
            events=tuple(occurrence_events),
            diagnostics=(diagnostic,),
            words=normalized.values if normalized is not None else (),
        )
    if switch is not None:
        occurrence_events.append(
            ExecutionEvent(
                "SINUMERIK_ISO_MODE" if switch == 291 else "SINUMERIK_SIEMENS_MODE",
                block.index,
                code=f"G{switch}",
            )
        )
        return normalized, _BlockOutcome(events=tuple(occurrence_events), words=normalized.values)
    if normalized is not None and ctx.runtime.controller_mode == "sinumerik_native":
        code = native_operation_code(block)
        if code is not None:
            occurrence_events.append(ExecutionEvent("SINUMERIK_NATIVE_OPERATION", block.index, code=code))
        if apply_native_declaration(block, normalized, ctx.state, occurrence_events):
            return normalized, _BlockOutcome(
                events=tuple(occurrence_events),
                words=normalized.values,
                diagnostics=tuple(native_ignored_mode_warnings(block)),
            )
    return normalized, None


def _finish_milling_block(ctx, block, prepared: _PreparedMillingBlock, occurrence_events):
    emitted: list[TraceMotion] = []
    cycle = execute_native_cycle(
        CycleContext(block, prepared.words, prepared.gcodes, ctx.state, coordinate_context=ctx.wcs_offsets)
    )
    if cycle.handled:
        apply_cycle_outcome(ctx.state, cycle)
        emitted.extend(cycle.motions)
        occurrence_events.extend(cycle.events)
        cycle_signals = cycle.signals
    else:
        cycle_signals = _emit_milling_motions(
            block,
            ctx.state,
            prepared.words,
            prepared.gcodes,
            emitted,
            ctx.home,
            ctx.wcs_offsets,
            rotary_start_angles=prepared.rotary_start_angles,
            events=occurrence_events,
            call_depth=len(ctx.runtime.call_stack),
        )
    if 43.4 in prepared.gcodes:
        _activate_tcp(ctx.state)
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
    diagnostics: list[Diagnostic] = (
        native_ignored_mode_warnings(block)
        + native_edge_diagnostics(block, words)
        + native_dc_diagnostics(block, ctx.state)
        if ctx.runtime.controller_mode == "sinumerik_native"
        else []
    )
    early_outcome = _diagnose_unknown_milling_codes(ctx, block, evaluated_block, occurrence_events, diagnostics)
    if early_outcome is not None:
        return early_outcome, None

    rotary_start_angles = dict(ctx.state.rotary_angles)
    early_outcome = _apply_rotary_index(ctx, block, evaluated_block, occurrence_events)
    if early_outcome is None:
        early_outcome = _apply_milling_block_state(ctx, block, evaluated_block, occurrence_events, diagnostics)
    if early_outcome is not None:
        return early_outcome, None

    early_outcome = _dispatch_milling_program_flow(ctx, block, evaluated_block, occurrence_events, diagnostics)
    if early_outcome is not None:
        return early_outcome, None
    return None, _PreparedMillingBlock(words, evaluated, gcodes, rotary_start_angles, signals, tuple(diagnostics))


def _milling_transform_error(ctx, block, evaluated_block):
    words = evaluated_block.words
    codes = evaluated_block.codes
    evaluated = evaluated_block.values
    twp_requested = 68.2 in codes.all_g
    orient_requested = 53.1 in codes.all_g
    tcp_requested = 43.4 in codes.all_g
    rotary_requested = any(axis in words for axis in ("A", "B", "C"))
    error = None
    if tcp_requested and (ctx.state.kinematics is None or ctx.state.kinematics.id not in TCP_TABLE_PROFILES):
        error = (
            "TCP_KINEMATICS_REQUIRED",
            "G43.4 requires a supported AC/BC table kinematics profile",
        )
    elif tcp_requested and (ctx.state.twp.active or twp_requested) or twp_requested and ctx.state.tcp_control:
        error = ("UNSUPPORTED_TCP_TWP_COMPOSITION", "G43.4 cannot combine with G68.2 tilted-work-plane mode")
    elif tcp_requested and rotary_requested:
        error = ("UNSUPPORTED_G43_4_START_ROTARY", "Rotary addresses in the G43.4 activation block are not modeled")
    elif (
        (ctx.state.twp.active or twp_requested)
        and rotary_requested
        and not _native_rotary_unchanged(ctx, block, evaluated_block)
        and not _native_frame_index(ctx, evaluated_block)
    ):
        frame = "CYCLE800" if ctx.runtime.controller_mode == "sinumerik_native" else "G68.2"
        error = (
            "UNSUPPORTED_TWP_EXPLICIT_ROTARY",
            f"Explicit A/B/C rotary motion with an active {frame} frame is not modeled",
        )
    elif orient_requested and (
        codes.all_g != (53.1,) or codes.all_m or any(key not in ("G", "N") for key, _ in evaluated)
    ):
        error = ("G53_1_MUST_BE_STANDALONE", "G53.1 must be a standalone block")
    elif orient_requested and (not ctx.state.twp.active or ctx.state.twp.start_block != block.index - 1):
        error = ("G53_1_REQUIRES_G68_2", "G53.1 must immediately follow G68.2")
    return (
        error
        or _milling_reference_mode_error(ctx.state, codes.all_g, words)
        or _milling_tcp_mode_error(ctx.state, codes.all_g, words)
    )


def _native_frame_index(ctx, evaluated_block):
    """Pure rapid machine-axis indexing leaves the Siemens frame active."""
    words, gcodes = evaluated_block.words, evaluated_block.codes.all_g
    move = next((g for g in reversed(gcodes) if g in (0, 1, 2, 3)), ctx.state.move)
    return (
        ctx.runtime.controller_mode == "sinumerik_native"
        and move == 0
        and not any(axis in words for axis in "XYZIJKR")
        and all(g in (0, 90, 91) for g in gcodes)
    )


def _native_rotary_unchanged(ctx, block, evaluated_block):
    """Repeated native rotary targets do not move the table or change its frame."""
    if ctx.runtime.controller_mode != "sinumerik_native":
        return False
    gcodes = evaluated_block.codes.all_g
    if 28 in gcodes:
        return False
    absolute = next((g == 90 for g in reversed(gcodes) if g in (90, 91)), ctx.state.absolute)
    if block.native_syntax is not None and block.native_syntax.supa:
        absolute = True
    return all(
        float(value) == (ctx.state.rotary_angles[axis] if absolute else 0.0)
        for axis, value in evaluated_block.words.items()
        if axis in ("A", "B", "C")
    )


def _milling_reference_mode_error(state, gcodes, words):
    move = next((g for g in reversed(gcodes) if g in (0, 1, 2, 3)), state.move)
    if 53 in gcodes and move not in (0, 1):
        return "UNSUPPORTED_G53_MOTION", "G53 requires rapid G0 or linear G1 machine motion"
    if 28 in gcodes and any(words.get(axis, 0) != 0 for axis in "ABC"):
        return "UNSUPPORTED_REFERENCE_ROTARY_INTERMEDIATE", "G28 nonzero rotary intermediate positions are not modeled"
    return None


def _milling_tcp_mode_error(state, gcodes, words):
    """Reject combinations outside the shared positional TCP model."""
    move = next((g for g in reversed(gcodes) if g in (0, 1, 2, 3)), state.move)
    if state.tcp_control and 49 in gcodes and move not in (0, 1) and any(axis in words for axis in "XYZIJKR"):
        return "UNSUPPORTED_TCP_CANCEL_MOTION", "Cancel G43.4 in G0/G1 mode before circular interpolation"
    active = 43.4 in gcodes or state.tcp_control and not any(g in (43, 49) for g in gcodes)
    if not active:
        return None
    cycle = next(
        (g for g in reversed(gcodes) if g in (0, 1, 2, 3, 73, 74, 76, 80, 81, 82, 83, 84, 85, 86, 87, 89)), state.cycle
    )
    if cycle not in (0, 1, 2, 3, 80):
        return "UNSUPPORTED_TCP_CYCLE", "Cancel TCP before canned drilling cycles"
    compensation = next((g for g in reversed(gcodes) if g in (40, 41, 42)), state.cutter_comp)
    if compensation != 40:
        return "UNSUPPORTED_TCP_CUTTER_COMPENSATION", "TCP cutter compensation is not modeled"
    return None


def _coordinate_preset_outcome(block, evaluated_block, occurrence_events):
    """Validate a standalone G92.1 preset without changing physical position."""
    words, codes, evaluated = evaluated_block.words, evaluated_block.codes, evaluated_block.values
    axes = tuple(axis for axis in "XYZABC" if axis in words)
    if (
        codes.all_g != (92.1,)
        or codes.all_m
        or not axes
        or any(words[axis] != 0 for axis in axes)
        or any(key not in "XYZABCGN" for key in words)
    ):
        return _BlockOutcome(
            action=_BlockAction.STOP,
            diagnostics=(
                Diagnostic(
                    "INVALID_COORDINATE_PRESET",
                    "G92.1 requires a standalone block with zero-valued axis selectors",
                    "error",
                    "malformed",
                    block.index + 1,
                    block.raw,
                ),
            ),
            words=evaluated,
        )
    # Preset cancels manual/G92 shifts, not motion. This interpreter has
    # no manual intervention or accepted G92 shift to undo; keep both
    # physical position and unwrapped rotary joints exactly as they are.
    return _BlockOutcome(
        events=tuple(occurrence_events)
        + (ExecutionEvent("COORDINATE_SYSTEM_PRESET", block.index, code="G92.1", axes=axes),),
        words=evaluated,
    )


def _validate_milling_block(ctx, block, evaluated_block, occurrence_events):
    """Return an early outcome for validation/dispatch, otherwise ``None``."""
    words = evaluated_block.words
    codes = evaluated_block.codes
    evaluated = evaluated_block.values
    if 92.1 in codes.all_g:
        return _coordinate_preset_outcome(block, evaluated_block, occurrence_events)
    conflict_diagnostics = modal_conflict_diagnostics(codes.all_g, "fanuc_mill", block)
    if conflict_diagnostics:
        return _BlockOutcome(
            events=tuple(occurrence_events),
            diagnostics=tuple(conflict_diagnostics),
            words=evaluated,
        )

    error = _milling_transform_error(ctx, block, evaluated_block)
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
    native_wcs = {93, 96, 97, 500, 961, 971} if ctx.runtime.controller_mode == "sinumerik_native" else set()
    unknown_g = tuple(g for g in codes.all_g if g not in MILLING_RECOGNIZED_G_CODES | native_wcs)
    position_words = any(letter in words for letter in ("X", "Y", "Z", "A", "B", "C"))
    _report_unknown_g_codes(block_diagnostics, unknown_g, position_words, block)
    controller = ctx.runtime.controller_mode
    recognized_m = MILLING_RECOGNIZED_M_CODES if controller == "fanuc" else COMMON_ISO_M_CODES
    if controller == "sinumerik_native":
        recognized_m = recognized_m | {19}
    _report_unknown_m_codes(
        block_diagnostics,
        codes.all_m,
        recognized_m,
        block,
        "fanuc_mill" if controller == "fanuc" else controller,
    )
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


def _apply_native_feed(block, state, words):
    if block.native_syntax is not None:
        from .sinumerik_feed import apply_native_feed_state  # pylint: disable=import-outside-toplevel

        apply_native_feed_state(block, state, words)


def _append_milling_state_events(
    ctx,
    block,
    codes,
    occurrence_events,
    *,
    was_twp_active,
    was_tcp_active,
    old_rotary_angles,
):
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
        if not was_tcp_active:
            occurrence_events.append(
                ExecutionEvent(
                    "TCP_CONTROL_ON",
                    block.index,
                    code="G43.4",
                    tool=ctx.state.active_tool,
                    length_offset=ctx.state.tool_length_h,
                    kinematics_profile=(ctx.state.kinematics.id if ctx.state.kinematics else None),
                )
            )
    elif was_tcp_active and not ctx.state.tcp_control:
        occurrence_events.append(
            ExecutionEvent("TCP_CONTROL_OFF", block.index, code="G49" if 49 in codes.all_g else "G43")
        )


def _resolve_unknown_milling_axes(state, words):
    if not state.absolute:
        return

    # Explicit absolute positions also update axes recovered in earlier blocks.
    for letter in ("X", "Y", "Z"):
        if letter not in words:
            continue

        setattr(state, letter.lower(), words[letter] * state.unit_scale)
        state.unknown_axes.discard(letter)


def _apply_milling_block_state(
    ctx,
    block,
    evaluated_block,
    occurrence_events,
    block_diagnostics,
):
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
    was_tcp_active = ctx.state.tcp_control
    old_rotary_angles = tuple(ctx.state.rotary_angles[axis] for axis in ("A", "B", "C"))

    _apply_pre_flow_modal_state(
        ctx.state,
        codes.all_g,
        codes.all_m,
        words,
        wcs_offsets=ctx.wcs_offsets,
        block_index=block.index,
    )
    _apply_native_feed(block, ctx.state, words)
    if any(g in (0, 1, 2, 3) for g in codes.all_g):
        ctx.state.cip_mode = False
    if block.native_syntax is not None and block.native_syntax.cip:
        ctx.state.cip_mode = True
    apply_native_tcp_edge(block, words, ctx.state)

    _append_milling_state_events(
        ctx,
        block,
        codes,
        occurrence_events,
        was_twp_active=was_twp_active,
        was_tcp_active=was_tcp_active,
        old_rotary_angles=old_rotary_angles,
    )

    if not ctx.state.unknown_axes:
        return None

    _resolve_unknown_milling_axes(ctx.state, words)

    return _BlockOutcome(
        events=tuple(occurrence_events),
        signals=evaluated_block.signals,
        diagnostics=tuple(block_diagnostics),
        words=evaluated_block.values,
    )


def _dispatch_milling_program_flow(ctx, block, evaluated_block, occurrence_events, block_diagnostics):
    codes = evaluated_block.codes
    if ctx.runtime.controller_mode != "fanuc":
        # M98 is not a modeled SINUMERIK subprogram call. Warn and ignore it,
        # preserving program-end semantics even when M98 shares an end block.
        codes = replace(codes, all_m=tuple(code for code in codes.all_m if code != 98), mcode=None)
        if not any(code in (2, 30, 99) for code in codes.all_m):
            return None
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


def _rotary_index_error(state, words, gcodes, changed, move, continuous_c, tcp_motion, machine_rapid=False):
    """Diagnose rotary semantics before applying any machine state."""
    message = ""
    if state.kinematics is None:
        code = "ROTARY_KINEMATICS_REQUIRED"
        message = f"Select a kinematics profile to resolve rotary address {', '.join(changed)}"
    elif any(axis not in state.kinematics.addresses for axis in changed):
        code = "UNCONFIGURED_ROTARY_AXIS"
        message = f"Rotary address {', '.join(changed)} is not configured in profile {state.kinematics.id}"
    elif any(axis in words for axis in ("X", "Y", "Z")) and not (continuous_c or tcp_motion or machine_rapid):
        code = "UNSUPPORTED_SIMULTANEOUS_ROTARY_MOTION"
        message = "Rotary and linear motion in one block is not supported"
    elif 28 not in gcodes and move != 0 and not (continuous_c and move == 1) and not tcp_motion:
        code = "UNSUPPORTED_ROTARY_INTERPOLATION"
        message = "Rotary motion requires rapid G0 indexing"
    else:
        code = None
    return code, message


def _cancel_tcp_before_index(state, block, gcodes, events):
    """Rebase the tip at the old rotary position before a cancellation index."""
    if state.tcp_control and any(g in (43, 49) for g in gcodes):
        _cancel_tcp(state)
        events.append(ExecutionEvent("TCP_CONTROL_OFF", block.index))


def _apply_rotary_index(ctx, block, evaluated_block, occurrence_events) -> _BlockOutcome | None:
    words = evaluated_block.words
    codes = evaluated_block.codes
    gcodes = codes.all_g
    rotary = tuple(axis for axis in ("A", "B", "C") if axis in words)
    if not rotary or 65 in gcodes:
        return None
    state = ctx.state
    supa = block.native_syntax is not None and block.native_syntax.supa
    absolute = next((g == 90 for g in reversed(gcodes) if g in (90, 91)), state.absolute)
    if supa:
        absolute = True
    targets = {
        axis: 0.0
        if 28 in gcodes
        else float(words[axis])
        if absolute
        else state.rotary_angles[axis] + float(words[axis])
        for axis in rotary
    }
    changed = tuple(axis for axis in rotary if targets[axis] != state.rotary_angles[axis])
    if supa and (state.kinematics is None or any(axis not in state.kinematics.addresses for axis in rotary)):
        changed = rotary
    if not changed and state.kinematics is not None and set(rotary) <= state.kinematics.addresses:
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
        and not any(g in (43, 49) for g in gcodes)
        and state.kinematics is not None
        and state.kinematics.id in TCP_TABLE_PROFILES
        and 28 not in gcodes
        and 53 not in gcodes
        and move in (0, 1, 2, 3)
    )
    machine_rapid = 28 in gcodes or 53 in gcodes and move == 0
    code, message = _rotary_index_error(state, words, gcodes, rotary, move, continuous_c, tcp_motion, machine_rapid)
    if code is not None:
        return _BlockOutcome(
            action=_BlockAction.STOP,
            events=tuple(occurrence_events),
            diagnostics=(Diagnostic(code, message, "error", "unsupported", block.index + 1, block.raw),),
            words=evaluated_block.values,
        )
    _cancel_tcp_before_index(state, block, gcodes, occurrence_events)
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


def _dispatch_milling_macro(ctx, block, occurrence_events):
    if ctx.runtime.controller_mode == "sinumerik_native":
        node = ctx.program.ast.nodes[ctx.runtime.pc]
        if isinstance(node, SinumerikFlowAstNode):
            return _BlockOutcome(
                action=_BlockAction.JUMP,
                next_pc=native_flow_destination(
                    node, ctx.runtime.pc, ctx.program, ctx.state, ctx.state.native_loop_pairs
                ),
                events=tuple(occurrence_events),
            )
        return None
    flow = ctx.runtime.dispatch_macro(block, ctx.runtime.pc, ctx.program.blocks)
    if flow.handled:
        return _BlockOutcome(
            action=_BlockAction.JUMP,
            next_pc=flow.next_pc,
            events=tuple(occurrence_events),
        )

    return None


def _execute_milling_block(ctx: _MillingExecutionContext, block) -> _BlockOutcome:
    """Run the named milling phases without committing PC or ExecutionStep."""
    occurrence_events: list[ExecutionEvent] = []
    if not ctx.program_started and block.index == ctx.program_start_block:
        occurrence_events.append(program_start_event(block, ctx.program_number))
        ctx.program_started = True

    _, early_outcome = _gate_milling_block(ctx, block, occurrence_events)
    if early_outcome is not None:
        return early_outcome

    early_outcome = _dispatch_milling_macro(ctx, block, occurrence_events)
    if early_outcome is not None:
        return early_outcome

    # Phase 2: evaluate the block once and establish its modal codes.
    evaluated_block = (
        evaluate_native_block(block, ctx.state)
        if ctx.runtime.controller_mode == "sinumerik_native" and block.native_syntax is not None
        else ctx.runtime.evaluate_block(block)
    )
    words = evaluated_block.words
    if words.errors:
        token, error = words.errors[0]
        raise ValueError(f"{error} at line {block.index + 1}: {block.raw} ({token.letter}{token.expr})") from error

    evaluated_block, early_outcome = _gate_milling_block(ctx, block, occurrence_events, evaluated_block)
    if early_outcome is not None:
        return early_outcome

    # Phases 3–5 validate and apply state before program-flow transfer.
    ctx.state.native_spindle_semantics = ctx.runtime.controller_mode == "sinumerik_native"
    early_outcome, prepared = _prepare_milling_block_state(ctx, block, evaluated_block, occurrence_events)
    if early_outcome is not None:
        return early_outcome
    assert prepared is not None

    # Phase 6: execute geometric semantics and return everything for one commit.
    return _finish_milling_block(ctx, block, prepared, occurrence_events)


def _validate_boring_tapping_configuration(state):
    if not math.isfinite(state.tapping_retract_distance) or state.tapping_retract_distance <= 0:
        raise ValueError("Tapping retract distance must be finite and positive")
    direction = state.boring_shift_direction
    if (
        len(direction) != 3
        or not all(math.isfinite(value) for value in direction)
        or direction[2] != 0
        or not math.isclose(math.hypot(*direction[:2]), 1.0)
    ):
        raise ValueError("Boring shift direction must be a finite unit vector in the XY plane")


def execute_milling(
    source: str,
    *,
    skip_optional_blocks: bool = False,
    default_unit_scale: float = 1.0,
    home: tuple[float, float, float] = (0.0, 0.0, 0.0),
    wcs_offsets: dict[int, tuple[float, float, float]] | None = None,
    g73_retract_distance: float = 1.0,
    g83_clearance: float = 1.0,
    boring_shift_direction: tuple[float, float, float] = (-1.0, 0.0, 0.0),
    tapping_retract_distance: float = 1.0,
    tapping_full_retract: bool = False,
    include_instructions: bool = True,
    kinematics: MachineKinematics | None = None,
    source_dialect: str = "fanuc",
    sinumerik_840d_sl: bool = True,
    tool_resolver=None,
):

    definition, fingerprint = kinematics_snapshot(kinematics)
    program = parse_sinumerik_program(source) if source_dialect == "sinumerik" else parse_program(source)
    resolve_program_tools(program, None, tool_resolver)
    program_start_block, program_number = main_program_location(program)
    ox, oy, oz = _wcs_offset(wcs_offsets, 54)
    state = MillState(
        native_feed_scale=default_unit_scale,
        kinematics=kinematics,
        x=home[0] - ox,
        y=home[1] - oy,
        z=home[2] - oz,
        unit_scale=float(default_unit_scale),
        source_arc_type=1 if source_dialect == "sinumerik" else None,
        g73_retract_distance=float(g73_retract_distance),
        g83_clearance=float(g83_clearance),
        boring_shift_direction=tuple(boring_shift_direction),
        tapping_retract_distance=float(tapping_retract_distance),
        tapping_full_retract=bool(tapping_full_retract),
        sinumerik_840d_sl=sinumerik_840d_sl,
    )
    motions: list[TraceMotion] = []
    diagnostics: list[Diagnostic] = []
    executed: list[int] = []
    steps: list[ExecutionStep] = []
    signals = []
    events: list[ExecutionEvent] = []
    runtime = ProgramRuntime.create(program)
    runtime.controller_mode = "sinumerik_native" if source_dialect == "sinumerik" else "fanuc"
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
    )
    contains_rotary = source_dialect == "fanuc" and any(
        any(token.letter in ("A", "B", "C") for token in block.parsed_words) for block in program.blocks
    )
    stopped_due_error = False

    try:
        _validate_g73_retract_distance(state.g73_retract_distance)
        _validate_boring_tapping_configuration(state)
        if source_dialect == "sinumerik":
            state.native_loop_pairs = build_native_loop_maps(program)
        _validate_g83_clearance(state.g83_clearance)
        while 0 <= runtime.pc < len(program.blocks):
            simple_blocks_available = (
                not contains_rotary
                and state.spindle_mode != "css"
                and not state.twp.active
                and not state.tcp_control
                and kinematics is None
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
            try:
                outcome = _execute_milling_block(ctx, block)
            except SemanticError as error:
                raise SemanticError(error.code, f"{error} at line {block.index + 1}", error.status) from error
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
        if isinstance(exc, SemanticError) and " at line " not in str(exc) and "line " not in str(exc):
            line = program.blocks[min(runtime.pc, len(program.blocks) - 1)].index + 1 if program.blocks else 1
            exc = SemanticError(exc.code, f"{exc} at line {line}", exc.status)
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
            kinematics_definition=definition,
            kinematics_fingerprint=fingerprint,
            source_dialect=source_dialect,
            sinumerik_840d_sl=sinumerik_840d_sl,
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
        kinematics_definition=definition,
        kinematics_fingerprint=fingerprint,
        source_dialect=source_dialect,
        sinumerik_840d_sl=sinumerik_840d_sl,
    )
