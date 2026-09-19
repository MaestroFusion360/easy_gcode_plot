from __future__ import annotations

# The historical dxf_exporter alias is intentionally imported beside its external ezdxf dependency.
# pylint: disable=wrong-import-order,ungrouped-imports
from dataclasses import replace

import ezdxf
import pytest
from ezdxf import units

from app.gcode.dxf_exporter import CUT_LAYER, RAPID_LAYER, build_dxf_document, export_dxf
from app.gcode.kernel import execute
from app.gcode.trace_tools import render_trace


def _document(source: str, language: str = "fanuc_mill"):
    result = execute(source, language=language)
    assert result.ok, result.diagnostics
    return result, build_dxf_document(result)


def test_dxf_exports_trace_lines_in_rapid_and_cut_layers():
    _, document = _document("G21 G90\nG0 X1 Y2 Z3\nG1 X4 Y5 Z6 F100\nM30")
    entities = list(document.modelspace())

    assert document.units == units.MM
    assert [entity.dxftype() for entity in entities] == ["LINE", "LINE"]
    assert [entity.dxf.layer for entity in entities] == [RAPID_LAYER, CUT_LAYER]
    assert tuple(entities[0].dxf.end) == pytest.approx((1.0, 2.0, 3.0))
    assert tuple(entities[1].dxf.start) == pytest.approx((1.0, 2.0, 3.0))
    assert tuple(entities[1].dxf.end) == pytest.approx((4.0, 5.0, 6.0))


def test_dxf_units_match_trace_physical_millimetres_for_inch_source():
    _, document = _document("G20 G90\nG1 X1 Y2 Z0.5 F10\nM30")
    line = list(document.modelspace())[0]

    assert document.units == units.MM
    assert tuple(line.dxf.end) == pytest.approx((25.4, 50.8, 12.7))


def test_dxf_preserves_planar_trace_arc_as_arc():
    _, document = _document("G21 G17 G90\nG0 X10 Y0 Z2\nG3 X0 Y10 I-10 J0 F100\nM30")
    arc = list(document.modelspace())[1]

    assert arc.dxftype() == "ARC"
    assert arc.dxf.layer == CUT_LAYER
    assert arc.dxf.radius == pytest.approx(10.0)
    assert tuple(arc.dxf.center) == pytest.approx((0.0, 0.0, 2.0))
    assert tuple(arc.start_point) == pytest.approx((10.0, 0.0, 2.0))
    assert tuple(arc.end_point) == pytest.approx((0.0, 10.0, 2.0))


def test_dxf_preserves_full_circle_as_circle():
    _, document = _document("G21 G17 G90\nG0 X10 Y0\nG2 X10 Y0 I-10 J0 F100\nM30")
    circle = list(document.modelspace())[1]

    assert circle.dxftype() == "CIRCLE"
    assert circle.dxf.layer == CUT_LAYER
    assert tuple(circle.dxf.center) == pytest.approx((0.0, 0.0, 0.0))
    assert circle.dxf.radius == pytest.approx(10.0)


def test_dxf_turning_matches_plot_orientation_with_z_horizontal_and_physical_x_vertical():
    result, document = _document(
        "G21 G18 G90\nG0 X20 Z5\nG1 X40 Z-10 F100\nG2 X40 Z-10 I-10 K0\nM30",
        language="fanuc_turn",
    )
    assert result.motions[0].x_scale == pytest.approx(0.5)
    rapid, feed, circle = list(document.modelspace())

    assert tuple(rapid.dxf.end) == pytest.approx((5.0, 10.0, 0.0))
    assert tuple(feed.dxf.end) == pytest.approx((-10.0, 20.0, 0.0))
    assert circle.dxftype() == "CIRCLE"
    assert tuple(circle.dxf.center) == pytest.approx((-10.0, 10.0, 0.0))
    assert circle.dxf.radius == pytest.approx(10.0)


def test_dxf_turning_arc_endpoints_follow_same_z_x_projection():
    _, document = _document(
        "G21 G18 G190 G90\nG0 X20 Z0\nG3 X40 Z-10 I0 K-10 F100\nM30",
        language="fanuc_turn",
    )
    arc = list(document.modelspace())[1]

    assert arc.dxftype() == "ARC"
    assert tuple(arc.start_point) == pytest.approx((0.0, 10.0, 0.0))
    assert tuple(arc.end_point) == pytest.approx((-10.0, 20.0, 0.0))


def test_dxf_milling_keeps_3d_lines_and_uses_plot_points_for_helix():
    source = "G21 G17 G90\nG0 X10 Y0 Z0\nG3 X10 Y0 Z-2 I-10 J0 F100\nM30"
    result = execute(source, language="fanuc_mill")
    assert result.ok, result.diagnostics
    plotted = render_trace(result, arc_points_per_circle=24)
    document = build_dxf_document(result, render_points=plotted)
    line, helix = list(document.modelspace())

    assert line.dxftype() == "LINE"
    assert tuple(line.dxf.end) == pytest.approx((10.0, 0.0, 0.0))
    assert helix.dxftype() == "POLYLINE"
    assert helix.is_3d_polyline
    vertices = [tuple(vertex.dxf.location) for vertex in helix.vertices]
    assert vertices[0] == pytest.approx((10.0, 0.0, 0.0))
    assert vertices[-1] == pytest.approx((10.0, 0.0, -2.0))
    assert len(vertices) == 25


def test_dxf_write_round_trip_and_incomplete_result_rejection(tmp_path):
    result = execute("G21 G90\nG1 X2 Y3 Z4 F100\nM30", language="fanuc_mill")
    output = tmp_path / "trace.dxf"
    export_dxf(result, output)

    loaded = ezdxf.readfile(output)
    assert loaded.units == units.MM
    assert len(loaded.modelspace()) == 1
    with pytest.raises(ValueError, match="complete"):
        build_dxf_document(replace(result, complete=False))


def test_flange_plate_benchmark_executes_subprograms_compensates_contours_and_exports_dxf(fixture_text):
    source = fixture_text("milling/flange_plate_benchmark.nc")
    result = execute(
        source,
        language="fanuc_mill",
        milling_tools={
            "T2": {"type": "mill_flat", "diameter": 10.0, "length": 50.0},
            "T3": {"type": "mill_flat", "diameter": 10.0, "length": 50.0},
        },
    )

    assert result.ok, result.diagnostics
    assert result.complete
    assert result.program_end == "M30"

    flow_blocks = {
        block.index for block in result.program.blocks if "M98" in block.raw.upper() or "M99" in block.raw.upper()
    }
    flow_steps = [step for step in result.execution_steps if step.source_block in flow_blocks]
    assert flow_steps
    assert all(step.emitted_count == 0 for step in flow_steps)

    drill_blocks = {244, 248, 252, 256, 260, 264}
    drill_locations = {
        (round(motion.start_x, 3), round(motion.start_y, 3))
        for motion in result.motions
        if motion.source_block in drill_blocks
    }
    assert drill_locations == {
        (50.0, 0.0),
        (25.0, 43.301),
        (-25.0, 43.301),
        (-50.0, 0.0),
        (-25.0, -43.301),
        (25.0, -43.301),
    }

    transformed_contour_starts = [
        (motion.start_x, motion.start_y) for motion in result.motions if motion.source_block == 281
    ]
    expected_contour_starts = [
        (-30.0, -20.0),
        (-10.0, -35.0),
        (-15.9807621135, -32.3205080757),
        (-36.0, -24.0),
    ]
    assert len(transformed_contour_starts) == len(expected_contour_starts)
    for actual, expected in zip(transformed_contour_starts, expected_contour_starts):
        assert actual == pytest.approx(expected)

    rotation_blocks = {block.index for block in result.program.blocks if block.raw.strip().startswith(("G68 ", "G69"))}
    rotation_steps = [step for step in result.execution_steps if step.source_block in rotation_blocks]
    assert rotation_steps
    assert all(step.emitted_count == 0 for step in rotation_steps)

    scaling_blocks = {block.index for block in result.program.blocks if block.raw.strip().startswith(("G51 ", "G50"))}
    scaling_steps = [step for step in result.execution_steps if step.source_block in scaling_blocks]
    assert scaling_steps
    assert all(step.emitted_count == 0 for step in scaling_steps)
    transformed_contours = [
        motion for motion in result.motions if motion.source_block is not None and 281 <= motion.source_block <= 288
    ]
    scaled_contour = transformed_contours[-8:]
    assert (scaled_contour[0].start_x, scaled_contour[0].start_y) == pytest.approx((-36.0, -24.0))
    assert (scaled_contour[0].end_x, scaled_contour[0].end_y) == pytest.approx((36.0, -24.0))
    assert [motion.arc.radius for motion in scaled_contour if motion.arc is not None] == pytest.approx(
        [12.0, 12.0, 12.0, 12.0]
    )

    for previous, current in zip(result.motions, result.motions[1:]):
        assert (current.start_x, current.start_y, current.start_z) == pytest.approx(
            (previous.end_x, previous.end_y, previous.end_z)
        )

    outer_compensation = [
        motion
        for motion in result.motions
        if motion.source_block is not None
        and 60 <= motion.source_block <= 69
        and motion.source_kind.startswith("cutter_compensation")
    ]
    assert (outer_compensation[0].end_x, outer_compensation[0].end_y) == pytest.approx((-55.0, -45.0))
    assert [motion.arc.radius for motion in outer_compensation if motion.arc is not None] == pytest.approx(
        [10.0, 10.0, 10.0]
    )
    assert (outer_compensation[-1].start_x, outer_compensation[-1].start_y) == pytest.approx((-55.0, -45.0))
    assert (outer_compensation[-1].end_x, outer_compensation[-1].end_y) == pytest.approx((-85.0, -50.0))

    slot_blocks = {175, 180, 272, 273, 274, 275, 276}
    slot_compensation = [motion for motion in result.motions if motion.source_block in slot_blocks]
    assert all(motion.compensation_applied for motion in slot_compensation if motion.compensation_mode in (41, 42))
    assert (slot_compensation[0].end_x, slot_compensation[0].end_y, slot_compensation[0].end_z) == pytest.approx(
        (-20.0, -1.0, 0.0)
    )
    assert {round(motion.arc.radius, 6) for motion in slot_compensation if motion.arc is not None} == {1.0}
    assert {
        round(value, 6)
        for motion in slot_compensation
        for value in (motion.start_y, motion.end_y)
        if motion.source_block in {273, 274, 275, 276}
    } == {-1.0, 1.0}

    document = build_dxf_document(result, render_points=render_trace(result))
    entities = list(document.modelspace())
    assert entities
    assert any(entity.dxf.layer == CUT_LAYER for entity in entities)
