"""Rigid trace-motion conversion shared by contour geometry and compensation."""

from dataclasses import replace

from ..types import TraceMotion, with_motion_endpoints
from .matrix import transform_vector


def motion_frame(motion: TraceMotion, *, local: bool) -> TraceMotion:
    """Move resolved geometry between fixed WCS display and the local cutter plane."""
    matrix = motion.orientation
    if matrix is None:
        return motion
    offset = motion.orientation_offset
    rotation = tuple(tuple(matrix[column][row] for column in range(3)) for row in range(3)) if local else matrix

    def point(value):
        source = tuple(value[i] - offset[i] for i in range(3)) if local else value
        transformed = transform_vector(rotation, source)
        return transformed if local else tuple(transformed[i] + offset[i] for i in range(3))

    def vector(value):
        return transform_vector(rotation, value)

    start = point((motion.start_x, motion.start_y, motion.start_z))
    end = point((motion.end_x, motion.end_y, motion.end_z))
    delta = vector((motion.i or 0.0, motion.j or 0.0, motion.k or 0.0))
    center_offset = motion.absolute_center_offset or offset
    center_offset = point(center_offset)
    has_ijk = any(value is not None for value in (motion.i, motion.j, motion.k))
    arc = motion.arc
    if arc is not None:
        normal = arc.normal
        if normal is None and not local:
            normal = {17: (0.0, 0.0, 1.0), 18: (0.0, 1.0, 0.0), 19: (1.0, 0.0, 0.0)}[arc.plane]
        arc = replace(
            arc,
            center=point(arc.center),
            normal=vector(normal) if normal is not None else None,
        )
    return with_motion_endpoints(
        motion,
        start,
        end,
        i=delta[0] if has_ijk else None,
        j=delta[1] if has_ijk else None,
        k=delta[2] if has_ijk else None,
        absolute_center_offset=center_offset,
        arc=arc,
    )
