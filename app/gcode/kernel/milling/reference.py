"""Resolved reference events retain machine targets and each G28 path leg."""

from ..api.types import ExecutionEvent, ReferenceSegment, ResolvedReferenceMove
from ..runtime.events import HOME_RETURN, MACHINE_COORDINATE_MOVE


def append_reference_event(events, *args, code, **kwargs):
    if events is not None:
        events.append(resolved_reference_event(*args, code=code, **kwargs))


def resolved_reference_event(
    block,
    state,
    words,
    home,
    start,
    target,
    segments,
    *,
    code,
    intermediate=None,
    orientation=None,
    offset=(0.0, 0.0, 0.0),
    call_depth=0,
):
    axes = tuple(axis for axis in "XYZABC" if axis in words)
    home_axes = tuple(axis for i, axis in enumerate("XYZ") if axis in axes and abs(target[i] - home[i]) <= 1e-9)
    home_axes += tuple(axis for axis in "ABC" if axis in axes and abs(state.rotary_angles[axis]) <= 1e-9)
    legs = tuple(
        ReferenceSegment(
            tuple(first),
            tuple(second),
            tuple(axis for i, axis in enumerate("XYZ") if abs(first[i] - second[i]) > 1e-9),
            "intermediate" if intermediate is not None and tuple(second) == tuple(intermediate) else "return",
        )
        for first, second in segments
    )
    return ExecutionEvent(
        HOME_RETURN if code == "G28" or home_axes else MACHINE_COORDINATE_MOVE,
        block.index,
        code=code,
        axes=axes,
        call_depth=call_depth,
        reference=ResolvedReferenceMove(
            tuple(start),
            tuple(target),
            tuple(home),
            legs,
            intermediate=intermediate,
            move=0 if code == "G28" else state.move,
            feed=None if code == "G28" or state.move == 0 else state.feed,
            orientation=orientation,
            offset=tuple(offset),
            home_axes=home_axes,
            rotary_target=tuple((axis, state.rotary_angles[axis]) for axis in axes if axis in "ABC"),
        ),
    )
