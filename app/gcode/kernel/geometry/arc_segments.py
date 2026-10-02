"""Serializer-side subdivision of resolved arcs; source trace stays intact."""

import math
from dataclasses import replace


def split_arc(motion, maximum_sweep=math.pi):
    arc = motion.arc
    count = max(1, math.ceil(arc.sweep / maximum_sweep))
    axes = {17: (0, 1, 2), 18: (0, 2, 1), 19: (1, 2, 0)}
    a, b, other = axes[motion.plane]
    start = (motion.start_x * motion.x_scale, motion.start_y, motion.start_z)
    end = (motion.end_x * motion.x_scale, motion.end_y, motion.end_z)
    angle = math.atan2(start[b] - arc.center[b], start[a] - arc.center[a])
    previous = start
    for index in range(1, count + 1):
        fraction = index / count
        current_angle = angle + (-1 if arc.clockwise else 1) * arc.sweep * fraction
        point = list(start)
        point[a] = arc.center[a] + arc.radius * math.cos(current_angle)
        point[b] = arc.center[b] + arc.radius * math.sin(current_angle)
        point[other] = start[other] + (end[other] - start[other]) * fraction
        current = end if index == count else tuple(point)
        center = list(arc.center)
        center[other] = previous[other]
        yield replace(
            motion,
            start_x=previous[0] / motion.x_scale,
            start_y=previous[1],
            start_z=previous[2],
            end_x=current[0] / motion.x_scale,
            end_y=current[1],
            end_z=current[2],
            additional_turns=0,
            arc=replace(arc, center=tuple(center), sweep=arc.sweep / count, full_circle=False),
        )
        previous = current
