"""Public immutable contracts shared by CNC language resolvers."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..frontend.model import Program


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    severity: str = "error"
    status: str = "verified"
    line: int | None = None
    raw: str | None = None
    cnc_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticInstruction:
    kind: str
    block_index: int
    raw: str
    words: tuple[tuple[str, str], ...]
    g_codes: tuple[int, ...] = ()
    m_codes: tuple[int, ...] = ()
    nlabel: int | None = None
    olabel: int | None = None


@dataclass(frozen=True, slots=True)
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
    playback_group: int | None = None
    orientation: tuple[tuple[float, float, float], ...] | None = None
    orientation_offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
    tool_orientation: tuple[tuple[float, float, float], ...] | None = None
    start_tool_orientation: tuple[tuple[float, float, float], ...] | None = None
    source_arc_type: int | None = None
    absolute_center_offset: tuple[float, float, float] | None = None
    additional_turns: int = 0


@dataclass(frozen=True, slots=True)
class ArcGeometry:
    """Resolved circle in physical millimetres; sweep is positive radians."""

    center: tuple[float, float, float]
    radius: float
    sweep: float
    plane: int
    clockwise: bool
    full_circle: bool
    normal: tuple[float, float, float] | None = None


@dataclass(frozen=True, slots=True)
class MachineSignal:
    kind: str
    block_index: int
    code: str
    value: float | None = None


@dataclass(frozen=True, slots=True)
class ResolvedDrillingOperation:
    """Controller-neutral hole parameters, in physical millimetres and seconds."""

    kind: str
    start: tuple[float, float, float]
    position: tuple[float, float, float]
    safety: tuple[float, float, float]
    reference: tuple[float, float, float]
    returned: tuple[float, float, float]
    feed: float
    feed_mode: str
    dwell_bottom: float = 0.0
    peck_first: float = 0.0
    peck_reduction: float = 0.0
    peck_minimum: float = 0.0
    peck_return_height: float = 0.0
    feed_return_height: float = 0.0
    full_retract: bool = True
    reentry_clearance: float = 0.0
    retract_distance: float = 1.0
    first_feed_factor: float = 1.0
    spindle_speed: float = 0.0
    rigid_tapping: bool = False
    emitted_count: int = 0
    orientation: tuple[tuple[float, float, float], ...] | None = None


@dataclass(frozen=True, slots=True)
class ReferenceSegment:
    """One resolved leg of a reference move, in machine millimetres."""

    start: tuple[float, float, float]
    end: tuple[float, float, float]
    axes: tuple[str, ...]
    phase: str


@dataclass(frozen=True, slots=True)
class ResolvedReferenceMove:
    """Machine-coordinate evidence independent of the displayed work frame."""

    start: tuple[float, float, float]
    target: tuple[float, float, float]
    home: tuple[float, float, float]
    segments: tuple[ReferenceSegment, ...]
    intermediate: tuple[float, float, float] | None = None
    move: int = 0
    feed: float | None = None
    orientation: tuple[tuple[float, float, float], ...] | None = None
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
    coordinate_space: str = "machine"
    home_axes: tuple[str, ...] = ()
    rotary_target: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    """One deterministic structural fact observed during actual execution."""

    kind: str
    source_block: int
    code: str | None = None
    program_number: int | None = None
    tool: str | None = None
    previous_tool: str | None = None
    axes: tuple[str, ...] = ()
    call_depth: int = 0
    target_block: int | None = None
    related_block: int | None = None
    old_abc: tuple[float, float, float] | None = None
    new_abc: tuple[float, float, float] | None = None
    kinematics_profile: str | None = None
    twp_origin: tuple[float, float, float] | None = None
    twp_angles: tuple[float, float, float] | None = None
    twp_orientation: tuple[tuple[float, float, float], ...] | None = None
    reference: ResolvedReferenceMove | None = None
    drilling: ResolvedDrillingOperation | None = None
    length_offset: int | None = field(default=None, kw_only=True)


@dataclass(frozen=True, slots=True)
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
    modal_move: int = 0
    variables: tuple[tuple[str, float], ...] = ()
    events: tuple[ExecutionEvent, ...] = ()
    rotary_angles: tuple[tuple[str, float], ...] = ()
    twp_origin: tuple[float, float, float] | None = None
    twp_orientation: tuple[tuple[float, float, float], ...] | None = None
    tool_axis_control: bool = False
    programmed_position: tuple[float, float, float] | None = None
    sinumerik_parameters: tuple[tuple[int, float], ...] = field(default=(), kw_only=True)
    sinumerik_variables: tuple[tuple[str, float], ...] = field(default=(), kw_only=True)


@dataclass(frozen=True, slots=True)
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
    events: tuple[ExecutionEvent, ...] = ()
    wcs_offsets: tuple[tuple[int, tuple[float, float, float]], ...] = ()
    extended_wcs_offsets: tuple[tuple[int, tuple[float, float, float]], ...] = ()
    rotary_angles: tuple[tuple[str, float], ...] = ()
    kinematics_profile: str | None = None
    rotary_axes: tuple[str, ...] = ()
    kinematics_definition: str | None = None
    kinematics_fingerprint: str | None = None
    source_dialect: str = "fanuc"
    lathe_gcode_system: str = "A"
    sinumerik_840d_sl: bool = True
