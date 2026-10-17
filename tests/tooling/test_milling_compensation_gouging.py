"""Impossible compensation must retain nominal geometry and ownership."""

import pytest

from app.gcode.kernel import execute
from app.gcode.kernel.api.types import TraceMotion
from app.gcode.kernel.compensation.milling.engine import apply_milling_cutter_compensation_with_owners
from app.gcode.kernel.compensation.milling.projection import _ProjectedMotion
from app.gcode.kernel.compensation.milling.validation import _distance


def contour(points, mode=41):
    return [
        TraceMotion(
            1, a[0], 0, b[0], 0, start_y=a[1], end_y=b[1], plane=17, tool="T1", compensation_mode=mode, source_block=i
        )
        for i, (a, b) in enumerate(zip(points, points[1:]))
    ]


@pytest.mark.parametrize("mode,sign", [(41, 1), (42, -1)])
def test_narrow_neck_gouges_even_when_every_line_keeps_its_direction(mode, sign):
    # Two 20x20 chambers connected by a 20x2 neck; cutter diameter 4.
    vertices = [
        (0, 0),
        (20, 0),
        (20, 9),
        (40, 9),
        (40, 0),
        (60, 0),
        (60, 20),
        (40, 20),
        (40, 11),
        (20, 11),
        (20, 20),
        (0, 20),
        (0, 0),
    ]
    points = [(-10, 0), *[(x, sign * y) for x, y in vertices]]
    motions = contour(points, mode)
    owners = [100 + 3 * i for i in range(len(motions))]
    solved, result_owners = apply_milling_cutter_compensation_with_owners(
        motions, {"T1": {"type": "mill_flat", "diameter": 4}}, owners
    )
    assert result_owners == owners
    assert [(m.start_x, m.start_y, m.end_x, m.end_y) for m in solved] == [
        (m.start_x, m.start_y, m.end_x, m.end_y) for m in motions
    ]
    assert all(not m.compensation_applied and m.compensation_status == "UNVERIFIED" for m in solved)


def test_invalid_run_does_not_poison_later_valid_run_or_exit():
    source = (
        "T1 M6\nG17 G90 G0 X-10 Y0\nG41 G1 X0 Y0 F100\nX20\nY2\nX0\n"
        "G40 X-10\nG0 X-10 Y30\nG41 G1 X0 Y30\nX20\nY50\nG40 X30\nM30"
    )
    result = execute(source, "fanuc_mill", milling_tools={"T1": {"type": "mill_flat", "diameter": 10}})
    assert result.ok and result.complete
    bad = next(m for m in result.motions if m.source_raw == "Y2")
    good = next(m for m in result.motions if m.source_raw == "Y50")
    assert bad.compensation_status == "UNVERIFIED"
    assert good.compensation_status == "APPLIED"
    assert sum(s.emitted_count for s in result.execution_steps) == len(result.motions)
    first_exit = next(m for m in result.motions if m.source_raw == "G40 X-10")
    assert (first_exit.start_x, first_exit.start_y) == (0, 2)


@pytest.mark.parametrize("move,expected", [(3, 3), (2, 5)])
@pytest.mark.parametrize("turns", [0, 1])
def test_clearance_respects_finite_arc_sweep(move, expected, turns):
    source = TraceMotion(move, 0, 0, 1, 0, plane=17, additional_turns=turns)
    line = _ProjectedMotion(source, 17, (-10, 0), (10, 0), 0, 0)
    arc = _ProjectedMotion(source, 17, (-2, 5), (2, 5), 0, 0, (0, 5), 2)
    # An extra revolution covers the lower half even when the final half-turn
    # is above the center. Checking just endpoint angles would miss that wall.
    distance = 3 if turns else expected
    assert _distance(line, arc) == pytest.approx(distance)
    assert _distance(arc, line) == pytest.approx(distance)


@pytest.mark.parametrize("center,radius,expected", [((10, 0), 3, 5), ((0, 0), 3, 1), ((4, 0), 2, 0)])
def test_circle_clearance_handles_separation_concentricity_and_tangency(center, radius, expected):
    source = TraceMotion(3, 0, 0, 1, 0, plane=17)
    a = _ProjectedMotion(source, 17, (2, 0), (2, 0), 0, 0, (0, 0), 2)
    start = center[0] + radius, center[1]
    b = _ProjectedMotion(source, 17, start, start, 0, 0, center, radius)
    assert _distance(a, b) == pytest.approx(expected)


@pytest.mark.parametrize("plane", [17, 18, 19])
def test_gouging_check_uses_active_plane(plane):
    axes = {17: ("X", "Y"), 18: ("Z", "X"), 19: ("Y", "Z")}
    u, v = axes[plane]
    source = f"T1 M6\nG{plane} G90 G0 {u}-10 {v}0\nG41 G1 {u}0 {v}0 F100\n{u}20\n{v}2\n{u}0\nG40 {u}-10\nM30"
    result = execute(source, "fanuc_mill", milling_tools={"T1": {"type": "mill_flat", "diameter": 10}})
    assert result.ok
    assert all(m.compensation_status == "UNVERIFIED" for m in result.motions if m.compensation_mode == 41)


@pytest.mark.parametrize("tilt", [0, -15])
def test_cam_short_line_between_arcs_keeps_nominal_geometry_when_offset_wraps(tilt):
    # Reduced N18700..N18740 from the native CAM reference. Joining the offset
    # across the 0.030 mm line can wrap the first short G3 to almost 360 degrees.
    source = (
        f'T1 M6\nG17 G90\nCYCLE800(1,"R_DATA",0,57,0,0,0,0,{tilt},0,0,0,0,-1,0)\n'
        "G0 X20.336 Y25.844 Z0\nG41 G1 X18.662 Y26.841 F100\nG1 X15.796 Y28.434\n"
        "G3 X12.508 Y30.026 I-15.796 J-28.434\nG1 X12.488 Y30.004\n"
        "G3 X9.057 Y31.212 I-12.55 J-30.159\nG40\nM30"
    )
    options = {
        "source_dialect": "sinumerik",
        "kinematics": "5ax_table_ac_angled",
        "milling_tools": {"T1": {"type": "mill_flat", "diameter": 10}},
    }
    nominal = execute(source, "fanuc_mill", milling_correction_enabled=False, **options)
    result = execute(source, "fanuc_mill", **options)
    assert nominal.ok and result.ok and result.complete, result.diagnostics
    assert len(result.motions) == len(nominal.motions)
    for actual, expected in zip(result.motions, nominal.motions, strict=True):
        assert (actual.source_block, actual.source_raw, actual.move) == (
            expected.source_block,
            expected.source_raw,
            expected.move,
        )
        assert (
            actual.start_x,
            actual.start_y,
            actual.start_z,
            actual.end_x,
            actual.end_y,
            actual.end_z,
        ) == pytest.approx(
            (expected.start_x, expected.start_y, expected.start_z, expected.end_x, expected.end_y, expected.end_z),
            abs=1e-8,
        )
        if expected.arc is not None:
            assert actual.arc.center == pytest.approx(expected.arc.center, abs=1e-8)
            assert (actual.arc.radius, actual.arc.sweep) == pytest.approx(
                (expected.arc.radius, expected.arc.sweep), abs=1e-8
            )
            assert actual.arc.clockwise == expected.arc.clockwise
            assert actual.arc.sweep < 0.2  # Two short programmed arcs, never a nearly complete circle.
        if expected.compensation_mode == 41:
            assert not actual.compensation_applied and actual.compensation_status == "UNVERIFIED"
    assert any(d.code == "UNVERIFIED_CUTTER_COMPENSATION" for d in result.diagnostics)
    assert sum(s.emitted_count for s in result.execution_steps) == len(result.motions)
