"""FANUC turning Type B source-code vocabulary and semantic mapping."""

from __future__ import annotations

from .type_a import TYPE_A_OPERATIONS, TYPE_A_SUPPORTED_G_CODES, TurningOperation

# These source codes select existing turning operations. G90/G91 only update
# Type B distance state, so they have no Type A executor G-code equivalent.
TYPE_B_TO_CANONICAL = {33: 32, 77: 90, 78: 92, 79: 94, 92: 50, 94: 98, 95: 99}
TYPE_B_OPERATIONS = {
    **{code: operation for code, operation in TYPE_A_OPERATIONS.items() if code not in {32, 50, 90, 92, 94, 98, 99}},
    33: TurningOperation.THREAD_MOVE,
    77: TurningOperation.TURN_CYCLE,
    78: TurningOperation.THREAD_SIMPLE,
    79: TurningOperation.FACE_CYCLE,
    90: TurningOperation.DISTANCE_ABSOLUTE,
    91: TurningOperation.DISTANCE_INCREMENTAL,
    92: TurningOperation.SPINDLE_CLAMP,
    94: TurningOperation.FEED_PER_MINUTE,
    95: TurningOperation.FEED_PER_REVOLUTION,
}
TYPE_B_SUPPORTED_G_CODES = frozenset(TYPE_A_SUPPORTED_G_CODES - {32, 50, 98, 99}) | frozenset({77, 78, 79, 91, 95})


def type_b_operation(code: int | float | None) -> TurningOperation | None:
    """Map a Type B source G word to its turning operation."""
    return TYPE_B_OPERATIONS.get(code)
