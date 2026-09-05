"""Public immutable contracts shared by CNC language resolvers."""

from __future__ import annotations

from dataclasses import dataclass

from .model import Program


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    severity: str = "error"
    status: str = "verified"
    line: int | None = None
    raw: str | None = None


@dataclass(frozen=True)
class SemanticInstruction:
    kind: str
    block_index: int
    raw: str
    words: tuple[tuple[str, str], ...]
    g_codes: tuple[int, ...] = ()
    m_codes: tuple[int, ...] = ()
    nlabel: int | None = None
    olabel: int | None = None


@dataclass(frozen=True)
class TraceMotion:
    # First six fields preserve the v1.1 positional constructor contract.
    move: int
    start_x: float
    start_z: float
    end_x: float
    end_z: float
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
    plane: int = 18
    cycle_generated: bool = False
    start_y: float = 0.0
    end_y: float = 0.0
    j: float | None = None
    arc: ArcGeometry | None = None
    x_scale: float = 1.0
    feed_mode: str = "per_minute"
    spindle_rpm: float | None = None
    spindle_mode: str = "rpm"
    surface_speed_m_min: float | None = None
    spindle_limit_rpm: float | None = None
    spindle_running: bool = False
    compensation_status: str = "NOT_APPLIED"
    threading: bool = False


@dataclass(frozen=True)
class ArcGeometry:
    """Resolved circle in physical millimetres; sweep is positive radians."""

    center: tuple[float, float, float]
    radius: float
    sweep: float
    plane: int
    clockwise: bool
    full_circle: bool


@dataclass(frozen=True)
class MachineSignal:
    kind: str
    block_index: int
    code: str
    value: float | None = None


@dataclass(frozen=True)
class ExecutionStep:
    """One source block execution and the number of trace motions it emitted."""

    source_block: int
    emitted_count: int
    unit_scale: float = 1.0
    x_is_diameter: bool = True
    contour_definition: bool = False
    stop: bool = False
    absolute: bool = True
    words: tuple[tuple[str, float], ...] = ()
    signals: tuple[MachineSignal, ...] = ()
    occurrence: int = 0
    position: tuple[float, float, float] | None = None
    active_wcs: int = 54
    feed_mode: str = "per_minute"
    spindle_rpm: float | None = None
    spindle_mode: str = "rpm"
    surface_speed_m_min: float | None = None
    spindle_limit_rpm: float | None = None
    spindle_running: bool = False


@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    program: Program | None
    instructions: tuple[SemanticInstruction, ...]
    motions: tuple[TraceMotion, ...]
    diagnostics: tuple[Diagnostic, ...]
    executed_blocks: tuple[int, ...]
    signals: tuple[MachineSignal, ...] = ()
    program_end: str | None = None
    execution_steps: tuple[ExecutionStep, ...] = ()
    complete: bool = True
    language: str = "fanuc_turn"
