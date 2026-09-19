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
    playback_group: int | None = None


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
    playback_group: int | None = None


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
