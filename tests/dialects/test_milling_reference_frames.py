"""Reference retracts stay in the current rotary frame instead of ABC=0."""

from pathlib import Path

import numpy as np
import pytest

from app.gcode.kernel import execute
from app.gcode.kernel.milling.kinematics import load_catalog, point_orientation
from app.gcode.trace_tools import render_trace
from app.ui.plot.toolpath_vbo import segments_from_render_points


@pytest.mark.parametrize("reference", ["G91 G28 Z0", "G53 Z0"])
@pytest.mark.parametrize(
    "angle, expected",
    [
        (0, (0, 0, 500)),
        (90, (500, 0, 0)),
        (180, (0, 0, -500)),
        (270, (-500, 0, 0)),
    ],
)
def test_b_reference_retract_reverses_approach_at_current_angle(reference, angle, expected):
    result = execute(
        f"G90 G0 X0 Y0 Z0\nB{angle}\nG0 Z10\nG1 Z2 F100\n{reference}\nM30",
        language="fanuc_mill",
        kinematics="4ax_table_b",
        home_z=500,
    )
    assert result.ok and result.complete, result.diagnostics
    approach, retract = result.motions[-2:]
    assert (retract.start_x, retract.start_y, retract.start_z) == pytest.approx(
        (approach.end_x, approach.end_y, approach.end_z)
    )
    assert (retract.end_x, retract.end_y, retract.end_z) == pytest.approx(expected, abs=1e-8)
    incoming = np.array(
        (approach.end_x - approach.start_x, approach.end_y - approach.start_y, approach.end_z - approach.start_z)
    )
    outgoing = np.array(
        (retract.end_x - retract.start_x, retract.end_y - retract.start_y, retract.end_z - retract.start_z)
    )
    assert np.dot(incoming, outgoing) < 0
    assert np.cross(incoming, outgoing) == pytest.approx((0, 0, 0), abs=1e-8)
    assert dict(result.rotary_angles)["B"] == angle
    assert retract.start_tool_orientation == retract.tool_orientation


@pytest.mark.parametrize("reference", ["G91 G28 Z0", "G53 Z0"])
@pytest.mark.parametrize(
    "profile, rotary",
    [
        ("5ax_table_ac_angled", "A60 C120"),
        ("5ax_table_ac_angled", "A-60 C-120"),
        ("5ax_table_bc_angled", "B60 C120"),
        ("5ax_table_bc_angled", "B-60 C-120"),
    ],
)
@pytest.mark.parametrize("cancel", ["", "G49\n"])
def test_five_axis_reference_preserves_tcp_tip_abc_and_next_motion(reference, profile, rotary, cancel):
    offset = np.array((40.0, -25.0, 80.0))
    source = f"G90 G0 X0 Y0 Z0\nG43.4 H1\nG1 X10 Y20 Z30 {rotary} F100\n{cancel}{reference}\nG90 G0 X15 Y25 Z50\nM30"
    result = execute(source, language="fanuc_mill", kinematics=profile, home_z=500, wcs_offsets={54: tuple(offset)})
    assert result.ok and result.complete, result.diagnostics
    before, retract, after = result.motions[-3:]
    start = np.array((before.end_x, before.end_y, before.end_z))
    end = np.array((retract.end_x, retract.end_y, retract.end_z))
    orientation = np.asarray(point_orientation(load_catalog()[profile], dict(result.rotary_angles)))
    raw_start = orientation.T @ (start - offset) + offset
    raw_target = np.array((raw_start[0], raw_start[1], 500))
    expected = orientation @ (raw_target - offset) + offset
    assert end == pytest.approx(expected)
    assert (retract.start_x, retract.start_y, retract.start_z) == pytest.approx(start)
    assert (after.start_x, after.start_y, after.start_z) == pytest.approx(end)
    assert end - start == pytest.approx(orientation[:, 2] * (500 - raw_start[2]))
    assert retract.start_tool_orientation == before.tool_orientation == retract.tool_orientation
    assert len([event for event in result.events if event.kind in {"ROTARY_INDEX", "ROTARY_MOTION"}]) == 1


@pytest.mark.parametrize("reference", ["G91 G28 Z0", "G53 Z0"])
def test_none_kinematics_reference_still_returns_to_positive_z(reference):
    result = execute(f"G90 G0 X10 Y20 Z30\n{reference}\nM30", language="fanuc_mill", home_z=500)
    assert result.ok and result.complete
    retract = result.motions[-1]
    assert (retract.end_x, retract.end_y, retract.end_z) == pytest.approx((10, 20, 500))


@pytest.mark.parametrize("profile", ["4ax_table_b", "5ax_table_bc_angled"])
@pytest.mark.parametrize("reference", ["G0G91G28Z0M5", "G0G90G53Z0M5"])
def test_indexed_table_b_fixture_retract_and_next_approach_stay_outside_part(reference, profile):
    source = (Path(__file__).parents[1] / "fixtures/milling/indexed_table_b.nc").read_text()
    source = source.replace("G0G91G28Z0M5", reference)
    result = execute(source, language="fanuc_mill", kinematics=profile, home_z=500)
    assert result.ok and result.complete, result.diagnostics
    steps = {step.source_block: step for step in result.execution_steps}
    motions = result.motions
    returns = [motion for motion in motions if motion.source_kind in {"g28", "g53"}]
    assert len(returns) == source.count(reference) == 41
    for motion in returns:
        step = steps[motion.source_block]
        outward = np.asarray(point_orientation(load_catalog()[profile], dict(step.rotary_angles)))[:, 2]
        start = np.array((motion.start_x, motion.start_y, motion.start_z))
        end = np.array((motion.end_x, motion.end_y, motion.end_z))
        assert min(np.dot(start, outward), np.dot(end, outward)) > 0
        assert np.dot(end - start, outward) > 0
        assert np.dot(end, outward) == pytest.approx(500)
        assert np.cross(end - start, outward) == pytest.approx((0, 0, 0), abs=1e-7)
        assert len([event for event in step.events if event.code in {"G28", "G53"}]) == 1
    # After an index, the next approach starts on that side's rotated home,
    # instead of carrying the previous side's global position through the part.
    for previous, current in zip(motions, motions[1:]):
        previous_b = dict(steps[previous.source_block].rotary_angles)["B"]
        current_b = dict(steps[current.source_block].rotary_angles)["B"]
        if previous_b == current_b or previous.source_kind not in {"g28", "g53"}:
            continue
        outward = np.asarray(
            point_orientation(load_catalog()[profile], dict(steps[current.source_block].rotary_angles))
        )[:, 2]
        start = np.array((current.start_x, current.start_y, current.start_z))
        end = np.array((current.end_x, current.end_y, current.end_z))
        assert current.move == 0
        assert np.dot(start, outward) == pytest.approx(500)
        assert np.dot(end, outward) >= 150 - 1e-7
        # Signed distance is affine along the segment: positive endpoints
        # prove the entire approach stays outside the WCS centre plane.
        assert min(np.dot(start, outward), np.dot(end, outward)) > 0

    # Check the actual independent UI line segments too: no artificial bridge
    # from the old home side to the new side may appear after indexing.
    segments = segments_from_render_points(render_trace(result), motions)
    for segment in segments:
        motion = motions[segment.logical_index]
        if motion.source_kind not in {"g28", "g53"}:
            continue
        outward = np.asarray(
            point_orientation(load_catalog()[profile], dict(steps[motion.source_block].rotary_angles))
        )[:, 2]
        assert min(np.dot(segment.start, outward), np.dot(segment.end, outward)) > 0


@pytest.mark.parametrize("reference", ["G91 G28 Z0", "G53 Z0"])
def test_rotated_reference_crossing_wcs_centre_is_rejected(reference):
    result = execute(
        f"G90 G0 B180\nG0 Z135\n{reference}\nM30", language="fanuc_mill", kinematics="4ax_table_b", home_z=0
    )
    assert not result.ok
    assert any("WCS centre plane" in d.message for d in result.diagnostics)
    assert not any(m.source_kind in {"g28", "g53"} for m in result.motions)
