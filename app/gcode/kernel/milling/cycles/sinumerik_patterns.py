"""HOLES1/2 positions: Siemens Cycles 01/2008, sections 2.3.2 and 2.3.3."""

import math

from ...resources import SemanticError
from ..sinumerik_parameters import parameter_value


def pattern_positions(syntax, state):
    """Yield absolute work coordinates; HOLES1 starts at the nearer row end."""
    if len(syntax.cycle_args) != 6:
        raise SemanticError("INVALID_SINUMERIK_PATTERN", "HOLES1/2 require six positional arguments")
    trees = dict(syntax.scalar_expressions)
    args = [
        parameter_value(arg, state.siemens_parameters, state.siemens_variables, trees.get(arg)) if arg else 0.0
        for arg in syntax.cycle_args
    ]
    if any(not arg for i, arg in enumerate(syntax.cycle_args) if i != 4 or syntax.kind != "holes2"):
        raise SemanticError("INVALID_SINUMERIK_PATTERN", "Only HOLES2 INDA can be omitted")
    if not all(math.isfinite(value) for value in args) or not args[5].is_integer() or args[5] < 1:
        raise SemanticError("INVALID_SINUMERIK_PATTERN", "Finite parameters and a positive integer NUM are required")
    if state.plane != 17 or state.native_cycle is None or state.tcp_control:
        raise SemanticError(
            "UNSUPPORTED_SINUMERIK_PATTERN", "HOLES1/2 require a G17 modal drilling cycle without TCP", "unsupported"
        )
    count = int(args[5])
    if syntax.kind == "holes1":
        yield from _row(args, count, state)
    else:
        cx, cy, radius, angle, step, _ = args
        if radius <= 0 or not -180 < angle <= 180:
            raise SemanticError("INVALID_SINUMERIK_PATTERN", "HOLES2 requires RAD>0 and -180<STA1<=180")
        step = step or 360 / count
        for i in range(count):
            radians = math.radians(angle + i * step)
            yield cx + radius * math.cos(radians), cy + radius * math.sin(radians)


def _row(args, count, state):
    x, y, angle, first, spacing, _ = args
    if first < 0 or spacing < 0 or not -180 < angle <= 180:
        raise SemanticError("INVALID_SINUMERIK_PATTERN", "HOLES1 requires unsigned distances and -180<STA1<=180")
    dx, dy = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    start = x + first * dx, y + first * dy
    end = x + (first + (count - 1) * spacing) * dx, y + (first + (count - 1) * spacing) * dy
    current = state.x / state.unit_scale, state.y / state.unit_scale
    near_start = math.hypot(start[0] - current[0], start[1] - current[1])
    near_end = math.hypot(end[0] - current[0], end[1] - current[1])
    order = reversed(range(count)) if near_end < near_start else range(count)
    for i in order:
        yield x + (first + i * spacing) * dx, y + (first + i * spacing) * dy
