from __future__ import annotations

from dataclasses import replace
from functools import partial

from ...compensation.turning import compensate_profile_segments
from ...frontend.program import eval_words
from ..execution import apply_unit_mode, classify_block_codes, retain_modal_turning_cycles
from .drilling import _expand_g83, _expand_g84
from .finishing import _expand_g70
from .peck import _expand_g74, _expand_g75
from .roughing import _expand_g71, _expand_g72, _expand_g73
from .threading import _expand_g76, _expand_g92
from .turning import _expand_g90, _expand_g94


def _cycle_length_to_mm(value, unit_scale, expr=None, *, pq_mm=False):
    raw = abs(value * unit_scale)
    if pq_mm or (expr is not None and ("." in expr or "E" in expr.upper())):
        return raw
    increment_mm = 0.001 if abs(unit_scale - 1.0) <= 1e-12 else (0.0001 * 25.4)
    return abs(value) * increment_mm


def _word_expr(block, letter):
    for token in reversed(block.parsed_words):
        if token.letter.upper() == letter.upper():
            return token.expr
    return None


def _profile_compensation_modes(blocks, state, variables, p_index, q_index):
    mode = state.compensation_mode
    modes = {}
    for profile_index in range(p_index, q_index + 1):
        profile_words = eval_words(blocks[profile_index].parsed_words, dict(variables or {}))
        profile_codes = classify_block_codes(profile_words)
        if 40 in profile_codes.all_g:
            mode = 40
        elif 41 in profile_codes.all_g:
            mode = 41
        elif 42 in profile_codes.all_g:
            mode = 42
        modes[profile_index] = mode
    return modes


def _compensated_profile(profile, p_index, q_index, *, blocks, state, tools, variables, roughing_side=None):
    if not tools:
        return profile, False
    modes = _profile_compensation_modes(blocks, state, variables, p_index, q_index)
    if roughing_side is not None and not any(mode in (41, 42) for mode in modes.values()):
        tool = tools.get(state.active_tool or "", {})
        if float(tool.get("noseRadius", 0.0)) > 0.0:
            modes = {index: roughing_side for index in modes}
    active = any(mode in (41, 42) for mode in modes.values())
    return (
        compensate_profile_segments(
            profile,
            compensation_mode=state.compensation_mode,
            compensation_modes=modes,
            tool_code=state.active_tool,
            tools=tools,
        ),
        active,
    )


def _mark_compensated(motions, profile_was_compensated, *, tools):
    if not tools or not profile_was_compensated:
        return motions
    return [replace(motion, compensation_applied=True) for motion in motions]


def expand_cycle_block(
    program,
    pc,
    words,
    state,
    *,
    supplementary_angles=False,
    pq_mm_for_g74758384=False,
    tools=None,
    variables=None,
    gcode_system="A",
    distance_absolute=True,
):
    """Expand one already evaluated occurrence; never execute Macro B or flow."""

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

    cycle_length_to_mm = partial(_cycle_length_to_mm, pq_mm=pq_mm_for_g74758384)
    compensated_profile = partial(_compensated_profile, blocks=blocks, state=state, tools=tools, variables=variables)
    mark_compensated = partial(_mark_compensated, tools=tools)

    # Apply every modal G word in the block, not only the last one.
    # This is required for normal safety blocks such as G18G21G40G54G80G99.
    apply_unit_mode(state, all_g)

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

    cycle_line_consumed |= _expand_g83(cycle_length_to_mm, _word_expr, block, gcode, rough_cycles, state, words)

    cycle_line_consumed |= _expand_g84(cycle_length_to_mm, _word_expr, block, gcode, rough_cycles, state, words)

    _expand_g71(
        blocks,
        compensated_profile,
        gcode,
        mark_compensated,
        pc,
        rough_cycles,
        state,
        supplementary_angles,
        words,
        variables,
        gcode_system,
        distance_absolute,
    )

    _expand_g72(
        blocks,
        compensated_profile,
        gcode,
        mark_compensated,
        pc,
        rough_cycles,
        state,
        supplementary_angles,
        words,
        variables,
        gcode_system,
        distance_absolute,
    )

    _expand_g73(
        blocks,
        compensated_profile,
        gcode,
        mark_compensated,
        pc,
        rough_cycles,
        state,
        supplementary_angles,
        words,
        variables,
        gcode_system,
        distance_absolute,
    )

    _expand_g74(cycle_length_to_mm, _word_expr, block, gcode, rough_cycles, state, words)

    _expand_g75(cycle_length_to_mm, _word_expr, block, gcode, rough_cycles, state, words)

    _expand_g76(gcode, rough_cycles, state, words)

    _expand_g70(
        blocks,
        compensated_profile,
        finish_cycles,
        gcode,
        mark_compensated,
        pc,
        state,
        supplementary_angles,
        words,
        variables,
        gcode_system,
        distance_absolute,
    )

    return rough_cycles, finish_cycles
