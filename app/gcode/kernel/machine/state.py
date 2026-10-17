"""Mutable turning runtime and cycle state shared by the interpreter and cycle expansion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MachineRuntimeState:
    """Machine-neutral modal state shared by turning and milling executors."""

    unit_scale: float = 1.0
    active_wcs: int = 54
    active_tool: str | None = None
    feed: float = 0.0
    feed_mode: str = "per_minute"
    spindle_rpm: float | None = None


@dataclass
class Cycle71First:
    depth_u_radius: float = 0.5
    retract_r_radius: float = 1.0
    stock_x: float = 0.0
    stock_z: float = 0.0
    valid: bool = False


@dataclass
class Cycle72First:
    depth_w: float = 1.0
    retract_r: float = 1.0
    stock_x: float = 0.0
    stock_z: float = 0.0
    valid: bool = False


@dataclass
class Cycle73First:
    total_u_x: float = 0.0
    total_w_z: float = 0.0
    passes: int = 1
    stock_x: float = 0.0
    stock_z: float = 0.0
    valid: bool = False


@dataclass
class Cycle74First:
    retract_r: float = 0.0
    valid: bool = False


@dataclass
class Cycle75First:
    retract_r: float = 0.0
    valid: bool = False


@dataclass
class Cycle76First:
    packed_p: int = 0
    q_min_microns: float = 0.0
    r_finish_microns: float = 0.0
    valid: bool = False


@dataclass
class RuntimeState(MachineRuntimeState):
    modal_x: float = 0.0
    modal_z: float = 0.0
    x_is_diameter: bool = True
    active_g90_cycle: bool = False
    g90_start_x: float = 0.0
    g90_start_z: float = 0.0
    g90_target_z: float = 0.0
    g90_feed: float = 0.0
    g90_last_x: float = 0.0
    active_g92_cycle: bool = False
    g92_start_x: float = 0.0
    g92_start_z: float = 0.0
    g92_target_z: float = 0.0
    g92_feed: float = 0.0
    g92_last_x: float = 0.0
    active_g94_cycle: bool = False
    g94_start_x: float = 0.0
    g94_start_z: float = 0.0
    g94_target_x: float = 0.0
    g94_target_z: float = 0.0
    g94_feed: float = 0.0
    active_g83_cycle: bool = False
    g83_retract_r: float = 0.0
    g83_step_q: float = 0.0
    g83_dwell_p: float = 0.0
    g83_feed: float = 0.0
    active_g84_cycle: bool = False
    g84_retract_r: float = 0.0
    g84_step_q: float = 0.0
    g84_dwell_p: float = 0.0
    g84_feed: float = 0.0
    active_g80: bool = True
    g71_first: Cycle71First | None = None
    g72_first: Cycle72First | None = None
    g73_first: Cycle73First | None = None
    g74_first: Cycle74First | None = None
    g75_first: Cycle75First | None = None
    g76_first: Cycle76First | None = None
    last_finish_stock_x: float | None = None
    last_finish_stock_z: float | None = None
    compensation_mode: int = 40

    def __post_init__(self) -> None:
        if self.g71_first is None:
            self.g71_first = Cycle71First()
        if self.g72_first is None:
            self.g72_first = Cycle72First()
        if self.g73_first is None:
            self.g73_first = Cycle73First()
        if self.g74_first is None:
            self.g74_first = Cycle74First()
        if self.g75_first is None:
            self.g75_first = Cycle75First()
        if self.g76_first is None:
            self.g76_first = Cycle76First()
