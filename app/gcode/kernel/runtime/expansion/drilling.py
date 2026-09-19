"""Turning drilling/simple-cycle expansion (G83/G84)."""

from __future__ import annotations

from collections.abc import Callable

from ...frontend.model import Motion
from ...frontend.program import scaled_word, scaled_word_or, x_delta_to_diameter, x_value_to_diameter
from ...lathe_cycles import build_g83_cycle, build_g84_cycle

_AXIS_WORDS = ("X", "U", "Z", "W")


def _update_axial_cycle_parameters(
    cycle_least_input_or_length_to_mm,
    word_expr,
    block,
    state,
    words,
    *,
    prefix: str,
    explicit: bool,
) -> None:
    if explicit:
        setattr(state, f"{prefix}_step_q", 0.0)
    if "R" in words:
        setattr(state, f"{prefix}_retract_r", abs(scaled_word(words, "R", state.unit_scale)))
    if "Q" in words:
        setattr(
            state,
            f"{prefix}_step_q",
            cycle_least_input_or_length_to_mm(words["Q"], state.unit_scale, word_expr(block, "Q")),
        )
    if "P" in words:
        setattr(state, f"{prefix}_dwell_p", abs(words["P"]))
    if explicit:
        setattr(state, f"{prefix}_feed", scaled_word_or(words, "F", state.feed, state.unit_scale))
    elif "F" in words:
        setattr(state, f"{prefix}_feed", scaled_word(words, "F", state.unit_scale))


def _axial_cycle_target(state, words) -> tuple[float, float]:
    target_x = (
        x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
        if "X" in words
        else (
            state.modal_x + x_delta_to_diameter(scaled_word(words, "U", state.unit_scale), state.x_is_diameter)
            if "U" in words
            else state.modal_x
        )
    )
    target_z = (
        scaled_word(words, "Z", state.unit_scale)
        if "Z" in words
        else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else state.modal_z)
    )
    return target_x, target_z


def _expand_axial_cycle(
    cycle_least_input_or_length_to_mm,
    word_expr,
    block,
    gcode,
    rough_cycles,
    state,
    words,
    *,
    code: int,
    other_code: int,
    builder: Callable[..., list[Motion]],
) -> bool:
    prefix = f"g{code}"
    active_attr = f"active_{prefix}_cycle"
    other_active_attr = f"active_g{other_code}_cycle"
    has_axis = any(key in words for key in _AXIS_WORDS)
    explicit = gcode == code and has_axis
    continuation = getattr(state, active_attr) and gcode is None and has_axis
    if not (explicit or continuation):
        return False

    if explicit:
        setattr(state, active_attr, True)
        setattr(state, other_active_attr, False)
        state.active_g80 = False

    _update_axial_cycle_parameters(
        cycle_least_input_or_length_to_mm,
        word_expr,
        block,
        state,
        words,
        prefix=prefix,
        explicit=explicit,
    )
    target_x, target_z = _axial_cycle_target(state, words)
    cycle = builder(
        state.modal_x,
        state.modal_z,
        target_x,
        target_z,
        getattr(state, f"{prefix}_retract_r"),
        getattr(state, f"{prefix}_step_q"),
        getattr(state, f"{prefix}_dwell_p"),
        getattr(state, f"{prefix}_feed"),
    )
    rough_cycles.append(cycle)
    if cycle:
        state.modal_x = cycle[-1].end.x
        state.modal_z = cycle[-1].end.z
    return True


def _expand_g83(cycle_least_input_or_length_to_mm, word_expr, block, gcode, rough_cycles, state, words):
    return _expand_axial_cycle(
        cycle_least_input_or_length_to_mm,
        word_expr,
        block,
        gcode,
        rough_cycles,
        state,
        words,
        code=83,
        other_code=84,
        builder=build_g83_cycle,
    )


def _expand_g84(cycle_least_input_or_length_to_mm, word_expr, block, gcode, rough_cycles, state, words):
    return _expand_axial_cycle(
        cycle_least_input_or_length_to_mm,
        word_expr,
        block,
        gcode,
        rough_cycles,
        state,
        words,
        code=84,
        other_code=83,
        builder=build_g84_cycle,
    )
