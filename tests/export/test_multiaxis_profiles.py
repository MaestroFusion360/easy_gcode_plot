"""Multiaxis EXPANDED post profiles, indexed geometry and TCP reconstruction."""

from __future__ import annotations

import re

import pytest
from export_signatures import motion_traces_match

from app.gcode.export.common import ExportLimitation, ExportOptions
from app.gcode.export.expanded import convert_resolved_program, load_post_profile
from app.gcode.export_file import ExportRequest, export_file
from app.gcode.kernel import execute

MULTIAXIS_TARGETS = ("fanuc_mill_multiaxis", "sinumerik_840d_multiaxis")
THREE_AXIS_TARGETS = ("fanuc_mill", "sinumerik_840d")

ROTARY_PROGRAMS = (
    ("G90 G0 X0 Y0 Z0\nA30\nG1 X10 Y0 Z0 F100\nM30", "4ax_table_a", "A"),
    ("G90 G0 X0 Y0 Z0\nB30\nG1 X10 Y0 Z0 F100\nM30", "4ax_table_b", "B"),
    ("G90 G0 X0 Y0 Z0\nC30\nG1 X10 Y0 Z0 F100\nM30", "4ax_table_c", "C"),
    ("G90 G0 X0 Y0 Z0\nA30 C45\nG1 X10 Y20 Z30 F100\nM30", "5ax_table_ac_angled", "A"),
    ("G90 G0 X0 Y0 Z0\nB30 C45\nG1 X10 Y20 Z30 F100\nM30", "5ax_table_bc_angled", "B"),
)


@pytest.mark.parametrize("target", MULTIAXIS_TARGETS)
def test_multiaxis_profile_declares_all_rotary_axes(target):
    profile = load_post_profile(target)
    assert {"X", "Y", "Z", "A", "B", "C"} <= set(profile["supports"]["axes"])
    words = profile["format"]["words"]
    assert {"A", "B", "C"} <= set(words)
    assert all(words[axis]["required"] is False for axis in "ABC")
    assert profile["supports"]["tcp"] is True
    assert set(profile["multiaxis"]) == {"tcpOn", "tcpOff"}


@pytest.mark.parametrize("target", MULTIAXIS_TARGETS)
def test_three_axis_program_exports_through_multiaxis_profile(target):
    result = execute("G21 G17 G90\nG0 X0 Y0 Z5\nG1 X10 Y0 Z0 F100\nM30", language="fanuc_mill")
    text = convert_resolved_program(result, target, ExportOptions(delimiter=True))
    assert "G1 X10 Z0 F100" in text
    assert not re.search(r"[ABC][-+]?\d", text)


@pytest.mark.parametrize(("source", "kinematics", "axis"), ROTARY_PROGRAMS)
def test_rotary_program_exports_only_through_multiaxis_profiles(source, kinematics, axis):
    result = execute(source, language="fanuc_mill", kinematics=kinematics)
    assert result.ok and result.complete, result.diagnostics

    for target in MULTIAXIS_TARGETS:
        text = convert_resolved_program(result, target, ExportOptions(delimiter=True))
        assert re.search(rf"(?<![A-Z]){axis}[-+]?\d", text), text
        replay = execute(
            text,
            language="fanuc_mill",
            source_dialect="sinumerik" if target.startswith("sinumerik") else "fanuc",
            kinematics=kinematics,
        )
        assert replay.ok and replay.complete, replay.diagnostics
        _assert_multiaxis_replay_matches(result, replay)

    for target in THREE_AXIS_TARGETS:
        with pytest.raises(ExportLimitation):
            convert_resolved_program(result, target, ExportOptions(delimiter=True))


def _assert_matrix_matches(actual, expected):
    if expected is None:
        assert actual is None
        return
    assert actual is not None
    assert tuple(value for row in actual for value in row) == pytest.approx(
        tuple(value for row in expected for value in row)
    )


def _assert_multiaxis_replay_matches(source, generated):
    assert motion_traces_match(source, generated)
    assert source.rotary_angles == generated.rotary_angles
    assert len(source.motions) == len(generated.motions)
    for expected, actual in zip(source.motions, generated.motions, strict=True):
        _assert_matrix_matches(actual.start_tool_orientation, expected.start_tool_orientation)
        _assert_matrix_matches(actual.tool_orientation, expected.tool_orientation)


@pytest.mark.parametrize(
    ("target", "dialect"),
    [("fanuc_mill_multiaxis", "fanuc"), ("sinumerik_840d_multiaxis", "sinumerik")],
)
def test_table_c_continuous_rotary_replays_through_multiaxis_posts(target, dialect):
    source = "G90 G0 X10 Y0 Z0\nG1 C90 F100\nG91 C-180\nM30"
    original = execute(source, language="fanuc_mill", kinematics="4ax_table_c")
    assert original.ok and original.complete, original.diagnostics

    text = convert_resolved_program(original, target, ExportOptions(delimiter=True))
    replay = execute(
        text,
        language="fanuc_mill",
        source_dialect=dialect,
        kinematics="4ax_table_c",
    )
    assert replay.ok and replay.complete, replay.diagnostics
    _assert_multiaxis_replay_matches(original, replay)


def test_fanuc_tcp_exports_to_sinumerik_multiaxis_and_replays():
    source = """G21 G17 G90 G94
G0 B20 C0
G0 X0 Y0 Z5
G43.4
G1 X10 Y0 Z0 B30 C45 F100
G3 X0 Y10 R10 B40 C90
G1 B45 C100
G49
M30
"""
    original = execute(source, language="fanuc_mill", kinematics="5ax_table_bc_angled")
    assert original.ok and original.complete, original.diagnostics

    text = convert_resolved_program(original, "sinumerik_840d_multiaxis", ExportOptions(delimiter=True))
    assert "TRAORI" in text and "TRAFOOF" in text
    replay = execute(
        text,
        language="fanuc_mill",
        source_dialect="sinumerik",
        kinematics="5ax_table_bc_angled",
    )
    assert replay.ok and replay.complete, replay.diagnostics
    _assert_multiaxis_replay_matches(original, replay)


def test_shared_export_service_allows_tcp_for_multiaxis_target(tmp_path):
    source = tmp_path / "five_axis.nc"
    source.write_text(
        "G21 G17 G90\nG0 B20 C0\nG0 X0 Y0 Z5\nG43.4\nG1 X10 Y0 Z0 B30 C45 F100\nG49\nM30\n",
        encoding="utf-8",
    )
    output = tmp_path / "five_axis.mpf"
    exported = export_file(
        source,
        output,
        ExportRequest(
            language="fanuc_mill",
            kinematics="5ax_table_bc_angled",
            target_dialect="sinumerik_840d_multiaxis",
        ),
    )
    assert exported.execution.ok and exported.execution.complete, exported.execution.diagnostics
    assert output.exists() and "TRAORI" in output.read_text(encoding="utf-8")


def test_sinumerik_tcp_exports_to_fanuc_multiaxis_and_replays():
    source = """G710 G17 G90 G94
G0 A=20 C=0
G0 X0 Y0 Z5
TRAORI
G1 X10 Y0 Z0 A=30 C=45 F100
G3 X0 Y10 CR=10 A=40 C=90
G1 A=45 C=100
TRAFOOF
M30
"""
    original = execute(
        source,
        language="fanuc_mill",
        source_dialect="sinumerik",
        kinematics="5ax_table_ac_angled",
    )
    assert original.ok and original.complete, original.diagnostics

    text = convert_resolved_program(original, "fanuc_mill_multiaxis", ExportOptions(delimiter=True))
    assert "G43.4" in text and "G49" in text
    replay = execute(text, language="fanuc_mill", kinematics="5ax_table_ac_angled")
    assert replay.ok and replay.complete, replay.diagnostics
    _assert_multiaxis_replay_matches(original, replay)


def test_indexed_rotary_is_emitted_as_a_separate_frame_and_replays():
    source = "G21 G17 G90\nG0 X0 Y0 Z5\nB90\nG0 X10 Y0 Z5\nG1 Z0 F100\nM30"
    original = execute(source, language="fanuc_mill", kinematics="4ax_table_b")
    assert original.ok and original.complete, original.diagnostics

    text = convert_resolved_program(original, "fanuc_mill_multiaxis", ExportOptions(delimiter=True))
    assert "G0 B90" in text
    assert not re.search(r"G[01][^\n]*X[^\n]*B90", text)
    replay = execute(text, language="fanuc_mill", kinematics="4ax_table_b")
    assert replay.ok and replay.complete, replay.diagnostics
    _assert_multiaxis_replay_matches(original, replay)


@pytest.mark.parametrize(
    ("fixture", "kinematics"),
    (("impeller.ptp", "5ax_table_bc_angled"), ("impeller2.ptp", "5ax_table_ac_angled")),
)
def test_full_fanuc_five_axis_fixture_exports_to_sinumerik_multiaxis(fixture_text, fixture, kinematics):
    original = execute(
        fixture_text(f"milling/fanuc/{fixture}"),
        language="fanuc_mill",
        kinematics=kinematics,
        home_z=500.0,
    )
    assert original.ok and original.complete, original.diagnostics

    text = convert_resolved_program(original, "sinumerik_840d_multiaxis", ExportOptions(delimiter=True))
    replay = execute(
        text,
        language="fanuc_mill",
        source_dialect="sinumerik",
        kinematics=kinematics,
        home_z=500.0,
    )
    assert replay.ok and replay.complete, replay.diagnostics
    _assert_multiaxis_replay_matches(original, replay)


@pytest.mark.parametrize("target", MULTIAXIS_TARGETS)
def test_multiaxis_profile_replays_tilted_plane_with_nonzero_origin(target):
    source = "G90 G0 X0 Y0 Z0\nG68.2 X0 Y0 Z-50 I0 J90 K0\nG53.1\nG0 X10 Y20 Z-5\nG69\nM30"
    result = execute(source, language="fanuc_mill", kinematics="5ax_table_ac_angled")
    assert result.ok and result.complete, result.diagnostics
    text = convert_resolved_program(result, target, ExportOptions(delimiter=True))
    replay = execute(
        text,
        language="fanuc_mill",
        source_dialect="sinumerik" if target.startswith("sinumerik") else "fanuc",
        kinematics="5ax_table_ac_angled",
    )
    assert replay.ok and replay.complete, replay.diagnostics
    _assert_multiaxis_replay_matches(result, replay)


def test_length_compensation_before_and_after_tcp_and_tool_changes():
    source = """G710 G17 G90 G94
T1 M6
D1
G0 X10 Y0 Z50
G1 Z10 F100
D0
SUPA G0 Z-200
D1
G0 X20 Y0 Z50
T2 M6
D1
TRAORI
G0 X0 Y0 Z50 A0 C0
G1 Z10 F100
TRAFOOF
D0
SUPA G0 Z-200
D1
G0 X20 Y0 Z50
T3 M6
D1
G0 X30 Y0 Z50
G1 Z10 F100
D0
SUPA G0 Z-200
D1
G0 X40 Y0 Z50
D0
SUPA G0 Z-200
M30"""
    original = execute(source, language="fanuc_mill", source_dialect="sinumerik", kinematics="5ax_table_ac")
    assert original.ok and original.complete, original.diagnostics
    text = convert_resolved_program(original, "fanuc_mill_multiaxis", ExportOptions(delimiter=True))
    lines = text.splitlines()
    offset = None
    tool = None
    tcp = False
    approaches = []
    for line in lines:
        if line.startswith("T") and "M06" in line:
            tool = int(line.split()[0][1:])
        if line == "G49":
            offset, tcp = None, False
        elif line.startswith("G43.4 H"):
            offset, tcp = int(line.split("H")[1]), True
        elif line.startswith("G43 H"):
            offset, tcp = int(line.split("H")[1]), False
        if line.startswith(("G0 ", "G1 ")) and "Z" in line and "G53" not in line:
            assert offset == tool, (line, offset, tool, text)
            approaches.append((tool, tcp))
    assert {(1, False), (2, True), (2, False), (3, False)} <= set(approaches)
    assert lines.count("G43 H1") >= 2
    assert lines.count("G43 H2") >= 2
    assert lines.count("G43 H3") >= 2
    replay = execute(text, language="fanuc_mill", kinematics="5ax_table_ac")
    assert replay.ok and replay.complete, replay.diagnostics
    _assert_multiaxis_replay_matches(original, replay)


def test_g43_cancelling_tcp_keeps_selected_ordinary_length_offset():
    source = "T2 M6\nG43 H2\nG0 X0 Y0 Z50\nG43.4 H2\nG1 Z10 F100\nG43 H7\nG0 Z50\nM30"
    original = execute(source, language="fanuc_mill", kinematics="5ax_table_ac")
    assert original.ok and original.complete, original.diagnostics
    text = convert_resolved_program(original, "fanuc_mill_multiaxis", ExportOptions(delimiter=True))
    tail = text.split("G43 H7\n", 1)[1]
    assert "G49" not in tail.split("G0", 1)[0], text
    replay = execute(text, language="fanuc_mill", kinematics="5ax_table_ac")
    assert replay.ok and replay.complete, replay.diagnostics
    _assert_multiaxis_replay_matches(original, replay)
