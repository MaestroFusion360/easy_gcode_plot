from __future__ import annotations

# Interpreter dispatch exits early for each explicit CNC motion/cycle opcode.
# pylint: disable=too-many-return-statements
from dataclasses import dataclass, field, replace

from .ast import CycleAstNode, MotionAstNode
from .execution import (
    POSITION_NEUTRAL_GCODES,
    build_program_execution_index,
    classify_block_codes,
    dispatch_macro_flow,
    dispatch_subprogram_flow,
    flow_control_mcode,
    retain_modal_turning_cycles,
)
from .model import RuntimeState
from .program import resolve_cycle_profile_indices
from .resources import checkpoint
from .runtime import expand_cycle_block
from .signals import signals_for_words

_X_AXIS_WORDS = ("X", "U")
_Z_AXIS_WORDS = ("Z", "W")


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


def _has_any_word(words: dict[str, float], keys: tuple[str, ...]) -> bool:
    return any(k in words for k in keys)


def _dispatch_explicit_cycle(
    *,
    cycle_code: int | None,
    words: dict[str, float],
) -> tuple[bool, bool, bool, bool, bool, bool, bool, bool]:
    # Returns:
    # is_cycle_exec, use_finish_cycle,
    # set_g90_active, set_g92_active, set_g94_active,
    # set_g83_active, set_g84_active, set_g80_active
    if cycle_code == 70 and "P" in words and "Q" in words:
        return True, True, False, False, False, False, False, False
    if cycle_code in (71, 72, 73) and "P" in words and "Q" in words:
        return True, False, False, False, False, False, False, False
    if cycle_code == 74 and _has_any_word(words, _Z_AXIS_WORDS):
        return True, False, False, False, False, False, False, False
    if cycle_code == 75 and _has_any_word(words, _X_AXIS_WORDS):
        return True, False, False, False, False, False, False, False
    if cycle_code == 76 and "X" in words and "Z" in words:
        return True, False, False, False, False, False, False, False
    if cycle_code == 83 and _has_any_word(words, _X_AXIS_WORDS + _Z_AXIS_WORDS):
        return True, False, False, False, False, True, False, False
    if cycle_code == 84 and _has_any_word(words, _X_AXIS_WORDS + _Z_AXIS_WORDS):
        return True, False, False, False, False, False, True, False
    if cycle_code == 80:
        return False, False, False, False, False, False, False, True
    if cycle_code == 90 and _has_any_word(words, _X_AXIS_WORDS):
        return True, False, True, False, False, False, False, False
    if cycle_code == 92 and _has_any_word(words, _X_AXIS_WORDS):
        return True, False, False, True, False, False, False, False
    if cycle_code == 94 and _has_any_word(words, _X_AXIS_WORDS):
        return True, False, False, False, True, False, False, False
    return False, False, False, False, False, False, False, False


def _cycle_code_from_ast_node(ast_node) -> int | None:
    if not isinstance(ast_node, CycleAstNode):
        return None
    cyc = ast_node.cycle.upper().strip()
    if cyc.startswith("G"):
        cyc = cyc[1:]
    try:
        return int(cyc)
    except ValueError:
        return None


def build_trace_execution_context(
    *,
    program,
    eval_words_fn,
    initial_state: TraceRuntimeState | None = None,
) -> TraceExecutionContext:
    state = initial_state or TraceRuntimeState()

    execution_index = build_program_execution_index(program)
    label_to_index = execution_index.label_to_index
    olabel_to_index = execution_index.olabel_to_index

    contour_block_indices: set[int] = set()

    while_to_end = execution_index.while_to_end
    end_to_while = execution_index.end_to_while

    return TraceExecutionContext(
        state=state,
        pc=0,
        guard=0,
        call_stack=[],
        max_call_depth=64,
        label_to_index=label_to_index,
        olabel_to_index=olabel_to_index,
        contour_block_indices=contour_block_indices,
        while_to_end=while_to_end,
        end_to_while=end_to_while,
    )


def dispatch_cycle_block(
    ast_node,
    words: dict[str, float],
    gcode: int | None,
    *,
    all_g: tuple[int, ...] | None = None,
    active_g90: bool,
    active_g92: bool,
    active_g94: bool,
    active_g83: bool,
    active_g84: bool,
    active_g80: bool,
) -> CycleDispatch:
    cancellation_codes = all_g if all_g is not None else (() if gcode is None else (gcode,))
    active_g90, active_g92, active_g94 = retain_modal_turning_cycles(
        cancellation_codes,
        active_g90=active_g90,
        active_g92=active_g92,
        active_g94=active_g94,
    )
    if "T" in words:
        active_g83 = False
        active_g84 = False
        active_g80 = True

    cycle_code = _cycle_code_from_ast_node(ast_node) if isinstance(ast_node, CycleAstNode) else gcode
    (
        is_cycle_exec,
        use_finish_cycle,
        set_g90,
        set_g92,
        set_g94,
        set_g83,
        set_g84,
        set_g80,
    ) = _dispatch_explicit_cycle(
        cycle_code=cycle_code,
        words=words,
    )
    if set_g90:
        active_g90 = True
    if set_g92:
        active_g92 = True
    if set_g94:
        active_g94 = True
    if set_g83:
        active_g83 = True
        active_g84 = False
        active_g80 = False
    if set_g84:
        active_g84 = True
        active_g83 = False
        active_g80 = False
    if set_g80:
        active_g83 = False
        active_g84 = False
        active_g80 = True

    if not is_cycle_exec:
        if active_g90 and gcode is None and _has_any_word(words, _X_AXIS_WORDS):
            is_cycle_exec = True
        elif active_g92 and gcode is None and _has_any_word(words, _X_AXIS_WORDS):
            is_cycle_exec = True
        elif active_g94 and gcode is None and _has_any_word(words, _Z_AXIS_WORDS):
            is_cycle_exec = True
        elif active_g83 and gcode is None and _has_any_word(words, _X_AXIS_WORDS + _Z_AXIS_WORDS):
            is_cycle_exec = True
        elif active_g84 and gcode is None and _has_any_word(words, _X_AXIS_WORDS + _Z_AXIS_WORDS):
            is_cycle_exec = True

    return CycleDispatch(
        is_cycle_exec=is_cycle_exec,
        use_finish_cycle=use_finish_cycle,
        active_g90=active_g90,
        active_g92=active_g92,
        active_g94=active_g94,
        active_g83=active_g83,
        active_g84=active_g84,
        active_g80=active_g80,
    )


def resolve_modal_move(ast_node, gcode: int | None, current_modal_move: int) -> int:
    if isinstance(ast_node, MotionAstNode):
        ag = ast_node.g_code
        if ag in (0, 1, 2, 3):
            return int(ag)
        if ag in (32, 33):
            return 1
    if gcode in (0, 1, 2, 3):
        return int(gcode)
    if gcode in (32, 33):
        return 1
    return current_modal_move


def has_position_words(ast_node, words: dict[str, float]) -> bool:
    if isinstance(ast_node, MotionAstNode):
        return any(
            v is not None
            for v in (
                ast_node.x_expr,
                ast_node.z_expr,
                ast_node.u_expr,
                ast_node.w_expr,
            )
        )
    return any(k in words for k in ("X", "Z", "U", "W"))


def dispatch_g28_home(
    *,
    emulate_g28_home: bool,
    gcode: int | None,
    words: dict[str, float],
    modal_x: float,
    modal_z: float,
    unit_scale: float,
    x_is_diameter: bool,
    home_x: float,
    home_z: float,
    to_machine_fn,
    x_value_to_diameter_fn,
    x_delta_to_diameter_fn,
    motion_ctor,
    point_ctor,
    source_block: int,
    source_nlabel: int | None,
    source_raw: str | None,
    active_wcs: int,
    wcs_off_fn,
) -> G28Dispatch:
    if (not emulate_g28_home) or gcode != 28:
        return G28Dispatch(False, modal_x, modal_z, [])

    ix = modal_x
    iz = modal_z
    has_x_axis = ("X" in words) or ("U" in words)
    has_z_axis = ("Z" in words) or ("W" in words)
    if "X" in words:
        ix = x_value_to_diameter_fn(words["X"] * unit_scale, x_is_diameter)
    elif "U" in words:
        ix = modal_x + x_delta_to_diameter_fn(words["U"] * unit_scale, x_is_diameter)
    if "Z" in words:
        iz = words["Z"] * unit_scale
    elif "W" in words:
        iz = modal_z + (words["W"] * unit_scale)

    emitted: list[object] = []
    smx, smz = to_machine_fn(modal_x, modal_z)
    imx, imz = to_machine_fn(ix, iz)
    if abs(imx - smx) > 1e-9 or abs(imz - smz) > 1e-9:
        emitted.append(
            motion_ctor(
                0,
                point_ctor(smx, smz),
                point_ctor(imx, imz),
                source_block=source_block,
                source_nlabel=source_nlabel,
                source_raw=source_raw,
                source_kind=("g30" if gcode == 30 else "g28"),
            )
        )
    target_mx = home_x if has_x_axis else imx
    target_mz = home_z if has_z_axis else imz
    if abs(target_mx - imx) > 1e-9 or abs(target_mz - imz) > 1e-9:
        emitted.append(
            motion_ctor(
                0,
                point_ctor(imx, imz),
                point_ctor(target_mx, target_mz),
                source_block=source_block,
                source_nlabel=source_nlabel,
                source_raw=source_raw,
                source_kind=("g30" if gcode == 30 else "g28"),
            )
        )

    ox, oz = wcs_off_fn(active_wcs)
    new_modal_x = target_mx - ox
    new_modal_z = target_mz - oz
    return G28Dispatch(True, new_modal_x, new_modal_z, emitted)


def dispatch_motion_block(
    *,
    has_pos: bool,
    non_motion_g: bool,
    modal_move: int,
    words: dict[str, float],
    modal_x: float,
    modal_z: float,
    modal_feed: float,
    unit_scale: float,
    x_is_diameter: bool,
    to_machine_fn,
    x_value_to_diameter_fn,
    x_delta_to_diameter_fn,
    motion_ctor,
    point_ctor,
    source_block: int,
    source_nlabel: int | None,
    source_raw: str | None,
) -> MotionDispatch:
    has_pos = has_pos or (modal_move in (2, 3) and any(k in words for k in ("I", "K", "R")))
    if (not has_pos) or non_motion_g or modal_move not in (0, 1, 2, 3):
        return MotionDispatch(False, modal_x, modal_z, None)

    tx = modal_x
    tz = modal_z
    if "X" in words:
        tx = x_value_to_diameter_fn(words["X"] * unit_scale, x_is_diameter)
    elif "U" in words:
        tx = modal_x + x_delta_to_diameter_fn(words["U"] * unit_scale, x_is_diameter)
    if "Z" in words:
        tz = words["Z"] * unit_scale
    elif "W" in words:
        tz = modal_z + (words["W"] * unit_scale)

    if tx == modal_x and tz == modal_z and not (modal_move in (2, 3) and any(k in words for k in ("I", "K", "R"))):
        return MotionDispatch(True, tx, tz, None)

    radius = (words["R"] * unit_scale) if (modal_move in (2, 3) and "R" in words) else None
    feed = modal_feed if modal_move in (1, 2, 3) and modal_feed > 0 else None
    i_off = None
    k_off = None
    if modal_move in (2, 3) and ("I" in words or "K" in words):
        i_raw = words.get("I", 0.0) * unit_scale
        i_off = i_raw * 2.0
        k_off = words.get("K", 0.0) * unit_scale
    smx, smz = to_machine_fn(modal_x, modal_z)
    emx, emz = to_machine_fn(tx, tz)
    emitted = motion_ctor(
        modal_move,
        point_ctor(smx, smz),
        point_ctor(emx, emz),
        radius,
        feed,
        i=i_off,
        k=k_off,
        source_block=source_block,
        source_nlabel=source_nlabel,
        source_raw=source_raw,
        source_kind="motion",
    )
    return MotionDispatch(True, tx, tz, emitted)


def dispatch_cycle_emission(
    *,
    is_cycle_exec: bool,
    use_finish_cycle: bool,
    rough_cycles: list[list[object]],
    finish_cycles: list[list[object]],
    rough_idx: int,
    finish_idx: int,
    modal_x: float,
    modal_z: float,
    source_block: int,
    blocks: list[object],
    to_machine_fn,
    motion_ctor,
    point_ctor,
) -> CycleEmissionDispatch:
    if not is_cycle_exec:
        return CycleEmissionDispatch(
            handled=False,
            emitted_motions=[],
            new_modal_x=modal_x,
            new_modal_z=modal_z,
            new_rough_idx=rough_idx,
            new_finish_idx=finish_idx,
        )

    cyc: list[object] = []
    new_rough_idx = rough_idx
    new_finish_idx = finish_idx
    if use_finish_cycle:
        if finish_idx < len(finish_cycles):
            cyc = finish_cycles[finish_idx]
            new_finish_idx += 1
    else:
        if rough_idx < len(rough_cycles):
            cyc = rough_cycles[rough_idx]
            new_rough_idx += 1

    emitted: list[object] = []
    for cm in cyc:
        src_block = getattr(cm, "source_block", None)
        if src_block is None:
            src_block = source_block
        try:
            src_block_int = int(src_block)
        except (TypeError, ValueError):
            src_block_int = source_block
        src_nlabel = None
        src_raw = None
        if 0 <= src_block_int < len(blocks):
            src_nlabel = blocks[src_block_int].nlabel
            src_raw = blocks[src_block_int].raw
        smx, smz = to_machine_fn(cm.start.x, cm.start.z)
        emx, emz = to_machine_fn(cm.end.x, cm.end.z)
        emitted.append(
            motion_ctor(
                cm.move,
                point_ctor(smx, smz),
                point_ctor(emx, emz),
                cm.radius,
                cm.feed,
                i=getattr(cm, "i", None),
                k=getattr(cm, "k", None),
                source_block=src_block_int,
                source_nlabel=src_nlabel,
                source_raw=src_raw,
                source_kind="cycle",
                compensation_applied=bool(getattr(cm, "compensation_applied", False)),
            )
        )

    new_modal_x = modal_x
    new_modal_z = modal_z
    if cyc:
        new_modal_x = cyc[-1].end.x
        new_modal_z = cyc[-1].end.z
    return CycleEmissionDispatch(
        handled=True,
        emitted_motions=emitted,
        new_modal_x=new_modal_x,
        new_modal_z=new_modal_z,
        new_rough_idx=new_rough_idx,
        new_finish_idx=new_finish_idx,
    )


def execute_trace_context_with_steps(
    *,
    program,
    ctx: TraceExecutionContext,
    rough_cycles: list[list[object]],
    finish_cycles: list[list[object]],
    skip_optional_blocks: bool,
    emulate_g28_home: bool,
    x_is_diameter: bool,
    home_x: float,
    home_z: float,
    eval_words_fn,
    try_wcs_from_gcode_fn,
    to_machine_fn,
    wcs_off_fn,
    x_value_to_diameter_fn,
    x_delta_to_diameter_fn,
    motion_ctor,
    point_ctor,
) -> tuple[list[object], list[TraceStepSnapshot]]:
    motions: list[object] = []
    steps: list[TraceStepSnapshot] = []
    while 0 <= ctx.pc < len(program.blocks):
        pc_before = ctx.pc
        if skip_optional_blocks and program.blocks[pc_before].optional_skip:
            ctx.pc += 1
            continue
        step_stop, step_motions = execute_trace_step(
            program=program,
            ctx=ctx,
            rough_cycles=rough_cycles,
            finish_cycles=finish_cycles,
            skip_optional_blocks=skip_optional_blocks,
            emulate_g28_home=emulate_g28_home,
            x_is_diameter=x_is_diameter,
            home_x=home_x,
            home_z=home_z,
            eval_words_fn=eval_words_fn,
            try_wcs_from_gcode_fn=try_wcs_from_gcode_fn,
            to_machine_fn=to_machine_fn,
            wcs_off_fn=wcs_off_fn,
            x_value_to_diameter_fn=x_value_to_diameter_fn,
            x_delta_to_diameter_fn=x_delta_to_diameter_fn,
            motion_ctor=motion_ctor,
            point_ctor=point_ctor,
        )
        motions.extend(step_motions)
        src_block = pc_before
        src_nlabel = None
        if 0 <= pc_before < len(program.blocks):
            src_block = int(program.blocks[pc_before].index)
            src_nlabel = program.blocks[pc_before].nlabel
        steps.append(
            TraceStepSnapshot(
                pc_before=pc_before,
                pc_after=ctx.pc,
                source_block=src_block,
                source_nlabel=src_nlabel,
                stop=step_stop,
                emitted_count=len(step_motions),
                modal_x=ctx.state.modal_x,
                modal_z=ctx.state.modal_z,
                modal_move=ctx.state.modal_move,
                unit_scale=ctx.state.unit_scale,
                active_wcs=ctx.state.active_wcs,
                x_is_diameter=ctx.state.x_is_diameter,
                contour_definition=pc_before in (ctx.contour_block_indices or set()),
                variables=tuple(sorted((ctx.state.vars_map or {}).items())),
                words=ctx.words,
                signals=ctx.signals,
                feed_mode=ctx.state.feed_mode,
                spindle_rpm=ctx.state.spindle_rpm,
                spindle_mode=ctx.state.spindle_mode,
                surface_speed_m_min=ctx.state.surface_speed_m_min,
                spindle_limit_rpm=ctx.state.spindle_limit_rpm,
                spindle_running=ctx.state.spindle_running,
            )
        )
        if step_stop:
            break
    return motions, steps


def execute_trace_step(
    *,
    program,
    ctx: TraceExecutionContext,
    rough_cycles: list[list[object]],
    finish_cycles: list[list[object]],
    skip_optional_blocks: bool,
    emulate_g28_home: bool,
    x_is_diameter: bool,
    home_x: float,
    home_z: float,
    eval_words_fn,
    try_wcs_from_gcode_fn,
    to_machine_fn,
    wcs_off_fn,
    x_value_to_diameter_fn,
    x_delta_to_diameter_fn,
    motion_ctor,
    point_ctor,
) -> tuple[bool, list[object]]:
    motions: list[object] = []
    blocks = program.blocks
    state = ctx.state

    checkpoint("executed_blocks")
    ctx.words = ()
    ctx.signals = ()
    ctx.guard += 1
    if ctx.guard > 500000:
        raise RuntimeError("Source trace execution guard reached")

    block = blocks[ctx.pc]
    ast_node = None
    if getattr(program, "ast", None) is not None and 0 <= ctx.pc < len(program.ast.nodes):
        ast_node = program.ast.nodes[ctx.pc]

    if skip_optional_blocks and block.optional_skip:
        ctx.pc += 1
        return False, motions

    if ctx.pc in (ctx.contour_block_indices or set()):
        ctx.pc += 1
        return False, motions

    vars_map = state.vars_map if state.vars_map is not None else {}
    flow_dispatch = dispatch_macro_flow(
        block=block,
        pc=ctx.pc,
        blocks=blocks,
        variables=vars_map,
        label_to_index=ctx.label_to_index or {},
        while_to_end=ctx.while_to_end or {},
        end_to_while=ctx.end_to_while or {},
    )
    if flow_dispatch.handled:
        ctx.pc = flow_dispatch.next_pc
        return False, motions

    words = eval_words_fn(block.parsed_words, vars_map)
    if getattr(words, "errors", None):
        details = ", ".join(f"{tok.letter}{tok.expr}: {msg}" for tok, msg in words.errors)
        raise ValueError(f"Cannot evaluate CNC words at line {block.index + 1}: {block.raw}: {details}")
    ctx.words = tuple((k, v) for k in words for v in words.all(k))
    ctx.signals = signals_for_words(block.index, words)
    codes = classify_block_codes(words)
    all_g = codes.all_g
    all_m = codes.all_m
    gcode = codes.gcode
    mcode = codes.mcode

    if 40 in all_g:
        state.compensation_mode = 40
    elif 41 in all_g:
        state.compensation_mode = 41
    elif 42 in all_g:
        state.compensation_mode = 42
    if "T" in words:
        packed_tool = abs(int(round(words["T"])))
        state.active_tool = f"T{packed_tool:04d}"

    def tagged(items: list[object]) -> list[object]:
        return [
            replace(
                item,
                compensation_mode=state.compensation_mode,
                tool=state.active_tool,
            )
            if hasattr(item, "compensation_mode") and hasattr(item, "tool")
            else item
            for item in items
        ]

    for candidate in all_g:
        wcs_code = try_wcs_from_gcode_fn(candidate)
        if wcs_code is not None:
            old_x, old_z = wcs_off_fn(state.active_wcs)
            new_x, new_z = wcs_off_fn(wcs_code)
            state.modal_x += old_x - new_x
            state.modal_z += old_z - new_z
            state.active_wcs = wcs_code

    # Modal words on an M98 block are active for the called subprogram.  Apply
    # state-only words before transferring control; the source block is not
    # revisited after M99 returns.
    if 20 in all_g:
        state.unit_scale = 25.4
    if 21 in all_g:
        state.unit_scale = 1.0
    if 190 in all_g:
        state.x_is_diameter = True
    if 191 in all_g:
        state.x_is_diameter = False
    if 98 in all_g:
        state.feed_mode = "per_minute"
    if 99 in all_g:
        state.feed_mode = "per_revolution"
    if 50 in all_g and "S" in words:
        state.spindle_limit_rpm = words["S"]
    if 96 in all_g:
        state.spindle_mode = "css"
        if "S" in words:
            state.surface_speed_m_min = words["S"] * (0.3048 if state.unit_scale > 1.0 else 1.0)
        state.spindle_rpm = None
    elif 97 in all_g:
        state.spindle_mode = "rpm"
        if "S" in words:
            state.spindle_rpm = words["S"]
    elif "S" in words and 50 not in all_g:
        if state.spindle_mode == "css":
            state.surface_speed_m_min = words["S"] * (0.3048 if state.unit_scale > 1.0 else 1.0)
        else:
            state.spindle_rpm = words["S"]
    if 3 in all_m or 4 in all_m:
        state.spindle_running = True
    if 5 in all_m:
        state.spindle_running = False
    if "F" in words:
        state.modal_feed = words["F"] * state.unit_scale

    flow_mcode = flow_control_mcode(all_m, mcode)
    sub_flow = dispatch_subprogram_flow(
        mcode=flow_mcode,
        words=words,
        pc=ctx.pc,
        olabel_to_index=ctx.olabel_to_index or {},
        call_stack=ctx.call_stack or [],
        max_call_depth=ctx.max_call_depth,
    )
    ctx.call_stack = sub_flow.call_stack
    if sub_flow.handled:
        if sub_flow.stop:
            return True, motions
        ctx.pc = sub_flow.next_pc
        return False, motions

    # G4 is non-modal dwell: X is seconds and P is milliseconds, not motion.
    # Consume the complete block before modal-motion dispatch so G0/G1 state
    # cannot reinterpret the dwell value as an X coordinate.
    if 4 in all_g:
        ctx.pc += 1
        return False, motions

    if ctx.pc in (ctx.contour_block_indices or set()):
        ctx.pc += 1
        return False, motions

    cs = ctx.cycle_state
    cs.modal_x, cs.modal_z = state.modal_x, state.modal_z
    cs.modal_feed, cs.unit_scale = state.modal_feed, state.unit_scale
    cs.x_is_diameter = state.x_is_diameter
    cs.variables = state.vars_map
    cs.compensation_mode, cs.active_tool = state.compensation_mode, state.active_tool
    rough_cycles, finish_cycles = expand_cycle_block(program, ctx.pc, words, cs, **ctx.cycle_options)
    state.rough_idx = state.finish_idx = 0
    if any(g in (70, 71, 72, 73) for g in all_g) and "P" in words and "Q" in words:
        bounds = resolve_cycle_profile_indices(
            blocks, ctx.pc, int(words["P"]), int(words["Q"]), prefer_preceding=70 in all_g
        )
        if bounds is None:
            raise ValueError(f"Missing cycle P/Q contour at line {block.index + 1}")
        ctx.contour_block_indices.update(range(bounds[0], bounds[1] + 1))

    cyc = dispatch_cycle_block(
        ast_node,
        words,
        gcode,
        all_g=all_g,
        active_g90=state.active_g90,
        active_g92=state.active_g92,
        active_g94=state.active_g94,
        active_g83=state.active_g83,
        active_g84=state.active_g84,
        active_g80=state.active_g80,
    )
    state.active_g90 = cyc.active_g90
    state.active_g92 = cyc.active_g92
    state.active_g94 = cyc.active_g94
    state.active_g83 = cyc.active_g83
    state.active_g84 = cyc.active_g84
    state.active_g80 = cyc.active_g80

    if cyc.is_cycle_exec:
        ced = dispatch_cycle_emission(
            is_cycle_exec=cyc.is_cycle_exec,
            use_finish_cycle=cyc.use_finish_cycle,
            rough_cycles=rough_cycles,
            finish_cycles=finish_cycles,
            rough_idx=state.rough_idx,
            finish_idx=state.finish_idx,
            modal_x=state.modal_x,
            modal_z=state.modal_z,
            source_block=block.index,
            blocks=blocks,
            to_machine_fn=to_machine_fn,
            motion_ctor=motion_ctor,
            point_ctor=point_ctor,
        )
        motions.extend(tagged(ced.emitted_motions))
        state.modal_x = ced.new_modal_x
        state.modal_z = ced.new_modal_z
        state.rough_idx = ced.new_rough_idx
        state.finish_idx = ced.new_finish_idx
        ctx.pc += 1
        return False, motions

    has_pos = has_position_words(ast_node, words)
    state.modal_move = resolve_modal_move(ast_node, gcode, state.modal_move)
    non_motion_g = gcode is not None and gcode not in (0, 1, 2, 3, 32, 33) and gcode not in POSITION_NEUTRAL_GCODES

    if gcode == 30 or (gcode == 28 and not emulate_g28_home):
        # The machine-reference coordinates are unknown without a machine
        # configuration. Mark the affected axes unknown and break the plotted
        # trace instead of joining two operations with a fictitious rapid.
        state.unknown_x_after_g28 = ("X" in words) or ("U" in words)
        state.unknown_z_after_g28 = ("Z" in words) or ("W" in words)
        state.position_unknown_reason = "g30" if gcode == 30 else "g28"
        ctx.pc += 1
        return False, motions

    if non_motion_g and has_pos and gcode not in (28, 30) and gcode not in POSITION_NEUTRAL_GCODES:
        # An unmodeled position-bearing command may have changed physical
        # position. Taint only the addressed axes and resume after absolute
        # X/Z re-establishes them; never invent a connecting segment.
        state.unknown_x_after_g28 = ("X" in words) or ("U" in words)
        state.unknown_z_after_g28 = ("Z" in words) or ("W" in words)
        state.position_unknown_reason = "unsupported"
        ctx.pc += 1
        return False, motions

    g28d = dispatch_g28_home(
        emulate_g28_home=emulate_g28_home,
        gcode=gcode,
        words=words,
        modal_x=state.modal_x,
        modal_z=state.modal_z,
        unit_scale=state.unit_scale,
        x_is_diameter=state.x_is_diameter,
        home_x=home_x,
        home_z=home_z,
        to_machine_fn=to_machine_fn,
        x_value_to_diameter_fn=x_value_to_diameter_fn,
        x_delta_to_diameter_fn=x_delta_to_diameter_fn,
        motion_ctor=motion_ctor,
        point_ctor=point_ctor,
        source_block=block.index,
        source_nlabel=block.nlabel,
        source_raw=block.raw,
        active_wcs=state.active_wcs,
        wcs_off_fn=wcs_off_fn,
    )
    if g28d.handled:
        motions.extend(tagged(g28d.emitted_motions))
        state.modal_x = g28d.new_modal_x
        state.modal_z = g28d.new_modal_z
        ctx.pc += 1
        return False, motions

    md = dispatch_motion_block(
        has_pos=has_pos,
        non_motion_g=non_motion_g,
        modal_move=state.modal_move,
        words=words,
        modal_x=state.modal_x,
        modal_z=state.modal_z,
        modal_feed=state.modal_feed,
        unit_scale=state.unit_scale,
        x_is_diameter=state.x_is_diameter,
        to_machine_fn=to_machine_fn,
        x_value_to_diameter_fn=x_value_to_diameter_fn,
        x_delta_to_diameter_fn=x_delta_to_diameter_fn,
        motion_ctor=motion_ctor,
        point_ctor=point_ctor,
        source_block=block.index,
        source_nlabel=block.nlabel,
        source_raw=block.raw,
    )
    if md.handled:
        if md.emitted_motion is not None:
            if state.unknown_x_after_g28 or state.unknown_z_after_g28:
                if "X" in words:
                    state.unknown_x_after_g28 = False
                if "Z" in words:
                    state.unknown_z_after_g28 = False
                if not (state.unknown_x_after_g28 or state.unknown_z_after_g28):
                    emitted = md.emitted_motion
                    motions.extend(
                        tagged(
                            [
                                motion_ctor(
                                    emitted.move,
                                    emitted.end,
                                    emitted.end,
                                    radius=emitted.radius,
                                    feed=emitted.feed,
                                    i=emitted.i,
                                    k=emitted.k,
                                    source_block=emitted.source_block,
                                    source_nlabel=emitted.source_nlabel,
                                    source_raw=emitted.source_raw,
                                    source_kind=(
                                        "reference_resume"
                                        if state.position_unknown_reason in {"g28", "g30"}
                                        else "position_resume"
                                    ),
                                )
                            ]
                        )
                    )
                    state.position_unknown_reason = None
            else:
                motions.extend(tagged([md.emitted_motion]))
        state.modal_x = md.new_modal_x
        state.modal_z = md.new_modal_z
    ctx.pc += 1
    return False, motions
