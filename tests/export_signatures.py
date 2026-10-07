from app.gcode.kernel import ExecutionResult


def _motion_trace_signature(result: ExecutionResult) -> tuple:
    return tuple(
        (
            motion.move,
            motion.plane,
            motion.feed_mode,
            *(
                round(value, 8)
                for value in (
                    motion.start_x,
                    motion.start_y,
                    motion.start_z,
                    motion.end_x,
                    motion.end_y,
                    motion.end_z,
                    motion.i or 0.0,
                    motion.j or 0.0,
                    motion.k or 0.0,
                    motion.feed or 0.0,
                )
            ),
            None
            if motion.arc is None
            else (
                *(round(value, 8) for value in motion.arc.center),
                round(motion.arc.radius, 8),
                round(motion.arc.sweep, 8),
            ),
            motion.tool,
        )
        for motion in result.motions
    )


# Index layout of one _motion_trace_signature entry.
_MOVE, _PLANE, _FEED_MODE = 0, 1, 2
_LINEAR_FIELDS = (3, 4, 5, 6, 7, 8, 12)  # start XYZ, end XYZ, feed
_ARC = 13


def _entries_match(left: tuple, right: tuple, tolerance: float) -> bool:
    if left[-1] != right[-1]:
        return False
    if left[_MOVE] != right[_MOVE] or left[_PLANE] != right[_PLANE] or left[_FEED_MODE] != right[_FEED_MODE]:
        return False
    if any(abs(left[index] - right[index]) > tolerance for index in _LINEAR_FIELDS):
        return False
    if (left[_ARC] is None) != (right[_ARC] is None):
        return False
    if left[_ARC] is None:
        return True
    return len(left[_ARC]) == len(right[_ARC]) and all(
        abs(left_value - right_value) <= tolerance for left_value, right_value in zip(left[_ARC], right[_ARC])
    )


def motion_traces_match(
    reference: ExecutionResult,
    replay: ExecutionResult,
    *,
    tolerance: float = 1e-5,
    allow_split_cycle_rapids: bool = False,
) -> bool:
    """Return True when two executions contain the same ordered logical motions.

    This is the strict trajectory contract: every motion must match in type,
    plane, feed mode, start/end position, feed rate and resolved arc geometry
    (center, radius, sweep). Raw I/J/K address words are intentionally excluded
    because they encode the source center convention (R versus IJK versus
    ``AC(...)``); the resolved arc geometry already captures that information.
    """
    expected = (
        _cycle_rapid_signature(reference, tolerance) if allow_split_cycle_rapids else _motion_trace_signature(reference)
    )
    actual = _cycle_rapid_signature(replay, tolerance) if allow_split_cycle_rapids else _motion_trace_signature(replay)
    return len(expected) == len(actual) and all(
        _entries_match(left, right, tolerance) for left, right in zip(expected, actual)
    )


def _cycle_rapid_signature(result, tolerance):
    """A cycle may return in two collinear Z rapids instead of one Z rapid."""
    normalized = []
    for entry, motion in zip(_motion_trace_signature(result), result.motions, strict=True):
        if normalized and _same_cycle_return(normalized[-1], (entry, motion.cycle_generated), tolerance):
            previous, cycle = normalized.pop()
            combined = previous[:6] + entry[6:9] + previous[9:]
            normalized.append((combined, cycle or motion.cycle_generated))
        else:
            normalized.append((entry, motion.cycle_generated))
    return tuple(entry for entry, _cycle in normalized)


def _same_cycle_return(previous, current, tolerance):
    left, _left_cycle = previous
    right, _right_cycle = current
    if left[:3] != right[:3] or left[_MOVE] != 0 or left[-1] != right[-1]:
        return False
    if any(abs(left[i] - right[i - 3]) > tolerance for i in (6, 7, 8)):
        return False
    if any(abs(entry[i] - entry[i + 3]) > tolerance for entry in (left, right) for i in (3, 4)):
        return False
    return (left[8] - left[5]) * (right[8] - right[5]) > 0
