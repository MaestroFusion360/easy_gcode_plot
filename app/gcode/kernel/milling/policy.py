"""Controller-specific milling capability and modal compatibility checks."""

from __future__ import annotations

import math

from ..api.types import Diagnostic, ExecutionEvent
from ..runtime.capabilities import COMMON_ISO_M_CODES
from ..runtime.diagnostics import modal_conflict_diagnostics
from .block import _BlockAction, _BlockOutcome
from .kinematics import TCP_TABLE_PROFILES
from .state import MillState, _apply_pre_flow_modal_state

MILLING_RECOGNIZED_M_CODES = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 19, 29, 30, 98, 99})


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
