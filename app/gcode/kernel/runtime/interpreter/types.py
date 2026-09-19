"""Mutable interpreter state and immutable dispatch result contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from ...api.types import ExecutionEvent
from ...frontend.model import RuntimeState


@dataclass
class TraceRuntimeState:
    modal_x: float = 0.0
    modal_z: float = 0.0
    modal_feed: float = 0.0
    modal_move: int = 0
    unit_scale: float = 1.0
    active_g90: bool = False
    active_g92: bool = False
    active_g94: bool = False
    active_g83: bool = False
    active_g84: bool = False
    active_g80: bool = True
    active_wcs: int = 54
    x_is_diameter: bool = True
    rough_idx: int = 0
    finish_idx: int = 0
    unknown_x_after_g28: bool = False
    unknown_z_after_g28: bool = False
    position_unknown_reason: str | None = None
    compensation_mode: int = 40
    active_tool: str | None = None
    vars_map: dict[str, float] | None = None
    feed_mode: str = "per_revolution"
    spindle_rpm: float | None = None
    spindle_mode: str = "rpm"
    surface_speed_m_min: float | None = None
    spindle_limit_rpm: float | None = None
    spindle_running: bool = False

    def __post_init__(self) -> None:
        if self.vars_map is None:
            self.vars_map = {}


@dataclass
class TraceExecutionContext:
    state: TraceRuntimeState
    pc: int = 0
    guard: int = 0
    call_stack: list[tuple[int, int, int]] | None = None
    max_call_depth: int = 64
    cycle_state: RuntimeState = field(default_factory=RuntimeState)
    cycle_options: dict = field(default_factory=dict)
    words: tuple = ()
    signals: tuple = ()
    events: tuple[ExecutionEvent, ...] = ()
    program_started: bool = False
    program_start_block: int = 0
    program_number: int | None = None
    label_to_index: dict[int, int] | None = None
    olabel_to_index: dict[int, int] | None = None
    contour_block_indices: set[int] | None = None
    while_to_end: dict[int, int] | None = None
    end_to_while: dict[int, int] | None = None

    def __post_init__(self) -> None:
        if self.call_stack is None:
            self.call_stack = []
        if self.label_to_index is None:
            self.label_to_index = {}
        if self.olabel_to_index is None:
            self.olabel_to_index = {}
        if self.contour_block_indices is None:
            self.contour_block_indices = set()
        if self.while_to_end is None:
            self.while_to_end = {}
        if self.end_to_while is None:
            self.end_to_while = {}


@dataclass(frozen=True)
class TraceStepSnapshot:
    pc_before: int
    pc_after: int
    source_block: int
    source_nlabel: int | None
    stop: bool
    emitted_count: int
    modal_x: float
    modal_z: float
    modal_move: int
    unit_scale: float
    active_wcs: int
    x_is_diameter: bool
    contour_definition: bool
    variables: tuple[tuple[str, float], ...] = ()
    words: tuple = ()
    signals: tuple = ()
    events: tuple[ExecutionEvent, ...] = ()
    feed_mode: str = "per_revolution"
    spindle_rpm: float | None = None
    spindle_mode: str = "rpm"
    surface_speed_m_min: float | None = None
    spindle_limit_rpm: float | None = None
    spindle_running: bool = False


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
