from __future__ import annotations

import math

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
from app.gcode.trace_tools import render_trace, trace_statistics


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
            (1, 1.0, -3.0),
            (0, -3.0, 1.0),
            (1, 1.0, -5.0),
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


def test_milling_g73_retract_clearance_is_one_mm_in_inch_mode():
    result = execute("G20 G90 G17\nG0 Z0.2\nG73 X0 Y0 Z-0.2 R0 Q0.1 F4\nG80\nM30", language="fanuc_mill")

    assert result.ok, result.diagnostics
    moves = _cycle_z_moves(result, "G73")
    first_peck_end = moves[1][2]
    first_retract_end = moves[2][2]
    assert first_retract_end - first_peck_end == pytest.approx(1.0)


def test_milling_real_subprogram_fixture_repeats_m98_m99_and_returns_to_main_program(fixture_text):
    result = execute(fixture_text("milling/subprogram.nc"), language="fanuc_mill")
    assert result.ok, result.diagnostics

    assert len(result.motions) == 172
    assert sum(motion.move == 1 for motion in result.motions) == 90
    assert sum(motion.move == 2 for motion in result.motions) == 46
    assert (result.motions[-1].end_x, result.motions[-1].end_y, result.motions[-1].end_z) == pytest.approx((0, 0, 0))


def test_milling_real_contour_fixture_covers_cw_ccw_arcs_and_depth(fixture_text):
    result = execute(fixture_text("milling/contur_2d.nc"), language="fanuc_mill")
    assert result.ok, result.diagnostics

    assert sum(motion.move == 2 for motion in result.motions) == 18
    assert sum(motion.move == 3 for motion in result.motions) == 8
    assert min(motion.end_z for motion in result.motions) == pytest.approx(-11.0)


def test_milling_wcs_fixture_executes_four_complete_contours(fixture_text):
    result = execute(fixture_text("milling/wcs_test.nc"), language="fanuc_mill")
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
