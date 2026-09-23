"""FANUC milling polar-coordinate endpoint resolution."""

from __future__ import annotations

import math

_PLANE_AXES = {
    17: ((0, "X"), (1, "Y")),
    18: ((2, "Z"), (0, "X")),
    19: ((1, "Y"), (2, "Z")),
}


def activate_polar(state, *, plane: int, absolute: bool) -> None:
    """Start a fresh polar session using the effective block modes."""
    if state.polar_active:
        select_polar_plane(state, plane)
        return
    state.polar_active = True
    state.polar_plane = plane
    state.polar_center = (0.0, 0.0, 0.0) if absolute else (state.x, state.y, state.z)
    state.polar_radius = 0.0
    state.polar_angle = 0.0


def cancel_polar(state) -> None:
    """Cancel polar programming and discard its modal endpoint state."""
    state.polar_active = False
    state.polar_center = (0.0, 0.0, 0.0)
    state.polar_radius = 0.0
    state.polar_angle = 0.0
    state.polar_plane = state.plane


def select_polar_plane(state, plane: int) -> None:
    """Select a plane, resetting radius/angle when an active pair changes."""
    if state.polar_active and state.polar_plane != plane:
        state.polar_radius = 0.0
        state.polar_angle = 0.0
    state.polar_plane = plane


def resolve_polar_endpoint(words, state) -> tuple[float, float, float]:
    """Resolve radius/angle words into a Cartesian local-coordinate endpoint."""
    (radius_index, radius_axis), (angle_index, angle_axis) = _PLANE_AXES[state.plane]
    radius = state.polar_radius
    angle = state.polar_angle

    if radius_axis in words:
        value = words[radius_axis] * state.unit_scale
        radius = value if state.absolute else radius + value
    if angle_axis in words:
        value = words[angle_axis]
        angle = value if state.absolute else angle + value

    state.polar_radius = radius
    state.polar_angle = angle
    endpoint = [state.x, state.y, state.z]
    endpoint[radius_index] = state.polar_center[radius_index] + radius * math.cos(math.radians(angle))
    endpoint[angle_index] = state.polar_center[angle_index] + radius * math.sin(math.radians(angle))

    polar_indices = {radius_index, angle_index}
    for index, axis in enumerate(("X", "Y", "Z")):
        if index in polar_indices or axis not in words:
            continue
        value = words[axis] * state.unit_scale
        endpoint[index] = value if state.absolute else endpoint[index] + value
    return endpoint[0], endpoint[1], endpoint[2]
