"""Programmable frames with independent physical-coordinate references."""

import math
from dataclasses import FrozenInstanceError

import pytest

from app.gcode.export.common import ExportOptions
from app.gcode.export.expanded import export_result
from app.gcode.export.full import export_full_mill_program
from app.gcode.kernel import execute
from app.gcode.kernel.frontend.sinumerik import parse_sinumerik_program
from app.gcode.kernel.geometry.transform import TransformState
from app.gcode.kernel.milling.sinumerik_frame import apply_frame, compile_frame
from app.gcode.kernel.milling.state import MillState
from app.gcode.trace_tools import motion_length, sample_motion, trace_statistics


def native(source, **options):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik", **options)


def end(motion):
    return motion.end_x, motion.end_y, motion.end_z


@pytest.mark.parametrize(
    "commands,expected",
    [
        ("TRANS X10 Y20 Z30", (10, 20, 30)),
        ("TRANS X10\nATRANS X5", (15, 0, 0)),
        ("TRANS X10\nAROT Z30\nTRANS Y20", (0, 20, 0)),
        ("TRANS X10\nAROT Z30\nTRANS", (0, 0, 0)),
        ("TRANS X10\nAROT Z30\nROT", (0, 0, 0)),
        ("TRANS X100\nAROT Z90\nATRANS X10", (100, 10, 0)),
        ("ROT Z90\nATRANS X10", (0, 10, 0)),
    ],
)
def test_translation_composition_replacement_and_reset(commands, expected):
    result = native("G54\n" + commands + "\nG0 X0 Y0 Z0\nM30")
    assert result.ok and result.complete and not result.diagnostics
    assert result.execution_steps[-2].position == pytest.approx(expected)
    assert len(result.motions) <= 1
    assert all(s.emitted_count == 0 for s in result.execution_steps[:-2])
    assert not any(e.kind.startswith("ROTARY") for e in result.events)


@pytest.mark.parametrize(
    "commands,point,expected",
    [
        ("ROT X90", "X0 Y10 Z0", (0, 0, 10)),
        ("ROT Y90", "X10 Y0 Z0", (0, 0, -10)),
        ("ROT Z90", "X10 Y0 Z0", (0, 10, 0)),
        ("TRANS X100\nAROT Z90", "X10 Y0 Z0", (100, 10, 0)),
        ("TRANS X100\nAROT Y30\nROT Z90", "X10 Y0 Z0", (0, 10, 0)),
        ("ROT Z90\nAROT X90", "X0 Y10 Z0", (0, 0, 10)),
        ("ROT X90 Y90 Z90", "X10 Y20 Z30", (30, 20, -10)),
        ("ROT Z90 X90 Y90", "X10 Y20 Z30", (30, 20, -10)),
    ],
)
def test_spatial_rotation_and_intrinsic_rpy_order(commands, point, expected):
    result = native(commands + "\nG1 " + point + " F100\nM30")
    assert result.ok and result.complete and not result.diagnostics
    assert end(result.motions[-1]) == pytest.approx(expected)


@pytest.mark.parametrize("command", ["ROT", "AROT"])
@pytest.mark.parametrize(
    "plane,point,expected",
    [(17, "X10 Y0 Z0", (0, 10, 0)), (18, "X10 Y0 Z0", (0, 0, -10)), (19, "X0 Y10 Z0", (0, 0, 10))],
)
def test_rpl_uses_positive_siemens_plane_normal(command, plane, point, expected):
    result = native(f"G{plane}\n{command} RPL=90\nG1 {point} F100\nM30")
    assert result.ok and result.complete and not result.diagnostics
    assert end(result.motions[-1]) == pytest.approx(expected)


def test_frame_rebases_program_position_without_physical_motion():
    source = "G0 X2 Y3 Z4\nTRANS X100\nAROT Z90\nATRANS X10\nROT\nG91 G1 X1 F100\nM30"
    result = native(source, wcs_offsets={54: (10, 20, 30)})
    assert result.ok and not result.diagnostics
    for step in result.execution_steps[1:5]:
        assert step.emitted_count == 0
        assert step.position == pytest.approx((12, 23, 34))
    assert result.execution_steps[2].programmed_position == pytest.approx((3, 98, 4))
    assert end(result.motions[-1]) == pytest.approx((13, 23, 34))


@pytest.mark.parametrize("wcs", [54, 55, 56, 57, 58, 59, 500])
def test_wcs_switch_retains_programmable_frame_and_physical_position(wcs):
    offsets = {code: (code, 2 * code, 3 * code) for code in range(54, 60)}
    result = native(f"TRANS X10\nAROT Z90\nG0 X1 Y0 Z0\nG{wcs}\nG0 X2 Y0 Z0\nM30", wcs_offsets=offsets)
    assert result.ok and not result.diagnostics
    assert result.execution_steps[3].position == pytest.approx(result.execution_steps[2].position)
    assert result.execution_steps[3].emitted_count == 0
    offset = offsets.get(wcs, (0, 0, 0))
    assert end(result.motions[-1]) == pytest.approx((offset[0] + 10, offset[1] + 2, offset[2]))


def test_literals_parameters_named_scalars_and_inch_translation():
    source = "R1=90\nDEF REAL _VALUE\n_VALUE=1\nG70\nTRANS X=_VALUE\nAROT Z=R1\nATRANS X1\nG1 X1 Y0 Z0 F10\nM30"
    result = native(source)
    assert result.ok and not result.diagnostics
    assert end(result.motions[-1]) == pytest.approx((25.4, 50.8, 0))


def test_full_preserves_boundaries_after_named_frame_values():
    source = "DEF REAL _SHIFT\n_SHIFT=10\nTRANS X=_SHIFT Y20 Z30\nAROT RPL=90\nG0 X1 Y0 Z0\nM30"
    result = native(source)
    assert result.ok and not result.diagnostics
    output = export_full_mill_program(result, source.splitlines(), ExportOptions())
    replay = native(output)
    assert replay.ok and not replay.diagnostics
    assert end(replay.motions[-1]) == pytest.approx((10, 21, 30))


def test_documented_local_spatial_translation_and_modal_moves():
    # Fundamentals 03/2013, section 12.4: local X shift after a Y rotation.
    source = "TRANS X10 Y10\nATRANS X35\nAROT Y30\nATRANS X5\nG0 X0 Y0 Z0\nX10\nY10\nM30"
    result = native(source)
    assert result.ok and not result.diagnostics
    expected = [
        (45 + 5 * math.sqrt(3) / 2, 10, -2.5),
        (45 + 15 * math.sqrt(3) / 2, 10, -7.5),
        (45 + 15 * math.sqrt(3) / 2, 20, -7.5),
    ]
    assert len(result.motions) == len(expected)
    for motion, point in zip(result.motions, expected, strict=True):
        assert end(motion) == pytest.approx(point)


def test_invalid_rotated_arc_has_source_location():
    result = native("ROT X30\nG0 X1 Y0 Z0\nG3 X10 Y10 CR=1 F100\nM30")
    assert not result.ok and not result.complete
    diagnostic = result.diagnostics[-1]
    assert diagnostic.code == "INVALID_GEOMETRY"
    assert diagnostic.line == 3 and diagnostic.raw == "G3 X10 Y10 CR=1 F100"


@pytest.mark.parametrize("command", ["TRANS", "TRANS Y20", "ROT", "ROT Z90"])
def test_substitution_clears_legacy_transform_components(command):
    state = MillState(x=3, y=4, z=5)
    state.transform = TransformState(
        translation=(10, 20, 30),
        rotation_active=True,
        rotation_degrees=30,
        scaling_active=True,
        scale_factors=(2, 3, 4),
    )
    physical = state.transform.build().apply((state.x, state.y, state.z))
    syntax = parse_sinumerik_program(command).blocks[0].native_syntax
    frame = compile_frame(syntax, state)
    apply_frame(frame, state)
    assert not frame.scaling_active and frame.scale_factors == (1, 1, 1)
    assert frame.rotation_degrees == 0
    if command in ("TRANS", "ROT"):
        assert frame.spatial_rotation is None
    assert frame.build().apply((state.x, state.y, state.z)) == pytest.approx(physical)


def test_frame_ast_is_immutable_native_syntax_and_preserves_raw():
    raw = "N10 ATRANS X=R1 Z=_VALUE ; local shift"
    program = parse_sinumerik_program(raw)
    syntax = program.blocks[0].native_syntax
    assert program.blocks[0].raw == raw
    assert syntax.kind == "programmed_frame"
    assert syntax.frame_command == "ATRANS"
    assert syntax.frame_values == (("X", "R1"), ("Z", "_VALUE"))
    assert program.ast.nodes[0].native_syntax == syntax
    with pytest.raises(FrozenInstanceError):
        syntax.frame_command = "TRANS"


@pytest.mark.parametrize(
    "command",
    [
        "G1 X10 TRANS X20",
        "TRANS X10 G0",
        "ROT X10 X20",
        "TRANS A10",
        "ROT RPL=10 Z20",
        "TRANS X=R1+2",
        "ATRANS",
        "AROT",
    ],
)
def test_invalid_frame_is_fail_closed_with_source_location(command):
    result = native("G0 X1\n" + command + "\nG1 X2\nM30")
    assert not result.ok and not result.complete
    diagnostic = result.diagnostics[-1]
    assert diagnostic.code == "INVALID_SINUMERIK_FRAME"
    assert diagnostic.line == 2 and diagnostic.raw == command
    assert len(result.motions) == 1


@pytest.mark.parametrize("command", ["TRANS X=R99", "ROT Z=_MISSING"])
def test_undefined_frame_parameter_retains_typed_diagnostic(command):
    result = native("G0 X1\n" + command + "\nM30")
    assert not result.ok and result.diagnostics[-1].line == 2
    assert result.diagnostics[-1].raw == command


@pytest.mark.parametrize("command", ["TRANS", "TRANS X10", "ROT", "AROT Z30"])
@pytest.mark.parametrize("active", ['CYCLE800(0,"",0,57,0,0,0,0,0,30,0,0,0,0)', "TRAORI"])
def test_frames_cannot_reset_or_compose_with_active_twp_tcp(command, active):
    result = native(active + "\n" + command + "\nM30", kinematics="5ax_table_ac_angled")
    assert not result.ok and not result.complete
    diagnostic = result.diagnostics[-1]
    assert diagnostic.code == "UNSUPPORTED_SINUMERIK_FRAME_COMPOSITION"
    assert diagnostic.line == 2 and diagnostic.raw == command
    assert not any(e.kind in ("TILTED_WORK_PLANE_OFF", "TCP_CONTROL_OFF") for e in result.events)


@pytest.mark.parametrize("command", ['CYCLE800(0,"",0,57,0,0,0,0,0,30,0,0,0,0)', "TRAORI", "G291"])
def test_existing_composition_guards_reject_active_programmable_frame(command):
    result = native("TRANS X10\nAROT Z90\n" + command + "\nM30", kinematics="5ax_table_ac_angled")
    assert not result.ok and not result.complete
    assert result.diagnostics[-1].line == 3 and result.diagnostics[-1].raw == command
    assert result.diagnostics[-1].severity != "warning"


@pytest.mark.parametrize(
    "plane,start,finish,ijk,normal",
    [
        (17, "X1 Y0 Z0", "X0 Y1 Z0", "I-1 J0", (0, -1, 0)),
        (18, "X1 Y0 Z0", "X0 Y0 Z-1", "I-1 K0", (0, 0, 1)),
        (19, "X0 Y1 Z0", "X0 Y0 Z1", "J-1 K0", (1, 0, 0)),
    ],
)
@pytest.mark.parametrize("radius_mode", [False, True])
def test_rotated_ijk_and_cr_arcs_all_planes(plane, start, finish, ijk, normal, radius_mode):
    result = native(
        f"TRANS X10 Y20 Z30\nAROT X90\nG{plane} G0 {start}\nG3 {finish} {'CR=1' if radius_mode else ijk} F100\nM30"
    )
    assert result.ok and not result.diagnostics
    motion = result.motions[-1]
    assert motion.arc.center == pytest.approx((10, 20, 30))
    assert motion.arc.normal == pytest.approx(normal)
    assert motion.arc.sweep == pytest.approx(math.pi / 2)
    assert motion_length(motion) == pytest.approx(math.pi / 2)
    points = sample_motion(motion, 1, arc_points_per_circle=100)
    assert all(math.dist((p.x, p.y, p.z), (10, 20, 30)) == pytest.approx(1) for p in points)
    assert (points[-1].x, points[-1].y, points[-1].z) == pytest.approx(end(motion))


@pytest.mark.parametrize("direction", [2, 3])
@pytest.mark.parametrize("travel", [0, 2])
def test_rotated_full_circle_helix_length_bounds_and_samples(direction, travel):
    result = native(f"ROT X90\nG0 X1 Y0 Z0\nG{direction} X1 Y0 Z{travel} I-1 J0 F100\nM30")
    assert result.ok and not result.diagnostics
    motion = result.motions[-1]
    assert motion.arc.full_circle
    assert len(sample_motion(motion, 1, arc_points_per_circle=1)) >= 4
    assert motion_length(motion) == pytest.approx(math.hypot(math.tau, travel))
    points = sample_motion(motion, 1, arc_points_per_circle=100)
    for p in points:
        assert math.hypot(p.x, p.z) == pytest.approx(1)
    midpoint = points[len(points) // 2 - 1]
    assert midpoint.y == pytest.approx(-travel / 2, abs=0.03)
    bounds = trace_statistics(result)["bounds"]
    assert bounds[0] == pytest.approx((-1, 1))
    assert bounds[2] == pytest.approx((-1, 1))


def test_oblique_helix_samples_match_independent_parametric_curve_and_bounds():
    result = native("ROT X30 Y45\nG0 X1 Y0 Z0\nG3 X1 Y0 Z4 I-1 J0 F100\nM30")
    assert result.ok and not result.diagnostics
    points = sample_motion(result.motions[-1], 1, arc_points_per_circle=2000)
    root = math.sqrt(0.5)
    for index, point in enumerate(points, 1):
        angle = math.tau * index / len(points)
        x, y, z = math.cos(angle), math.sin(angle), 4 * angle / math.tau
        expected = (
            root * x + root * 0.5 * y + root * math.sqrt(3) / 2 * z,
            math.sqrt(3) / 2 * y - 0.5 * z,
            -root * x + root * 0.5 * y + root * math.sqrt(3) / 2 * z,
        )
        assert (point.x, point.y, point.z) == pytest.approx(expected)
    bounds = trace_statistics(result)["bounds"]
    physical_points = [(0, 0, 0), (root, 0, -root), *[(p.x, p.y, p.z) for p in points]]
    for axis, bound in enumerate(bounds):
        assert bound == pytest.approx(
            (min(p[axis] for p in physical_points), max(p[axis] for p in physical_points)), abs=1e-5
        )


@pytest.mark.parametrize("target,dialect", [("fanuc_mill", "fanuc"), ("sinumerik_840d", "sinumerik")])
def test_expanded_bakes_frames_and_linearizes_noncanonical_arc_plane(target, dialect):
    source = "TRANS X10 Y20 Z30\nAROT X90\nG0 X1 Y0 Z0\nG3 X0 Y1 I-1 J0 F100\nM30"
    result = native(source)
    output = export_result(result, ExportOptions(linearization_tolerance=0.001), target=target)
    replay = execute(output, language="fanuc_mill", source_dialect=dialect)
    assert replay.ok and not replay.diagnostics
    assert len(replay.motions) > 10
    assert end(replay.motions[-1]) == pytest.approx((10, 20, 31))
    assert all(math.dist(end(m), (10, 20, 30)) == pytest.approx(1, abs=2e-5) for m in replay.motions)
    full = export_full_mill_program(result, source.splitlines(), ExportOptions())
    full_replay = native(full)
    assert full_replay.ok and not full_replay.diagnostics
    assert [end(m) for m in full_replay.motions] == [end(m) for m in result.motions]


def test_real_impeller_reset_has_no_motion_or_unmodeled_frame_warning(fixture_text):
    result = native(fixture_text("milling/sinumerik/impeller.mpf"), kinematics="5ax_table_bc_angled", home_z=300)
    assert result.ok and result.complete
    step = next(s for s in result.execution_steps if result.program.blocks[s.source_block].raw.strip() == "N14 TRANS")
    assert step.emitted_count == 0
    assert not any(d.line == 10 for d in result.diagnostics)
    assert len(result.motions) == 5469
