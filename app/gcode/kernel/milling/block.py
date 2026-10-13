"""Milling block outcomes and execution context contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from ..api.types import Diagnostic, ExecutionEvent, TraceMotion
from ..frontend.program import EvaluatedWords
from ..runtime.execution import ProgramRuntime
from .state import MillState


class _BlockAction(Enum):
    ADVANCE = auto()
    JUMP = auto()
    STOP = auto()


@dataclass(frozen=True)
class _BlockOutcome:
    """Complete result of one interpreted block, finalized by the caller."""

    action: _BlockAction = _BlockAction.ADVANCE
    next_pc: int | None = None
    motions: tuple[TraceMotion, ...] = ()
    events: tuple[ExecutionEvent, ...] = ()
    signals: tuple = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    words: tuple = ()


@dataclass(frozen=True)
class _PreparedMillingBlock:
    """State-phase output consumed by geometric execution."""

    words: EvaluatedWords
    evaluated: tuple
    gcodes: tuple
    rotary_start_angles: dict[str, float]
    signals: tuple
    diagnostics: tuple[Diagnostic, ...]


@dataclass
class _MillingExecutionContext:
    program: object
    state: MillState
    runtime: ProgramRuntime
    home: tuple[float, float, float]
    wcs_offsets: dict[int, tuple[float, float, float]] | None
    program_start_block: int
    program_number: int | None
    source_dialect: str = "fanuc"
    program_started: bool = False
