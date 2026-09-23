"""Adapter from legacy turning cycle emission to the common cycle contract."""

from __future__ import annotations

from ...runtime.cycles import CycleContext, CycleOutcome


def adapt_cycle_emission(context: CycleContext, dispatch, motions) -> CycleOutcome:
    """Wrap turning's existing grouped expansion without changing its semantics."""
    if not hasattr(context.machine_state, "modal_x"):
        raise TypeError("Turning cycle context requires turning machine state")
    if not dispatch.handled:
        return CycleOutcome()
    return CycleOutcome(
        handled=True,
        motions=tuple(motions),
        modal_updates=(
            ("rough_idx", dispatch.new_rough_idx),
            ("finish_idx", dispatch.new_finish_idx),
        ),
        position_update=(
            ("modal_x", dispatch.new_modal_x),
            ("modal_z", dispatch.new_modal_z),
        ),
    )
