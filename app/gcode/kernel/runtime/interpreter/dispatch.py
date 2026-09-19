"""Pure dispatch helpers for turning blocks, cycles and reference moves."""

from __future__ import annotations

# Dispatch helpers intentionally exit early per explicit CNC motion/cycle opcode.
# pylint: disable=too-many-return-statements
from ...frontend.ast import CycleAstNode, MotionAstNode
from ...geometry import apply_a_programming
from ..execution import retain_modal_turning_cycles
from .types import CycleDispatch, CycleEmissionDispatch, G28Dispatch, MotionDispatch

_X_AXIS_WORDS = ("X", "U")
_Z_AXIS_WORDS = ("Z", "W")


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
    supplementary_angles: bool = False,
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

    if modal_move == 1 and "A" in words:
        has_x = "X" in words or "U" in words
        has_z = "Z" in words or "W" in words
        tx, tz, _has_x, _has_z = apply_a_programming(
            modal_x,
            modal_z,
            tx,
            tz,
            has_x,
            has_z,
            words["A"],
            supplementary_angle=supplementary_angles,
        )

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
                playback_group=getattr(cm, "playback_group", None),
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
