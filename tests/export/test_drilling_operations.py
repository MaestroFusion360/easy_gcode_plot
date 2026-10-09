"""Cycle posts consume semantic hole operations and preserve executed paths."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.gcode.export.common import ExportOptions
from app.gcode.export.expanded import convert_resolved_program, load_post_profile
from app.gcode.kernel import execute
from app.gcode.trace_tools import motion_length

TARGETS = ("fanuc_mill", "fanuc_mill_multiaxis", "sinumerik_iso", "sinumerik_840d", "sinumerik_840d_multiaxis")


@pytest.mark.parametrize("target", ["fanuc_mill", "sinumerik_840d"])
@pytest.mark.parametrize(
    "dialect,cycle",
    [
        ("fanuc", "G98 G74 X2 Z-5 R1 Q2 F500"),
        ("fanuc", "G99 G76 X2 Z-5 R1 Q0.2 F100"),
        ("fanuc", "G99 G87 X2 Z-3 R-5 Q0.2 F100"),
        ("fanuc", "G98 G89 X2 Z-5 R1 P100 F100"),
        ("sinumerik", "CYCLE85(10,0,1,-5,,.1,100,250,0,0,0)"),
        ("sinumerik", "CYCLE86(10,0,1,-5,,.1,3,.2,.3,.4,0,0,0,0)"),
        ("sinumerik", "CYCLE87(10,0,1,-5,,3)"),
        ("sinumerik", "CYCLE89(10,0,1,-5,,.1)"),
    ],
)
def test_new_cycle_export_preserves_expanded_geometry_and_feeds(target, dialect, cycle):
    if dialect == "sinumerik":
        cycle = f"MCALL {cycle}\nX2\nMCALL"
    else:
        cycle += "\nG80"
    before = execute(f"G90 G0 Z10\nS500 M3\nF100\n{cycle}\nM30", "fanuc_mill", source_dialect=dialect)
    assert before.ok and before.complete, before.diagnostics
    text = convert_resolved_program(before, target, ExportOptions(decimal_places=6))
    _assert_geometry(before, _replay(text, target))


@pytest.mark.parametrize("fixture,cycles", [("toolchange.nc", {84: 2}), ("cycles_fanuc.nc", {81: 4, 83: 2})])
@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("delimiter", [False, True])
def test_cam_fixtures_emit_post_cycles_with_valid_native_keyword_separators(fixture, cycles, target, delimiter):
    source = (Path(__file__).parents[1] / "fixtures" / "milling" / "fanuc" / fixture).read_text(encoding="utf-8")
    before = execute(source, language="fanuc_mill")
    assert before.ok, before.diagnostics
    text = convert_resolved_program(before, target, ExportOptions(delimiter=delimiter, decimal_places=6))
    for code, count in cycles.items():
        command = f"MCALL CYCLE{code}(" if target.startswith("sinumerik_840d") else f"G{code}"
        expected = count // 2 if target.startswith("sinumerik_840d") and code != 83 else count
        assert text.count(command) == expected
    assert "MCALLCYCLE" not in text
    _assert_geometry(before, _replay(text, target))


@pytest.mark.parametrize("delimiter", [False, True])
@pytest.mark.parametrize("target", ["sinumerik_840d", "sinumerik_840d_multiaxis"])
def test_native_mcall_group_keeps_first_stationary_xy_hole(delimiter, target):
    source = "G21 G90 G17\nS400 M3\nG0 X-25 Y10 Z5\nG98 G81 X-25 Y10 Z-17 R4 F400\nX25\nG80\nM30"
    before = execute(source, language="fanuc_mill")
    text = convert_resolved_program(before, target, ExportOptions(delimiter=delimiter))
    group = text.split("MCALL CYCLE81(")[1].split("\nMCALL\n")[0].splitlines()[1:]
    assert [line.replace(" ", "") for line in group] == ["X-25Y10", "X25Y10"]
    after = _replay(text, target)
    assert [event.drilling.position for event in after.events if event.drilling is not None] == [
        (-25, 10, -17),
        (25, 10, -17),
    ]
    _assert_geometry(before, after)


@pytest.mark.parametrize("delimiter", [False, True])
@pytest.mark.parametrize("target", ["sinumerik_840d", "sinumerik_840d_multiaxis"])
def test_native_cam_fixture_retains_both_holes_in_each_mcall_group(delimiter, target):
    source = (Path(__file__).parents[1] / "fixtures" / "milling" / "sinumerik" / "cycles_sin840d.mpf").read_text(
        encoding="utf-8"
    )
    before = execute(source, language="fanuc_mill", source_dialect="sinumerik")
    assert before.ok, before.diagnostics
    text = convert_resolved_program(before, target, ExportOptions(delimiter=delimiter, decimal_places=6))
    for code in (81, 82, 83):
        assert text.count(f"MCALL CYCLE{code}(") == 1
        group = text.split(f"MCALL CYCLE{code}(")[1].split("\nMCALL\n")[0].splitlines()[1:]
        assert [line.replace(" ", "") for line in group] == ["X-25Y10", "X25Y10"]
    after = _replay(text, target)
    assert len([event for event in after.events if event.drilling is not None]) == 6
    _assert_geometry(before, after)


def _replay(text, target):
    result = execute(
        text, language="fanuc_mill", source_dialect="sinumerik" if target.startswith("sinumerik") else "fanuc"
    )
    assert result.ok and result.complete, result.diagnostics
    return result


def _assert_geometry(before, after):
    assert sum(map(motion_length, after.motions)) == pytest.approx(sum(map(motion_length, before.motions)), abs=1e-5)
    assert (after.motions[-1].end_x, after.motions[-1].end_y, after.motions[-1].end_z) == pytest.approx(
        (before.motions[-1].end_x, before.motions[-1].end_y, before.motions[-1].end_z), abs=1e-5
    )
    before_feeds = [(m.end_x, m.end_y, m.end_z, m.feed) for m in before.motions if m.move == 1]
    after_feeds = [(m.end_x, m.end_y, m.end_z, m.feed) for m in after.motions if m.move == 1]
    assert len(before_feeds) == len(after_feeds)
    for expected, actual in zip(before_feeds, after_feeds, strict=True):
        assert actual == pytest.approx(expected, abs=1e-5)


@pytest.mark.parametrize("solution_line", [False, True])
@pytest.mark.parametrize("target", ["sinumerik_840d", "sinumerik_840d_multiaxis"])
@pytest.mark.parametrize("delimiter", [False, True])
@pytest.mark.parametrize("code,parameters", [(81, (5, 9)), (82, (6, 9)), (83, (17, 20)), (84, (18, 24))])
def test_selected_sinumerik_generation_controls_post_interface(solution_line, target, delimiter, code, parameters):
    source = (
        f"G21 G90 G17\nS400 M3\nG0 Z5\nG98 G{code} X-25 Y10 Z-17 R4 Q{0 if code == 84 else 1} P100 F400\nX25\nG80\nM30"
    )
    before = execute(source, language="fanuc_mill", sinumerik_840d_sl=solution_line)
    text = convert_resolved_program(before, target, ExportOptions(delimiter=delimiter))
    calls = [line for line in text.splitlines() if line.startswith(f"MCALL CYCLE{code}(")]
    assert calls
    assert all(len(line.split("(")[1].removesuffix(")").split(",")) == parameters[solution_line] for line in calls)
    after = execute(text, language="fanuc_mill", source_dialect="sinumerik", sinumerik_840d_sl=solution_line)
    assert after.ok and after.sinumerik_840d_sl == solution_line, after.diagnostics
    _assert_geometry(before, after)


@pytest.mark.parametrize("code", [81, 82, 83, 84])
def test_classic_source_rejects_expanded_sl_cycle_signature(code):
    before = execute(
        f"S400 M3\nG0 Z5\nG99 G{code} X2 Z-5 R2 Q{0 if code == 84 else 1} F400\nG80\nM30", language="fanuc_mill"
    )
    text = convert_resolved_program(before, "sinumerik_840d")
    classic = execute(text, language="fanuc_mill", source_dialect="sinumerik", sinumerik_840d_sl=False)
    assert not classic.ok
    assert any(d.code == "UNSUPPORTED_SINUMERIK_CYCLE" and "classic" in d.message for d in classic.diagnostics)
    assert not any(event.drilling is not None for event in classic.events)


def test_sl_cycle81_dwell_survives_conversion_to_classic_cycle82():
    source = "G710 G90\nS400 M3\nF400\nG0 Z5\nMCALL CYCLE81(5,0,2,-5,,0.2,0,1,12)\nX2\nMCALL\nM30"
    before = execute(source, language="fanuc_mill", source_dialect="sinumerik", sinumerik_840d_sl=True)
    assert before.ok, before.diagnostics
    text = convert_resolved_program(before, "sinumerik_840d", sinumerik_840d_sl=False)
    assert "MCALL CYCLE82(5,0,2,-5,,0.2)" in text
    after = execute(text, language="fanuc_mill", source_dialect="sinumerik", sinumerik_840d_sl=False)
    assert after.ok, after.diagnostics
    assert [signal.value for signal in after.signals if signal.kind == "dwell"] == [0.2]
    _assert_geometry(before, after)


def test_shortened_eight_argument_sl_cycle81_keeps_dwell_at_sixth_position():
    source = "G710 G90\nF100\nG0 Z5\nMCALL CYCLE81(5,0,2,-5,,0.2,0,1)\nX2\nMCALL\nM30"
    result = execute(source, language="fanuc_mill", source_dialect="sinumerik", sinumerik_840d_sl=True)
    assert result.ok, result.diagnostics
    assert [signal.value for signal in result.signals if signal.kind == "dwell"] == [0.2]
    assert next(event.drilling for event in result.events if event.drilling is not None).dwell_bottom == 0.2


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("cycle", ["G81", "G82 P100", "G83 Q2", "G73 Q2", "G84 P100"])
@pytest.mark.parametrize("incremental", [False, True])
def test_iso_holes_collapse_to_post_cycles_and_resume_normal_motion(target, cycle, incremental):
    source = f"G21 G17 G90\nS500 M3\nG0 Z5\nG99 {cycle} X2 Y3 Z-5 R2 F100\nX4\nG80\nG1 X8 Z3 F200\nM30"
    before = execute(source, language="fanuc_mill")
    assert before.ok, before.diagnostics
    text = convert_resolved_program(before, target, ExportOptions(delimiter=True, incremental=incremental))
    assert ("MCALL CYCLE" if target.startswith("sinumerik_840d") else cycle.split()[0]) in text
    assert len([event for event in before.events if event.drilling is not None]) == 2
    _assert_geometry(before, _replay(text, target))


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("cycle", ["G81", "G82 P100", "G83 Q2"])
def test_initial_return_and_displaced_wcs_survive_cycle_conversion(target, cycle):
    source = f"G21 G17 G90 G54\nG0 Z5\nG98 {cycle} X2 Y3 Z-5 R2 F100\nX4\nG80\nG1 X8 F200\nM30"
    before = execute(source, language="fanuc_mill", wcs_offsets={54: (10, -20, 80)})
    assert before.ok
    text = convert_resolved_program(before, target, ExportOptions(delimiter=True))
    _assert_geometry(before, _replay(text, target))


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize(
    "cycle",
    [
        "CYCLE81(5,0,2,-9)",
        "CYCLE82(5,0,2,-9,,0.2)",
        "CYCLE83(2,2,0,-9,,0,,0,0,0,1,1,3,0,1,0,1)",
        "CYCLE84(2,0,2,-9,,0.1,3,0,1.25,0,500,500)",
    ],
)
def test_native_holes_use_neutral_operation_in_each_post(target, cycle):
    source = f"G710 G90\nS500 M3\nG0 Z5 F100\nMCALL {cycle}\nX2 Y3\nX4 Y3\nMCALL\nG1 X8 F200\nM30"
    before = execute(source, language="fanuc_mill", source_dialect="sinumerik")
    assert before.ok, before.diagnostics
    text = convert_resolved_program(before, target, ExportOptions(delimiter=True))
    assert ("MCALL CYCLE" if target.startswith("sinumerik_840d") else "G8") in text
    _assert_geometry(before, _replay(text, target))


def test_drilling_event_is_resolved_immutable_and_present_for_each_occurrence():
    before = execute("G0 Z5\nG99 G83 X2 Y3 Z-5 R2 Q2 F100\nX4\nG80\nM30", language="fanuc_mill")
    operations = [event.drilling for event in before.events if event.drilling is not None]
    assert [operation.position for operation in operations] == [(2, 3, -5), (4, 3, -5)]
    assert operations[0].peck_first == 2
    assert operations[0].safety == (2, 3, 2)
    with pytest.raises(FrozenInstanceError):
        operations[0].feed = 999


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("scale", [1.0, 25.4])
def test_incremental_source_holes_and_per_revolution_feed_survive_unit_conversion(target, scale):
    source = "G21 G17 G90\nS500 M3\nG0 Z5\nG95 G91\nG99 G83 X2 Y3 Z-7 R-3 Q2 F0.2\nX2\nG80\nG90 G1 X8 F0.3\nM30"
    before = execute(source, language="fanuc_mill")
    assert before.ok, before.diagnostics
    text = convert_resolved_program(
        before,
        target,
        ExportOptions(delimiter=True, output_unit_scale=scale, decimal_places=9, decimal_places_explicit=True),
    )
    _assert_geometry(before, _replay(text, target))


def test_zero_depth_hole_preserves_execution_without_dividing_by_depth():
    result = execute("G0 Z5\nG81 X2 Y3 Z2 R2 F100\nG80\nM30", language="fanuc_mill")
    assert result.ok, result.diagnostics
    assert next(event.drilling for event in result.events if event.drilling is not None).position == (2, 3, 2)


def test_zero_motion_dwell_hole_keeps_its_machine_signal_when_not_collapsed():
    result = execute("G99 G82 X0 Y0 Z0 R0 P100 F100\nG80\nM30", language="fanuc_mill")
    assert result.ok, result.diagnostics
    text = convert_resolved_program(result, "fanuc_mill", ExportOptions(delimiter=True))
    assert "G4 P100" in text


@pytest.mark.parametrize("target", ["fanuc_mill_multiaxis", "sinumerik_840d_multiaxis"])
def test_table_c_cycle_is_emitted_in_the_indexed_frame_once(target):
    source = "G90 G0 C30\nG0 X10 Y0 Z5\nG99 G81 X20 Y10 Z-5 R2 F100\nG80\nM30"
    before = execute(source, language="fanuc_mill", kinematics="4ax_table_c")
    text = convert_resolved_program(before, target, ExportOptions(delimiter=True))
    after = execute(
        text,
        language="fanuc_mill",
        kinematics="4ax_table_c",
        source_dialect="sinumerik" if target.startswith("sinumerik") else "fanuc",
    )
    assert after.ok, after.diagnostics
    assert ("CYCLE81" if target.startswith("sinumerik") else "G81") in text
    _assert_geometry(before, after)


def test_left_hand_tapping_is_not_changed_to_native_right_hand_cycle():
    before = execute("S500 M4\nG0 Z5\nG99 G84 X2 Y3 Z-5 R2 F100\nG80\nM30", language="fanuc_mill")
    text = convert_resolved_program(before, "sinumerik_840d", ExportOptions(delimiter=True))
    assert "CYCLE84" not in text
    _assert_geometry(before, _replay(text, "sinumerik_840d"))


def test_custom_post_without_cycles_retains_expanded_geometry(tmp_path):
    profile = load_post_profile("fanuc_mill")
    profile.pop("cycles")
    post = tmp_path / "legacy.json"
    post.write_text(json.dumps(profile), encoding="utf-8")
    before = execute("G0 Z5\nG99 G83 X2 Y3 Z-5 R2 Q2 F100\nG80\nM30", language="fanuc_mill")
    text = convert_resolved_program(before, str(post), ExportOptions(delimiter=True))
    assert "G83" not in text
    _assert_geometry(before, _replay(text, "fanuc_mill"))


@pytest.mark.parametrize(
    "mutation",
    [
        {"cancel": ""},
        {"drill": "G81 {unknown}"},
        {"drill": "G81 {depth.__class__}"},
        {"syntax": "other"},
        {"drill": "G81 {depth:.2f}"},
    ],
)
def test_cycle_post_templates_are_validated_before_serialization(tmp_path, mutation):
    profile = load_post_profile("fanuc_mill")
    profile["cycles"].update(mutation)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(ValueError):
        load_post_profile(str(path))
