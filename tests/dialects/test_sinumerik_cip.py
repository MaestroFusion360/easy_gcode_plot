"""Independent three-point circle references and CIMCO source regressions."""

import math

import pytest

from app.gcode.export.common import ExportOptions
from app.gcode.export.expanded import export_result
from app.gcode.export.full import export_full_mill_program
from app.gcode.kernel import execute
from app.gcode.kernel.geometry.spatial_arc import point_at
from app.gcode.trace_tools import motion_length, sample_motion, trace_statistics
from app.ui.plot.playback import arc_playback_samples


def native(source, **options):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik", **options)


@pytest.fixture
def ic_ac_cip_programs():
    """Exact supplied programs, including the AC variant's extra rapid move."""
    return (
        "; CIP SAMPLE IC\n"
        "T1 D1\n"
        "M6\n"
        "G0 G90 G54 X130 Y70.70 S800 M3\n"
        "G17 G1 Z-2 F100 M8\n"
        "CIP X80 Y120 Z-10 I1=IC(-85.35) J1=IC(-35.35) K1=-6\n"
        "M9\n"
        "SUPA Z0 D0 M5\n"
        "M30\n",
        "; CIP SAMPLE AC\n"
        "T1 D1\n"
        "M6\n"
        "G0 G90 G54 X130 Y70.70 S800 M3\n"
        "G17 G1 Z-2 F100 M8\n"
        "CIP X80 Y120 Z-10 I1=AC(44.65) J1=AC(35.35) K1=-6\n"
        "G0 X130 Y70.70\n"
        "M9\n"
        "SUPA Z0 D0 M5\n"
        "M30\n",
    )


def _expected_ic_ac_cip_point(fraction):
    # Independent reference: solve the two equidistance equations and the
    # plane through S=(130,70.7,-2), M=(44.65,35.35,-6), E=(80,120,-10).
    # These constants do not come from through_three_points or a kernel run.
    center = (80.27156473423358, 70.27685113815008, -5.960559450109953)
    normal = (0.07981490199191571, -0.08028048892020188, -0.9935716504202172)
    radial = tuple(start - value for start, value in zip((130, 70.7, -2), center, strict=True))
    tangent = (
        normal[1] * radial[2] - normal[2] * radial[1],
        normal[2] * radial[0] - normal[0] * radial[2],
        normal[0] * radial[1] - normal[1] * radial[0],
    )
    angle = fraction * 4.708988660475327
    return tuple(center[i] + radial[i] * math.cos(angle) + tangent[i] * math.sin(angle) for i in range(3))


def test_supplied_cip_ic_and_ac_have_identical_complete_spatial_arcs(ic_ac_cip_programs):
    incremental, absolute = (native(source) for source in ic_ac_cip_programs)
    # SUPA after modal CIP is outside the existing rapid-only SUPA subset.
    # Assert the exact later blocker rather than hiding arbitrary failures;
    # the trustworthy CIP motion has already been resolved in both programs.
    assert not incremental.ok and not incremental.complete
    assert len(incremental.diagnostics) == 1
    diagnostic = incremental.diagnostics[0]
    assert diagnostic.code == "UNSUPPORTED_SINUMERIK_CIP"
    assert diagnostic.line == 8 and diagnostic.raw == "SUPA Z0 D0 M5"
    assert absolute.ok and absolute.complete and not absolute.diagnostics
    motions = []
    for result in (incremental, absolute):
        cip = [motion for motion in result.motions if motion.source_kind == "cip"]
        assert len(cip) == 1
        motion = cip[0]
        motions.append(motion)
        assert motion.source_block == 5
        assert (motion.start_x, motion.start_y, motion.start_z) == pytest.approx((130, 70.7, -2), abs=1e-10, rel=0)
        assert (motion.end_x, motion.end_y, motion.end_z) == pytest.approx((80, 120, -10), abs=1e-10, rel=0)
        assert motion.arc.center == pytest.approx(
            (80.27156473423358, 70.27685113815008, -5.960559450109953), abs=1e-10, rel=0
        )
        assert motion.arc.normal == pytest.approx(
            (0.07981490199191571, -0.08028048892020188, -0.9935716504202172), abs=1e-12
        )
        assert motion.arc.radius == pytest.approx(49.887697482432095, abs=1e-10, rel=0)
        assert motion.arc.sweep == pytest.approx(4.708988660475327, abs=1e-12, rel=0)
        assert not motion.arc.clockwise and not motion.arc.full_circle
        assert motion_length(motion) == pytest.approx(234.92060174199622, abs=1e-9, rel=0)
        # The expected intermediate point lies inside the directed major arc.
        # In G90, bare K1=-6 remains absolute despite IC on I1/J1.
        assert point_at(motion, 2.371371458433027) == pytest.approx((44.65, 35.35, -6), abs=1e-10, rel=0)
        points = sample_motion(motion, 1, arc_points_per_circle=720)
        assert len(points) > 500
        for index, point in enumerate(points, 1):
            assert (point.x, point.y, point.z) == pytest.approx(
                _expected_ic_ac_cip_point(index / len(points)), abs=1e-9
            )
    first, second = motions[0], motions[1]
    assert first.arc == second.arc
    # Compare corresponding normalized parameters even if tessellation counts
    # change; every point also has an independent XYZ reference above.
    for index in range(1001):
        fraction = index / 1000
        assert point_at(first, fraction * first.arc.sweep) == pytest.approx(
            point_at(second, fraction * second.arc.sweep), abs=1e-10
        )
    later = [motion for motion in absolute.motions if motion.source_block == 6]
    assert len(later) == 1 and later[0].move == 0 and later[0].source_kind != "cip"
    assert (later[0].end_x, later[0].end_y, later[0].end_z) == pytest.approx((130, 70.7, -10), abs=1e-10, rel=0)


@pytest.mark.parametrize("plane", [17, 18, 19])
@pytest.mark.parametrize("dimensions", ["G90", "G91"])
def test_spatial_semicircle_geometry_render_playback_and_statistics(plane, dimensions):
    root = math.sqrt(0.5)
    end = -1 if dimensions == "G90" else -2
    mid = 0 if dimensions == "G90" else -1
    source = f"G{plane} G90 G0 X1\n{dimensions} CIP X{end} I1={mid} J1={root} K1={root} F100\nM30"
    result = native(source)
    assert result.ok and result.complete, result.diagnostics
    motion = result.motions[-1]
    assert motion.arc.center == pytest.approx((0, 0, 0))
    assert motion.arc.radius == pytest.approx(1)
    assert motion.arc.sweep == pytest.approx(math.pi)
    assert motion.arc.normal == pytest.approx((0, -root, root))
    assert motion_length(motion) == pytest.approx(math.pi)
    for points in (sample_motion(motion, 1, arc_points_per_circle=100), arc_playback_samples(motion, 1)):
        assert len(points) > 2
        assert min(math.dist((p.x, p.y, p.z), (0, root, root)) for p in points) < 1e-12
        assert all(math.dist((p.x, p.y, p.z), (0, 0, 0)) == pytest.approx(1) for p in points)
        assert (points[-1].x, points[-1].y, points[-1].z) == (-1, 0, 0)
    stats = trace_statistics(result)
    assert stats["bounds"][1][1] == pytest.approx(root)
    assert stats["bounds"][2][1] == pytest.approx(root)


def test_cimco_first_cip_preserves_all_three_programmed_points():
    source = "G90 G71 G17 G0 X75.575 Y-73.008 Z10.8\n"
    source += "N27 CIP X75.009 Y-73.574 Z10 I1=75.409 J1=-73.174 K1=10.234 F1000\nM30"
    result = native(source)
    assert result.ok and result.complete, result.diagnostics
    motion = result.motions[-1]
    intermediate = (75.409, -73.174, 10.234)
    assert math.dist(motion.arc.center, intermediate) == pytest.approx(motion.arc.radius, abs=1e-10)
    # Independent triangle-side / Heron reference, not the kernel's vector formula.
    start, end = (75.575, -73.008, 10.8), (75.009, -73.574, 10)
    a, b, c = math.dist(start, intermediate), math.dist(intermediate, end), math.dist(start, end)
    half = (a + b + c) / 2
    area = math.sqrt(half * (half - a) * (half - b) * (half - c))
    radius = a * b * c / (4 * area)
    assert motion.arc.radius == pytest.approx(radius, abs=1e-10)
    assert motion.arc.sweep == pytest.approx(2 * math.asin(c / (2 * radius)), abs=1e-10)
    assert motion.source_nlabel == 27
    assert motion.source_kind == "cip"


def test_major_arc_and_reverse_direction_pass_through_the_intermediate_point():
    for mid, end, expected_normal in [("J1=-1", "Y1", -1), ("J1=1", "Y-1", 1)]:
        result = native(f"G0 X1 Y0 Z0\nCIP X0 {end} I1=0 {mid} F100\nM30")
        assert result.ok and result.complete, result.diagnostics
        motion = result.motions[-1]
        assert motion.arc.sweep == pytest.approx(1.5 * math.pi)
        assert motion.arc.normal == pytest.approx((0, 0, expected_normal))
        points = sample_motion(motion, 1, arc_points_per_circle=120)
        assert min(math.dist((p.x, p.y, p.z), (0, -expected_normal, 0)) for p in points) < 1e-12


def test_spatial_arc_is_transformed_with_the_static_tilted_frame():
    root = math.sqrt(0.5)
    source = 'CYCLE800(0,"",0,57,10,20,30,0,0,90,0,0,0,0)\nG0 X1 Y0 Z0\n'
    source += f"CIP X-1 I1=0 J1={root} K1={root} F100\nM30"
    result = native(source, kinematics="5ax_table_ac_angled")
    assert result.ok and result.complete, result.diagnostics
    motion = result.motions[-1]
    assert motion.arc.center == pytest.approx((10, 20, 30))
    assert motion.arc.normal == pytest.approx((root, 0, root))
    points = sample_motion(motion, 1, arc_points_per_circle=100)
    assert min(math.dist((p.x, p.y, p.z), (10 - root, 20, 30 + root)) for p in points) < 1e-12


def test_missing_next_modal_intermediate_point_cannot_bypass_controller_gate():
    result = native("G0 X1\nCIP X-1 I1=0 J1=1 F100\nX1\nM30")
    assert not result.ok and not result.complete
    assert result.diagnostics[-1].code == "INVALID_SINUMERIK_CIP"
    assert result.diagnostics[-1].line == 3


def test_cip_modal_state_explicit_point_modes_units_wcs_and_full_replay():
    source = "G70 G90 G0 X1 Y0 Z0\nCIP X-1 I1=IC(-1) J1=AC(1) F10\n"
    source += "X1 I1=AC(0) J1=IC(-1)\nG1 X2\nM30"
    result = native(source, wcs_offsets={54: (100, 200, 300)})
    assert result.ok and result.complete, result.diagnostics
    assert [m.source_kind for m in result.motions] == ["motion", "cip", "cip", "motion"]
    assert result.motions[1].arc.center == pytest.approx((100, 200, 300))
    assert result.motions[1].arc.radius == pytest.approx(25.4)
    formatted = export_full_mill_program(result, source.splitlines(), ExportOptions())
    replay = native(formatted, wcs_offsets={54: (100, 200, 300)})
    assert replay.ok and replay.complete, replay.diagnostics
    assert [m.arc for m in replay.motions] == [m.arc for m in result.motions]


@pytest.mark.parametrize(
    "command,code",
    [
        ("CIP X2 I1=1", "INVALID_SINUMERIK_CIP"),
        ("CIP X0 I1=1 J1=1", "INVALID_SINUMERIK_CIP"),
        ("CIP X2", "INVALID_SINUMERIK_CIP"),
        ("CIP I1=1 J1=1", "INVALID_SINUMERIK_CIP"),
        ("G1 X2 I1=1 J1=1", "INVALID_SINUMERIK_CIP"),
        ("G41 CIP X2 I1=1 J1=1", "UNSUPPORTED_SINUMERIK_CIP"),
    ],
)
def test_invalid_cip_fails_with_source_location(command, code):
    result = native("G0 X0\n" + command + "\nM30")
    assert not result.ok and not result.complete
    assert result.diagnostics[-1].code == code
    assert result.diagnostics[-1].line == 2


@pytest.mark.parametrize("target,dialect", [("fanuc_mill", "fanuc"), ("sinumerik_840d", "sinumerik")])
def test_expanded_spatial_arc_uses_verified_linearization(target, dialect):
    result = native("G0 X1\nCIP X-1 I1=0 J1=0.7071067811865476 K1=0.7071067811865476 F100\nM30")
    output = export_result(result, ExportOptions(linearization_tolerance=0.001), target=target)
    replay = execute(output, language="fanuc_mill", source_dialect=dialect)
    assert replay.ok and replay.complete, replay.diagnostics
    points = [(m.end_x, m.end_y, m.end_z) for m in replay.motions[1:]]
    assert len(points) > 20
    assert all(math.dist(p, (0, 0, 0)) == pytest.approx(1, abs=2e-5) for p in points)
    assert points[-1] == (-1, 0, 0)
