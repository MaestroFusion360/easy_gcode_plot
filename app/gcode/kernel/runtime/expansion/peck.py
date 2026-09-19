"""Turning peck-drilling/peck-grooving expansion (G74/G75)."""

from __future__ import annotations

from ...frontend.program import scaled_word, scaled_word_or, x_delta_to_diameter, x_value_to_diameter
from ...lathe_cycles import build_g74_cycle, build_g75_cycle


def _expand_g74(_cycle_least_input_or_length_to_mm, _word_expr, block, gcode, rough_cycles, state, words):
    if gcode == 74:
        if "X" not in words and "Z" not in words and "R" in words:
            assert state.g74_first is not None
            state.g74_first.valid = True
            state.g74_first.retract_r = abs(scaled_word(words, "R", state.unit_scale))
        elif any(k in words for k in ("X", "U", "Z", "W")):
            assert state.g74_first is not None
            retract = state.g74_first.retract_r if state.g74_first.valid else 0.0
            tx = (
                x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
                if "X" in words
                else (
                    state.modal_x + x_delta_to_diameter(words.get("U", 0.0) * state.unit_scale, state.x_is_diameter)
                    if "U" in words
                    else None
                )
            )
            tz = (
                scaled_word(words, "Z", state.unit_scale)
                if "Z" in words
                else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else None)
            )
            p_step = _cycle_least_input_or_length_to_mm(words.get("P", 0.0), state.unit_scale, _word_expr(block, "P"))
            q_step = _cycle_least_input_or_length_to_mm(words.get("Q", 0.0), state.unit_scale, _word_expr(block, "Q"))
            bottom = _cycle_least_input_or_length_to_mm(
                words.get("R", 0.0),
                state.unit_scale,
                _word_expr(block, "R"),
            )
            cycle_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
            cyc = build_g74_cycle(
                state.modal_x,
                state.modal_z,
                tx,
                tz,
                retract,
                p_step,
                q_step,
                bottom,
                cycle_feed,
            )
            rough_cycles.append(cyc)
            if cyc:
                state.modal_x = cyc[-1].end.x
                state.modal_z = cyc[-1].end.z


def _expand_g75(_cycle_least_input_or_length_to_mm, _word_expr, block, gcode, rough_cycles, state, words):
    if gcode == 75:
        if "X" not in words and "Z" not in words and "R" in words:
            assert state.g75_first is not None
            state.g75_first.valid = True
            state.g75_first.retract_r = abs(scaled_word(words, "R", state.unit_scale))
        elif "X" in words or "U" in words:
            assert state.g75_first is not None
            retract = state.g75_first.retract_r if state.g75_first.valid else 0.0
            tx = (
                x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
                if "X" in words
                else (state.modal_x + x_delta_to_diameter(words.get("U", 0.0) * state.unit_scale, state.x_is_diameter))
            )
            tz = (
                scaled_word(words, "Z", state.unit_scale)
                if "Z" in words
                else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else None)
            )
            p_step = _cycle_least_input_or_length_to_mm(words.get("P", 0.0), state.unit_scale, _word_expr(block, "P"))
            q_step = _cycle_least_input_or_length_to_mm(words.get("Q", 0.0), state.unit_scale, _word_expr(block, "Q"))
            bottom = _cycle_least_input_or_length_to_mm(
                words.get("R", 0.0),
                state.unit_scale,
                _word_expr(block, "R"),
            )
            cycle_feed = scaled_word_or(words, "F", state.modal_feed, state.unit_scale)
            cyc = build_g75_cycle(
                state.modal_x,
                state.modal_z,
                tx,
                tz,
                retract,
                p_step,
                q_step,
                bottom,
                cycle_feed,
            )
            rough_cycles.append(cyc)
            if cyc:
                state.modal_x = cyc[-1].end.x
                state.modal_z = cyc[-1].end.z
