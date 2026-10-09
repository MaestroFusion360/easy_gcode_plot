from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
from gcode_samples import (
    ARC_ABSOLUTE,
    ARC_RADIUS,
    ARC_RELATIVE,
    MILLING_ARC_PLANES,
    MILLING_CYCLES,
    MILLING_HELIX_FULL_CIRCLE,
)

from app.gcode.kernel import execute
from app.gcode.kernel.api import engine as kernel_engine
from app.gcode.kernel.milling.kinematics import (
    CATALOG_PATH,
    InvalidKinematicsProfile,
    load_catalog,
    point_orientation,
    profile_document,
    save_profile_override,
    user_catalog_path,
)
from app.gcode.trace_tools import render_trace, sample_motion, trace_statistics

_MILLING_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "milling" / "fanuc"
_FIXTURE_KINEMATICS = {
    "smpl_sim08_5ax_fanuc_mm.nc": "5ax_table_ac",
    "test_5ax_ac_fanuc.nc": "5ax_table_ac",
    "test_5ax_bc_fanuc.nc": "5ax_table_bc",
    "indexed_table_a.nc": "4ax_table_a",
    "indexed_table_b.nc": "4ax_table_b",
    "indexed_table_c.nc": "4ax_table_c",
    "Machine_tool_simulation.ptp": "5ax_table_ac_angled",
    "Machine_tool_simulation_BC.ptp": "5ax_table_bc_angled",
    "g68_2_cube.nc": "5ax_table_ac_angled",
    "impeller.ptp": "5ax_table_bc_angled",
    "impeller2.ptp": "5ax_table_ac_angled",
}
_MILLING_FIXTURE_CASES = tuple(
    (path.name, _FIXTURE_KINEMATICS.get(path.name))
    for path in sorted(_MILLING_FIXTURE_DIR.iterdir())
    if path.is_file() and path.suffix.lower() in {".nc", ".ptp"}
)


@pytest.mark.parametrize("cycle", ["G99 G81 Z10 R2 F100", "G91 G99 G81 Z5 R-18 F100"])
def test_drilling_depth_above_r_is_invalid(cycle):
    result = execute(cycle + "\nM30", "fanuc_mill")
    assert not result.ok
    assert any(d.code == "INVALID_DRILLING_DEPTH" and d.status == "invalid_geometry" for d in result.diagnostics)
    assert not result.motions


@pytest.mark.parametrize("depth", [-5, 2])
def test_drilling_depth_at_or_below_r_is_valid(depth):
    result = execute(f"G99 G81 Z{depth} R2 F100\nG80\nM30", "fanuc_mill")
    assert result.ok, result.diagnostics
    assert sum(m.move == 1 for m in result.motions) == (1 if depth < 2 else 0)


def _motion_endpoints(result, source_blocks):
    return [
        (motion.end_x, motion.end_y, motion.end_z)
        for motion in result.motions
        if motion.source_block in source_blocks and motion.source_kind == "motion"
    ]


def test_indexed_table_b_maps_tool_tip_z_moves_into_fixed_wcs_x():
    result = execute(
        "G90 G0 B90\nG0 Z50\nG91 B180\nG90 G0 Z100\nM30",
        language="fanuc_mill",
        kinematics="4ax_table_b",
    )
    assert result.ok and result.complete, result.diagnostics
    for motion, expected in zip(result.motions, ((50, 0, 0), (-100, 0, 0)), strict=True):
        assert (motion.end_x, motion.end_y, motion.end_z) == pytest.approx(expected, abs=1e-8)
    assert result.motions[0].tool_orientation[0][2] == pytest.approx(1)
    assert result.motions[1].tool_orientation[0][2] == pytest.approx(-1)


def test_rotary_profile_override_is_persistent_and_does_not_edit_installed_catalog(tmp_path):
    original = CATALOG_PATH.read_bytes()
    assert user_catalog_path() == tmp_path / "rotary_profiles.json"
    edited = profile_document("4ax_table_b")
    edited["table"][0]["axis"] = [0, -1, 0]
    save_profile_override("4ax_table_b", edited)
    assert user_catalog_path().exists()
    assert CATALOG_PATH.read_bytes() == original
    assert load_catalog()["4ax_table_b"].table_rotary_axes[0].axis == pytest.approx((0, -1, 0))
    result = execute("G90 G0 B90\nG0 Z10\nM30", language="fanuc_mill", kinematics="4ax_table_b")
    assert result.ok, result.diagnostics
    assert result.motions[-1].end_x == pytest.approx(-10)
    invalid = profile_document("4ax_table_b")
    invalid["table"][0]["axis"] = [0, 0, 0]
    with pytest.raises(InvalidKinematicsProfile):
        save_profile_override("4ax_table_b", invalid)
    assert load_catalog()["4ax_table_b"].table_rotary_axes[0].axis == pytest.approx((0, -1, 0))


def test_invalid_user_rotary_catalog_is_strict_by_default_and_has_explicit_fallback():
    path = user_catalog_path()
    path.write_text("{broken json", encoding="utf-8")

    with pytest.raises(InvalidKinematicsProfile):
        load_catalog()

    fallback = load_catalog(ignore_user_errors=True)
    assert {key for key, profile in fallback.items() if profile.enabled} == {
        "4ax_table_a",
        "4ax_table_b",
        "4ax_table_c",
        "5ax_table_ac_angled",
        "5ax_table_bc_angled",
    }


def test_g10_at_rotary_index_preserves_machine_position_and_rebases_next_move():
    source = "G21 G90 G54\nG0 X10 Z20\nB90\nG10 L2 P1 X100 Z5\nG0 X10 Z20\nM30"
    result = execute(source, language="fanuc_mill", kinematics="4ax_table_b")
    assert result.ok, result.diagnostics
    assert result.execution_steps[3].position == pytest.approx(result.execution_steps[2].position)
    assert (result.motions[-1].start_x, result.motions[-1].start_z) == pytest.approx((20, -10))
    assert (result.motions[-1].end_x, result.motions[-1].end_z) == pytest.approx((120, -5))


def test_rotary_angles_and_wcs_are_recorded_per_execution_step():
    source = "G21 G90 G54\nG10 L2 P1 X100 Z5\nG10 L2 P2 X-20 Z30\nG0 X10 Z20\nB90\nG55\nG0 X10 Z20\nM30"
    result = execute(source, language="fanuc_mill", kinematics="4ax_table_b")
    assert result.ok, result.diagnostics
    assert [dict(step.rotary_angles)["B"] for step in result.execution_steps] == [0, 0, 0, 0, 90, 90, 90, 90]
    assert result.execution_steps[5].active_wcs == 55
    assert result.execution_steps[5].position == pytest.approx(result.execution_steps[4].position)
    assert (result.motions[-1].end_x, result.motions[-1].end_z) == pytest.approx((0, 20))


def test_indexed_table_a_fixture_preserves_both_sides_and_restores_a_zero(fixture_text):
    result = execute(
        fixture_text("milling/fanuc/indexed_table_a.nc"), language="fanuc_mill", kinematics="4ax_table_a", home_z=500
    )
    assert result.ok and result.complete, result.diagnostics
    indices = [event for event in result.events if event.kind == "ROTARY_INDEX"]
    assert [(event.old_abc[0], event.new_abc[0]) for event in indices] == [
        (0.0, -180.0),
        (-180.0, 0.0),
    ]
    z45 = [motion for motion in result.motions if motion.source_raw == "Z45.911"]
    assert len(z45) >= 2
    assert (z45[0].end_x, z45[0].end_y, z45[0].end_z) == pytest.approx((506.0, 86.909, 45.911), abs=1e-6)
    assert (z45[-1].end_x, z45[-1].end_y, z45[-1].end_z) == pytest.approx((486.0, -86.909, -45.911), abs=1e-6)
    restored = next(motion for motion in result.motions if motion.source_block > indices[-1].source_block)
    assert restored.tool_orientation[2][2] == pytest.approx(1.0)


def test_table_c_fixture_xc_contour_overlays_first_xy_contour(fixture_text):
    result = execute(fixture_text("milling/fanuc/indexed_table_c.nc"), language="fanuc_mill", kinematics="4ax_table_c")
    assert result.ok and result.complete, result.diagnostics
    assert not result.diagnostics

    first = [
        motion
        for motion in result.motions
        if 10 <= motion.source_block <= 33 and motion.move in (1, 2, 3) and abs(motion.end_z + 40) < 1e-8
    ]
    second = [
        motion
        for motion in result.motions
        if 45 <= motion.source_block <= 808 and motion.move == 1 and abs(motion.end_z + 40) < 1e-8
    ]
    assert len(first) == 22
    assert len(second) == 764
    first_xy = [(first[0].start_x, first[0].start_y)]
    for index, motion in enumerate(first):
        first_xy.extend((point.x, point.y) for point in sample_motion(motion, index, arc_points_per_circle=2000))
    polyline = np.asarray(first_xy)
    start, direction = polyline[:-1], np.diff(polyline, axis=0)
    squared_length = np.maximum(np.sum(direction * direction, axis=1), 1e-20)
    maximum_distance = 0.0
    for motion in second:
        endpoint = np.asarray((motion.end_x, motion.end_y))
        fraction = np.clip(np.sum((endpoint - start) * direction, axis=1) / squared_length, 0, 1)
        distance = np.linalg.norm(endpoint - (start + fraction[:, None] * direction), axis=1).min()
        maximum_distance = max(maximum_distance, distance)
    assert maximum_distance < 0.05
    assert (second[0].start_x, second[0].start_y) == pytest.approx(first_xy[0], abs=0.002)
    assert (second[-1].end_x, second[-1].end_y) == pytest.approx(first_xy[-1], abs=0.002)

    c_only = next(motion for motion in result.motions if motion.source_raw == "C-112.836")
    assert (c_only.start_x, c_only.start_y) != (c_only.end_x, c_only.end_y)
    assert any(event.kind == "ROTARY_MOTION" for event in result.events)


def test_table_c_absolute_and_incremental_c_only_moves_follow_positive_z_rotation():
    result = execute(
        "G90 G0 X10 Y0\nG1 C90 F100\nG91 C-180\nM30",
        language="fanuc_mill",
        kinematics="4ax_table_c",
    )
    assert result.ok and result.complete, result.diagnostics
    for motion, expected in zip(result.motions[-2:], ((0.0, 10.0), (0.0, -10.0)), strict=True):
        assert (motion.end_x, motion.end_y) == pytest.approx(expected, abs=1e-8)
    assert [event.kind for event in result.events if event.kind.startswith("ROTARY_")] == [
        "ROTARY_MOTION",
        "ROTARY_MOTION",
    ]


def test_table_c_cutter_compensation_keeps_uncompensated_xc_path():
    source = "G17 G90 G0 X10 Y0 C0\nG41 G1 X10 C90 D1 F100\nG1 X10 C180\nG40 G1 X10 C270\nM30"
    tools = {"T1": {"type": "mill_flat", "diameter": 6.0, "length": 50.0}}
    nominal = execute(source.replace("G41 ", "").replace("G40 ", ""), language="fanuc_mill", kinematics="4ax_table_c")
    result = execute(source, language="fanuc_mill", kinematics="4ax_table_c", milling_tools=tools)

    assert result.ok and result.complete, result.diagnostics
    assert [(m.start_x, m.start_y, m.end_x, m.end_y) for m in result.motions] == pytest.approx(
        [(m.start_x, m.start_y, m.end_x, m.end_y) for m in nominal.motions]
    )
    assert not any(m.compensation_applied for m in result.motions)
    assert {d.code for d in result.diagnostics} == {"UNSUPPORTED_TABLE_C_CUTTER_COMPENSATION"}
    assert result.diagnostics[0].severity == "warning"


@pytest.mark.parametrize(("profile", "axis"), [("4ax_table_a", "A"), ("4ax_table_b", "B")])
def test_table_a_b_still_reject_simultaneous_rotary_linear_motion(profile, axis):
    result = execute(f"G90 G1 X10 {axis}90 F100\nM30", language="fanuc_mill", kinematics=profile)
    assert not result.complete
    assert result.diagnostics[0].code == "UNSUPPORTED_SIMULTANEOUS_ROTARY_MOTION"


@pytest.mark.parametrize(
    ("profile", "rotary_word"),
    [("5ax_table_ac_angled", "A30 C45"), ("5ax_table_bc_angled", "B30 C45")],
)
def test_g43_4_tcp_linear_motion_keeps_programmed_tool_center_path(profile, rotary_word):
    result = execute(
        f"G90 G0 X1 Y2 Z3\nG1 G43.4 H7 Z20 F100\nG1 X10 Y5 Z-2 {rotary_word} F100\nG49\nM30",
        language="fanuc_mill",
        kinematics=profile,
    )
    assert result.ok and result.complete, result.diagnostics
    tcp_move = next(m for m in result.motions if rotary_word in m.source_raw)
    assert (tcp_move.end_x, tcp_move.end_y, tcp_move.end_z) == pytest.approx((10, 5, -2))
    assert tcp_move.orientation is None
    assert tcp_move.start_tool_orientation is not None
    assert tcp_move.tool_orientation is not None
    assert tcp_move.start_tool_orientation != tcp_move.tool_orientation


def test_g43_4_accepts_activation_then_continuous_rotary_linear_moves():
    for profile, initial, first, second in (
        ("5ax_table_ac_angled", "A0 C0", "A30 C45", "A60 C90"),
        ("5ax_table_bc_angled", "B0 C0", "B30 C45", "B60 C90"),
    ):
        result = execute(
            f"G90 G0 X0 Y0 Z0 {initial}\nG43.4 H1\nG1 X10 Y20 Z30 {first} F100\nG1 X20 Y25 Z35 {second}\nM30",
            language="fanuc_mill",
            kinematics=profile,
        )
        assert result.ok and result.complete, result.diagnostics
        assert result.motions[-1].orientation is None
        assert result.motions[-1].start_tool_orientation != result.motions[-1].tool_orientation


def test_g43_4_rejects_unsupported_profile_and_post_g49_motion_but_accepts_tcp_arc():
    unsupported = execute("G43.4 H1\nM30", language="fanuc_mill", kinematics="4ax_table_a")
    assert unsupported.diagnostics[0].code == "TCP_KINEMATICS_REQUIRED"
    arc = execute(
        "G90 G0 X0 Y0 A0 C0\nG43.4 H1\nG2 X10 Y0 I5 J0 A30 C45 F100\nM30",
        language="fanuc_mill",
        kinematics="5ax_table_ac_angled",
    )
    assert arc.ok and arc.complete, arc.diagnostics
    assert arc.motions[-1].arc is not None
    assert arc.motions[-1].start_tool_orientation != arc.motions[-1].tool_orientation
    after_cancel = execute(
        "G90 G0 X0 A0 C0\nG43.4 H1\nG1 X10 A30 C45 F100\nG49\nG1 X20 A60 C90\nM30",
        language="fanuc_mill",
        kinematics="5ax_table_ac_angled",
    )
    assert after_cancel.diagnostics[-1].code == "UNSUPPORTED_SIMULTANEOUS_ROTARY_MOTION"


@pytest.mark.parametrize(("reference", "source_kind"), [("G53 Z0", "g53"), ("G91 G28 Z0", "g28")])
@pytest.mark.parametrize("home_z", [300.0, 500.0])
def test_g43_4_cancel_keeps_reference_move_contiguous_and_uses_home_z(reference, source_kind, home_z):
    result = execute(
        f"G90 G0 X0 Y0 Z0 A0 C0\nG43.4 H1\nG1 X10 Y20 Z30 A30 C45 F100\nG0 X20 Y10 Z180 A30 C45\nG49\n{reference}\nM30",
        language="fanuc_mill",
        kinematics="5ax_table_ac_angled",
        home_z=home_z,
    )
    assert result.ok and result.complete, result.diagnostics
    retract_start = next(m for m in result.motions if "X20 Y10 Z180" in m.source_raw)
    reference_move = next(m for m in result.motions if m.source_kind == source_kind)
    assert (reference_move.start_x, reference_move.start_y, reference_move.start_z) == pytest.approx(
        (retract_start.end_x, retract_start.end_y, retract_start.end_z),
        abs=1e-7,
    )
    orientation = np.asarray(point_orientation(load_catalog()["5ax_table_ac_angled"], dict(result.rotary_angles)))
    start = np.array((reference_move.start_x, reference_move.start_y, reference_move.start_z))
    end = np.array((reference_move.end_x, reference_move.end_y, reference_move.end_z))
    raw_start, raw_end = orientation.T @ start, orientation.T @ end
    assert raw_end == pytest.approx((raw_start[0], raw_start[1], home_z))
    assert end - start == pytest.approx(orientation[:, 2] * (home_z - raw_start[2]))
    assert reference_move.start_tool_orientation == reference_move.tool_orientation


@pytest.mark.parametrize("name,kinematics", _MILLING_FIXTURE_CASES)
def test_fanuc_mill_fixture_motion_trace_never_teleports_between_adjacent_moves(name, kinematics, fixture_text):
    result = execute(
        fixture_text(f"milling/fanuc/{name}"),
        language="fanuc_mill",
        kinematics=kinematics,
        home_z=500.0,
    )
    assert result.ok and result.complete, result.diagnostics
    assert result.motions

    steps = {step.source_block: step for step in result.execution_steps}
    for previous, current in zip(result.motions, result.motions[1:]):
        expected = np.array((previous.end_x, previous.end_y, previous.end_z))
        previous_step, current_step = steps[previous.source_block], steps[current.source_block]
        if kinematics and previous.source_kind in {"g28", "g53"}:
            # Reference return ends a trace run; the following indexed approach
            # is independently resolved and must not be joined to the old end.
            continue
        actual = (current.start_x, current.start_y, current.start_z)
        if (
            kinematics
            and previous_step.rotary_angles != current_step.rotary_angles
            and not np.allclose(actual, expected, atol=1e-7, rtol=0)
        ):
            # An index changes the displayed table frame, not programmed XYZ.
            # Verify the exact frame change rather than accepting arbitrary gaps.
            catalog = load_catalog()
            old_frame = np.asarray(point_orientation(catalog[kinematics], dict(previous_step.rotary_angles)))
            new_frame = np.asarray(point_orientation(catalog[kinematics], dict(current_step.rotary_angles)))
            expected = new_frame @ old_frame.T @ expected
        assert (current.start_x, current.start_y, current.start_z) == pytest.approx(
            expected,
            abs=1e-7,
        ), f"{name}: unexpected trajectory gap between N{previous.source_nlabel} and N{current.source_nlabel}"


@pytest.mark.parametrize(
    ("angle", "expected_y", "expected_z"),
    [(90, -20.0, 10.0), (270, 20.0, -10.0)],
)
def test_table_a_quarter_turn_signs(angle, expected_y, expected_z):
    result = execute(
        f"G90 G0 A{angle}\nG0 Y10 Z20\nM30",
        language="fanuc_mill",
        kinematics="4ax_table_a",
    )
    assert result.ok and result.complete, result.diagnostics
    assert (result.motions[-1].end_y, result.motions[-1].end_z) == pytest.approx((expected_y, expected_z), abs=1e-8)


@pytest.mark.parametrize(
    ("reference", "source_kind"),
    [("G91 G28 Z0", "g28"), ("G53 G0 Z100", "g53")],
)
def test_reference_return_after_b_index_targets_machine_home_axes(reference, source_kind):
    source = f"G90 G0 X10 Z20\nB90\n{reference}\nG90 G0 Z10\n{reference}\nM30"
    result = execute(source, language="fanuc_mill", kinematics="4ax_table_b", home_z=100)
    assert result.ok and result.complete, result.diagnostics
    returns = [motion for motion in result.motions if motion.source_kind == source_kind]
    assert len(returns) == 2
    for motion, start in zip(returns, ((20, 0, -10), (10, 0, -10))):
        assert (motion.start_x, motion.start_y, motion.start_z) == pytest.approx(start, abs=1e-8)
        assert (motion.end_x, motion.end_y, motion.end_z) == pytest.approx((100, 0, -10), abs=1e-8)


def test_incremental_g53_z_after_b_index_uses_oriented_machine_z():
    result = execute(
        "G90 G0 X10 Z20\nB90\nG53 G0 Z100\nG91 G53 G0 Z10\nM30",
        language="fanuc_mill",
        kinematics="4ax_table_b",
        home_z=100,
    )
    assert result.ok and result.complete, result.diagnostics
    assert result.motions[-1].end_x == pytest.approx(110)
    assert result.motions[-1].end_z == pytest.approx(-10)


def test_b_index_obeys_g90_g91_on_same_block_and_modal_blocks():
    result = execute(
        "G90 G0 B90\nG91 B90\nG90 B180\nG91 B-90\nG90 G0 Z20\nM30",
        language="fanuc_mill",
        kinematics="4ax_table_b",
    )
    assert result.ok and result.complete, result.diagnostics
    indices = [event for event in result.events if event.kind == "ROTARY_INDEX"]
    assert [event.new_abc[1] for event in indices] == pytest.approx([90, 180, 90])
    assert result.motions[-1].end_x == pytest.approx(20)


@pytest.mark.parametrize(
    ("angle", "expected_x", "expected_z"),
    [(40, 64.27876097, 76.60444431), (320, -64.27876097, 76.60444431)],
)
def test_non_right_angle_b_index_preserves_signed_side(angle, expected_x, expected_z):
    result = execute(
        f"G90 G0 B{angle}\nG0 Z100\nM30",
        language="fanuc_mill",
        kinematics="4ax_table_b",
    )
    assert result.ok and result.complete, result.diagnostics
    assert (result.motions[-1].end_x, result.motions[-1].end_z) == pytest.approx((expected_x, expected_z), abs=1e-6)


def test_milling_polar_drilling_fixture_matches_absolute_and_incremental_manual_examples(fixture_text):
    result = execute(fixture_text("milling/fanuc/polar_drilling.nc"), language="fanuc_mill")
    assert result.ok, result.diagnostics

    expected = [(86.602540, 50.0), (-86.602540, 50.0), (0.0, -100.0)]
    for blocks in ({4, 5, 6}, {10, 11, 12}):
        holes = [
            (motion.end_x, motion.end_y)
            for motion in result.motions
            if motion.source_block in blocks and motion.source_kind == "cycle" and motion.move == 1
        ]
        assert len(holes) == len(expected)
        for actual, target in zip(holes, expected, strict=True):
            assert actual == pytest.approx(target, abs=1e-6)


def test_milling_polar_incremental_center_and_g15_cartesian_restore():
    result = execute(
        "G21 G17 G90\nG0 X10 Y20\nG91 G16\nG0 X5 Y90\nG15 G90\nG0 X1 Y2\nM30",
        language="fanuc_mill",
    )
    assert result.ok, result.diagnostics
    assert [(motion.end_x, motion.end_y) for motion in result.motions] == pytest.approx([(10, 20), (10, 25), (1, 2)])


@pytest.mark.parametrize("activation", ("G17 G90 G16", "G90 G17 G16", "G16 G17 G90"))
def test_milling_polar_activation_uses_effective_block_modes_regardless_of_word_order(activation):
    result = execute(f"G21\n{activation}\nG0 X10 Y90\nM30", language="fanuc_mill")
    assert result.ok, result.diagnostics
    assert (result.motions[-1].end_x, result.motions[-1].end_y) == pytest.approx((0, 10), abs=1e-6)


def test_milling_polar_plane_change_resets_modal_radius_and_angle():
    result = execute(
        "G21 G17 G90 G16\nG0 X10 Y30\nG18\nG0 X90\nG0 Z5\nM30",
        language="fanuc_mill",
    )
    assert result.ok, result.diagnostics
    switched, radial = result.motions[-2:]
    assert (switched.end_x, switched.end_z) == pytest.approx((0, 0), abs=1e-6)
    assert (radial.end_x, radial.end_z) == pytest.approx((5, 0), abs=1e-6)


@pytest.mark.parametrize(
    ("plane", "words", "expected"),
    [
        (17, "X10 Y90", (0, 10, 0)),
        (18, "Z10 X90", (10, 0, 0)),
        (19, "Y10 Z90", (0, 0, 10)),
        (17, "X10 Y-90", (0, -10, 0)),
        (17, "X10 Y390", (8.660254, 5, 0)),
    ],
)
def test_milling_polar_plane_axis_order_and_unbounded_angles(plane, words, expected):
    result = execute(f"G21 G{plane} G90 G16\nG0 {words}\nM30", language="fanuc_mill")
    assert result.ok, result.diagnostics
    motion = result.motions[-1]
    assert (motion.end_x, motion.end_y, motion.end_z) == pytest.approx(expected, abs=1e-6)


def test_milling_polar_units_scale_radius_but_not_angle_and_macro_words_resolve_first():
    source = "#100=1\n#101=90\nG20 G17 G90 G16\nG0 X[#100] Y[#101]\nG21 G91\nG0 X1\nM30"
    result = execute(source, language="fanuc_mill")
    assert result.ok, result.diagnostics
    endpoints = [(motion.end_x, motion.end_y) for motion in result.motions]
    for actual, expected in zip(endpoints, [(0, 25.4), (0, 26.4)], strict=True):
        assert actual == pytest.approx(expected, abs=1e-6)


def test_milling_polar_radius_arc_resolves_cartesian_endpoint():
    result = execute(
        "G21 G17 G90\nG0 X10 Y0\nG16\nG2 X10 Y90 R10 F100\nM30",
        language="fanuc_mill",
    )
    assert result.ok, result.diagnostics
    arc = result.motions[-1]
    assert arc.move == 2
    assert (arc.end_x, arc.end_y, arc.end_z) == pytest.approx((0, 10, 0), abs=1e-6)
    assert arc.radius == pytest.approx(10)


@pytest.mark.parametrize("center_words", ["I-10 J0", "I-10 J0 R10", ""])
def test_milling_polar_arc_without_exclusive_r_is_skipped_and_execution_recovers(center_words):
    source = f"G21 G17 G90\nG0 X10 Y0\nG16\nG2 X10 Y90 {center_words} M8\nG1 X10 Y180\nG15\nM30"
    result = execute(source, language="fanuc_mill")
    assert not result.ok
    assert result.complete
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["UNSUPPORTED_POLAR_ARC_CENTER"]
    assert all(signal.block_index != 3 for signal in result.signals)
    assert all(motion.source_block != 3 for motion in result.motions)
    assert (result.motions[-1].end_x, result.motions[-1].end_y) == pytest.approx((-10, 0), abs=1e-6)


def test_milling_polar_control_coordinates_remain_cartesian_and_do_not_change_radius_angle():
    dwell = execute("G17 G90 G16\nG0 X10 Y0\nG4 X999\nG0 Y90\nM30", language="fanuc_mill")
    g52 = execute("G17 G90 G16\nG52 X10 Y20\nG15\nG0 X0 Y0\nM30", language="fanuc_mill")
    g51 = execute("G17 G90 G16\nG51 X0 Y0 P2000\nG15\nG0 X1 Y1\nM30", language="fanuc_mill")
    g68 = execute("G17 G90 G16\nG68 X0 Y0 R90\nG15\nG0 X1 Y0\nM30", language="fanuc_mill")
    g10 = execute("G17 G90 G16\nG10 L2 P1 X10 Y20\nG15 G54\nG0 X0 Y0\nM30", language="fanuc_mill")
    g53 = execute("G17 G90 G16\nG53 G0 X3 Y4\nM30", language="fanuc_mill")
    for result in (dwell, g52, g51, g68, g10, g53):
        assert result.ok, result.diagnostics
    assert (dwell.motions[-1].end_x, dwell.motions[-1].end_y) == pytest.approx((0, 10))
    assert (g52.motions[-1].end_x, g52.motions[-1].end_y) == pytest.approx((10, 20))
    assert (g51.motions[-1].end_x, g51.motions[-1].end_y) == pytest.approx((2, 2))
    assert (g68.motions[-1].end_x, g68.motions[-1].end_y) == pytest.approx((0, 1))
    assert (g10.motions[-1].end_x, g10.motions[-1].end_y) == pytest.approx((10, 20))
    assert (g53.motions[-1].end_x, g53.motions[-1].end_y) == pytest.approx((3, 4))


def test_milling_polar_conversion_precedes_wcs_local_rotation_and_scaling_transforms():
    extended = execute(
        "G21 G17 G90 G54.1 P7 G16\nG0 X10 Y90\nM30",
        language="fanuc_mill",
        extended_wcs_offsets={7: (100, 200, 3)},
    )
    local = execute("G21 G17 G90\nG52 X10 Y20\nG16\nG0 X10 Y90\nM30", language="fanuc_mill")
    rotated = execute("G21 G17 G90\nG68 X0 Y0 R90\nG16\nG0 X10 Y0\nM30", language="fanuc_mill")
    scaled = execute("G21 G17 G90\nG51 X0 Y0 P2000\nG16\nG0 X10 Y0\nM30", language="fanuc_mill")
    for result in (extended, local, rotated, scaled):
        assert result.ok, result.diagnostics
    assert (extended.motions[-1].end_x, extended.motions[-1].end_y, extended.motions[-1].end_z) == pytest.approx(
        (100, 210, 0), abs=1e-6
    )
    assert (local.motions[-1].end_x, local.motions[-1].end_y) == pytest.approx((10, 30), abs=1e-6)
    assert (rotated.motions[-1].end_x, rotated.motions[-1].end_y) == pytest.approx((0, 10), abs=1e-6)
    assert (scaled.motions[-1].end_x, scaled.motions[-1].end_y) == pytest.approx((20, 0), abs=1e-6)


def test_milling_polar_modal_conflict_skips_complete_block():
    result = execute("G17 G90\nG15 G16 X10 Y30\nG0 X1 Y2\nM30", language="fanuc_mill")
    assert not result.ok
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["MODAL_GROUP_CONFLICT"]
    assert [(motion.end_x, motion.end_y) for motion in result.motions] == pytest.approx([(1, 2)])


@pytest.mark.parametrize(
    ("programming", "selection", "offsets"),
    [
        ("G10 L2 P1", "G54", {}),
        ("G10 L20 P7", "G54.1 P7", {7: (0, 0, 0)}),
    ],
)
def test_milling_g10_g91_incrementally_modifies_existing_work_offset(programming, selection, offsets):
    source = f"G21 G90\n{programming} X100 Y20\nG91\n{programming} X5 Y-2\nG90 {selection}\nG0 X0 Y0\nM30"
    result = execute(source, language="fanuc_mill", extended_wcs_offsets=offsets)
    assert result.ok, result.diagnostics
    assert (result.motions[-1].end_x, result.motions[-1].end_y) == pytest.approx((105, 18))


def test_milling_arc_planes_are_logical_and_keep_programmed_endpoints():
    result = execute(MILLING_ARC_PLANES, language="fanuc_mill")
    assert result.ok, result.diagnostics

    arcs = [motion for motion in result.motions if motion.move in (2, 3)]
    assert [motion.plane for motion in arcs] == [17, 18, 19]
    assert [motion.source_nlabel for motion in arcs] == [10, 20, 30]
    assert (arcs[0].end_x, arcs[0].end_y, arcs[0].end_z) == pytest.approx((0, 10, 0))
    assert (arcs[1].end_x, arcs[1].end_y, arcs[1].end_z) == pytest.approx((0, 0, 0))
    assert (arcs[2].end_x, arcs[2].end_y, arcs[2].end_z) == pytest.approx((0, 0, 10))

    points = render_trace(result)
    assert points
    assert all(math.isfinite(value) for point in points for value in (point.x, point.y, point.z))


def test_milling_full_circle_helix_stays_logical_and_renderer_reaches_depth_and_radius():
    result = execute(MILLING_HELIX_FULL_CIRCLE, language="fanuc_mill")
    assert result.ok, result.diagnostics

    arcs = [motion for motion in result.motions if motion.move in (2, 3)]
    assert [motion.source_nlabel for motion in arcs] == [100, 110]
    assert [(motion.end_x, motion.end_y, motion.end_z) for motion in arcs] == pytest.approx([(10, 0, -2), (10, 0, -4)])

    points = render_trace(result)
    assert min(point.z for point in points) == pytest.approx(-4.0, abs=0.01)
    assert max(math.hypot(point.x, point.y) for point in points) == pytest.approx(10.0, abs=0.01)


def test_milling_relative_absolute_and_radius_arc_encodings_render_same_contour():
    relative = execute(ARC_RELATIVE, language="fanuc_mill")
    absolute = execute(ARC_ABSOLUTE, language="fanuc_mill", source_arc_type=2)
    radius = execute(ARC_RADIUS, language="fanuc_mill")
    assert relative.ok and absolute.ok and radius.ok

    rel_points = render_trace(relative)
    abs_points = render_trace(absolute)
    rad_points = render_trace(radius)

    for points in (rel_points, abs_points, rad_points):
        assert (points[-1].x, points[-1].y) == pytest.approx((-55.123, 39.556), abs=1e-6)
        assert min(point.x for point in points) == pytest.approx(-55.123, abs=0.01)
        assert max(point.y for point in points) == pytest.approx(55.123, abs=0.01)


def test_milling_rounded_ijk_arc_is_renderable_without_radius_equality_rejection():
    source = """\
G21 G90 G17
G0 X5.365 Y4.496 Z0
G2 X15 Y0 I3.768 J-4.496 F500
M30
"""
    result = execute(source, language="fanuc_mill", source_arc_type=1)
    assert result.ok, result.diagnostics
    arc = next(motion for motion in result.motions if motion.move in (2, 3))
    assert arc.arc is not None


def test_milling_ijk_words_are_not_discarded_by_radius_source_mode():
    source = """\
G21 G90 G17
G0 X0 Y50 Z0
G2 X50 Y0 I0 J-50 F500
M30
"""
    result = execute(source, language="fanuc_mill", source_arc_type=3)
    assert result.ok, result.diagnostics
    arc = next(motion for motion in result.motions if motion.move in (2, 3))
    assert arc.arc is not None
    assert arc.arc.radius == pytest.approx(50.0)


def _autodetected_arcs(source, *, fallback=1):
    result = execute(
        source,
        language="fanuc_mill",
        source_arc_type=fallback,
        autodetect_arc_type=True,
        arc_tolerance=0.001,
    )
    assert result.ok, result.diagnostics
    return [motion for motion in result.motions if motion.arc is not None]


def test_milling_autodetects_relative_ijk_instead_of_manual_fallback():
    arcs = _autodetected_arcs("G17 G90\nG0 X10 Y0\nG2 X20 Y10 I0 J10\nM30", fallback=2)

    assert arcs[0].arc.center == pytest.approx((10.0, 10.0, 0.0))


def test_milling_autodetects_absolute_ijk_instead_of_manual_fallback():
    arcs = _autodetected_arcs("G17 G90\nG0 X10 Y0\nG2 X20 Y10 I10 J10\nM30", fallback=1)

    assert arcs[0].arc.center == pytest.approx((10.0, 10.0, 0.0))


def test_milling_autodetect_skips_leading_r_arc_and_preserves_mixed_arc_program():
    arcs = _autodetected_arcs(
        "G17 G90\nG0 X0 Y0\nG2 X10 Y0 R5\nG0 X10 Y0\nG2 X20 Y10 I10 J10\nM30",
        fallback=1,
    )

    assert len(arcs) == 2
    assert arcs[0].radius == pytest.approx(5.0)
    assert arcs[0].arc.radius == pytest.approx(5.0)
    assert arcs[1].arc.center == pytest.approx((10.0, 10.0, 0.0))


def test_milling_autodetected_ijk_mode_stays_fixed_across_r_arc():
    arcs = _autodetected_arcs(
        "G17 G90\nG0 X10 Y0\nG2 X20 Y10 I0 J10\nG2 X30 Y10 R5\nG0 X10 Y0\nG2 X20 Y10 I0 J10\nM30",
        fallback=2,
    )

    assert arcs[0].arc.center == pytest.approx((10.0, 10.0, 0.0))
    assert arcs[1].arc.radius == pytest.approx(5.0)
    assert arcs[2].arc.center == pytest.approx((10.0, 10.0, 0.0))


def test_milling_autodetect_skips_ambiguous_full_circle_and_uses_next_ijk_arc():
    arcs = _autodetected_arcs(
        "G17 G90\nG0 X10 Y0\nG2 X10 Y0 I-10 J0\nG2 X20 Y10 I0 J10\nM30",
        fallback=2,
    )

    assert arcs[0].arc.center == pytest.approx((0.0, 0.0, 0.0))
    assert arcs[1].arc.center == pytest.approx((10.0, 10.0, 0.0))


def test_milling_autodetect_uses_manual_fallback_when_every_ijk_arc_is_ambiguous():
    arcs = _autodetected_arcs("G17 G90\nG0 X10 Y0\nG2 X10 Y0 I-10 J0\nM30", fallback=2)

    assert arcs[0].arc.center == pytest.approx((-10.0, 0.0, 0.0))


def test_milling_disabled_autodetect_preserves_manual_arc_type():
    result = execute(
        "G17 G90\nG0 X10 Y0\nG2 X20 Y10 I10 J10\nM30",
        language="fanuc_mill",
        source_arc_type=1,
        autodetect_arc_type=False,
    )

    arc = next(motion for motion in result.motions if motion.arc is not None)
    assert arc.arc.center == pytest.approx((20.0, 10.0, 0.0))


def test_milling_arc_autodetect_does_not_execute_program_twice(monkeypatch):
    calls = 0
    original = getattr(kernel_engine, "_execute_impl")

    def counted_execute(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(kernel_engine, "_execute_impl", counted_execute)
    result = kernel_engine.execute(
        "G17 G90\nG0 X10 Y0\nG2 X20 Y10 I0 J10\nM30",
        language="fanuc_mill",
        autodetect_arc_type=True,
    )

    assert result.ok
    assert calls == 1


def test_milling_canned_cycles_execute_exact_source_blocks_and_depths():
    result = execute(MILLING_CYCLES, language="fanuc_mill")
    assert result.ok, result.diagnostics

    expected_depth = {100: -2.0, 200: -3.0, 300: -4.0, 400: -5.0}
    for label, depth in expected_depth.items():
        motions = [motion for motion in result.motions if motion.source_nlabel == label and motion.cycle_generated]
        assert motions, f"cycle N{label} produced no logical motions"
        assert min(motion.end_z for motion in motions) == pytest.approx(depth)

    g83 = [motion for motion in result.motions if motion.source_nlabel == 300 and motion.cycle_generated]
    assert sum(motion.move == 1 for motion in g83) >= 2


def _cycle_z_moves(result, raw_prefix):
    return [
        (motion.move, motion.start_z, motion.end_z)
        for motion in result.motions
        if motion.cycle_generated and motion.source_raw.startswith(raw_prefix)
    ]


def _assert_cycle_z_moves(result, raw_prefix, expected):
    actual = _cycle_z_moves(result, raw_prefix)
    assert len(actual) == len(expected)
    for actual_move, expected_move in zip(actual, expected, strict=True):
        assert actual_move == pytest.approx(expected_move)


def _assert_xy_endpoints(motions, expected):
    actual = [(motion.end_x, motion.end_y) for motion in motions]
    assert len(actual) == len(expected)
    for actual_point, expected_point in zip(actual, expected, strict=True):
        assert actual_point == pytest.approx(expected_point, abs=1e-9)


def test_milling_g83_peck_drilling_fully_retracts_to_r_between_pecks():
    result = execute("G21 G90 G17\nG0 Z5\nG83 X0 Y0 Z-5 R1 Q2 F100\nG80\nM30", language="fanuc_mill")

    assert result.ok, result.diagnostics
    _assert_cycle_z_moves(
        result,
        "G83",
        [
            (0, 5.0, 1.0),
            (1, 1.0, -1.0),
            (0, -1.0, 1.0),
            (0, 1.0, 0.0),
            (1, 0.0, -3.0),
            (0, -3.0, 1.0),
            (0, 1.0, -2.0),
            (1, -2.0, -5.0),
            (0, -5.0, 1.0),
        ],
    )


def test_milling_g73_peck_drilling_uses_small_retract_between_pecks():
    result = execute("G21 G90 G17\nG0 Z5\nG73 X0 Y0 Z-5 R1 Q2 F100\nG80\nM30", language="fanuc_mill")

    assert result.ok, result.diagnostics
    _assert_cycle_z_moves(
        result,
        "G73",
        [
            (0, 5.0, 1.0),
            (1, 1.0, -1.0),
            (0, -1.0, 0.0),
            (1, 0.0, -3.0),
            (0, -3.0, -2.0),
            (1, -2.0, -5.0),
            (0, -5.0, 1.0),
        ],
    )


@pytest.mark.parametrize("clearance,feed_starts", [(0, [1, -1, -3]), (0.25, [1, -0.75, -2.75]), (10, [1, 1, 1])])
def test_milling_g83_reentry_clearance_option_and_r_plane_clamp(clearance, feed_starts):
    result = execute(
        "G0 Z5\nG98\nG83 Z-5 R1 Q2 F100\nG80\nM30",
        "fanuc_mill",
        milling_g83_clearance=clearance,
    )
    assert result.ok, result.diagnostics
    moves = _cycle_z_moves(result, "G83")
    assert [start for move, start, _ in moves if move == 1] == pytest.approx(feed_starts)
    assert moves[-1] == pytest.approx((0, -5, 5))
    assert all(end <= 1 for move, _, end in moves[:-1] if move == 0)


def test_milling_g83_reentry_clearance_is_one_mm_in_inch_mode():
    result = execute("G20\nG0 Z0.2\nG83 Z-0.2 R0 Q0.1 F4\nG80\nM30", "fanuc_mill")
    assert result.ok, result.diagnostics
    feeds = [m for m in result.motions if m.cycle_generated and m.move == 1]
    assert feeds[1].start_z - feeds[0].end_z == pytest.approx(1)


@pytest.mark.parametrize("clearance", [-1, float("inf"), float("nan")])
def test_milling_g83_clearance_must_be_finite_and_non_negative(clearance):
    result = execute("G83 Z-5 R1 Q2 F100\nM30", "fanuc_mill", milling_g83_clearance=clearance)
    assert not result.ok and not result.complete
    assert any("G83 reentry clearance" in d.message for d in result.diagnostics)


def test_milling_g73_retract_clearance_is_one_mm_in_inch_mode():
    result = execute("G20 G90 G17\nG0 Z0.2\nG73 X0 Y0 Z-0.2 R0 Q0.1 F4\nG80\nM30", language="fanuc_mill")

    assert result.ok, result.diagnostics
    moves = _cycle_z_moves(result, "G73")
    first_peck_end = moves[1][2]
    first_retract_end = moves[2][2]
    assert first_retract_end - first_peck_end == pytest.approx(1.0)


def test_milling_g84_tapping_returns_from_depth_at_feed():
    result = execute("G21 G90 G17\nG0 Z5\nG84 X0 Y0 Z-5 R1 F100\nG80\nM30", language="fanuc_mill")

    assert result.ok, result.diagnostics
    _assert_cycle_z_moves(
        result,
        "G84",
        [
            (0, 5.0, 1.0),
            (1, 1.0, -5.0),
            (1, -5.0, 1.0),
        ],
    )


def test_milling_g82_publishes_dwell_for_each_hole():
    result = execute(
        "G21 G90 G17\nG0 Z5\nG82 X0 Y0 Z-5 R1 P1500 F100\nX10\nG80\nM30",
        language="fanuc_mill",
    )

    assert result.ok, result.diagnostics
    dwell = [signal for signal in result.signals if signal.kind == "dwell" and signal.code == "G82"]
    assert [signal.value for signal in dwell] == pytest.approx([1.5, 1.5])


def test_milling_g84_publishes_spindle_synchronization_and_reverse():
    result = execute("G21 G90 G17\nG0 Z5\nG84 X0 Y0 Z-5 R1 F100\nG80\nM30", language="fanuc_mill")

    assert result.ok, result.diagnostics
    kinds = [signal.kind for signal in result.signals if signal.code == "G84"]
    assert kinds == ["spindle_sync", "spindle_reverse"]


def test_m19_s_angle_does_not_replace_spindle_speed():
    result = execute("G95\nS600 M03\nM19 S90\nG1 X10 F1.5\nM30", language="fanuc_mill")

    assert result.ok, result.diagnostics
    assert [(signal.kind, signal.value) for signal in result.signals if signal.code == "M19"] == [
        ("spindle_orient", 90.0)
    ]
    move = next(motion for motion in result.motions if motion.move == 1)
    assert move.spindle_rpm == 600.0
    assert move.feed_mode == "per_revolution"
    assert move.feed == 1.5
    assert not any(diagnostic.code == "UNSUPPORTED_M_CODE" for diagnostic in result.diagnostics)


def test_m29_prepares_g84_and_g80_cancels_rigid_tapping_state():
    result = execute(
        "G95\nM29 S500\nG84 Z-20 R2 F1.5\nG80\nG84 Z-10 R2 F1.5\nG80\nM30",
        language="fanuc_mill",
    )

    assert result.ok, result.diagnostics
    assert [(signal.kind, signal.value) for signal in result.signals if signal.code == "M29"] == [
        ("rigid_tapping_prepare", 500.0)
    ]
    assert [signal.kind for signal in result.signals if signal.code == "G84"] == [
        "rigid_tapping",
        "spindle_sync",
        "spindle_reverse",
        "spindle_sync",
        "spindle_reverse",
    ]
    cycle_feed = [motion for motion in result.motions if motion.cycle_generated and motion.move == 1]
    assert cycle_feed
    assert all(motion.spindle_rpm == 500.0 and motion.feed_mode == "per_revolution" for motion in cycle_feed)
    assert all(motion.feed == 1.5 for motion in cycle_feed)


def test_m29_g94_keeps_programmed_feed_per_minute():
    result = execute("G94\nM29 S600\nG84 Z-18 R2 F900\nG80\nM30", language="fanuc_mill")

    assert result.ok, result.diagnostics
    assert any(signal.kind == "rigid_tapping" for signal in result.signals)
    cycle_feed = [motion for motion in result.motions if motion.cycle_generated and motion.move == 1]
    assert cycle_feed
    assert all(motion.spindle_rpm == 600.0 and motion.feed_mode == "per_minute" for motion in cycle_feed)
    assert all(motion.feed == 900.0 for motion in cycle_feed)


def test_milling_g86_publishes_spindle_stop_at_depth():
    result = execute("G21 G90 G17\nG0 Z5\nG86 X0 Y0 Z-5 R1 F100\nG80\nM30", language="fanuc_mill")

    assert result.ok, result.diagnostics
    assert [(signal.kind, signal.code) for signal in result.signals if signal.code == "G86"] == [
        ("spindle_stop", "G86")
    ]


def test_milling_g73_retract_distance_is_a_kernel_option():
    result = execute(
        "G21 G90 G17\nG0 Z5\nG73 X0 Y0 Z-5 R1 Q2 F100\nG80\nM30",
        language="fanuc_mill",
        milling_g73_retract_distance=0.25,
    )

    assert result.ok, result.diagnostics
    moves = _cycle_z_moves(result, "G73")
    assert moves[1] == pytest.approx((1, 1.0, -1.0))
    assert moves[2] == pytest.approx((0, -1.0, -0.75))


@pytest.mark.parametrize("distance", [-1.0, float("inf"), float("nan")])
def test_milling_g73_retract_distance_must_be_finite_and_non_negative(distance):
    result = execute("G73 X0 Y0 Z-5 R1 Q2 F100\nM30", language="fanuc_mill", milling_g73_retract_distance=distance)

    assert not result.ok
    assert not result.complete
    assert any("G73 retract distance" in diagnostic.message for diagnostic in result.diagnostics)


def test_milling_real_subprogram_fixture_repeats_m98_m99_and_returns_to_main_program(fixture_text):
    result = execute(fixture_text("milling/fanuc/subprogram.nc"), language="fanuc_mill")
    assert result.ok, result.diagnostics

    assert len(result.motions) == 172
    assert sum(motion.move == 1 for motion in result.motions) == 90
    assert sum(motion.move == 2 for motion in result.motions) == 46
    assert (result.motions[-1].end_x, result.motions[-1].end_y, result.motions[-1].end_z) == pytest.approx((0, 0, 0))


def test_milling_real_contour_fixture_covers_cw_ccw_arcs_and_depth(fixture_text):
    result = execute(fixture_text("milling/fanuc/contur_2d.nc"), language="fanuc_mill")
    assert result.ok, result.diagnostics

    assert sum(motion.move == 2 for motion in result.motions) == 18
    assert sum(motion.move == 3 for motion in result.motions) == 8
    assert min(motion.end_z for motion in result.motions) == pytest.approx(-11.0)


def test_milling_wcs_fixture_executes_four_complete_contours(fixture_text):
    result = execute(fixture_text("milling/fanuc/wcs_test.nc"), language="fanuc_mill")
    assert result.ok, result.diagnostics

    assert len(result.motions) == 71
    assert sum(motion.move == 3 for motion in result.motions) == 16
    assert min(motion.end_x for motion in result.motions) == pytest.approx(-55.123)
    assert max(motion.end_x for motion in result.motions) == pytest.approx(55.123)
    assert min(motion.end_y for motion in result.motions) == pytest.approx(-55.123)
    assert max(motion.end_y for motion in result.motions) == pytest.approx(65.123)


def test_milling_xyz_wcs_offsets_are_applied_in_machine_space():
    source = """\
G90 G17 G54
G0 X1 Y2 Z3
G55
G1 X4 Y5 Z6 F100
M30
"""
    result = execute(
        source,
        language="fanuc_mill",
        wcs_offsets={
            54: (10.0, 20.0, 30.0),
            55: (-1.0, -2.0, -3.0),
        },
    )

    assert result.ok, result.diagnostics
    assert (result.motions[0].end_x, result.motions[0].end_y, result.motions[0].end_z) == pytest.approx(
        (11.0, 22.0, 33.0)
    )
    assert (result.motions[1].end_x, result.motions[1].end_y, result.motions[1].end_z) == pytest.approx((3.0, 3.0, 3.0))


def test_milling_g52_sets_local_origin_offset_and_cancel_preserves_machine_position():
    source = """\
G90 G17 G54
G0 X200 Y160 Z30
G52 X100 Y100 Z20
G1 X110 Y110 Z10 F100
G52 X0 Y0 Z0
G1 X100 Y100 Z10
M30
"""
    result = execute(
        source,
        language="fanuc_mill",
        wcs_offsets={54: (10.0, 20.0, 30.0)},
    )

    assert result.ok, result.diagnostics
    assert len(result.motions) == 3
    assert (result.motions[0].end_x, result.motions[0].end_y, result.motions[0].end_z) == pytest.approx(
        (210.0, 180.0, 60.0)
    )
    assert (result.motions[1].start_x, result.motions[1].start_y, result.motions[1].start_z) == pytest.approx(
        (210.0, 180.0, 60.0)
    )
    assert (result.motions[1].end_x, result.motions[1].end_y, result.motions[1].end_z) == pytest.approx(
        (220.0, 230.0, 60.0)
    )
    assert (result.motions[2].start_x, result.motions[2].start_y, result.motions[2].start_z) == pytest.approx(
        (220.0, 230.0, 60.0)
    )
    assert (result.motions[2].end_x, result.motions[2].end_y, result.motions[2].end_z) == pytest.approx(
        (110.0, 120.0, 40.0)
    )


def test_milling_g52_omitted_axes_keep_their_existing_local_shift():
    result = execute(
        "G90 G17 G54\nG0 X20 Y30 Z40\nG52 X10 Y20 Z30\nG52 X5\nG0 X0 Y0 Z0\nM30",
        language="fanuc_mill",
    )

    assert result.ok, result.diagnostics
    motion = result.motions[-1]
    assert (motion.end_x, motion.end_y, motion.end_z) == pytest.approx((5.0, 20.0, 30.0))


def test_milling_two_axis_wcs_input_keeps_backward_compatible_xz_mapping():
    result = execute(
        "G90 G54\nG0 X1 Y2 Z3\nM30",
        language="fanuc_mill",
        wcs_offsets={54: (10.0, 30.0)},
    )

    assert result.ok, result.diagnostics
    motion = result.motions[0]
    assert (motion.end_x, motion.end_y, motion.end_z) == pytest.approx((11.0, 2.0, 33.0))


def test_milling_g68_rotates_rectangular_profile_90_degrees_about_origin():
    source = """\
G21 G90 G17 G54
G68 X0 Y0 R90
G0 X0 Y0 Z0
G1 X10 Y0 F100
G1 X10 Y20
G1 X0 Y20
G1 X0 Y0
G69
M30
"""
    result = execute(source, language="fanuc_mill")

    assert result.ok, result.diagnostics
    cutting = [motion for motion in result.motions if motion.move == 1]
    _assert_xy_endpoints(cutting, [(0.0, 10.0), (-20.0, 10.0), (-20.0, 0.0), (0.0, 0.0)])


def test_milling_g69_cancels_coordinate_rotation():
    source = """\
G21 G90 G17
G68 X0 Y0 R90
G1 X10 Y0 F100
G69
G1 X20 Y0
M30
"""
    result = execute(source, language="fanuc_mill")

    assert result.ok, result.diagnostics
    cutting = [motion for motion in result.motions if motion.move == 1]
    assert (cutting[0].end_x, cutting[0].end_y) == pytest.approx((0.0, 10.0), abs=1e-9)
    assert (cutting[1].start_x, cutting[1].start_y) == pytest.approx((0.0, 10.0), abs=1e-9)
    assert (cutting[1].end_x, cutting[1].end_y) == pytest.approx((20.0, 0.0), abs=1e-9)


def test_milling_g68_rotates_rectangular_profile_30_degrees_about_programmed_center():
    source = """\
G21 G90 G17 G54
G68 X50 Y50 R30
G0 X20 Y10 Z5
G1 Z-3 F100
G1 X80 Y10
G1 X80 Y30
G1 X20 Y30
G1 X20 Y10
G69
M30
"""
    result = execute(source, language="fanuc_mill")

    assert result.ok, result.diagnostics
    profile = [motion for motion in result.motions if motion.move == 1][1:]
    _assert_xy_endpoints(
        profile,
        [
            (95.98076211353316, 30.35898384862245),
            (85.98076211353316, 47.67949192431122),
            (34.01923788646684, 17.679491924311225),
            (44.01923788646684, 0.3589838486224579),
        ],
    )


def test_milling_g52_shift_is_applied_before_g68_rotation_and_wcs_offset():
    source = """\
G21 G90 G17 G54
G0 X20 Y0 Z0
G52 X10 Y0 Z0
G68 X0 Y0 R90
G0 X20 Y0 Z0
M30
"""
    result = execute(source, language="fanuc_mill", wcs_offsets={54: (100.0, 200.0, 300.0)})

    assert result.ok, result.diagnostics
    motion = result.motions[-1]
    assert (motion.end_x, motion.end_y, motion.end_z) == pytest.approx((110.0, 220.0, 300.0), abs=1e-9)


def test_trace_statistics_use_logical_arc_geometry_not_render_sample_count():
    result = execute("G90 G17\nG0 X10 Y0\nG3 X0 Y10 I-10 J0 F100\nM30", language="fanuc_mill")
    stats = trace_statistics(result)
    assert stats["motion_count"] == 2
    assert stats["arc_count"] == 1
    assert stats["bounds"][0] == pytest.approx((0.0, 10.0))
    assert stats["bounds"][1] == pytest.approx((0.0, 10.0))
    assert stats["bounds"][2] == pytest.approx((0.0, 0.0))


@pytest.mark.parametrize("mode", [41, 42])
def test_milling_compensation_state_is_tracked_and_unmodeled_geometry_is_reported(mode):
    source = f"""\
G90 G17 G21
G0 X0 Y0 Z5
G43 H7 Z1
G{mode} D3 X10 Y0 F100
G40 X20
G49
M30
"""
    result = execute(source, language="fanuc_mill")
    assert result.ok, result.diagnostics

    diagnostics = {item.code: item for item in result.diagnostics}
    assert "UNVERIFIED_TOOL_LENGTH_COMPENSATION" not in diagnostics
    assert diagnostics["UNVERIFIED_CUTTER_COMPENSATION"].status == "unverified"
    assert diagnostics["UNVERIFIED_CUTTER_COMPENSATION"].severity == "warning"

    compensated = next(motion for motion in result.motions if motion.source_raw.startswith(f"G{mode}"))
    cancelled = next(motion for motion in result.motions if motion.source_raw.startswith("G40"))
    assert compensated.compensation_mode == mode
    assert compensated.compensation_applied is False
    assert cancelled.compensation_mode == 40


def test_milling_g53_uses_machine_coordinates_without_changing_active_wcs():
    source = """\
G90 G17 G54
G0 X10 Y20 Z30
G53 G0 X0 Y0 Z0
G1 X5 Y6 Z7 F100
M30
"""
    result = execute(
        source,
        language="fanuc_mill",
        wcs_offsets={54: (100.0, 200.0, 300.0)},
    )

    assert result.ok, result.diagnostics
    assert len(result.motions) == 3
    assert (result.motions[0].end_x, result.motions[0].end_y, result.motions[0].end_z) == pytest.approx(
        (110.0, 220.0, 330.0)
    )
    assert result.motions[1].source_kind == "g53"
    assert (result.motions[1].end_x, result.motions[1].end_y, result.motions[1].end_z) == pytest.approx((0.0, 0.0, 0.0))
    assert (result.motions[2].end_x, result.motions[2].end_y, result.motions[2].end_z) == pytest.approx(
        (105.0, 206.0, 307.0)
    )


def test_milling_unknown_g_and_m_codes_are_informational_and_do_not_drop_trace():
    source = """\
G90 G17
G0 X0 Y0 Z5
G64
M123
G1 X10 Y0 Z5 F100
M30
"""
    result = execute(source, language="fanuc_mill")

    assert result.ok
    assert len(result.motions) == 2
    diagnostics = {(item.code, item.line): item for item in result.diagnostics}
    g_diag = diagnostics[("UNSUPPORTED_G_CODE", 3)]
    m_diag = diagnostics[("UNSUPPORTED_M_CODE", 4)]
    assert g_diag.severity == "warning"
    assert g_diag.status == "unverified"
    assert m_diag.severity == "warning"
    assert m_diag.status == "unverified"
    assert (result.motions[-1].end_x, result.motions[-1].end_y, result.motions[-1].end_z) == pytest.approx(
        (10.0, 0.0, 5.0)
    )


def test_indexed_compensation_and_unknown_extended_m_do_not_stop_execution():
    result = execute(
        "G90 G0 X0 Y0 Z0\nB90\nG41 G1 X10 F100 M250\nG40 G1 X20\nM30",
        language="fanuc_mill",
        kinematics="4ax_table_b",
    )
    codes = {diagnostic.code: diagnostic for diagnostic in result.diagnostics}
    assert codes["UNVERIFIED_CUTTER_COMPENSATION"].severity == "warning"
    assert codes["UNSUPPORTED_M_CODE"].severity == "warning"
    assert result.executed_blocks[-1] == 4
    assert any(motion.source_block == 3 for motion in result.motions)


@pytest.mark.parametrize(
    ("profile", "axis", "expected"),
    [
        ("4ax_table_a", "A", (7.0, 0.0, 10.0)),
        ("4ax_table_b", "B", (0.0, 10.0, -7.0)),
    ],
)
def test_indexed_cutter_compensation_is_solved_in_local_g17_plane(profile, axis, expected):
    result = execute(
        f"G21 G17 G90\nT1 M6\nG0 X0 Y0 Z0\n{axis}90\nG41 G1 X10 Y0 F100\nG1 X10 Y10\nG40 G1 X20 Y10\nM30",
        language="fanuc_mill",
        kinematics=profile,
        milling_tools={"T1": {"type": "mill_flat", "diameter": 6.0, "length": 50.0}},
    )
    assert result.ok and result.complete, result.diagnostics
    steady = next(motion for motion in result.motions if motion.source_block == 5)
    assert steady.compensation_applied
    assert (steady.end_x, steady.end_y, steady.end_z) == pytest.approx(expected)
    assert not any("UNVERIFIED" in diagnostic.code for diagnostic in result.diagnostics)


def test_table_b_compensated_g17_arc_has_rotated_center_and_normal():
    result = execute(
        "G21 G17 G90 G40\nT1 M6\nG0 X0 Y0\nB90\nG1 Z-1 F300\nG41 G1 X5 F100\nG3 X0 Y5 I-5 J0\nG40 G1 X0 Y0\nM30",
        language="fanuc_mill",
        kinematics="4ax_table_b",
        milling_tools={"T1": {"type": "mill_flat", "diameter": 6.0, "length": 50.0}},
    )
    assert result.ok and result.complete, result.diagnostics
    arc_motion = next(motion for motion in result.motions if motion.move == 3)
    assert arc_motion.compensation_applied
    assert arc_motion.arc.radius == pytest.approx(2.0)
    assert arc_motion.arc.center == pytest.approx((-1.0, 0.0, 0.0), abs=1e-8)
    assert arc_motion.arc.normal == pytest.approx((1.0, 0.0, 0.0), abs=1e-8)


@pytest.mark.parametrize(
    ("profile", "index_word"),
    [
        ("4ax_table_a", "A90"),
        ("4ax_table_b", "B90"),
        ("4ax_table_c", "C90"),
    ],
)
def test_four_axis_reference_retract_follows_current_kinematics(profile, index_word):
    result = execute(
        f"G90 G0 X10 Y20 Z30\n{index_word}\nG91 G28 Z0\nM30",
        language="fanuc_mill",
        kinematics=profile,
        home_z=500.0,
    )

    assert result.ok and result.complete, result.diagnostics
    retract = next(motion for motion in result.motions if motion.source_kind == "g28")
    expected = {
        "4ax_table_a": (10, -500, 20),
        "4ax_table_b": (500, 20, -10),
        "4ax_table_c": (-20, 10, 500),
    }
    assert (retract.end_x, retract.end_y, retract.end_z) == pytest.approx(expected[profile])
