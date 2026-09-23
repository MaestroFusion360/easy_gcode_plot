"""Machine-neutral cycle execution contracts.

Cycle implementations remain dialect-specific.  This module only defines the
boundary used to return their effects to the block executor.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..api.types import Diagnostic, MachineSignal


@dataclass(frozen=True, slots=True)
class CycleContext:
    """Inputs visible to one machine-specific cycle handler."""

    block: object
    words: object
    codes: tuple[int | float, ...]
    machine_state: object
    runtime_state: object | None = None
    modal_cycle_state: object | None = None
    coordinate_context: object | None = None


@dataclass(frozen=True, slots=True)
class CycleOutcome:
    """Effects produced by a cycle without prescribing its expansion model."""

    handled: bool = False
    motions: tuple[object, ...] = ()
    signals: tuple[MachineSignal, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    modal_updates: tuple[tuple[str, object], ...] = ()
    position_update: tuple[tuple[str, float], ...] = ()


def apply_cycle_outcome(state: object, outcome: CycleOutcome) -> None:
    """Commit a cycle's state effects after its expansion has completed."""
    for attribute, value in outcome.modal_updates:
        setattr(state, attribute, value)
    for attribute, value in outcome.position_update:
        setattr(state, attribute, value)
