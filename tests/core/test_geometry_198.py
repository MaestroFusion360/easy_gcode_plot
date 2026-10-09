"""Geometry regressions for endpoint validation, frames and compensation."""

import math
from dataclasses import replace

import pytest

from app.gcode.kernel import execute
from app.gcode.kernel.api.resources import SemanticError
from app.gcode.kernel.frontend.model import ArcGeom, Point2, ProfileSegment
from app.gcode.kernel.geometry.profile_arcs import arc_progress01, is_point_on_arc
from app.gcode.kernel.geometry.spatial_arc import extreme_points, point_at
from app.gcode.kernel.turning.cycles.g76 import build_g76_threading


@pytest.mark.parametrize("dialect", ["fanuc", "sinumerik"])
@pytest.mark.parametrize(
    "plane,start,end,center",
    [
        (17, "X1 Y0", "X0 Y2", "I-1 J0"),
        (18, "X1 Z0", "X0 Z2", "I-1 K0"),
        (19, "Y1 Z0", "Y0 Z2", "J-1 K0"),
        (17, "X1 Y0", "X2 Y0", "I-1 J0"),
    ],
)
def test_inconsistent_ijk_endpoints_are_diagnosed_at_source(dialect, plane, start, end, center):
    source = f"G21 G90 G{plane}\nG0 {start}\nG3 {end} {center} F100\nM30"
    result = execute(source, "fanuc_mill", source_dialect=dialect)
    assert not result.ok
    error = next(d for d in result.diagnostics if d.code == "INVALID_GEOMETRY")
    assert error.line == 3
    assert error.raw.strip() == source.splitlines()[2]
    assert not any(m.move in (2, 3) for m in result.motions)


@pytest.mark.parametrize("tolerance,valid", [(0.001, False), (0.01, True)])
def test_ijk_radius_validation_uses_execution_tolerance(tolerance, valid):
    result = execute("G0 X1\nG3 X0 Y1.005 I-1 J0 F100\nM30", "fanuc_mill", arc_tolerance=tolerance)
    assert result.ok is valid


@pytest.mark.parametrize("move", [2, 3])
def test_full_circle_retains_nonzero_sweep_and_spatial_consumers(move):
    result = execute(f"G0 X1\nG{move} I-1 J0 F100\nM30", "fanuc_mill")
    assert result.ok, result.diagnostics
    arc = result.motions[-1]
    arc = replace(arc, arc=replace(arc.arc, normal=(0, 0, 1)))
    assert arc.arc.sweep == pytest.approx(math.tau)
    assert point_at(arc, math.pi) == pytest.approx((-1, 0, 0))
    assert extreme_points(arc)


@pytest.mark.parametrize(
    "setup,offset,center,radius",
    [
        ("G52 X5", None, (5, 0, 0), 10),
        ("G52 X5\nG68 X0 Y0 R90", None, (5, 0, 0), 10),
        ("G51 X2 Y3 P2000", None, (-2, -3, 0), 20),
        ("G52 X5", {54: (100, 200, 3)}, (105, 200, 3), 10),
    ],
)
@pytest.mark.parametrize("autodetect", [False, True])
def test_absolute_arc_centers_follow_point_transforms(setup, offset, center, radius, autodetect):
    result = execute(
        f"G21 G90 G17\n{setup}\nG0 X10 Y0 Z0\nG3 X0 Y10 I0 J0 F100\nM30",
        "fanuc_mill",
        wcs_offsets=offset,
        source_arc_type=2,
        autodetect_arc_type=autodetect,
    )
    assert result.ok, result.diagnostics
    arc = result.motions[-1].arc
    assert arc.center == pytest.approx(center)
    assert arc.radius == pytest.approx(radius)
    assert arc.sweep == pytest.approx(math.pi / 2)


def test_absolute_and_relative_centers_agree_in_indexed_frame():
    prefix = "G21 G90 G17\nB45\nG52 X5\nG0 X10 Y0 Z0\n"
    options = {"kinematics": "4ax_table_b", "wcs_offsets": {54: (100, 200, 3)}}
    relative = execute(prefix + "G3 X0 Y10 I-10 J0 F100\nM30", "fanuc_mill", **options)
    absolute = execute(prefix + "G3 X0 Y10 I0 J0 F100\nM30", "fanuc_mill", source_arc_type=2, **options)
    assert relative.ok and absolute.ok, (relative.diagnostics, absolute.diagnostics)
    assert absolute.motions[-1].arc.center == pytest.approx(relative.motions[-1].arc.center)
    assert absolute.motions[-1].arc.radius == pytest.approx(10)
    assert absolute.motions[-1].arc.sweep == pytest.approx(math.pi / 2)


@pytest.mark.parametrize("mode", [41, 42])
@pytest.mark.parametrize("move", [2, 3])
@pytest.mark.parametrize("plane", [17, 18, 19])
def test_compensated_quarter_circle_has_correct_radius_and_direction(mode, move, plane):
    # Right-handed plane coordinates: XY, ZX, YZ.
    a, b, ij = {17: ("X", "Y", "I-10 J0"), 18: ("Z", "X", "I0 K-10"), 19: ("Y", "Z", "J-10 K0")}[plane]
    sign = 1 if move == 3 else -1
    radius = 9 if (mode == 41) == (move == 3) else 11
    source = (
        f"G21 G90 G{plane}\nT1 M6\nG0 {a}10 {b}{-20 * sign}\nG1 G{mode} {b}{-10 * sign} F100\n"
        f"{b}0\nG{move} {a}0 {b}{10 * sign} {ij}\nG1 {a}-10\nG40 {a}-20\nM30"
    )
    result = execute(source, "fanuc_mill", milling_tools={"T1": {"type": "mill_flat", "diameter": 2}})
    assert result.ok, result.diagnostics
    arc_motion = next(m for m in result.motions if m.move == move)
    assert arc_motion.compensation_applied, result.diagnostics
    assert arc_motion.arc.radius == pytest.approx(radius)
    assert arc_motion.arc.sweep == pytest.approx(math.pi / 2)
    axes = {17: (0, 1), 18: (2, 0), 19: (1, 2)}[plane]
    start = (arc_motion.start_x, arc_motion.start_y, arc_motion.start_z)
    end = (arc_motion.end_x, arc_motion.end_y, arc_motion.end_z)
    assert (start[axes[0]], start[axes[1]]) == pytest.approx((radius, 0))
    assert (end[axes[0]], end[axes[1]]) == pytest.approx((0, sign * radius))


@pytest.mark.parametrize("move", [2, 3])
@pytest.mark.parametrize("start_angle", [0, 170, 350])
def test_turning_profile_arc_includes_start_end_and_wraparound(move, start_angle):
    # XZ plot reverses G2/G3; use physical radial coordinates for the oracle.
    sign = 1 if move == 2 else -1

    def point(degrees):
        angle = math.radians(degrees)
        return Point2(2 * math.cos(angle), math.sin(angle))

    start, end = point(start_angle), point(start_angle + sign * 90)
    segment = ProfileSegment(0, move, start, end, False, 0, True, Point2(0, 0))
    geom = ArcGeom(Point2(0, 0), 0.5)
    assert arc_progress01(segment, geom, start) == pytest.approx(0)
    assert arc_progress01(segment, geom, end) == pytest.approx(1)
    assert arc_progress01(segment, geom, point(start_angle + sign * 45)) == pytest.approx(0.5)
    assert is_point_on_arc(segment, geom, start)
    assert not is_point_on_arc(segment, geom, point(start_angle - sign * 45))


@pytest.mark.parametrize("frame", ["TRANS X5 Y7 Z2", "TRANS X5 Y7 Z2\nAROT Z90"])
def test_native_absolute_centers_follow_frames_once(frame):
    result = execute(
        f"G290\nG17 G90\n{frame}\nG0 X10 Y0 Z0\nG3 X0 Y10 I=AC(0) J=AC(0) F100\nM30",
        "fanuc_mill",
        source_dialect="sinumerik",
        wcs_offsets={54: (100, 200, 3)},
    )
    assert result.ok, result.diagnostics
    assert result.motions[-1].arc.center == pytest.approx((105, 207, 5))
    assert result.motions[-1].arc.radius == pytest.approx(10)
    assert result.motions[-1].arc.sweep == pytest.approx(math.pi / 2)


def test_spatial_consumers_reject_zero_sweep_before_division():
    result = execute("G0 X1\nG3 X0 Y1 I-1 J0 F100\nM30", "fanuc_mill")
    motion = result.motions[-1]
    motion = replace(motion, arc=replace(motion.arc, sweep=0, normal=(0, 0, 1)))
    for consumer in (lambda m: point_at(m, 0), extreme_points):
        with pytest.raises(SemanticError, match="sweep"):
            consumer(motion)


@pytest.mark.parametrize("mode", [41, 42])
@pytest.mark.parametrize("middle", [-1, 1])
def test_cip_with_either_normal_keeps_compensation_fail_closed(mode, middle):
    result = execute(
        f"G290\nG0 X1 Y0\nG1 G{mode} X2 F100\nCIP X0 Y2 I1=1 J1={middle}\nM30",
        "fanuc_mill",
        source_dialect="sinumerik",
        milling_tools={"T1": {"type": "mill_flat", "diameter": 2}},
    )
    assert not result.ok and not result.complete
    error = next(d for d in result.diagnostics if d.code == "UNSUPPORTED_SINUMERIK_CIP")
    assert error.code == "UNSUPPORTED_SINUMERIK_CIP" and error.line == 4
    assert not any(m.source_kind == "cip" for m in result.motions)


@pytest.mark.parametrize("move", [2, 3])
def test_full_turning_profile_circle_keeps_start_at_zero(move):
    segment = ProfileSegment(0, move, Point2(2, 0), Point2(2, 0), False, 0, True, Point2(0, 0))
    geom = ArcGeom(Point2(0, 0), 0.5)
    assert arc_progress01(segment, geom, segment.start) == 0
    assert arc_progress01(segment, geom, Point2(-2, 0)) == pytest.approx(0.5)
    assert is_point_on_arc(segment, geom, segment.start)


def test_g76_retains_axial_interval_without_inventing_pullout_angle():
    motions = build_g76_threading(20, 2, 16, -20, 11060, 0.1, 0, 1, 0.3, 2)
    cuts = [m for m in motions if m.move == 1]
    assert cuts
    for first, last in zip(cuts[::2], cuts[1::2], strict=True):
        assert first.end == last.start
        assert last.end.z - last.start.z == pytest.approx(-2)
        assert first.start.x == first.end.x == last.end.x
