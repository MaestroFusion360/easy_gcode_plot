"""Mutable interpreter state and immutable dispatch result contracts."""

from __future__ import annotations

from dataclasses import dataclass

from ...api.types import ExecutionEvent, ExecutionStep
from ..execution import ProgramRuntime
from ..state import RuntimeState


@dataclass
class TraceRuntimeState(RuntimeState):
    """Turning runtime state used by both block execution and cycle expansion."""

    modal_move: int = 0
    rough_idx: int = 0
    finish_idx: int = 0
    unknown_x_after_g28: bool = False
    unknown_z_after_g28: bool = False
    position_unknown_reason: str | None = None
    feed_mode: str = "per_revolution"
    spindle_mode: str = "rpm"
    surface_speed_m_min: float | None = None
    spindle_limit_rpm: float | None = None
    spindle_running: bool = False


@dataclass
class TraceExecutionContext:
    state: TraceRuntimeState
    runtime: ProgramRuntime
    cycle_options: dict | None = None
    words: tuple = ()
    signals: tuple = ()
    events: tuple[ExecutionEvent, ...] = ()
    program_started: bool = False
    program_start_block: int = 0
    program_number: int | None = None
    contour_block_indices: set[int] | None = None

    @property
    def pc(self) -> int:
        return self.runtime.pc

    @pc.setter
    def pc(self, value: int) -> None:
        self.runtime.pc = value

    def __post_init__(self) -> None:
        if self.cycle_options is None:
            self.cycle_options = {}
        if self.contour_block_indices is None:
            self.contour_block_indices = set()


# Compatibility name: turning and milling now publish the same ExecutionStep contract.
TraceStepSnapshot = ExecutionStep


@dataclass(frozen=True)
class CycleDispatch:
    is_cycle_exec: bool
    use_finish_cycle: bool
    active_g90: bool
    active_g92: bool
    active_g94: bool
    active_g83: bool
    active_g84: bool
    active_g80: bool


@dataclass(frozen=True)
class G28Dispatch:
    handled: bool
    new_modal_x: float
    new_modal_z: float
    emitted_motions: list[object]


@dataclass(frozen=True)
class MotionDispatch:
    handled: bool
    new_modal_x: float
    new_modal_z: float
    emitted_motion: object | None


@dataclass(frozen=True)
class CycleEmissionDispatch:
    handled: bool
    emitted_motions: list[object]
    new_modal_x: float
    new_modal_z: float
    new_rough_idx: int
    new_finish_idx: int
