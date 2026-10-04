"""Native units and inverse-time block duration regressions."""

import pytest

from app.gcode.export.options import ExportOptions
from app.gcode.export.resolved import convert_resolved_program
from app.gcode.kernel import execute
from app.gcode.trace_tools import trace_statistics


def native(source):
    return execute(source, language="fanuc_mill", source_dialect="sinumerik")


def test_independent_length_and_feed_units_and_modal_reinterpretation():
    result = native("G70 G1 X1 F2\nG700 X2\nG71 X60\nG710 X70\nM30")
    assert result.ok and result.complete, result.diagnostics
    assert [m.end_x for m in result.motions] == pytest.approx([25.4, 50.8, 60, 70])
    assert [m.feed for m in result.motions] == pytest.approx([2, 50.8, 50.8, 2])


def test_inverse_time_is_modal_and_independent_of_distance_and_units():
    result = native("G93 G1 X10 F2\nX100\nG700 X5 F4\nM30")
    assert result.ok and result.complete, result.diagnostics
    assert [m.feed for m in result.motions] == [2, 2, 4]
    assert result.motions[-1].end_x == 127
    assert trace_statistics(result)["total_time_min"] == pytest.approx(1.25)


@pytest.mark.parametrize("feed", ["", "F0", "F-2"])
def test_inverse_time_requires_positive_feed(feed):
    result = native(f"G93 G1 X10 {feed}\nM30")
    assert not result.ok and not result.motions
    assert any(d.code == "INVALID_G93_FEED" for d in result.diagnostics)


def test_feed_mode_change_cannot_reuse_linear_feed():
    result = native("G94 G1 X10 F100\nG93 X20\nM30")
    assert not result.ok
    assert len(result.motions) == 1


def test_inverse_time_arc_and_switch_back_to_linear_feed():
    result = native("G0 X1\nG93 G3 X0 Y1 CR=1 F2\nG94 G1 X2 F120\nM30")
    assert result.ok and result.complete, result.diagnostics
    assert result.motions[1].arc is not None
    assert result.motions[1].feed_mode == "inverse_time"
    assert result.motions[2].feed_mode == "per_minute"


def test_inverse_time_cycle_is_explicitly_unsupported():
    result = native("G93 F2\nMCALL CYCLE81(10,0,2,-5)\nM30")
    assert not result.ok
    assert any(d.code == "UNSUPPORTED_G93_CYCLE" for d in result.diagnostics)


def test_pure_rotary_inverse_time():
    result = execute(
        "TRAORI\nG93 G1 A=10 F2\nC=90\nM30",
        language="fanuc_mill",
        source_dialect="sinumerik",
        kinematics="5ax_table_ac_angled",
    )
    assert result.ok and result.complete, result.diagnostics
    assert len(result.motions) == 2
    assert trace_statistics(result)["total_time_min"] == 1


@pytest.mark.parametrize(
    "command",
    [
        "G505",
        "G599",
        "G601",
        "G641",
        "G642",
        "G645",
        "ORIWKS",
        "ORIMKS",
        "ORIAXES",
        "ORIVECT",
        "FFWON",
        "FFWOF",
        "UPATH",
        "SOFT",
        "COMPCAD",
        "COMPCURV",
        "ORIRESET",
        "CUT3DC",
        "CUT3DF",
        "CUT3DFF",
        "FL[A]=300",
        "FGREF[C]=50",
        "FGROUP(X,Y,Z,A,C)",
        "SPOS=90",
        "TRANS X10 Y20",
        "AROT Z90",
        "G4 S2",
    ],
)
def test_known_unmodeled_commands_warn_and_continue(command):
    result = native(f"G1 X1 F100\n{command}\nX2\nM30")
    assert result.ok and result.complete, result.diagnostics
    assert [m.end_x for m in result.motions] == [1, 2]
    assert any(d.code == "UNMODELED_SINUMERIK_NATIVE" and d.severity == "warning" for d in result.diagnostics)


@pytest.mark.parametrize("scale", [1.0, 25.4])
def test_inverse_time_native_export_roundtrip(scale):
    result = native("G93 G1 X25.4 F2\nG3 X0 Y25.4 CR=25.4 F4\nM30")
    output = convert_resolved_program(result, "sinumerik_native", ExportOptions(output_unit_scale=scale))
    replay = native(output)
    assert replay.ok and replay.complete, replay.diagnostics
    assert [m.feed for m in replay.motions] == [2, 4]
    assert trace_statistics(replay)["total_time_min"] == pytest.approx(0.75)
    assert replay.motions[-1].end_y == pytest.approx(25.4, abs=0.001)
    with pytest.raises(ValueError, match="G93"):
        convert_resolved_program(result, "fanuc_mill")


def test_warning_geometry_cannot_be_converted_to_verified_nc():
    result = native("TRANS X10\nG1 X1 F100\nM30")
    with pytest.raises(ValueError, match="ignored SINUMERIK"):
        convert_resolved_program(result, "sinumerik_native")
