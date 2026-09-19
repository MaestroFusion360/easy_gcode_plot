"""Turning drilling/simple-cycle expansion (G83/G84)."""

from __future__ import annotations

from ...frontend.program import scaled_word, scaled_word_or, x_delta_to_diameter, x_value_to_diameter
from ...lathe_cycles import build_g83_cycle, build_g84_cycle


def _expand_g83(_cycle_least_input_or_length_to_mm, _word_expr, block, gcode, rough_cycles, state, words):
    cycle_line_consumed = False
    can_continue_g83 = state.active_g83_cycle and gcode is None and any(k in words for k in ("X", "U", "Z", "W"))
    is_g83_cycle_line = (gcode == 83 and any(k in words for k in ("X", "U", "Z", "W"))) or can_continue_g83
    if is_g83_cycle_line:
        cycle_line_consumed = True
        if gcode == 83:
            state.active_g83_cycle = True
            state.active_g84_cycle = False
            state.active_g80 = False
            state.g83_step_q = 0.0
            if "R" in words:
                state.g83_retract_r = abs(scaled_word(words, "R", state.unit_scale))
            if "Q" in words:
                state.g83_step_q = _cycle_least_input_or_length_to_mm(
                    words["Q"], state.unit_scale, _word_expr(block, "Q")
                )
            if "P" in words:
                state.g83_dwell_p = abs(words["P"])
            state.g83_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
        else:
            if "R" in words:
                state.g83_retract_r = abs(scaled_word(words, "R", state.unit_scale))
            if "Q" in words:
                state.g83_step_q = _cycle_least_input_or_length_to_mm(
                    words["Q"], state.unit_scale, _word_expr(block, "Q")
                )
            if "P" in words:
                state.g83_dwell_p = abs(words["P"])
            if "F" in words:
                state.g83_feed = scaled_word(words, "F", state.unit_scale)

        tx = (
            x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
            if "X" in words
            else (
                state.modal_x + x_delta_to_diameter(scaled_word(words, "U", state.unit_scale), state.x_is_diameter)
                if "U" in words
                else state.modal_x
            )
        )
        tz = (
            scaled_word(words, "Z", state.unit_scale)
            if "Z" in words
            else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else state.modal_z)
        )
        cyc = build_g83_cycle(
            state.modal_x,
            state.modal_z,
            tx,
            tz,
            state.g83_retract_r,
            state.g83_step_q,
            state.g83_dwell_p,
            state.g83_feed,
        )
        rough_cycles.append(cyc)
        if cyc:
            state.modal_x = cyc[-1].end.x
            state.modal_z = cyc[-1].end.z

    return cycle_line_consumed


def _expand_g84(_cycle_least_input_or_length_to_mm, _word_expr, block, gcode, rough_cycles, state, words):
    cycle_line_consumed = False
    can_continue_g84 = state.active_g84_cycle and gcode is None and any(k in words for k in ("X", "U", "Z", "W"))
    is_g84_cycle_line = (gcode == 84 and any(k in words for k in ("X", "U", "Z", "W"))) or can_continue_g84
    if is_g84_cycle_line:
        cycle_line_consumed = True
        if gcode == 84:
            state.active_g84_cycle = True
            state.active_g83_cycle = False
            state.active_g80 = False
            state.g84_step_q = 0.0
            if "R" in words:
                state.g84_retract_r = abs(scaled_word(words, "R", state.unit_scale))
            if "Q" in words:
                state.g84_step_q = _cycle_least_input_or_length_to_mm(
                    words["Q"], state.unit_scale, _word_expr(block, "Q")
                )
            if "P" in words:
                state.g84_dwell_p = abs(words["P"])
            state.g84_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
        else:
            if "R" in words:
                state.g84_retract_r = abs(scaled_word(words, "R", state.unit_scale))
            if "Q" in words:
                state.g84_step_q = _cycle_least_input_or_length_to_mm(
                    words["Q"], state.unit_scale, _word_expr(block, "Q")
                )
            if "P" in words:
                state.g84_dwell_p = abs(words["P"])
            if "F" in words:
                state.g84_feed = scaled_word(words, "F", state.unit_scale)

        tx = (
            x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
            if "X" in words
            else (
                state.modal_x + x_delta_to_diameter(scaled_word(words, "U", state.unit_scale), state.x_is_diameter)
                if "U" in words
                else state.modal_x
            )
        )
        tz = (
            scaled_word(words, "Z", state.unit_scale)
            if "Z" in words
            else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else state.modal_z)
        )
        cyc = build_g84_cycle(
            state.modal_x,
            state.modal_z,
            tx,
            tz,
            state.g84_retract_r,
            state.g84_step_q,
            state.g84_dwell_p,
            state.g84_feed,
        )
        rough_cycles.append(cyc)
        if cyc:
            state.modal_x = cyc[-1].end.x
            state.modal_z = cyc[-1].end.z

    return cycle_line_consumed
