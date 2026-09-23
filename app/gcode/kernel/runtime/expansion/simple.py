"""Shared mechanics for modal rectangular turning cycles."""

from __future__ import annotations

from collections.abc import Callable

from ...frontend.model import Motion, Point2
from ...frontend.program import scaled_word, scaled_word_or, x_delta_to_diameter, x_value_to_diameter
from ...turning.cycles import ensure_cycle_return


def _longitudinal_target_x(state, words, *, last_x: float) -> float:
    if "X" in words:
        return x_value_to_diameter(scaled_word(words, "X", state.unit_scale), state.x_is_diameter)
    return last_x + x_delta_to_diameter(scaled_word(words, "U", state.unit_scale), state.x_is_diameter)


def expand_longitudinal_cycle(
    gcode,
    rough_cycles,
    state,
    words,
    *,
    code: int,
    add_pass: Callable[..., None],
    first_block_direct: bool,
) -> bool:
    """Expand the shared modal X-in/Z-cut mechanics used by G90 and G92."""
    prefix = f"g{code}"
    active_attr = f"active_{prefix}_cycle"
    continuation = getattr(state, active_attr) and gcode is None and ("X" in words or "U" in words)
    explicit = gcode == code and ("X" in words or "U" in words)
    if not (explicit or continuation):
        return False

    if explicit:
        setattr(state, active_attr, True)
        setattr(state, f"{prefix}_start_x", state.modal_x)
        setattr(state, f"{prefix}_start_z", state.modal_z)
        target_z = (
            scaled_word(words, "Z", state.unit_scale)
            if "Z" in words
            else (state.modal_z + scaled_word(words, "W", state.unit_scale) if "W" in words else state.modal_z)
        )
        setattr(state, f"{prefix}_target_z", target_z)
        setattr(state, f"{prefix}_feed", scaled_word_or(words, "F", state.feed, state.unit_scale))
        setattr(state, f"{prefix}_last_x", state.modal_x)
    else:
        if "Z" in words:
            setattr(state, f"{prefix}_target_z", scaled_word(words, "Z", state.unit_scale))
        elif "W" in words:
            setattr(
                state,
                f"{prefix}_target_z",
                getattr(state, f"{prefix}_target_z") + scaled_word(words, "W", state.unit_scale),
            )
        if "F" in words:
            setattr(state, f"{prefix}_feed", scaled_word(words, "F", state.unit_scale))

    target_x = _longitudinal_target_x(state, words, last_x=getattr(state, f"{prefix}_last_x"))
    cycle: list[Motion] = []
    kwargs = {}
    if first_block_direct:
        kwargs["first_block_with_z"] = explicit and ("Z" in words or "W" in words)
    add_pass(
        cycle,
        getattr(state, f"{prefix}_start_x"),
        getattr(state, f"{prefix}_start_z"),
        target_x,
        getattr(state, f"{prefix}_target_z"),
        getattr(state, f"{prefix}_feed"),
        **kwargs,
    )
    ensure_cycle_return(cycle, Point2(getattr(state, f"{prefix}_start_x"), getattr(state, f"{prefix}_start_z")))
    rough_cycles.append(cycle)
    setattr(state, f"{prefix}_last_x", target_x)
    if cycle:
        state.modal_x = cycle[-1].end.x
        state.modal_z = cycle[-1].end.z
    return True
