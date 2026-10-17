"""Bounded depth progression shared by roughing cycles, without contour policy."""

from ...resources import SemanticError, checkpoint


def roughing_passes(start, signed_step, limit, *, tolerance):
    value = start
    guard = 0
    while (value <= limit + tolerance) if signed_step > 0 else (value >= limit - tolerance):
        checkpoint("cycle_iterations")
        guard += 1
        if guard > 10000:
            raise SemanticError("RESOURCE_LIMIT", "Cycle exceeds 10000 passes", "resource_limit")
        yield value
        value = min(value + signed_step, limit) if signed_step > 0 else max(value + signed_step, limit)
