"""Programmable rigid frames: Siemens Fundamentals 03/2013, sections 12.3/12.4.

TRANS/ROT replace; ATRANS/AROT post-compose in the current local frame.
Spatial angles use MD10600=1 (RPY default), intrinsic Z, Y', X''.
"""

import math

from ..api.resources import SemanticError
from ..geometry.matrix import IDENTITY, multiply, rotation, transform_vector
from ..geometry.transform import TransformState
from .sinumerik_parameters import parameter_value


def frame_rotation(values, plane):
    """The sole rotation-order policy; no machine-specific Euler inference."""
    if "RPL" in values:
        axis = {17: (0.0, 0.0, 1.0), 18: (0.0, 1.0, 0.0), 19: (1.0, 0.0, 0.0)}[plane]
        return rotation(axis, values["RPL"])
    return multiply(
        multiply(rotation((0, 0, 1), values.get("Z", 0)), rotation((0, 1, 0), values.get("Y", 0))),
        rotation((1, 0, 0), values.get("X", 0)),
    )


def compile_frame(syntax, state):
    if state.twp.active or state.tcp_control or state.polar_active:
        raise SemanticError(
            "UNSUPPORTED_SINUMERIK_FRAME_COMPOSITION",
            "Cancel CYCLE800/TWP, TCP and polar mode before programmable frames",
            "unsupported",
        )
    if state.native_cycle is not None or state.cycle != 80 or state.cutter_comp != 40:
        raise SemanticError(
            "UNSUPPORTED_SINUMERIK_FRAME_COMPOSITION",
            "Cancel cycles and cutter compensation before programmable frames",
            "unsupported",
        )
    command = syntax.frame_command
    if command in ("ATRANS", "AROT") and not syntax.frame_values:
        raise SemanticError("INVALID_SINUMERIK_FRAME", "Additive frame commands require values", "unsupported")
    values = {
        axis: parameter_value(value, state.siemens_parameters, state.siemens_variables)
        for axis, value in syntax.frame_values
    }
    previous = state.transform
    if (
        command.startswith("A")
        and previous.spatial_rotation is None
        and (previous.rotation_active or previous.scaling_active)
    ):
        raise SemanticError(
            "UNSUPPORTED_SINUMERIK_FRAME_COMPOSITION",
            "Cancel ISO rotation/scaling before additive programmable frames",
            "unsupported",
        )
    matrix = previous.spatial_rotation or IDENTITY if command.startswith("A") else IDENTITY
    origin = previous.translation if command.startswith("A") else (0.0, 0.0, 0.0)
    if command.endswith("TRANS"):
        shift = tuple(values.get(axis, 0) * state.unit_scale for axis in "XYZ")
        shift = transform_vector(matrix, shift)
        origin = tuple(origin[i] + shift[i] for i in range(3))
    else:
        matrix = multiply(matrix, frame_rotation(values, state.plane))
    if not all(math.isfinite(value) for value in origin):
        raise SemanticError("INVALID_SINUMERIK_FRAME", "Frame translation exceeds finite coordinates", "unsupported")
    if origin == (0.0, 0.0, 0.0) and matrix == IDENTITY:
        return TransformState()
    return TransformState(translation=origin, spatial_rotation=matrix, rotation_active=matrix != IDENTITY)


def apply_frame(frame, state):
    work = state.transform.build().apply((state.x, state.y, state.z))
    state.transform = frame
    state.x, state.y, state.z = frame.build().inverse(work)
