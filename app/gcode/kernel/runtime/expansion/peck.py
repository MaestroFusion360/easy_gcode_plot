"""Turning peck-drilling/peck-grooving expansion (G74/G75)."""

from __future__ import annotations

from collections.abc import Callable

from ...frontend.model import Motion
from ...frontend.program import scaled_word, scaled_word_or, x_delta_to_diameter, x_value_to_diameter
from ...turning.cycles import build_g74_cycle, build_g75_cycle


def _peck_target_x(state, words, *, optional: bool) -> float | None:
    if "X" in words:
        return x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
    if "U" in words:
        return state.modal_x + x_delta_to_diameter(words["U"] * state.unit_scale, state.x_is_diameter)
    return None if optional else state.modal_x


def _peck_target_z(state, words) -> float | None:
    if "Z" in words:
        return scaled_word(words, "Z", state.unit_scale)
    if "W" in words:
        return state.modal_z + scaled_word(words, "W", state.unit_scale)
    return None


def _expand_peck_cycle(
    cycle_least_input_or_length_to_mm,
    word_expr,
    block,
    gcode,
    rough_cycles,
    state,
    words,
    *,
    code: int,
    builder: Callable[..., list[Motion]],
    execute_words: tuple[str, ...],
    optional_x: bool,
) -> None:
    if gcode != code:
        return
    first = getattr(state, f"g{code}_first")
    assert first is not None
    if "X" not in words and "Z" not in words and "R" in words:
        first.valid = True
        first.retract_r = abs(scaled_word(words, "R", state.unit_scale))
        return
    if not any(key in words for key in execute_words):
        return

    retract = first.retract_r if first.valid else 0.0
    target_x = _peck_target_x(state, words, optional=optional_x)
    target_z = _peck_target_z(state, words)
    step_p = cycle_least_input_or_length_to_mm(words.get("P", 0.0), state.unit_scale, word_expr(block, "P"))
    step_q = cycle_least_input_or_length_to_mm(words.get("Q", 0.0), state.unit_scale, word_expr(block, "Q"))
    bottom = cycle_least_input_or_length_to_mm(words.get("R", 0.0), state.unit_scale, word_expr(block, "R"))
    feed = scaled_word_or(words, "F", state.feed, state.unit_scale)
    cycle = builder(
        state.modal_x,
        state.modal_z,
        target_x,
        target_z,
        retract,
        step_p,
        step_q,
        bottom,
        feed,
    )
    rough_cycles.append(cycle)
    if cycle:
        state.modal_x = cycle[-1].end.x
        state.modal_z = cycle[-1].end.z


def _expand_g74(cycle_least_input_or_length_to_mm, word_expr, block, gcode, rough_cycles, state, words):
    _expand_peck_cycle(
        cycle_least_input_or_length_to_mm,
        word_expr,
        block,
        gcode,
        rough_cycles,
        state,
        words,
        code=74,
        builder=build_g74_cycle,
        execute_words=("X", "U", "Z", "W"),
        optional_x=True,
    )


def _expand_g75(cycle_least_input_or_length_to_mm, word_expr, block, gcode, rough_cycles, state, words):
    _expand_peck_cycle(
        cycle_least_input_or_length_to_mm,
        word_expr,
        block,
        gcode,
        rough_cycles,
        state,
        words,
        code=75,
        builder=build_g75_cycle,
        execute_words=("X", "U"),
        optional_x=False,
    )
