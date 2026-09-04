"""Core data model for FANUC turning programs and motions."""

from __future__ import annotations

from dataclasses import dataclass

from .ast import ProgramAst
from .lang import FlowNode, WordToken


@dataclass(frozen=True)
class Point2:
    x: float
    z: float


@dataclass(frozen=True)
class Motion:
    move: int
    start: Point2
    end: Point2
    radius: float | None = None
    feed: float | None = None
    i: float | None = None
    k: float | None = None
    source_block: int | None = None
    source_nlabel: int | None = None
    source_raw: str | None = None
    source_kind: str = "motion"
    compensation_mode: int = 40
    tool: str | None = None
    compensation_applied: bool = False


@dataclass(frozen=True)
class ArcGeom:
    center: Point2
    x_scale: float


@dataclass(frozen=True)
class ProfileSegment:
    block: int
    move: int
    start: Point2
    end: Point2
    has_radius: bool
    radius: float
    has_center: bool
    center: Point2
    corner_chamfer: float = 0.0
    corner_radius_cmd: float = 0.0


@dataclass(frozen=True)
class PendingAngleSegment:
    block: int
    start: Point2
    angle_deg: float
    corner_chamfer: float
    corner_radius_cmd: float


@dataclass(frozen=True)
class ModalSnapshot:
    g_expr: str | None
    x_expr: str | None
    z_expr: str | None
    u_expr: str | None
    w_expr: str | None
    f_expr: str | None


@dataclass(frozen=True)
class MotionNode:
    g_expr: str | None
    x_expr: str | None
    z_expr: str | None
    u_expr: str | None
    w_expr: str | None
    i_expr: str | None
    k_expr: str | None
    r_expr: str | None
    f_expr: str | None
    a_expr: str | None
    c_expr: str | None


@dataclass(frozen=True)
class CycleNode:
    cycle: str
    params: tuple[WordToken, ...]


@dataclass(frozen=True)
class Block:
    index: int
    raw: str
    parsed_words: tuple[WordToken, ...]
    modal_snapshot: ModalSnapshot
    motion_node: MotionNode | None
    cycle_node: CycleNode | None
    flow_node: FlowNode | None
    nlabel: int | None
    olabel: int | None
    optional_skip: bool


@dataclass(frozen=True)
class Program:
    blocks: tuple[Block, ...]
    ast: ProgramAst | None = None


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
class RuntimeState:
    modal_x: float = 0.0
    modal_z: float = 0.0
    modal_feed: float = 0.0
    unit_scale: float = 1.0  # G21: mm=1.0, G20: inch->mm=25.4
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
    g83_step_q: float = 0.05
    g83_dwell_p: float = 0.0
    g83_feed: float = 0.0
    active_g84_cycle: bool = False
    g84_retract_r: float = 0.0
    g84_step_q: float = 0.05
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
    variables: dict[str, float] | None = None
    compensation_mode: int = 40
    active_tool: str | None = None

    def __post_init__(self) -> None:
        if self.variables is None:
            self.variables = {}
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

    def clone_vars(self) -> dict[str, float]:
        return dict(self.variables or {})
