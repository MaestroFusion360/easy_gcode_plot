"""Derive public motion metadata from execution-step ownership."""

from __future__ import annotations

from ..api.types import ExecutionStep
from .execution import CYCLE_CODES, MOTION_CODES


def threading_step_flags(steps: tuple[ExecutionStep, ...]) -> tuple[bool, ...]:
    """Resolve explicit and modal FANUC threading blocks for published motions."""
    flags: list[bool] = []
    modal_thread_move = False
    active_g92 = False
    for step in steps:
        words = tuple(step.words)
        all_g = tuple(value for letter, value in words if letter == "G")
        explicit_motion_or_cycle = tuple(code for code in all_g if code in MOTION_CODES or code in CYCLE_CODES)
        has_position = any(letter in {"X", "U", "Z", "W"} for letter, _value in words)
        has_g92_depth = any(letter in {"X", "U"} for letter, _value in words)

        explicit_thread = any(code in {32, 33, 76, 92} for code in all_g)
        modal_g32_g33 = modal_thread_move and not explicit_motion_or_cycle and has_position
        modal_g92 = active_g92 and not explicit_motion_or_cycle and has_g92_depth
        flags.append(explicit_thread or modal_g32_g33 or modal_g92)

        if explicit_motion_or_cycle:
            modal_thread_move = any(code in {32, 33} for code in explicit_motion_or_cycle)
            active_g92 = 92 in explicit_motion_or_cycle and has_g92_depth

    return tuple(flags)
