"""1.9.2 export goldens remain a semantic baseline, not a text contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app.gcode.export as export_pkg
from app.gcode.export.common import ExportOptions
from app.gcode.export.expanded import convert_resolved_program
from app.gcode.kernel import execute
from app.gcode.trace_tools import motion_length, sample_motion

GOLDEN = Path(__file__).with_name("golden") / "phase0_export_192.json"
GOLDEN_TEXT = json.loads(GOLDEN.read_text(encoding="utf-8"))

MILL = "G21 G17 G90\nT2 M6\nS3000 M3\nG0 X10 Y0 Z5\nG1 Z0 F200\nG3 X0 Y10 I-10 J0\nM5 M9\nM30\n"
TURN = "G21 G18 G90\nT0202\nS500 M3\nG0 X20 Z5\nG1 Z0 F100\nG3 X40 Z-10 I0 K-10\nM5 M9\nM30\n"
NATIVE = "G710 G17 G90\nR1=10\nT2 M6\nS500 M3\nG0 X=R1 Y0 Z5\nG1 Z0 F100\nG3 X0 Y10 CR=10\nM5 M9\nM30\n"


def _legacy_cases():
    cases = {}
    for language, source in (("fanuc_mill", MILL), ("fanuc_turn", TURN)):
        for incremental in (False, True):
            for arc_mode in (0, 1, 2, 3):
                replay_options = {"source_arc_type": 2 if arc_mode == 1 and not incremental else 1}
                cases[f"{language}_expanded_{incremental}_{arc_mode}"] = (
                    source,
                    language,
                    "fanuc",
                    {},
                    "fanuc",
                    replay_options,
                )
        cases[language + "_full"] = (source, language, "fanuc", {}, "fanuc", {})
        cases[language + "_plot"] = (source, language, "fanuc", {}, "fanuc", {})

    extras = {
        "incremental_input": "G21 G17 G91\nG0 X10 Z5\nG1 X5 Z-5 F100\nG3 X-5 Y5 I-5 J0\nM30",
        "g18": "G21 G18 G90\nG0 X10 Z0\nG3 X0 Z10 I-10 K0 F100\nM30",
        "g19": "G21 G19 G90\nG0 Y10 Z0\nG3 Y0 Z10 J-10 K0 F100\nM30",
        "cw_circle": "G21 G17\nG0 X10 Y0\nG2 X10 Y0 I-10 J0 F100\nM30",
        "large_r": "G21 G17\nG0 X10 Y0\nG2 X0 Y10 R-10 F100\nM30",
        "inch": "G20 G17\nG0 X1 Z0.5\nG1 X2 Z0 F10\nM30",
        "macro_subprogram": "O1\n#1=5\nG90 G0 X#1\nM98 P2 L2\nM30\nO2\nG91 G1 X#1 F100\nM99",
        "compensation": "G21 G17 G90\nG0 X0 Y0\nG41 D1 G1 X10 F100\nG1 Y10\nG40 X0\nM30",
    }
    for name, source in extras.items():
        cases[name] = (source, "fanuc_mill", "fanuc", {}, "fanuc", {})
    for code in (81, 82, 83, 84):
        source = f"G21 G17 G90\nT1 M6\nS500 M3\nG0 Z5\nG99 G{code} X2 Y3 Z-5 R2 Q2 P100 F100\nX4\nG80\nM30"
        cases[f"cycle_{code}"] = (source, "fanuc_mill", "fanuc", {}, "fanuc", {})

    cases["absolute_ijk_input"] = (
        "G17 G0 X10 Y0\nG3 X0 Y10 I0 J0 F100\nM30",
        "fanuc_mill",
        "fanuc",
        {"source_arc_type": 2},
        "fanuc",
        {},
    )
    cases["fanuc_to_iso"] = (MILL, "fanuc_mill", "fanuc", {}, "sinumerik", {})
    cases["iso_to_fanuc"] = ("G291\n" + MILL, "fanuc_mill", "sinumerik", {}, "fanuc", {})
    cases["native_full"] = (NATIVE, "fanuc_mill", "sinumerik", {}, "sinumerik", {})
    cases["native_to_fanuc"] = (NATIVE, "fanuc_mill", "sinumerik", {}, "fanuc", {})
    cases["native_resolved_fanuc_mill"] = (NATIVE, "fanuc_mill", "sinumerik", {}, "fanuc", {})
    cases["native_resolved_sinumerik_iso"] = (NATIVE, "fanuc_mill", "sinumerik", {}, "sinumerik", {})
    cases["native_resolved_sinumerik_native"] = (NATIVE, "fanuc_mill", "sinumerik", {}, "sinumerik", {})

    for profile, rotary in (("4ax_table_b", "B30"), ("5ax_table_bc_angled", "B30 C45")):
        options = {"kinematics": profile}
        cases[profile + "_full"] = (
            f"G90 G0 X0 Y0 Z0\n{rotary}\nG1 X10 Y0 Z0 F100\nM30",
            "fanuc_mill",
            "fanuc",
            options,
            "fanuc",
            options,
        )
    tcp_options = {"kinematics": "5ax_table_bc_angled"}
    cases["tcp_full"] = (
        "G90 G0 X0 Y0 Z0\nG43.4 H1\nG1 X10 Y20 Z30 B30 C45 F100\nG49\nM30",
        "fanuc_mill",
        "fanuc",
        tcp_options,
        "fanuc",
        tcp_options,
    )
    return cases


LEGACY_CASES = _legacy_cases()


def _bounds(result):
    points = [
        point
        for index, motion in enumerate(result.motions)
        for point in sample_motion(motion, index, chord_error=0.001)
    ]
    return tuple(
        value
        for axis in "xyz"
        for value in (min(getattr(point, axis) for point in points), max(getattr(point, axis) for point in points))
    )


def _assert_same_geometry(reference, replay):
    assert replay.ok and replay.complete, replay.diagnostics
    expected_length = sum(map(motion_length, reference.motions))
    actual_length = sum(map(motion_length, replay.motions))
    assert actual_length == pytest.approx(expected_length, abs=max(0.002, expected_length * 2e-5))
    assert _bounds(replay) == pytest.approx(_bounds(reference), abs=0.002)
    assert (replay.motions[-1].end_x, replay.motions[-1].end_y, replay.motions[-1].end_z) == pytest.approx(
        (reference.motions[-1].end_x, reference.motions[-1].end_y, reference.motions[-1].end_z), abs=0.001
    )


@pytest.mark.parametrize("name", sorted(LEGACY_CASES))
def test_legacy_192_golden_still_replays_the_same_geometry(name):
    source, language, source_dialect, source_options, replay_dialect, replay_options = LEGACY_CASES[name]
    original = execute(source, language=language, source_dialect=source_dialect, **source_options)
    assert original.ok and original.complete, original.diagnostics
    replay = execute(GOLDEN_TEXT[name], language=language, source_dialect=replay_dialect, **replay_options)
    _assert_same_geometry(original, replay)


def _step_signals(result, kind):
    return [signal for step in result.execution_steps for signal in step.signals if signal.kind == kind]


def test_legacy_192_expanded_cycles_lost_non_geometric_cycle_effects():
    cycle82_source = LEGACY_CASES["cycle_82"][0]
    cycle84_source = LEGACY_CASES["cycle_84"][0]
    original82 = execute(cycle82_source, language="fanuc_mill")
    original84 = execute(cycle84_source, language="fanuc_mill")
    legacy82 = execute(GOLDEN_TEXT["cycle_82"], language="fanuc_mill")
    legacy84 = execute(GOLDEN_TEXT["cycle_84"], language="fanuc_mill")

    assert len(_step_signals(original82, "dwell")) == 2
    assert not _step_signals(legacy82, "dwell")
    assert len(_step_signals(original84, "dwell")) == 2
    assert len(_step_signals(original84, "spindle_reverse")) == 2
    assert not _step_signals(legacy84, "dwell")
    assert not _step_signals(legacy84, "spindle_reverse")


def test_legacy_192_unverified_compensation_was_exported_but_current_expanded_refuses_it():
    source = LEGACY_CASES["compensation"][0]
    result = execute(source, language="fanuc_mill")
    assert result.ok and result.complete
    assert any(diagnostic.code == "UNVERIFIED_CUTTER_COMPENSATION" for diagnostic in result.diagnostics)
    assert GOLDEN_TEXT["compensation"]
    with pytest.raises(ValueError, match="cannot preserve"):
        convert_resolved_program(result, "fanuc_mill", ExportOptions(delimiter=True))


def test_plot_data_is_a_192_historical_mode_not_a_current_export_path():
    assert "fanuc_mill_plot" in GOLDEN_TEXT and "fanuc_turn_plot" in GOLDEN_TEXT
    assert not hasattr(export_pkg, "PLOT_DATA_MODE")
