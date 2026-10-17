"""Compatible API imports; canonical types belong to the kernel foundation."""

from ..types import (
    ArcGeometry,
    Diagnostic,
    ExecutionEvent,
    ExecutionResult,
    ExecutionStep,
    MachineSignal,
    Program,
    ReferenceSegment,
    ResolvedDrillingOperation,
    ResolvedReferenceMove,
    SemanticInstruction,
    TraceMotion,
)

__all__ = [
    "Diagnostic",
    "SemanticInstruction",
    "TraceMotion",
    "ArcGeometry",
    "MachineSignal",
    "ResolvedDrillingOperation",
    "ReferenceSegment",
    "ResolvedReferenceMove",
    "ExecutionEvent",
    "ExecutionStep",
    "ExecutionResult",
    "Program",
]
