"""Execution runtime: control flow, dispatch, cycle expansion and tracing."""

from __future__ import annotations

import sys

from ..machine import cycles, diagnostics, drilling, events, execution, home, signals, state
from ..machine.cycles import CycleContext, CycleOutcome, apply_cycle_outcome

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


_COMPAT_MODULES = {
    "cycles": cycles,
    "drilling": drilling,
    "home": home,
    "events": events,
    "execution": execution,
    "signals": signals,
    "state": state,
    "diagnostics": diagnostics,
}

for _name, _module in _COMPAT_MODULES.items():
    sys.modules[f"{__name__}.{_name}"] = _module
    globals()[_name] = _module
