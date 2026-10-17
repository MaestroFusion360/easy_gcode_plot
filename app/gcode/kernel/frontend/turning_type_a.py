"""The supported FANUC turning Type A G-code vocabulary.

The operation names are internal semantic identifiers.  Other controller
families can supply their own mapping without changing the turning executor.
"""

from __future__ import annotations

from enum import Enum


class TurningOperation(str, Enum):
    RAPID = "rapid"
    LINEAR = "linear"
    ARC_CW = "arc_cw"
    ARC_CCW = "arc_ccw"
    THREAD_MOVE = "thread_move"
    FINISH = "finish"
    ROUGH_TURN = "rough_turn"
    ROUGH_FACE = "rough_face"
    PATTERN_REPEAT = "pattern_repeat"
    PECK_FACE = "peck_face"
    PECK_GROOVE = "peck_groove"
    THREAD_CYCLE = "thread_cycle"
    CANCEL_CYCLE = "cancel_cycle"
    DRILL = "drill"
    TAP = "tap"
    TURN_CYCLE = "turn_cycle"
    THREAD_SIMPLE = "thread_simple"
    FACE_CYCLE = "face_cycle"
    FEED_PER_MINUTE = "feed_per_minute"
    FEED_PER_REVOLUTION = "feed_per_revolution"
    SPINDLE_CLAMP = "spindle_clamp"
    DISTANCE_ABSOLUTE = "distance_absolute"
    DISTANCE_INCREMENTAL = "distance_incremental"


TYPE_A_MOTION = {
    0: TurningOperation.RAPID,
    1: TurningOperation.LINEAR,
    2: TurningOperation.ARC_CW,
    3: TurningOperation.ARC_CCW,
    32: TurningOperation.THREAD_MOVE,
    33: TurningOperation.THREAD_MOVE,
}
TYPE_A_CYCLES = {
    70: TurningOperation.FINISH,
    71: TurningOperation.ROUGH_TURN,
    72: TurningOperation.ROUGH_FACE,
    73: TurningOperation.PATTERN_REPEAT,
    74: TurningOperation.PECK_FACE,
    75: TurningOperation.PECK_GROOVE,
    76: TurningOperation.THREAD_CYCLE,
    80: TurningOperation.CANCEL_CYCLE,
    83: TurningOperation.DRILL,
    84: TurningOperation.TAP,
    90: TurningOperation.TURN_CYCLE,
    92: TurningOperation.THREAD_SIMPLE,
    94: TurningOperation.FACE_CYCLE,
}
TYPE_A_OPERATIONS = {
    **TYPE_A_MOTION,
    **TYPE_A_CYCLES,
    50: TurningOperation.SPINDLE_CLAMP,
    98: TurningOperation.FEED_PER_MINUTE,
    99: TurningOperation.FEED_PER_REVOLUTION,
}
TYPE_A_SUPPORTED_G_CODES = frozenset(TYPE_A_OPERATIONS) | frozenset(
    {4, 10, 18, 20, 21, 28, 30, 40, 41, 42, 50, 53, 54, 55, 56, 57, 58, 59, 65, 96, 97, 98, 99}
)


def type_a_operation(code: int | float | None) -> TurningOperation | None:
    """Map a source G word to its canonical turning operation, if applicable."""
    return TYPE_A_OPERATIONS.get(code)
