"""The user's complete indexed AC programs, including multi-turn helical arcs."""

import math
from dataclasses import replace
from pathlib import Path

import pytest

from app.gcode.export.common import ExportLimitation, ExportOptions
from app.gcode.export.expanded import convert_resolved_program
from app.gcode.export.tool_numbers import target_tool_numbers
from app.gcode.export_file import ExportRequest, write_export
from app.gcode.kernel import execute
from app.gcode.kernel.geometry.spatial_arc import axial_travel, point_at
from app.gcode.post_profiles import load_post_profile
from app.gcode.program_execution import execute_program
from app.tools.definitions import DEFAULT_MILLING_TOOL

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/milling"
TOOL_NUMBERS = {"UGT0201_085": 4, "UGT0301_495": 8, "UGT0201_088": 3, "UGT0201_096": 5}
TOLERANCE = 0.000002


def _source(dialect):
    filename = "smpl_sim08_5ax_sinumerik_mm.mpf" if dialect == "sinumerik" else "smpl_sim08_5ax_fanuc_mm.nc"
    return (FIXTURES / dialect / filename).read_text(encoding="utf-8").replace("_Z_HOME=-10", "_Z_HOME=-200")


def _geometry(dialect):
    keys = list(TOOL_NUMBERS) if dialect == "sinumerik" else [f"T{value}" for value in TOOL_NUMBERS.values()]
    return {
        key: {**DEFAULT_MILLING_TOOL, "type": kind, "diameter": diameter, "cornerRadius": radius}
        for key, kind, diameter, radius in zip(
            keys, ["mill_flat", "drill", "mill_bull", "mill_flat"], [8, 10, 10, 1.5], [0, 0, 2, 0], strict=True
        )
    }


def _start(motion):
    return motion.start_x, motion.start_y, motion.start_z


def _end(motion):
    return motion.end_x, motion.end_y, motion.end_z


def _nonempty(motions):
    # Reparameterization can create sub-nanometre no-op rapids. Retain full circles.
    return [motion for motion in motions if motion.arc or math.dist(_start(motion), _end(motion)) >= 1e-8]


def _expected_motions(result, split_turns):
    expected = []
    for motion in _nonempty(result.motions):
        arc = motion.arc
        count = math.ceil(arc.sweep / math.pi) if split_turns and arc and arc.sweep > math.tau + 1e-10 else 1
        previous = _start(motion)
        for index in range(1, count + 1):
            end = _end(motion) if index == count else point_at(motion, arc.sweep * index / count)
            segment_arc = arc
            if arc and count > 1:
                travel = axial_travel(motion) * (index - 1) / count
                segment_arc = replace(
                    arc,
                    center=tuple(arc.center[i] + arc.normal[i] * travel for i in range(3)),
                    sweep=arc.sweep / count,
                    full_circle=False,
                )
            expected.append(
                replace(
                    motion,
                    start_x=previous[0],
                    start_y=previous[1],
                    start_z=previous[2],
                    end_x=end[0],
                    end_y=end[1],
                    end_z=end[2],
                    arc=segment_arc,
                )
            )
            previous = end
    return expected


def _compare(source, target, *, named_to_numeric):
    expected = _expected_motions(source, split_turns=named_to_numeric)
    actual = _nonempty(target.motions)
    assert len(expected) == len(actual)
    errors = []
    for a, b in zip(expected, actual, strict=True):
        error = max(math.dist(_start(a), _start(b)), math.dist(_end(a), _end(b)))
        assert error <= TOLERANCE, (a.source_raw, b.source_raw, error)
        errors.append(error)
        assert a.move == b.move
        assert a.feed == pytest.approx(b.feed)
        assert a.feed_mode == b.feed_mode
        assert a.spindle_rpm == b.spindle_rpm
        tool = f"T{TOOL_NUMBERS[a.tool]}" if named_to_numeric and a.tool else a.tool
        assert tool == b.tool
        assert (a.arc is None) == (b.arc is None)
        if a.arc:
            assert a.arc.center == pytest.approx(b.arc.center, abs=TOLERANCE)
            assert a.arc.radius == pytest.approx(b.arc.radius, abs=TOLERANCE)
            assert a.arc.sweep == pytest.approx(b.arc.sweep, abs=1e-5)
        if a.tool_orientation:
            assert [row[2] for row in a.tool_orientation] == pytest.approx(
                [row[2] for row in b.tool_orientation], abs=1e-7
            )
    return max(errors)


@pytest.mark.parametrize("profile", ["5ax_table_ac", "5ax_table_ac_angled"])
@pytest.mark.parametrize("offset", [(0.0, 0.0, 0.0), (1.294, 0.0, 95.17)])
def test_real_sinumerik_to_fanuc(profile, offset):
    source = _source("sinumerik")
    offsets = {55: offset}
    original, _tools, _inferred = execute_program(
        source,
        language="fanuc_mill",
        source_dialect="sinumerik",
        kinematics=profile,
        correction_enabled=False,
        current_tools=_geometry("sinumerik"),
        home_z=-200,
        wcs_offsets=offsets,
    )
    assert original.ok and original.complete, original.diagnostics
    assert not original.diagnostics
    artifact = ROOT / "tmp/sim08_conversion" / f"{profile}_{int(bool(offset[2]))}_correction_off.nc"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    exported = write_export(
        original,
        source,
        artifact,
        ExportRequest(language="fanuc_mill", target_dialect="fanuc_mill_multiaxis", tool_numbers=TOOL_NUMBERS),
    )
    assert exported.execution.ok, exported.execution.diagnostics
    text = artifact.read_text(encoding="utf-8")
    replay = execute(
        text, language="fanuc_mill", kinematics=profile, home_z=-200, wcs_offsets=offsets, autodetect_arc_type=True
    )
    assert replay.ok and replay.complete, replay.diagnostics
    assert not replay.diagnostics
    _compare(original, replay, named_to_numeric=True)
    assert "G53 G0 Z-200" in text
    assert "G55" in text
    assert text.count("G68.2 ") == 4
    assert text.count("G53.1") == 4
    assert "TURN=" not in text
    assert "G41" not in text  # The resolved path is emitted with G40.
    for name, number in TOOL_NUMBERS.items():
        assert f"T{number} = {name}" in text
        assert f"G43 H{number}" in text


def test_real_fanuc_to_sinumerik():
    source = _source("fanuc")
    original, _tools, _inferred = execute_program(
        source,
        language="fanuc_mill",
        kinematics="5ax_table_ac",
        correction_enabled=False,
        home_z=0,
    )
    assert original.ok and original.complete, original.diagnostics
    text = convert_resolved_program(original, "sinumerik_840d_multiaxis", ExportOptions(delimiter=True))
    replay = execute(text, language="fanuc_mill", source_dialect="sinumerik", kinematics="5ax_table_ac", home_z=0)
    assert replay.ok and replay.complete, replay.diagnostics
    _compare(original, replay, named_to_numeric=False)


def test_partial_named_tool_mapping_reserves_explicit_slots():
    result = execute('T="FIRST" M6\nT="SECOND" M6\nT3 M6\nM30', language="fanuc_mill", source_dialect="sinumerik")
    profile = load_post_profile("fanuc_mill_multiaxis")
    assert target_tool_numbers(result, profile, {"SECOND": 1}) == {"FIRST": "T2", "SECOND": "T1"}
    with pytest.raises(ExportLimitation, match="distinct available"):
        target_tool_numbers(result, profile, {"FIRST": 3})
    with pytest.raises(ExportLimitation, match="distinct available"):
        target_tool_numbers(result, profile, {"FIRST": 4, "SECOND": 4})
