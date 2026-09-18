from __future__ import annotations

import pytest

from app.gcode.kernel.ast import MotionAstNode
from app.gcode.kernel.interpreter import (
    dispatch_cycle_block,
    dispatch_g28_home,
    dispatch_motion_block,
    has_position_words,
    resolve_modal_move,
)
from app.gcode.kernel.model import Motion, Point2


def _motion_dispatch(**overrides):
    arguments = {
        "has_pos": True,
        "non_motion_g": False,
        "modal_move": 1,
        "words": {},
        "modal_x": 20.0,
        "modal_z": 5.0,
        "modal_feed": 120.0,
        "unit_scale": 1.0,
        "x_is_diameter": True,
        "to_machine_fn": lambda x, z: (x + 100.0, z - 50.0),
        "x_value_to_diameter_fn": lambda value, is_diameter: value if is_diameter else value * 2.0,
        "x_delta_to_diameter_fn": lambda value, is_diameter: value if is_diameter else value * 2.0,
        "motion_ctor": Motion,
        "point_ctor": Point2,
        "source_block": 7,
        "source_nlabel": 120,
        "source_raw": "G1 X24 Z-3",
    }
    arguments.update(overrides)
    return dispatch_motion_block(**arguments)


def _cycle_dispatch(words, gcode, **overrides):
    state = {
        "active_g90": False,
        "active_g92": False,
        "active_g94": False,
        "active_g83": False,
        "active_g84": False,
        "active_g80": True,
    }
    state.update(overrides)
    return dispatch_cycle_block(None, words, gcode, **state)


def test_motion_dispatch_converts_radius_programming_and_incremental_axes():
    result = _motion_dispatch(
        words={"U": 2.0, "W": -3.0},
        unit_scale=2.0,
        x_is_diameter=False,
    )

    assert result.handled
    assert result.new_modal_x == pytest.approx(28.0)
    assert result.new_modal_z == pytest.approx(-1.0)
    assert result.emitted_motion.start == Point2(120.0, -45.0)
    assert result.emitted_motion.end == Point2(128.0, -51.0)
    assert result.emitted_motion.feed == pytest.approx(120.0)


def test_arc_center_words_emit_a_zero_endpoint_arc_and_scale_i_as_diameter():
    result = _motion_dispatch(
        has_pos=False,
        modal_move=2,
        words={"I": -5.0, "K": 2.0},
        unit_scale=2.0,
    )

    assert result.handled
    assert result.emitted_motion.start == result.emitted_motion.end
    assert result.emitted_motion.i == pytest.approx(-20.0)
    assert result.emitted_motion.k == pytest.approx(4.0)


def test_identical_linear_endpoint_is_handled_without_emitting_a_motion():
    result = _motion_dispatch(words={"X": 20.0, "Z": 5.0})

    assert result.handled
    assert result.emitted_motion is None


@pytest.mark.parametrize(
    ("overrides", "handled"),
    [({"has_pos": False}, False), ({"non_motion_g": True}, False), ({"modal_move": 33}, False)],
)
def test_non_motion_blocks_do_not_leak_into_the_motion_trace(overrides, handled):
    result = _motion_dispatch(**overrides)

    assert result.handled is handled
    assert result.emitted_motion is None


def test_g28_homes_only_selected_axis_and_keeps_modal_coordinates_in_the_wcs():
    result = dispatch_g28_home(
        emulate_g28_home=True,
        gcode=28,
        words={"U": 4.0},
        modal_x=10.0,
        modal_z=-5.0,
        unit_scale=1.0,
        x_is_diameter=True,
        home_x=500.0,
        home_z=600.0,
        to_machine_fn=lambda x, z: (x + 100.0, z + 200.0),
        x_value_to_diameter_fn=lambda value, _is_diameter: value,
        x_delta_to_diameter_fn=lambda value, _is_diameter: value,
        motion_ctor=Motion,
        point_ctor=Point2,
        source_block=4,
        source_nlabel=40,
        source_raw="G28 U4",
        active_wcs=54,
        wcs_off_fn=lambda _wcs: (100.0, 200.0),
    )

    assert result.handled
    assert [(item.start, item.end) for item in result.emitted_motions] == [
        (Point2(110.0, 195.0), Point2(114.0, 195.0)),
        (Point2(114.0, 195.0), Point2(500.0, 195.0)),
    ]
    assert (result.new_modal_x, result.new_modal_z) == (400.0, -5.0)
    assert all(item.source_kind == "g28" for item in result.emitted_motions)


def test_disabled_g28_emulation_leaves_state_and_trace_untouched():
    result = dispatch_g28_home(
        emulate_g28_home=False,
        gcode=28,
        words={"U": 4.0},
        modal_x=10.0,
        modal_z=-5.0,
        unit_scale=1.0,
        x_is_diameter=True,
        home_x=500.0,
        home_z=600.0,
        to_machine_fn=lambda x, z: (x, z),
        x_value_to_diameter_fn=lambda value, _is_diameter: value,
        x_delta_to_diameter_fn=lambda value, _is_diameter: value,
        motion_ctor=Motion,
        point_ctor=Point2,
        source_block=4,
        source_nlabel=None,
        source_raw="G28 U4",
        active_wcs=54,
        wcs_off_fn=lambda _wcs: (0.0, 0.0),
    )

    assert not result.handled
    assert result.emitted_motions == []
    assert (result.new_modal_x, result.new_modal_z) == (10.0, -5.0)


def test_tool_change_cancels_modal_axial_cycles():
    result = _cycle_dispatch(
        {"T": 202.0},
        None,
        active_g83=True,
        active_g84=False,
        active_g80=False,
    )

    assert not result.is_cycle_exec
    assert not result.active_g83
    assert not result.active_g84
    assert result.active_g80


@pytest.mark.parametrize("cycle", [83, 84])
def test_axial_cycle_continues_modally_on_an_axis_only_block(cycle):
    result = _cycle_dispatch(
        {"Z": -20.0},
        None,
        active_g83=cycle == 83,
        active_g84=cycle == 84,
        active_g80=False,
    )

    assert result.is_cycle_exec
    assert result.active_g83 is (cycle == 83)
    assert result.active_g84 is (cycle == 84)


def test_g80_cancels_axial_cycle_and_prevents_modal_execution():
    result = _cycle_dispatch(
        {"Z": -20.0},
        80,
        active_g83=True,
        active_g80=False,
    )

    assert not result.is_cycle_exec
    assert not result.active_g83
    assert result.active_g80


def test_threading_codes_resolve_to_linear_motion_without_losing_modal_fallback():
    node = MotionAstNode(kind="motion", block_index=0, raw="G32 Z-10", g_code=32, z_expr="-10")

    assert resolve_modal_move(node, None, current_modal_move=0) == 1
    assert resolve_modal_move(None, None, current_modal_move=3) == 3
    assert has_position_words(node, {})
