"""Publish complete or partial milling execution without duplicating metadata."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..api.types import Diagnostic, ExecutionEvent, ExecutionResult, ExecutionStep, TraceMotion
from ..runtime.events import program_end_code


@dataclass
class MillingOutput:
    """Lists shared with both interpreted blocks and the compiled bulk loop."""

    motions: list[TraceMotion] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    executed: list[int] = field(default_factory=list)
    steps: list[ExecutionStep] = field(default_factory=list)
    signals: list = field(default_factory=list)
    events: list[ExecutionEvent] = field(default_factory=list)

    def result(self, ctx, instructions, definition, fingerprint, *, failed=False, stopped_due_error=False):
        kinematics = ctx.state.kinematics
        events = tuple(self.events)
        return ExecutionResult(
            ok=False if failed else not any(d.severity == "error" for d in self.diagnostics),
            complete=not failed and not stopped_due_error,
            program=ctx.program,
            instructions=instructions,
            motions=tuple(self.motions),
            diagnostics=tuple(self.diagnostics),
            executed_blocks=tuple(self.executed),
            signals=tuple(self.signals),
            program_end=None if failed else program_end_code(events),
            execution_steps=tuple(self.steps),
            events=events,
            rotary_angles=tuple(ctx.state.rotary_angles.items()),
            kinematics_profile=kinematics.id if kinematics else None,
            rotary_axes=tuple(sorted(kinematics.addresses)) if kinematics else (),
            kinematics_definition=definition,
            kinematics_fingerprint=fingerprint,
            source_dialect=ctx.source_dialect,
            sinumerik_840d_sl=ctx.state.sinumerik_840d_sl,
        )
