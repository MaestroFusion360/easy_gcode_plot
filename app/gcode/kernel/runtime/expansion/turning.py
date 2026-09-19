"""Modal turning-cycle expansion (G90/G92/G94)."""

from __future__ import annotations

from ...frontend.model import Motion, Point2
from ...frontend.program import scaled_word, scaled_word_or, x_delta_to_diameter, x_value_to_diameter
from ...lathe_cycles import add_g90_longitudinal_pass, add_g92_thread_pass, add_g94_facing_pass, ensure_cycle_return


def _expand_g90(gcode, rough_cycles, state, words):
    cycle_line_consumed = False
    can_continue_g90 = state.active_g90_cycle and gcode is None and ("X" in words or "U" in words)
    is_g90_cycle_line = (gcode == 90 and ("X" in words or "U" in words)) or can_continue_g90
    if is_g90_cycle_line:
        cycle_line_consumed = True
        if gcode == 90:
            state.active_g90_cycle = True
            state.g90_start_x = state.modal_x
            state.g90_start_z = state.modal_z
            state.g90_target_z = (
                scaled_word(words, "Z", state.unit_scale)
                if "Z" in words
                else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else state.modal_z)
            )
            state.g90_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
            state.g90_last_x = state.modal_x
        else:
            if "Z" in words:
                state.g90_target_z = scaled_word(words, "Z", state.unit_scale)
            elif "W" in words:
                state.g90_target_z = state.g90_target_z + scaled_word(words, "W", state.unit_scale)
            if "F" in words:
                state.g90_feed = scaled_word(words, "F", state.unit_scale)

        target_x = (
            x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
            if "X" in words
            else (
                state.g90_last_x + x_delta_to_diameter(scaled_word(words, "U", state.unit_scale), state.x_is_diameter)
            )
        )
        cyc: list[Motion] = []
        add_g90_longitudinal_pass(
            cyc,
            state.g90_start_x,
            state.g90_start_z,
            target_x,
            state.g90_target_z,
            state.g90_feed,
            first_block_with_z=(gcode == 90 and ("Z" in words or "W" in words)),
        )
        ensure_cycle_return(cyc, Point2(state.g90_start_x, state.g90_start_z))
        rough_cycles.append(cyc)
        state.g90_last_x = target_x
        if cyc:
            state.modal_x = cyc[-1].end.x
            state.modal_z = cyc[-1].end.z

    return cycle_line_consumed


def _expand_g92(gcode, rough_cycles, state, words):
    cycle_line_consumed = False
    can_continue_g92 = state.active_g92_cycle and gcode is None and ("X" in words or "U" in words)
    is_g92_cycle_line = (gcode == 92 and ("X" in words or "U" in words)) or can_continue_g92
    if is_g92_cycle_line:
        cycle_line_consumed = True
        if gcode == 92:
            state.active_g92_cycle = True
            state.g92_start_x = state.modal_x
            state.g92_start_z = state.modal_z
            state.g92_target_z = (
                scaled_word(words, "Z", state.unit_scale)
                if "Z" in words
                else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else state.modal_z)
            )
            state.g92_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
            state.g92_last_x = state.modal_x
        else:
            if "Z" in words:
                state.g92_target_z = scaled_word(words, "Z", state.unit_scale)
            elif "W" in words:
                state.g92_target_z = state.g92_target_z + scaled_word(words, "W", state.unit_scale)
            if "F" in words:
                state.g92_feed = scaled_word(words, "F", state.unit_scale)

        target_x = (
            x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
            if "X" in words
            else (
                state.g92_last_x + x_delta_to_diameter(scaled_word(words, "U", state.unit_scale), state.x_is_diameter)
            )
        )
        cyc: list[Motion] = []
        add_g92_thread_pass(
            cyc,
            state.g92_start_x,
            state.g92_start_z,
            target_x,
            state.g92_target_z,
            state.g92_feed,
        )
        ensure_cycle_return(cyc, Point2(state.g92_start_x, state.g92_start_z))
        rough_cycles.append(cyc)
        state.g92_last_x = target_x
        if cyc:
            state.modal_x = cyc[-1].end.x
            state.modal_z = cyc[-1].end.z

    return cycle_line_consumed


def _expand_g94(gcode, rough_cycles, state, words):
    cycle_line_consumed = False
    can_continue_g94 = state.active_g94_cycle and gcode is None and ("Z" in words or "W" in words)
    is_g94_cycle_line = (gcode == 94 and ("X" in words or "U" in words)) or can_continue_g94
    if is_g94_cycle_line:
        cycle_line_consumed = True
        if gcode == 94:
            state.active_g94_cycle = True
            state.g94_start_x = state.modal_x
            state.g94_start_z = state.modal_z
            state.g94_target_x = (
                x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
                if "X" in words
                else (
                    state.modal_x
                    + x_delta_to_diameter(
                        scaled_word(words, "U", state.unit_scale),
                        state.x_is_diameter,
                    )
                )
            )
            state.g94_target_z = (
                scaled_word(words, "Z", state.unit_scale)
                if "Z" in words
                else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else state.modal_z)
            )
            state.g94_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
        else:
            if "Z" in words:
                state.g94_target_z = scaled_word(words, "Z", state.unit_scale)
            elif "W" in words:
                state.g94_target_z = state.g94_target_z + scaled_word(words, "W", state.unit_scale)
            if "F" in words:
                state.g94_feed = scaled_word(words, "F", state.unit_scale)

        cyc: list[Motion] = []
        add_g94_facing_pass(
            cyc,
            state.g94_start_x,
            state.g94_start_z,
            state.g94_target_x,
            state.g94_target_z,
            state.g94_feed,
            first_block_with_z=(gcode == 94 and ("Z" in words or "W" in words)),
        )
        ensure_cycle_return(cyc, Point2(state.g94_start_x, state.g94_start_z))
        rough_cycles.append(cyc)
        if cyc:
            state.modal_x = cyc[-1].end.x
            state.modal_z = cyc[-1].end.z

    return cycle_line_consumed
