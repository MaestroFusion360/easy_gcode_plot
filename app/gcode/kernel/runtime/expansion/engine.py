from __future__ import annotations

from dataclasses import replace

from ...compensation.turning import compensate_profile_segments
from ...frontend.program import eval_words, scaled_word, x_delta_to_diameter, x_value_to_diameter
from ..execution import classify_block_codes, retain_modal_turning_cycles
from .drilling import _expand_g83, _expand_g84
from .finishing import _expand_g70
from .peck import _expand_g74, _expand_g75
from .roughing import _expand_g71, _expand_g72, _expand_g73
from .threading import _expand_g76
from .turning import _expand_g90, _expand_g92, _expand_g94


def expand_cycle_block(
    program,
    pc,
    words,
    state,
    *,
    supplementary_angles=False,
    pq_mm_for_g74758384=False,
    tools=None,
):
    """Expand one already evaluated occurrence; never execute Macro B or flow."""

    def _cycle_least_input_or_length_to_mm(value: float, unit_scale: float, expr: str | None = None) -> float:
        raw = abs(value * unit_scale)
        if pq_mm_for_g74758384:
            return raw
        # FANUC commonly programs P/Q as integer least-input increments.  Some
        # CAM posts (including the CncKernelCli donor fixtures) intentionally
        # emit decimal words such as P3. Q3. R1. to mean direct length units.
        # Use lexical precision rather than a value-magnitude heuristic.
        if expr is not None and ("." in expr or "E" in expr.upper()):
            return raw
        increment_mm = 0.001 if abs(unit_scale - 1.0) <= 1e-12 else (0.0001 * 25.4)
        return abs(value) * increment_mm

    def _word_expr(block, letter: str) -> str | None:
        for token in reversed(block.parsed_words):
            if token.letter.upper() == letter.upper():
                return token.expr
        return None

    blocks = program.blocks
    block = blocks[pc]
    rough_cycles = []
    finish_cycles = []
    codes = classify_block_codes(words)
    all_g = codes.all_g
    gcode = codes.gcode
    cycle_line_consumed = False
    if 40 in all_g:
        state.compensation_mode = 40
    elif 41 in all_g:
        state.compensation_mode = 41
    elif 42 in all_g:
        state.compensation_mode = 42
    if "T" in words:
        state.active_tool = f"T{abs(int(round(words['T']))):04d}"

    def profile_compensation_modes(p_index: int, q_index: int) -> dict[int, int]:
        mode = state.compensation_mode
        modes: dict[int, int] = {}
        for profile_index in range(p_index, q_index + 1):
            profile_words = eval_words(blocks[profile_index].parsed_words, state.clone_vars())
            profile_codes = classify_block_codes(profile_words)
            if 40 in profile_codes.all_g:
                mode = 40
            elif 41 in profile_codes.all_g:
                mode = 41
            elif 42 in profile_codes.all_g:
                mode = 42
            modes[profile_index] = mode
        return modes

    def compensated_profile(profile, p_index: int, q_index: int):
        if not tools:
            return profile, False
        modes = profile_compensation_modes(p_index, q_index)
        active = any(mode in (41, 42) for mode in modes.values())
        return (
            compensate_profile_segments(
                profile,
                compensation_mode=state.compensation_mode,
                compensation_modes=modes,
                tool_code=state.active_tool,
                tools=tools or {},
            ),
            active,
        )

    def mark_compensated(motions, profile_was_compensated: bool):
        if not tools or not profile_was_compensated:
            return motions
        return [replace(motion, compensation_applied=True) for motion in motions]

    # Apply every modal G word in the block, not only the last one.
    # This is required for normal safety blocks such as G18G21G40G54G80G99.
    if 20 in all_g:
        state.unit_scale = 25.4
    if 21 in all_g:
        state.unit_scale = 1.0
    if 190 in all_g:
        state.x_is_diameter = True
    if 191 in all_g:
        state.x_is_diameter = False

    (
        state.active_g90_cycle,
        state.active_g92_cycle,
        state.active_g94_cycle,
    ) = retain_modal_turning_cycles(
        all_g,
        active_g90=state.active_g90_cycle,
        active_g92=state.active_g92_cycle,
        active_g94=state.active_g94_cycle,
    )
    if "T" in words:
        state.active_g83_cycle = False
        state.active_g84_cycle = False
        state.active_g80 = True
    if 80 in all_g:
        state.active_g83_cycle = False
        state.active_g84_cycle = False
        state.active_g80 = True

    cycle_line_consumed |= _expand_g90(gcode, rough_cycles, state, words)

    cycle_line_consumed |= _expand_g92(gcode, rough_cycles, state, words)

    cycle_line_consumed |= _expand_g94(gcode, rough_cycles, state, words)

    cycle_line_consumed |= _expand_g83(
        _cycle_least_input_or_length_to_mm, _word_expr, block, gcode, rough_cycles, state, words
    )

    cycle_line_consumed |= _expand_g84(
        _cycle_least_input_or_length_to_mm, _word_expr, block, gcode, rough_cycles, state, words
    )

    _expand_g71(
        blocks, compensated_profile, gcode, mark_compensated, pc, rough_cycles, state, supplementary_angles, words
    )

    _expand_g72(
        blocks, compensated_profile, gcode, mark_compensated, pc, rough_cycles, state, supplementary_angles, words
    )

    _expand_g73(
        blocks, compensated_profile, gcode, mark_compensated, pc, rough_cycles, state, supplementary_angles, words
    )

    _expand_g74(_cycle_least_input_or_length_to_mm, _word_expr, block, gcode, rough_cycles, state, words)

    _expand_g75(_cycle_least_input_or_length_to_mm, _word_expr, block, gcode, rough_cycles, state, words)

    _expand_g76(gcode, rough_cycles, state, words)

    _expand_g70(
        blocks, compensated_profile, finish_cycles, gcode, mark_compensated, pc, state, supplementary_angles, words
    )

    cycle_pos_locked = cycle_line_consumed or gcode in (
        70,
        71,
        72,
        73,
        74,
        75,
        76,
        83,
        84,
        90,
        92,
        94,
    )
    if "X" in words and not cycle_pos_locked:
        state.modal_x = x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
    elif "U" in words and gcode not in (70, 71, 72, 73, 74, 75, 76, 83, 84, 90, 92):
        state.modal_x += x_delta_to_diameter(scaled_word(words, "U", state.unit_scale), state.x_is_diameter)
    if "Z" in words and not cycle_pos_locked:
        state.modal_z = scaled_word(words, "Z", state.unit_scale)
    elif "W" in words and gcode not in (70, 71, 72, 73, 74, 75, 76, 83, 84, 90, 92):
        state.modal_z += scaled_word(words, "W", state.unit_scale)
    if "F" in words:
        state.modal_feed = scaled_word(words, "F", state.unit_scale)

    return rough_cycles, finish_cycles
