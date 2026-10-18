"""Native Klartext rotary execution and independent three-post CAM geometry."""

import math
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest

from app.gcode.kernel import execute
from app.gcode.kernel.frontend.ast import _build_program_ast_python
from app.gcode.kernel.frontend.heidenhain import parse_heidenhain_program
from app.gcode.kernel.frontend.heidenhain_lexer import HeidenhainParseError
from app.gcode.kernel.geometry.arc_segments import split_arc
from app.gcode.kernel.geometry.spatial_arc import point_at
from app.gcode.kernel.milling.heidenhain_rotary import spatial_angles
from app.gcode.kernel.milling.kinematics import effective_orientation, load_catalog, transform_vector

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/milling/test_5ax"
DIALECTS = {"nc": "fanuc", "mpf": "sinumerik", "h": "heidenhain"}
PROFILE = "5ax_table_ac"
# The FANUC/Klartext posts round coordinates and angles to three decimals;
# SINUMERIK retains five/six. Rotation of rounded coordinates adds further error.
POSITION_TOLERANCE = 0.002
AXIS_TOLERANCE = 2e-5


def run(source, **options):
    return execute(source, "fanuc_mill", source_dialect="heidenhain", **options)


def point(motion, *, end):
    return (motion.end_x, motion.end_y, motion.end_z) if end else (motion.start_x, motion.start_y, motion.start_z)


def axis(matrix):
    return tuple(row[2] for row in matrix)


@pytest.fixture(scope="module")
def cam_results():
    return {
        extension: execute(
            (FIXTURES / f"1001.{extension}").read_text(encoding="utf-8"),
            "fanuc_mill",
            source_dialect=dialect,
            kinematics=PROFILE,
            home_z=100,
            emulate_g28_home=True,
        )
        for extension, dialect in DIALECTS.items()
    }


def quarter_arc_feed_trace(result):
    # The same circle is one CP in Klartext, two semicircles in FANUC and four
    # quadrants in SINUMERIK. Compare geometry independently of block partition.
    return tuple(
        part
        for motion in result.motions
        if motion.move != 0
        for part in (split_arc(motion, math.pi / 2 + 1e-4) if motion.arc else (motion,))
    )


@pytest.mark.parametrize("extension", DIALECTS)
def test_original_cam_program_completes_with_source_and_rotary_poses(cam_results, extension):
    result = cam_results[extension]
    assert result.ok and result.complete and result.program_end == "M30", result.diagnostics
    assert not any(d.severity == "error" for d in result.diagnostics)
    assert result.kinematics_profile == PROFILE and result.kinematics_fingerprint
    assert result.rotary_axes == ("A", "C")
    assert sum(step.emitted_count for step in result.execution_steps) == len(result.motions)
    assert all(m.source_raw == result.program.blocks[m.source_block].raw for m in result.motions)
    feeds = quarter_arc_feed_trace(result)
    assert len(feeds) == 1182
    assert sum(m.arc is not None for m in feeds) == 16
    varying = [m for m in feeds if not np.allclose(m.start_tool_orientation, m.tool_orientation, atol=1e-7)]
    assert len(varying) > 500  # The supplied swarf operation is continuous five-axis.


@pytest.mark.parametrize("first,second", list(combinations(DIALECTS, 2)))
def test_three_posts_preserve_all_cutting_geometry_and_tool_axes(cam_results, first, second):
    left, right = (quarter_arc_feed_trace(cam_results[key]) for key in (first, second))
    for index, (a, b) in enumerate(zip(left, right, strict=True)):
        context = (first, second, index, a.source_raw, b.source_raw)
        assert a.tool == b.tool and a.feed == b.feed, context
        assert (a.arc is None) == (b.arc is None), context
        for end in (False, True):
            assert math.dist(point(a, end=end), point(b, end=end)) < POSITION_TOLERANCE, context
        for field in ("start_tool_orientation", "tool_orientation"):
            assert math.dist(axis(getattr(a, field)), axis(getattr(b, field))) < AXIS_TOLERANCE, context
        if a.arc is not None:
            assert math.dist(a.arc.center, b.arc.center) < POSITION_TOLERANCE, context
            assert abs(a.arc.radius - b.arc.radius) < POSITION_TOLERANCE, context
            assert abs(a.arc.sweep - b.arc.sweep) < 2e-5, context
            # Intermediate points catch reversed arcs with identical endpoints.
            for fraction in (0.25, 0.5, 0.75):
                assert (
                    math.dist(point_at(a, a.arc.sweep * fraction), point_at(b, b.arc.sweep * fraction))
                    < POSITION_TOLERANCE
                ), context


def test_native_plane_ast_preserves_options_expressions_and_portable_parity():
    program = parse_heidenhain_program(
        "Q1=30\nPLANE SPATIAL SPA+Q1 SPB0 SPC-90 TURN FMAX SEQ+ TABLE ROT\nPLANE RESET STAY"
    )
    syntax = program.blocks[1].native_syntax
    assert syntax.kind == "transform" and syntax.command == "PLANE SPATIAL"
    assert syntax.word("SPA").expression.kind == "unary"
    assert syntax.plane.positioning == "TURN" and syntax.plane.sequence == 1
    assert syntax.plane.table_rotation == "ROT"
    assert program.ast == _build_program_ast_python(program.blocks)
    assert all(not block.parsed_words and block.motion_node is None for block in program.blocks)


@pytest.mark.parametrize(
    "source",
    [
        "PLANE SPATIAL SPA0 SPB0 SPC0",
        "PLANE SPATIAL SPA0 SPB0 TURN FMAX",
        "PLANE RESET SPA0 STAY",
        "PLANE RESET STAY FMAX",
        "PLANE RESET TURN SEQ+ SEQ-",
    ],
)
def test_malformed_plane_reports_physical_location(source):
    with pytest.raises(HeidenhainParseError) as caught:
        parse_heidenhain_program("L X1 F100\n" + source)
    assert caught.value.line == 2 and caught.value.raw == source


@pytest.mark.parametrize(
    "source,profile,code",
    [
        ("L A0 FMAX", None, "ROTARY_KINEMATICS_REQUIRED"),
        ("PLANE RESET STAY", None, "ROTARY_KINEMATICS_REQUIRED"),
        ("L B30 FMAX", PROFILE, "UNCONFIGURED_ROTARY_AXIS"),
        ("M128", "4ax_head_a", "UNSUPPORTED_HEIDENHAIN_TCP"),
        ("L A30 X2 F100", PROFILE, "UNSUPPORTED_SIMULTANEOUS_ROTARY_MOTION"),
        ("PLANE RESET MOVE FMAX", PROFILE, "UNSUPPORTED_HEIDENHAIN_PLANE"),
        ("PLANE RESET TURN TABLE COORD", PROFILE, "UNSUPPORTED_HEIDENHAIN_PLANE"),
        ("PLANE SPATIAL SPA30 SPB0 SPC0 STAY\nM128", PROFILE, "UNSUPPORTED_HEIDENHAIN_TCP"),
    ],
)
def test_unsupported_rotary_contract_stops_without_later_geometry(source, profile, code):
    result = run("TOOL CALL Z\nL X1 F100\n" + source + "\nL X999", kinematics=profile)
    assert not result.ok and not result.complete
    assert result.diagnostics[-1].code == code
    assert result.motions[-1].end_x == 1
    assert all(m.end_x != 999 for m in result.motions)


@pytest.mark.parametrize("profile", ["5ax_table_ac", "5ax_table_bc"])
def test_plane_turn_matches_requested_axis_and_preserves_fixed_frame(profile):
    result = run("TOOL CALL Z\nPLANE SPATIAL SPA30 SPB20 SPC15 TURN FMAX\nL X10 Y20 Z30 F100", kinematics=profile)
    assert result.ok and result.complete, result.diagnostics
    matrix = spatial_angles((30, 20, 15))
    assert point(result.motions[-1], end=True) == pytest.approx(transform_vector(matrix, (10, 20, 30)))
    achieved = effective_orientation(load_catalog()[profile], dict(result.rotary_angles))
    assert axis(achieved) == pytest.approx(axis(matrix), abs=1e-7)


@pytest.mark.parametrize(
    "control,reset", [("M128", "M129"), ("FUNCTION TCPM F TCP AXIS POS PATHCTRL AXIS", "FUNCTION RESET TCPM")]
)
def test_tcp_rotary_only_motion_retains_tip_and_captures_both_orientations(control, reset):
    result = run(f"TOOL CALL Z\nL X10 Y20 Z30 F100\n{control}\nL A30 C45 F100\n{reset}\nL X0 FMAX", kinematics=PROFILE)
    assert result.ok and result.complete, result.diagnostics
    motion = next(m for m in result.motions if "A30" in m.source_raw)
    assert point(motion, end=False) == point(motion, end=True) == (10, 20, 30)
    assert axis(motion.start_tool_orientation) == pytest.approx((0, 0, 1))
    assert axis(motion.tool_orientation) == pytest.approx((math.sqrt(0.125), -math.sqrt(0.125), math.sqrt(0.75)))
    assert [e.kind for e in result.events if e.kind.startswith("TCP_CONTROL")] == ["TCP_CONTROL_ON", "TCP_CONTROL_OFF"]


@pytest.mark.parametrize("address", ["A", "B", "C"])
@pytest.mark.parametrize("negative", [False, True])
def test_single_table_tcp_keeps_tip_and_uses_signed_joint(address, negative):
    profile = f"4ax_table_{address.lower()}" + ("_negative" if negative else "")
    result = run(
        f"TOOL CALL 1 Z\nL X10 Y20 Z30 F100\nM128\nL {address}30 F100\nL X11 Y22 Z33 F100\nM129\nL X0 Y0 Z0 FMAX\nM30",
        kinematics=profile,
    )
    assert result.ok and result.complete, result.diagnostics
    rotary = next(m for m in result.motions if m.source_raw == f"L {address}30 F100")
    assert point(rotary, end=False) == point(rotary, end=True) == (10, 20, 30)
    angle = math.radians(-30 if negative else 30)
    sine, cosine = math.sin(angle), math.cos(angle)
    expected_axis = {"A": (0, -sine, cosine), "B": (sine, 0, cosine), "C": (0, 0, 1)}[address]
    assert axis(rotary.tool_orientation) == pytest.approx(expected_axis)
    cutting = next(m for m in result.motions if m.source_raw == "L X11 Y22 Z33 F100")
    assert point(cutting, end=True) == (11, 22, 33)
    assert [e.kind for e in result.events if e.kind.startswith("TCP_CONTROL")] == ["TCP_CONTROL_ON", "TCP_CONTROL_OFF"]


def test_legacy_zero_index_and_repeated_tcp_controls_keep_xyz_geometry():
    source = (
        "BEGIN PGM PART 080.016 MM\nA+0\nTOOL CALL 6 Z S2387\nL M126\n"
        "L M128 F1000\nL X141 Y0 Z150 A0 FMAX M13\nL Z91 FMAX\nL Z88 F239\n"
        "L X115 Y3\nL M128 F1000\nTOOL CALL Z S1857\nL Z150 FMAX\nM30\nEND PGM PART 080.016 MM"
    )
    result = run(source, kinematics="4ax_table_a")
    assert result.ok and result.complete, result.diagnostics
    assert not result.diagnostics
    assert result.program_end == "M30"
    assert [point(m, end=True) for m in result.motions] == [
        (141, 0, 150),
        (141, 0, 91),
        (141, 0, 88),
        (115, 3, 88),
        (115, 3, 150),
    ]
    assert sum(e.kind == "TCP_CONTROL_ON" for e in result.events) == 1


def test_rotary_profile_error_is_a_structured_native_result():
    result = run("L A30 FMAX", kinematics="missing-profile")
    assert not result.ok and result.diagnostics[-1].code == "INVALID_KINEMATICS_PROFILE"
    assert result.source_dialect == "heidenhain"


@pytest.mark.parametrize("command,raw_z", [("L Z0 FMAX M91", -300), ("L M140 MB MAX", 200), ("L M140 MB10", 40)])
def test_machine_positioning_and_home_retraction_bypass_tilted_program_coordinates(command, raw_z):
    result = run(
        "TOOL CALL Z\nL A30 C0 FMAX\nPLANE SPATIAL SPA30 SPB0 SPC0 STAY\nL X10 Y20 Z30 FMAX\n" + command,
        kinematics=PROFILE,
        wcs_offsets={54: (100, 200, 300)},
        home_z=500,
        emulate_g28_home=True,
    )
    assert result.ok and result.complete, result.diagnostics
    rotated = transform_vector(spatial_angles((30, 0, 0)), (10, 20, raw_z))
    assert point(result.motions[-1], end=True) == pytest.approx(
        tuple(v + offset for v, offset in zip(rotated, (100, 200, 300), strict=True))
    )
    if "MB MAX" in command:
        assert any(d.code == "HEIDENHAIN_M140_HOME_EMULATION" for d in result.diagnostics)


def test_m126_shortest_path_and_incremental_rotary_addresses():
    result = run("TOOL CALL Z\nM126\nL A0 C350 FMAX\nL IC20 FMAX\nM127\nL C350 FMAX", kinematics=PROFILE)
    assert result.ok and result.complete, result.diagnostics
    indices = [e for e in result.events if e.kind == "ROTARY_INDEX"]
    assert [e.new_abc[2] for e in indices] == [-10, 10, 350]
