"""Exact path comparison allowing only subdivisions of axis-aligned rapids."""

from dataclasses import replace


def rapid_path(motions):
    """Joining monotone segments changes neither the rapid path nor clearance."""
    output = []
    for motion in motions:
        if output and _same_rapid(output[-1], motion):
            output[-1] = replace(output[-1], end_x=motion.end_x, end_y=motion.end_y, end_z=motion.end_z)
        else:
            output.append(motion)
    return tuple(output)


def _same_rapid(first, second):
    if first.move != 0 or second.move != 0 or first.plane != second.plane or first.feed_mode != second.feed_mode:
        return False
    end = (first.end_x, first.end_y, first.end_z)
    if end != (second.start_x, second.start_y, second.start_z):
        return False
    first_delta = tuple(b - a for a, b in zip((first.start_x, first.start_y, first.start_z), end, strict=True))
    second_delta = tuple(b - a for a, b in zip(end, (second.end_x, second.end_y, second.end_z), strict=True))
    axes = [i for i, (a, b) in enumerate(zip(first_delta, second_delta, strict=True)) if a != 0 or b != 0]
    return len(axes) == 1 and first_delta[axes[0]] * second_delta[axes[0]] > 0


def cycle_signals(result, *, native_tapping):
    """Compare equivalent cycle actions; M29 prepares the verified rigid G84."""
    aliases = {"CYCLE81": "G82", "CYCLE82": "G82", "CYCLE84": "G84"}
    return tuple(
        (signal.kind, aliases.get(signal.code, signal.code), signal.value)
        for signal in result.signals
        if not (
            native_tapping and signal.kind == "rigid_tapping_prepare" and signal.code == "M29" and signal.value is None
        )
    )
