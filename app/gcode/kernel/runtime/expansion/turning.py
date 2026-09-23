"""Modal non-threading turning-cycle expansion (G90/G94)."""

from __future__ import annotations

from ...frontend.model import Motion, Point2
from ...frontend.program import scaled_word, scaled_word_or, x_delta_to_diameter, x_value_to_diameter
from ...turning.cycles import add_g90_longitudinal_pass, add_g94_facing_pass, ensure_cycle_return
from .simple import expand_longitudinal_cycle


def _expand_g90(gcode, rough_cycles, state, words):
    return expand_longitudinal_cycle(
        gcode,
        rough_cycles,
        state,
        words,
        code=90,
        add_pass=add_g90_longitudinal_pass,
        first_block_direct=True,
    )


def _expand_g94(gcode, rough_cycles, state, words):
    continuation = state.active_g94_cycle and gcode is None and ("Z" in words or "W" in words)
    explicit = gcode == 94 and ("X" in words or "U" in words)
    if not (explicit or continuation):
        return False

    if explicit:
        state.active_g94_cycle = True
        state.g94_start_x = state.modal_x
        state.g94_start_z = state.modal_z
        state.g94_target_x = (
            x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
            if "X" in words
            else state.modal_x + x_delta_to_diameter(scaled_word(words, "U", state.unit_scale), state.x_is_diameter)
        )
        state.g94_target_z = (
            scaled_word(words, "Z", state.unit_scale)
            if "Z" in words
            else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else state.modal_z)
        )
        state.g94_feed = scaled_word_or(words, "F", state.feed, state.unit_scale)
    else:
        if "Z" in words:
            state.g94_target_z = scaled_word(words, "Z", state.unit_scale)
        elif "W" in words:
            state.g94_target_z += scaled_word(words, "W", state.unit_scale)
        if "F" in words:
            state.g94_feed = scaled_word(words, "F", state.unit_scale)

    cycle: list[Motion] = []
    add_g94_facing_pass(
        cycle,
        state.g94_start_x,
        state.g94_start_z,
        state.g94_target_x,
        state.g94_target_z,
        state.g94_feed,
        first_block_with_z=explicit and ("Z" in words or "W" in words),
    )
    ensure_cycle_return(cycle, Point2(state.g94_start_x, state.g94_start_z))
    rough_cycles.append(cycle)
    if cycle:
        state.modal_x = cycle[-1].end.x
        state.modal_z = cycle[-1].end.z
    return True
