"""Nonmodal RND/CHR between planar G1 elements, before cutter compensation."""

import math
from dataclasses import replace

from ..compensation.milling.projection import _project_motion, _projected_to_motion
from ..geometry.matrix import IDENTITY
from ..geometry.motion_frame import motion_frame
from ..resources import SemanticError


def _error(motion, message):
    raise SemanticError(
        "INVALID_SINUMERIK_CORNER",
        message,
        "invalid_geometry",
        line=motion.source_block + 1,
        raw=motion.source_raw,
    )


def _command(step):
    return [(key, value * step.unit_scale) for key, value in step.words if key in {"RND", "CHR"} and value != 0]


def _geometry(projected):
    source = projected.source
    return replace(
        _projected_to_motion(projected, comp_mode=source.compensation_mode, source_kind=source.source_kind),
        compensation_applied=source.compensation_applied,
        compensation_status=source.compensation_status,
    )


def _corner(incoming, outgoing, command, size):
    """Construct in the common local plane, regardless of its rotary angles."""
    first, second = incoming.orientation or IDENTITY, outgoing.orientation or IDENTITY
    if any(abs(first[i][j] - second[i][j]) > 1e-9 for i in range(3) for j in range(3)):
        _error(incoming, "RND/CHR adjacent elements must share a working plane")
    if incoming.orientation is None and outgoing.orientation is None:
        return _local_corner(incoming, outgoing, command, size)
    local = tuple(
        motion_frame(replace(motion, orientation=motion.orientation or IDENTITY), local=True)
        for motion in (incoming, outgoing)
    )
    result = _local_corner(*local, command, size)
    return tuple(
        replace(motion_frame(motion, local=False), orientation=original.orientation)
        for motion, original in zip(result, (incoming, incoming, outgoing), strict=True)
    )


def _local_corner(incoming, outgoing, command, size):
    a, b = _project_motion(incoming), _project_motion(outgoing)
    if a is None or b is None:
        _error(incoming, "RND/CHR requires nonzero feed contour elements")
    incompatible = any(
        (
            not a.is_line,
            not b.is_line,
            a.is_helix,
            b.is_helix,
            a.plane != b.plane,
            incoming.orientation_offset != outgoing.orientation_offset,
            incoming.tool != outgoing.tool,
            incoming.compensation_mode != outgoing.compensation_mode,
            math.dist(a.end, b.start) > 1e-7,
            abs(a.end_w - b.start_w) > 1e-7,
        )
    )
    if incompatible:
        _error(incoming, "RND/CHR subset requires continuous planar G1 elements with the same tool and compensation")
    lengths = math.dist(a.start, a.end), math.dist(b.start, b.end)
    before = tuple((a.end[i] - a.start[i]) / lengths[0] for i in range(2))
    after = tuple((b.end[i] - b.start[i]) / lengths[1] for i in range(2))
    cross = before[0] * after[1] - before[1] * after[0]
    if size < 0 or abs(cross) < 1e-9:
        _error(incoming, "RND/CHR requires a positive size and a noncollinear corner")
    angle = math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(before, after)))))
    trim = size if command == "CHR" else size * math.tan(angle / 2)
    if trim >= min(lengths) - 1e-7:
        _error(incoming, "RND/CHR exceeds the supported local corner size")
    start = tuple(a.end[i] - trim * before[i] for i in range(2))
    end = tuple(a.end[i] + trim * after[i] for i in range(2))
    sign = 1 if cross > 0 else -1
    center = (start[0] - sign * size * before[1], start[1] + sign * size * before[0]) if command == "RND" else None
    source = replace(
        incoming, move=(3 if cross > 0 else 2) if center else 1, source_kind="sinumerik_" + command.lower()
    )
    inserted = replace(a, source=source, start=start, end=end, center=center, radius=size if center else None)
    return _geometry(replace(a, end=start)), _geometry(inserted), _geometry(replace(b, start=end))


def append_contour_motion(trace, motion, owner, steps):
    """Keep inserted geometry owned by the executed block carrying RND/CHR."""
    if trace.motions:
        previous, previous_owner = trace.motions[-1], trace.owners[-1]
        commands = _command(steps[previous_owner])
        if commands:
            if len(commands) != 1 or previous_owner == owner:
                _error(previous, "Use one RND or CHR on a single contour element")
            incoming, inserted, motion = _corner(previous, motion, *commands[0])
            trace.motions[-1] = incoming
            trace.append(inserted, previous_owner)
    trace.append(motion, owner)


def finish_contour(trace, steps):
    if trace.motions and _command(steps[trace.owners[-1]]):
        _error(trace.motions[-1], "RND/CHR requires a following contour element")
