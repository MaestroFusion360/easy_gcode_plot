"""Native TCP declarations share FANUC's existing geometry and cancellation core."""

from dataclasses import replace

import pytest

from app.cli import main
from app.gcode.batch import analyze_directory
from app.gcode.export_file import ExportRequest, export_file
from app.gcode.kernel import execute
from app.gcode.trace_tools import motion_length, render_trace, sample_motion, trace_statistics
from app.ui.plot.playback import build_playback_movements
from app.ui.plot.toolpath_vbo import segments_from_render_points


def native(source, **options):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik", **options)


@pytest.mark.parametrize("profile,axis", [("5ax_table_ac_angled", "A"), ("5ax_table_bc_angled", "B")])
def test_native_tcp_matches_fanuc_geometry_orientation_and_rebasing(profile, axis):
    fanuc = f"""G21 G17 G90 G94
G0 {axis}20 C0
G0 X10 Y0 Z5
G43.4
G1 X10 Y0 Z0 {axis}30 C45 F100
G3 X0 Y10 R10 {axis}40 C90
G1 {axis}45 C100
G49
G0 X1 Y2 Z3
M30
"""
    siemens = f"""G710 G17 G90 G94
G0 {axis}=20 C=0
G0 X10 Y0 Z5
TRAORI
G1 X10 Y0 Z0 {axis}=30 C=45 F100
G3 X0 Y10 CR=10 {axis}=40 C=90
G1 {axis}=45 C=100
TRAFOOF
G0 X1 Y2 Z3
M30
"""
    a = execute(fanuc, language="fanuc_mill", kinematics=profile)
    b = native(siemens, kinematics=profile)
    assert a.ok and a.complete and b.ok and b.complete, (a.diagnostics, b.diagnostics)
    assert len(a.motions) == len(b.motions) == 5
    for first, second in zip(a.motions, b.motions, strict=True):
        assert (first.start_x, first.start_y, first.start_z) == pytest.approx(
            (second.start_x, second.start_y, second.start_z)
        )
        assert (first.end_x, first.end_y, first.end_z) == pytest.approx((second.end_x, second.end_y, second.end_z))
        assert first.tool_orientation == second.tool_orientation
        assert first.start_tool_orientation == second.start_tool_orientation
        assert first.orientation == second.orientation
        assert first.arc == second.arc
    assert a.rotary_angles == b.rotary_angles
    assert a.signals == b.signals
    assert b.source_dialect == "sinumerik"
    assert [e.kind for e in b.events if e.kind.startswith("TCP_")] == ["TCP_CONTROL_ON", "TCP_CONTROL_OFF"]
    # Activation/cancellation are standalone semantic steps, not XYZ moves.
    assert all(m.source_block not in {3, 7} for m in b.motions)
    assert b.motions[2].start_tool_orientation != b.motions[2].tool_orientation
    assert b.motions[3].start_x == b.motions[3].end_x  # pure rotary, fixed TCP


def test_tcp_rotary_arc_preserves_analytic_sampling_render_playback_and_statistics():
    result = native(
        "G710 G17 G90\nG0 X10 Y0\nTRAORI\nG3 X0 Y10 CR=10 A=30 C=90 F100\nTRAFOOF\nM30",
        kinematics="5ax_table_ac_angled",
    )
    assert result.ok and result.complete, result.diagnostics
    arc = result.motions[-1]
    assert arc.arc.radius == pytest.approx(10)
    assert arc.arc.sweep == pytest.approx(1.5707963267948966)
    assert motion_length(arc) == pytest.approx(15.707963267948966)
    assert (sample_motion(arc, 1)[-1].x, sample_motion(arc, 1)[-1].y) == (0, 10)
    points = render_trace(result)
    segments = segments_from_render_points(points, result.motions)
    assert len(segments) > 3
    assert segments[-1].logical_index == 1
    movements, mapping = build_playback_movements(result.motions)
    assert len(movements) == 2 and mapping == (0, 1)
    assert trace_statistics(result)["arc_count"] == 1


@pytest.mark.parametrize(
    "profile,source,code",
    [
        (None, "TRAORI", "TCP_KINEMATICS_REQUIRED"),
        ("4ax_table_a", "TRAORI", "TCP_KINEMATICS_REQUIRED"),
        (None, "G0 A=10", "ROTARY_KINEMATICS_REQUIRED"),
        ("5ax_table_ac_angled", "TRAORI\nG1 B=30 F100", "UNCONFIGURED_ROTARY_AXIS"),
        ("5ax_table_ac_angled", "TRAORI\nG291", "UNSUPPORTED_SINUMERIK_MODE"),
        ("5ax_table_ac_angled", "TRAORI\nG290", "UNSUPPORTED_SINUMERIK_MODE"),
        ("5ax_table_ac_angled", "TRAOOF", "UNSUPPORTED_SINUMERIK_MODE"),
        ("5ax_table_ac_angled", "TRAORI X1", "UNSUPPORTED_SINUMERIK_MODE"),
    ],
)
def test_unverified_native_modes_fail_closed(profile, source, code):
    result = native(source, kinematics=profile)
    assert not result.ok and not result.complete
    assert result.diagnostics[-1].code == code
    assert not result.motions
    assert dict(result.rotary_angles) == {"A": 0, "B": 0, "C": 0}


@pytest.mark.parametrize(
    ("source", "dialect"),
    [
        ("G17 G90 G49\nG0 X1 Y2 Z3\nM30", "fanuc"),
        ("G710 G90\nG0 SUPA Z0 D0\nM30", "sinumerik"),
        ("G710 G90\nTRAFOOF\nG0 X1 Y2 Z3\nM30", "sinumerik"),
    ],
)
def test_inactive_tcp_cancellation_does_not_create_control_events(source, dialect):
    result = execute(
        source,
        language="fanuc_mill",
        source_dialect=dialect,
        kinematics="5ax_table_ac_angled",
        home_z=100.0,
    )
    assert result.ok and result.complete, result.diagnostics
    assert not [event for event in result.events if event.kind.startswith("TCP_CONTROL_")]


def test_tcp_events_record_state_edges_only():
    fanuc = execute(
        "G90 G43.4\nG43.4\nG49\nG49\nM30",
        language="fanuc_mill",
        kinematics="5ax_table_ac_angled",
    )
    native_result = native(
        "G710 G90\nTRAORI\nTRAORI\nTRAFOOF\nTRAFOOF\nM30",
        kinematics="5ax_table_ac_angled",
    )
    for result in (fanuc, native_result):
        assert result.ok and result.complete, result.diagnostics
        assert [event.kind for event in result.events if event.kind.startswith("TCP_CONTROL_")] == [
            "TCP_CONTROL_ON",
            "TCP_CONTROL_OFF",
        ]


def test_rotary_parameter_reference_and_incremental_mode():
    result = native(
        "R11=15\nTRAORI\nG90 G1 X1 A=R11 C=30 F100\nG91 X1 A=5 C=10\nTRAFOOF\nM30", kinematics="5ax_table_ac_angled"
    )
    assert result.ok, result.diagnostics
    assert result.motions[-1].end_x == 2
    assert dict(result.rotary_angles) == {"A": 20, "B": 0, "C": 40}


def test_native_tcp_reaches_cli_batch_and_export_stays_closed(tmp_path):
    source = tmp_path / "part.mpf"
    source.write_text("TRAORI\nG1 X10 A=30 C=90 F100\nTRAFOOF\nM30", encoding="utf-8")
    args = [str(source), "--lang", "fanuc_mill", "--kinematics", "5ax_table_ac_angled"]
    assert main(["trace", *args, "-o", str(tmp_path / "trace.json")]) == 0
    assert main(["analyze", *args]) == 0
    report = analyze_directory(
        tmp_path, language="fanuc_mill", encoding="utf-8", extensions=(".mpf",), kinematics="5ax_table_ac_angled"
    )
    assert report["status"] == "CLEAN"
    request = ExportRequest(language="fanuc_mill", kinematics="5ax_table_ac_angled")
    for mode in ("expanded", "full"):
        output = tmp_path / f"{mode}.nc"
        if mode == "full":
            exported = export_file(source, output, replace(request, mode=mode))
            assert exported.execution.ok and "TRAORI" in output.read_text()
            continue
        try:
            exported = export_file(source, output, replace(request, mode=mode))
        except ValueError:
            pass
        else:
            assert not exported.execution.ok
        assert not output.exists()


def test_native_compact_fixture_and_cut3dc_negative_fixture(fixture_text):
    result = native(fixture_text("milling/sinumerik/sinumerik_traori_ac.mpf"), kinematics="5ax_table_ac_angled")
    assert result.ok and result.complete, result.diagnostics
    assert any(m.arc is not None for m in result.motions)
    failed = native(
        fixture_text("milling/sinumerik/sinumerik_cut3dc_unsupported.mpf"), kinematics="5ax_table_ac_angled"
    )
    assert failed.ok and failed.complete
    assert failed.motions
    assert any(d.raw == "CUT3DC" and d.severity == "warning" for d in failed.diagnostics)


@pytest.mark.parametrize(
    "source,code",
    [
        ("TRAORI\nMCALL CYCLE81(5,0,1,-3,)", "UNSUPPORTED_TCP_CYCLE"),
        ("MCALL CYCLE81(5,0,1,-3,)\nTRAORI", "UNSUPPORTED_TCP_COMPOSITION"),
        ("MCALL CYCLE81(5,0,1,-3,)\nG0 A=20", "UNSUPPORTED_SINUMERIK_CYCLE"),
        ("TRAORI\nG41 G1 X10 D1 F100", "UNSUPPORTED_TCP_CUTTER_COMPENSATION"),
    ],
)
def test_native_tcp_and_cycle_compensation_combinations_reject_before_motion(source, code):
    result = native(source, kinematics="5ax_table_ac_angled")
    assert not result.ok and not result.complete
    assert result.diagnostics[-1].code == code
    assert not result.motions
    assert dict(result.rotary_angles) == {"A": 0, "B": 0, "C": 0}
