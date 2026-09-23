"""Execution runtime: control flow, dispatch, cycle expansion and tracing."""

from __future__ import annotations

from .cycles import CycleContext, CycleOutcome, apply_cycle_outcome

# ``expand_cycle_block`` is provided lazily by ``__getattr__`` below.
# pylint: disable=undefined-all-variable
__all__ = [
    "CycleContext",
    "CycleOutcome",
    "apply_cycle_outcome",
    "expand_cycle_block",
]


def __getattr__(name: str):
    if name == "expand_cycle_block":
        from .expansion import expand_cycle_block  # pylint: disable=import-outside-toplevel

        return expand_cycle_block
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
