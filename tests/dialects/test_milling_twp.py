"""FANUC milling tilted working plane regression checks."""

from pathlib import Path

import numpy as np
import pytest

from app.gcode.export import export_program
from app.gcode.export.common import EXPANDED_EXECUTION_MODE, MILL_FULL_PROGRAM_MODE, ExportOptions
from app.gcode.export.dxf import build_dxf_document
from app.gcode.export.full import format_full_program_source
from app.gcode.kernel.api.engine import execute
from app.gcode.kernel.milling.kinematics import (
    effective_orientation,
    load_catalog,
    parse_catalog,
    point_orientation,
    transform_vector,
)
from app.gcode.kernel.milling.twp import euler_zxz
from app.gcode.trace_tools import render_trace
from app.ui.plot.toolpath_vbo import segments_from_render_points

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "milling" / "fanuc" / "g68_2_cube.nc"


def _mill(source: str, profile: str = "5ax_table_ac_angled"):
    return execute(source, language="fanuc_mill", kinematics=profile, home_z=500)


@pytest.mark.parametrize("profile", ["5ax_table_ac_angled", "5ax_table_bc_angled"])
def test_cube_golden_faces_and_vertical_arcs(profile):
    result = _mill(FIXTURE.read_text(), profile)
    assert result.ok and result.complete, result.diagnostics
    on = [event for event in result.events if event.kind == "TILTED_WORK_PLANE_ON"]
    orient = [event for event in result.events if event.kind == "TOOL_AXIS_ORIENT"]
    off = [event for event in result.events if event.kind == "TILTED_WORK_PLANE_OFF"]
    assert len(on) == len(orient) == len(off) == 4
    assert [event.twp_angles for event in on] == [
        (0.0, 90.0, 0.0),
        (90.0, 90.0, 0.0),
        (180.0, 90.0, 0.0),
        (-90.0, 90.0, 0.0),
    ]
    machine = load_catalog()[profile]
    for event in orient:
        assert event.kinematics_profile == profile
        assert event.new_abc is not None and event.old_abc is not None
        rotary = dict(zip(("A", "B", "C"), event.new_abc, strict=True))
        actual_axis = transform_vector(effective_orientation(machine, rotary), (0, 0, 1))
        expected_axis = tuple(row[2] for row in event.twp_orientation)
        assert actual_axis == pytest.approx(expected_axis, abs=1e-5)
    plunges = [motion for motion in result.motions if "G94 G01 Z-5." in motion.source_raw]
    assert len(plunges) == 4
    for motion, expected in zip(plunges, ((25, 5, -35), (45, 25, -35), (25, 45, -25), (5, 25, -15)), strict=True):
        assert (motion.end_x, motion.end_y, motion.end_z) == pytest.approx(expected)
        assert motion.tool_orientation is not None
        assert tuple(row[2] for row in motion.tool_orientation) == pytest.approx(
            tuple(row[2] for row in motion.orientation), abs=1e-5
        )
    arcs = [motion for motion in result.motions if motion.arc is not None]
    assert len(arcs) == 4
    assert abs(arcs[0].arc.normal[0]) == pytest.approx(1)
    assert abs(arcs[1].arc.normal[1]) == pytest.approx(1)
    document = build_dxf_document(result)
    assert sum(entity.dxftype() == "ARC" for entity in document.modelspace()) == 4


def test_twp_cancel_and_machine_reference_bypass():
    source = "G90 G0 X0 Y0 Z0\nG68.2 X0 Y0 Z-50 I0 J90 K0\nG53.1\nG0 X10 Y20 Z-5\nG53 G0 X0\nG69\nG0 X1 Y2 Z3\nM30"
    result = _mill(source)
    assert result.ok, result.diagnostics
    first, machine, after = result.motions[-3:]
    assert (first.end_x, first.end_y, first.end_z) == pytest.approx((10, 5, -30))
    assert machine.source_kind == "g53"
    orientation = np.asarray(point_orientation(load_catalog()["5ax_table_ac_angled"], dict(result.rotary_angles)))
    raw = orientation.T @ np.array((first.end_x, first.end_y, first.end_z))
    raw[0] = 0
    expected = orientation @ raw
    assert (machine.end_x, machine.end_y, machine.end_z) == pytest.approx(expected)
    assert (after.start_x, after.start_y, after.start_z) == pytest.approx(expected)
    profile = load_catalog()["5ax_table_ac_angled"]
    last_angles = dict(result.rotary_angles)
    assert (after.end_x, after.end_y, after.end_z) == pytest.approx(
        transform_vector(effective_orientation(profile, last_angles), (1, 2, 3))
    )


@pytest.mark.parametrize(
    "source,code",
    [
        ("G53.1\nM30", "G53_1_REQUIRES_G68_2"),
        ("G68.2 X0 Y0 Z0 I0 J90 K0\nG0 X1\nG53.1", "G53_1_REQUIRES_G68_2"),
        ("G68.2 X0 Y0 Z0 I0 J90 K0\nG53.1 X1", "G53_1_MUST_BE_STANDALONE"),
        ("G68.2 X0 Y0 Z0 I0 J90 K0 A90", "UNSUPPORTED_TWP_EXPLICIT_ROTARY"),
        ("G68 X0 Y0 R30\nG68.2 X0 Y0 Z0 I0 J90 K0", "UNSUPPORTED_TWP_COMPOSITION"),
    ],
)
def test_invalid_twp_sequences_stop(source, code):
    result = _mill(source)
    assert not result.ok and not result.complete
    assert any(diagnostic.code == code for diagnostic in result.diagnostics)


@pytest.mark.parametrize("profile", [None, "4ax_table_a"])
def test_twp_requires_supported_kinematics(profile):
    result = execute("G68.2 X0 Y0 Z0 I0 J90 K0\nG53.1", language="fanuc_mill", kinematics=profile)
    assert not result.ok and not result.complete
    assert any(diagnostic.code == "TWP_KINEMATICS_REQUIRED" for diagnostic in result.diagnostics)


@pytest.mark.parametrize(
    ("profile_id", "angles", "expected_axis"),
    [
        ("5ax_table_ab", "I0 J90 K0", (0, -1, 0)),
        ("5ax_head_ac_angled", "I90 J90 K0", (1, 0, 0)),
        ("5ax_table_a_head_b", "I0 J90 K0", (0, -1, 0)),
    ],
)
def test_twp_accepts_two_axis_table_head_topologies(profile_id, angles, expected_axis):
    profile = load_catalog()[profile_id]
    document = {
        "schema_version": 1,
        "profiles": [
            {
                "id": profile.id,
                "name": profile.name,
                "table": [{"address": axis.address, "axis": list(axis.axis)} for axis in profile.table_rotary_axes],
                "head": [{"address": axis.address, "axis": list(axis.axis)} for axis in profile.head_rotary_axes],
                "enabled": True,
            }
        ],
    }
    custom = parse_catalog(document)[profile_id]
    result = execute(f"G68.2 X0 Y0 Z0 {angles}\nG53.1", language="fanuc_mill", kinematics=custom)
    assert result.ok, result.diagnostics
    solved = dict(result.rotary_angles)
    actual_axis = transform_vector(effective_orientation(custom, solved), (0, 0, 1))
    assert actual_axis == pytest.approx(expected_axis, abs=1e-5)


@pytest.mark.parametrize("profile", ["5ax_table_ac_angled", "5ax_table_bc_angled"])
def test_twp_rejects_unreachable_tool_axis(profile):
    result = _mill("G68.2 X0 Y0 Z0 I0 J180 K0\nG53.1", profile)
    assert not result.ok and not result.complete
    assert any(diagnostic.code == "TWP_ORIENTATION_UNREACHABLE" for diagnostic in result.diagnostics)


def test_euler_zxz_face_axes():
    for angles, expected in [
        ((0, 90, 0), (0, -1, 0)),
        ((90, 90, 0), (1, 0, 0)),
        ((180, 90, 0), (0, 1, 0)),
        ((-90, 90, 0), (-1, 0, 0)),
    ]:
        matrix = euler_zxz(*angles)
        assert tuple(row[2] for row in matrix) == pytest.approx(expected)


def test_twp_nc_export_preserves_source_or_fails_closed(tmp_path):
    source = FIXTURE.read_text()
    result = _mill(source)
    assert export_program(
        result, source, mode=MILL_FULL_PROGRAM_MODE, lathe_mode=False, options=ExportOptions()
    ) == format_full_program_source(source, ExportOptions())
    with pytest.raises(ValueError, match="G68.2"):
        export_program(result, source, mode=EXPANDED_EXECUTION_MODE, lathe_mode=False, options=ExportOptions())


def test_g28_returns_to_machine_home_from_tilted_plane():
    source = "G90 G0 X0 Y0 Z0\nG68.2 X0 Y0 Z-50 I0 J90 K0\nG53.1\nG0 X10 Y20 Z-5\nG91 G28 Z0\nG69\nM30"
    # This tilted setup starts on the negative reference-Z side.
    result = execute(source, language="fanuc_mill", kinematics="5ax_table_ac_angled", home_z=-500)
    assert result.ok, result.diagnostics
    reference = [motion for motion in result.motions if motion.source_kind == "g28"]
    assert reference
    motion = reference[-1]
    orientation = np.asarray(point_orientation(load_catalog()["5ax_table_ac_angled"], dict(result.rotary_angles)))
    raw = orientation.T @ np.array((motion.start_x, motion.start_y, motion.start_z))
    raw[2] = -500
    assert (motion.end_x, motion.end_y, motion.end_z) == pytest.approx(orientation @ raw)


def test_turning_does_not_execute_twp():
    result = execute("G68.2 X0 Y0 Z0 I0 J90 K0\nG53.1\nM30", language="fanuc_turn")
    assert not any(event.kind.startswith("TILTED_WORK_PLANE") for event in result.events)
    assert any(diagnostic.code == "UNSUPPORTED_G_CODE" for diagnostic in result.diagnostics)


@pytest.mark.parametrize("profile", ["5ax_table_ac_angled", "5ax_table_bc_angled"])
def test_cube_xy_approaches_after_g53_1_stay_on_retracted_side(profile):
    source = FIXTURE.read_text()
    result = _mill(source, profile)
    assert result.ok and result.complete, result.diagnostics
    steps = {step.source_block: step for step in result.execution_steps}
    approaches = []
    for index, motion in enumerate(result.motions):
        if motion.move != 0 or not motion.source_raw.strip().startswith("G0"):
            continue
        step = steps[motion.source_block]
        if not step.tool_axis_control or "Z" in motion.source_raw:
            continue
        # First XY approach following each G53.1, before the explicit Z25.
        previous_block = result.motions[index - 1].source_block if index else -1
        if not any(
            block.raw.strip() == "G53.1" for block in result.program.blocks[previous_block + 1 : motion.source_block]
        ):
            continue
        approaches.append((index, motion, step))
    assert len(approaches) == 4
    segments = segments_from_render_points(render_trace(result), result.motions)
    for index, motion, step in approaches:
        normal = np.asarray(step.twp_orientation)[:, 2]
        origin = np.asarray(step.twp_origin)
        start = np.array((motion.start_x, motion.start_y, motion.start_z))
        end = np.array((motion.end_x, motion.end_y, motion.end_z))
        # Clearance is affine along this XY segment. Positive endpoints prove
        # it stays on the retracted side rather than crossing the centre plane.
        assert np.dot(start - origin, normal) > 400
        assert np.dot(end - origin, normal) == pytest.approx(np.dot(start - origin, normal))
        rendered = [segment for segment in segments if segment.logical_index == index]
        assert rendered and rendered[0].start == pytest.approx(start)
        for segment in rendered:
            assert (
                min(np.dot(np.array(segment.start) - origin, normal), np.dot(np.array(segment.end) - origin, normal))
                > 400
            )
