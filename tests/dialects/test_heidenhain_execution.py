"""Native Klartext runtime contracts, independent of the ISO interpreter."""

import math
from pathlib import Path

import pytest

from app.gcode.execution.program import execute_program
from app.gcode.execution.source import language_for_path, source_dialect_for_path
from app.gcode.export.common import ExportLimitation, ExportOptions
from app.gcode.export.expanded import convert_resolved_program, default_target_post
from app.gcode.export.full import normalize_full_program
from app.gcode.export.tool_numbers import named_tools
from app.gcode.kernel import execute
from app.gcode.kernel.api.resources import ExecutionLimits
from app.gcode.kernel.frontend.heidenhain import parse_heidenhain_program
from app.gcode.trace import render_trace


def run(source, **kwargs):
    return execute(source, "fanuc_mill", source_dialect="heidenhain", **kwargs)


def test_complete_supplied_cam_sample_and_tool_discovery(fixture_text):
    source = fixture_text("milling/heidenhain/sample.h")
    result, tools, _ = execute_program(source, language="fanuc_mill", source_dialect="heidenhain")
    assert result.ok and result.complete and result.program_end == "M30"
    assert len(result.program.blocks) == 5605
    assert len(result.motions) == 3958
    assert len(result.execution_steps) == 5604
    assert sum(m.arc is not None for m in result.motions) == 1632
    assert {motion.tool for motion in result.motions} == {"T2"}
    assert tools["T2"]["diameter"] == 10
    assert [(d.code, d.line) for d in result.diagnostics] == [
        ("HEIDENHAIN_SMOOTHING_NOT_SIMULATED", 9),
        ("HEIDENHAIN_ZERO_FEED", 5092),
        ("HEIDENHAIN_ZERO_FEED", 5194),
        ("HEIDENHAIN_ZERO_FEED", 5576),
    ]
    assert all(d.severity == "warning" for d in result.diagnostics)
    assert len([m for m in result.motions if m.feed == 0]) >= 3
    assert result.motions[-1].end_z == -1
    lines = source.splitlines()
    assert all(m.source_raw == lines[m.source_block] for m in result.motions)
    assert sum(step.emitted_count for step in result.execution_steps) == len(result.motions)
    points = render_trace(result)
    assert len(points) > len(result.motions)
    assert default_target_post(result) == "heidenhain_itnc530"


@pytest.mark.parametrize("suffix", [".h", ".H"])
def test_native_container_and_unnamed_signature(suffix):
    assert source_dialect_for_path("part" + suffix, "L X1") == "heidenhain"
    assert language_for_path("part" + suffix) == "fanuc_mill"
    assert source_dialect_for_path(None, "0 BEGIN PGM PART MM\nL X1\nEND PGM PART MM") == "heidenhain"
    assert source_dialect_for_path("part.nc", "BEGIN PGM PART MM") == "fanuc"
    assert source_dialect_for_path(None, "; BEGIN PGM PART MM") == "fanuc"


@pytest.mark.parametrize("unit, scale", [("MM", 1), ("INCH", 25.4)])
def test_units_incremental_coordinates_spindle_and_end(unit, scale):
    result = run(f"BEGIN PGM A {unit}\nTOOL CALL 4 Z S1200\nL X1 F10 M3\nL IX2 IZ-1\nM30\nEND PGM A {unit}")
    assert result.ok and result.complete
    assert (result.motions[-1].end_x, result.motions[-1].end_z) == (3 * scale, -scale)
    assert result.motions[-1].feed == 10 * scale
    assert result.motions[-1].spindle_running and result.motions[-1].spindle_rpm == 1200
    assert result.events[0].kind == "tool_change" and result.events[0].tool == "T4"
    assert result.program_end == "M30"


@pytest.mark.parametrize(
    "axis, plane, point, center, end",
    [
        ("Z", 17, "X1 Y0", "X0 Y0", "X0 Y1"),
        ("Y", 18, "X1 Z0", "X0 Z0", "X0 Z1"),
        ("X", 19, "Y1 Z0", "Y0 Z0", "Y0 Z1"),
    ],
)
def test_native_circle_direction_plane_and_center(axis, plane, point, center, end):
    result = run(f"TOOL CALL 1 {axis}\nL {point} F100\nCC {center}\nC {end} DR+")
    assert result.ok, result.diagnostics
    arc = result.motions[-1].arc
    assert arc.plane == plane and not arc.clockwise
    assert arc.radius == pytest.approx(1) and arc.sweep == pytest.approx(math.pi / 2)


def test_radius_arc_and_arc_conventions_are_independent_of_iso_options():
    source = "L X1 F100\nCC X0 Y0\nC X0 Y1 DR+\nCR X-1 Y0 R1 DR+"
    result = run(source, source_arc_type=3, autodetect_arc_type=True)
    assert result.ok and len(result.motions) == 3
    assert all(m.arc.radius == pytest.approx(1) for m in result.motions[1:])


def test_machine_move_is_block_local_and_respects_wcs():
    result = run(
        "L X20 Y30 Z40 F100\nZ0 FMAX M91\nL X1", home_x=10, home_y=20, home_z=30, wcs_offsets={54: (10, 20, 30)}
    )
    assert result.ok
    assert result.motions[1].end_z == 0
    assert (result.motions[2].end_x, result.motions[2].end_y, result.motions[2].end_z) == (11, 50, 0)


_UNSUPPORTED_RUNTIME_FEATURES = frozenset(
    {
        # Rotary axes, move-back retraction, tool offsets and unmodeled M words
        # are parsed as native facts but have no runtime semantics.
        "L X2 A30",
        "L X2 M140 MB MAX",
        "TOOL CALL 1 Z DL1",
        "L X2 M92",
    }
)


@pytest.mark.parametrize(
    "command",
    [
        "LP PR2 PA30",
        "CT X2",
        "L X2 RL",
        "L X2 A30",
        "L X2 M140 MB MAX",
        "Q1=2",
        "LBL 1",
        "CYCL DEF 200 DRILLING",
        "TOOL CALL 1 Z DL1",
        "CC IX1",
        "L X2 M92",
    ],
)
def test_unimplemented_runtime_features_stop_with_source_and_valid_prefix(command):
    source = "L X1 F100\n" + command + "\nL X99"
    result = run(source)
    if command in _UNSUPPORTED_RUNTIME_FEATURES:
        assert not result.ok and not result.complete
        assert len(result.motions) == 1 and result.motions[0].end_x == 1
        assert result.diagnostics[-1].code == "UNSUPPORTED_HEIDENHAIN_EXECUTION"
        assert result.diagnostics[-1].line == 2 and result.diagnostics[-1].raw == command
        return
    # Extended native execution reaches these commands instead of refusing them:
    # they either run (Q/LBL/CYCL/RL/CC) or stop on geometry that is specific to
    # the fragment (LP/CT without their center/contour), never via the gate.
    assert all(diagnostic.code != "UNSUPPORTED_HEIDENHAIN_EXECUTION" for diagnostic in result.diagnostics)
    assert result.motions and result.motions[0].end_x == 1


def test_invalid_arc_does_not_publish_later_geometry():
    result = run("L X1 F100\nCC X0 Y0\nC X0 Y3 DR+\nL X99")
    assert not result.ok and not result.complete
    assert len(result.motions) == 1
    assert result.diagnostics[-1].line == 3


def test_resource_limits_and_cancellation_apply_to_native_execution():
    result = run("L X1\nL X2\nL X3", limits=ExecutionLimits(generated_motions=2))
    assert not result.ok and len(result.motions) == 2
    assert result.diagnostics[-1].code == "RESOURCE_LIMIT"
    assert result.diagnostics[-1].line == 3
    cancelled = run("L X1", cancelled=lambda: True)
    assert not cancelled.ok and cancelled.diagnostics[-1].code == "EXECUTION_CANCELLED"


def test_cached_native_ast_and_named_tools():
    source = 'TOOL CALL "T8" Z S800\nL X1 F100'
    program = parse_heidenhain_program(source)
    result, tools, _ = execute_program(
        source, language="fanuc_mill", source_dialect="heidenhain", parsed_program=program
    )
    assert result.ok and result.program is program
    assert named_tools(result) == {"T8"} and "T8" in tools
    with pytest.raises(ExportLimitation, match="Klartext FULL"):
        normalize_full_program(result, source)


def test_native_optional_blocks_and_turning_guard():
    result = run("/L X5\nL X1", skip_optional_blocks=True)
    assert result.ok and len(result.motions) == 1 and result.motions[0].end_x == 1
    turning = execute("L X1", "fanuc_turn", source_dialect="heidenhain")
    assert not turning.ok and turning.diagnostics[0].code == "UNSUPPORTED_HEIDENHAIN_TURNING"


@pytest.mark.parametrize("axis,plane", [("X", 19), ("Y", 18), ("Z", 17)])
def test_axis_only_tool_call_preserves_tool_and_discovery(axis, plane):
    source = f"TOOL CALL 4 Z S5000\nTOOL CALL {axis}\nL X1 F100"
    result, tools, _ = execute_program(source, language="fanuc_mill", source_dialect="heidenhain")
    assert result.ok, result.diagnostics
    assert result.motions[0].tool == "T4" and result.motions[0].plane == plane
    assert set(tools) == {"T4"}
    assert len([event for event in result.events if event.kind == "tool_change"]) == 1


def test_supplied_cam_cycle_fixture_parses_and_reports_unmodeled_retraction(fixture_text):
    source = fixture_text("milling/heidenhain/cycles_itnc530.h")
    program = parse_heidenhain_program(source)
    assert program.blocks[6].native_syntax.tool is None
    result = run(source)
    assert not result.ok and not result.complete
    assert not result.motions
    diagnostic = result.diagnostics[-1]
    assert diagnostic.code == "UNSUPPORTED_HEIDENHAIN_EXECUTION"
    assert diagnostic.line == 8 and diagnostic.raw == "7 L M140 MB MAX"
    assert "machine travel limit" in diagnostic.message


@pytest.mark.parametrize("feed,move,expected_feed", [("MAX", 0, None), ("0", 1, 100), ("300", 1, 300)])
def test_cycle203_retraction_feed_and_max_are_distinct(feed, move, expected_feed):
    source = (
        "TOOL CALL Z\nL Z10 FMAX\nCYCL DEF 203 UNIVERSAL DRILLING ~\n"
        "Q200=2 ~\nQ201=-6 ~\nQ206=100 ~\nQ202=2 ~\nQ203=0 ~\nQ204=10 ~\n"
        f"Q208={feed}\nL X1 FMAX M99\nM30"
    )
    result = run(source)
    assert result.ok and result.complete, result.diagnostics
    retracts = [
        motion for motion in result.motions if motion.cycle_generated and motion.start_z < 0 and motion.end_z == 2
    ]
    assert len(retracts) == 3
    assert all(motion.move == move and motion.feed == expected_feed for motion in retracts)
    assert min(motion.end_z for motion in result.motions) == -6
    assert result.motions[-1].end_z == 10


def test_unsupported_cycle_is_rejected_at_definition_before_geometry_can_use_wrong_origin():
    result = run("L X1 F100\nCYCL DEF 8 MIRROR IMAGE\nL X99")
    assert not result.ok and len(result.motions) == 1
    assert result.diagnostics[-1].code == "UNSUPPORTED_HEIDENHAIN_CYCLE"
    assert result.diagnostics[-1].line == 2


@pytest.mark.parametrize("preset", range(1, 7))
def test_datum_presets_map_to_configured_g54_through_g59_in_machine_space(preset):
    offsets = {54: (10, 20, 30), 53 + preset: (100 * preset, -10 * preset, 5 * preset)}
    native = run(
        f"L X1 Y2 Z3 FMAX\nCYCL DEF 247 DATUM SETTING ~\nQ339={preset}\nL X4 Y5 Z6 F100",
        wcs_offsets=offsets,
    )
    iso = execute(f"G54\nG0 X1 Y2 Z3\nG{53 + preset}\nG1 X4 Y5 Z6 F100", "fanuc_mill", wcs_offsets=offsets)
    assert native.ok and iso.ok, native.diagnostics

    def coordinates(motion):
        return (motion.start_x, motion.start_y, motion.start_z, motion.end_x, motion.end_y, motion.end_z)

    assert [coordinates(motion) for motion in native.motions] == [coordinates(motion) for motion in iso.motions]
    exported = convert_resolved_program(native, "fanuc_mill", ExportOptions())
    # Ordinary EXPANDED output uses the shared zero-offset target G54 contract.
    replay = execute(exported, "fanuc_mill")
    assert replay.ok, replay.diagnostics
    assert [coordinates(motion) for motion in replay.motions] == [coordinates(motion) for motion in native.motions]
    datum_step = native.execution_steps[2]
    assert datum_step.emitted_count == 0
    assert datum_step.position == native.execution_steps[1].position


@pytest.mark.parametrize("number", [0, 7, -1, 1.5])
def test_datum_selection_rejects_entries_outside_the_application_table(number):
    result = run(f"L X1 F100\nCYCL DEF 247 DATUM SETTING\nQ339={number}\nL X99")
    assert not result.ok and len(result.motions) == 1
    assert result.diagnostics[-1].line == 3
    assert "G54..G59" in result.diagnostics[-1].message


def test_datum_selection_preserves_drilling_cycle_and_applies_offsets_to_operations():
    result = run(
        "CYCL DEF 200 DRILLING\nQ200=2\nQ201=-5\nQ206=100\nQ203=0\nQ204=10\n"
        "CYCL DEF 247 DATUM SETTING\nQ339=2\nL X1 Y2 FMAX M99",
        wcs_offsets={55: (100, 200, 30)},
    )
    assert result.ok, result.diagnostics
    operation = next(event.drilling for event in result.events if event.drilling is not None)
    assert operation.position == (101, 202, 25)
    assert operation.reference == (101, 202, 30)
    assert operation.safety == (101, 202, 32)
    assert result.motions[-1].end_z == 40


def test_datum_switch_preserves_circle_center_and_arc_tangent_in_machine_space():
    result = run(
        "L X10 Y0 F100\nCC X0 Y0\nCYCL DEF 247 DATUM SETTING\nQ339=2\nC X-100 Y10 DR+\nCT X-110 Y0",
        wcs_offsets={55: (100, 0, 0)},
    )
    assert result.ok, result.diagnostics
    arcs = [motion.arc for motion in result.motions if motion.arc is not None]
    assert len(arcs) == 2
    assert all(arc.center == pytest.approx((0, 0, 0)) and arc.radius == pytest.approx(10) for arc in arcs)


def test_supplied_cam_cycles_reach_m30_when_machine_retractions_are_isolated(fixture_text):
    program = parse_heidenhain_program(fixture_text("milling/heidenhain/cycles_itnc530.h"))
    # Test the machining cycles independently of the unsupported M140 travel.
    # The real fixture remains unchanged and its limitation is tested above.
    source = "\n".join(
        block.raw
        for block in program.blocks
        if not any(function.code.value == "140" for function in block.native_syntax.machine_functions)
    )
    result = run(source, wcs_offsets={54: (10, 20, 30)})
    assert result.ok and result.complete and result.program_end == "M30", result.diagnostics
    operations = [event.drilling for event in result.events if event.drilling is not None]
    assert len(operations) == 8
    assert all(operation.position[2] == pytest.approx(30 - 1 - 16.262) for operation in operations)
    assert {operation.position[:2] for operation in operations} == {(-15, 30), (35, 30)}


def test_datum_offsets_remain_millimetres_in_an_inch_program():
    result = run(
        "BEGIN PGM INCH_PART INCH\nCYCL DEF 247 DATUM SETTING\nQ339=2\nL X1 Y2 Z3 FMAX\nEND PGM INCH_PART INCH",
        wcs_offsets={55: (10, 20, 30)},
    )
    assert result.ok, result.diagnostics
    motion = result.motions[-1]
    assert (motion.end_x, motion.end_y, motion.end_z) == pytest.approx((35.4, 70.8, 106.2))


def test_cycle203_max_does_not_leak_into_the_next_cycle_definition():
    result = run(
        "CYCL DEF 203\nQ200=2\nQ201=-4\nQ206=100\nQ202=2\nQ208=MAX\nL X1 FMAX M99\n"
        "CYCL DEF 203\nQ200=2\nQ201=-4\nQ206=100\nQ202=2\nQ208=250\nL X2 FMAX M99"
    )
    assert result.ok, result.diagnostics
    retracts = [
        motion for motion in result.motions if motion.cycle_generated and motion.start_z < 0 and motion.end_z == 2
    ]
    assert [(motion.move, motion.feed) for motion in retracts] == [(0, None), (0, None), (1, 250), (1, 250)]


def test_supplied_cam_cycles_execute_unchanged_with_configured_home(fixture_text):
    source = fixture_text("milling/heidenhain/cycles_itnc530.h")
    result, tools, _ = execute_program(
        source,
        language="fanuc_mill",
        source_dialect="heidenhain",
        home_z=100,
        emulate_g28_home=True,
    )
    assert result.ok and result.complete and result.program_end == "M30", result.diagnostics
    operations = [event.drilling for event in result.events if event.drilling is not None]
    assert len(operations) == 8 and set(tools) == {"T4"}
    assert all(operation.position[2] == pytest.approx(-17.262) for operation in operations)
    assert result.motions[-1].end_z == 100
    assert sum(d.code == "HEIDENHAIN_M140_HOME_EMULATION" for d in result.diagnostics) == 1
    assert all(d.severity == "warning" for d in result.diagnostics)
    with pytest.raises(ExportLimitation, match="HEIDENHAIN_M140_HOME_EMULATION"):
        convert_resolved_program(result, "fanuc_mill", ExportOptions())


@pytest.mark.parametrize("axis", "XYZ")
def test_finite_m140_uses_vertical_z_before_positioning_and_has_separate_feed(axis):
    result = run(f"TOOL CALL 1 {axis}\nL X1 Y2 Z3 F100\nL X10 F125 M140 MB+5 F750\nL X20")
    assert result.ok, result.diagnostics
    retreat, positioning, following = result.motions[1:]
    before = (retreat.start_x, retreat.start_y, retreat.start_z)
    after = (retreat.end_x, retreat.end_y, retreat.end_z)
    assert tuple(after[i] - before[i] for i in range(3)) == (0, 0, 5)
    assert retreat.move == 1 and retreat.feed == 750
    assert positioning.feed == following.feed == 125
    assert (positioning.start_x, positioning.start_y, positioning.start_z) == after


def test_m140_max_requires_explicit_home_emulation_and_never_moves_backwards():
    source = "TOOL CALL Z\nL Z150 FMAX\nL M140 MB MAX"
    missing = run(source)
    assert not missing.ok and "configured Home" in missing.diagnostics[-1].message
    enabled = run(source, home_z=100, emulate_g28_home=True)
    assert enabled.ok and len(enabled.motions) == 1 and enabled.motions[-1].end_z == 150


def test_m140_scoped_fmax_does_not_turn_the_positioning_move_into_rapid():
    result = run("TOOL CALL Z\nL Z-10 F100\nL X10 F125 M140 MB+5 FMAX")
    assert result.ok, result.diagnostics
    retreat, positioning = result.motions[-2:]
    assert retreat.move == 0 and retreat.feed is None
    assert positioning.move == 1 and positioning.feed == 125


@pytest.mark.parametrize("axis,home", [("X", (100, 200, 300)), ("Y", (100, 200, 300)), ("Z", (100, 200, 300))])
def test_m140_max_always_uses_g28_home_z_with_wcs(axis, home):
    result = run(
        f"TOOL CALL {axis}\nL X1 Y2 Z3 FMAX\nL M140 MB MAX",
        home_x=home[0],
        home_y=home[1],
        home_z=home[2],
        wcs_offsets={54: (10, 20, 30)},
        emulate_g28_home=True,
    )
    assert result.ok, result.diagnostics
    retreat = result.motions[-1]
    assert (retreat.end_x, retreat.end_y, retreat.end_z) == (11, 22, home[2])
    assert retreat.move == 0


@pytest.mark.parametrize(
    "name",
    sorted(path.name for path in (Path(__file__).resolve().parents[1] / "fixtures/milling/heidenhain").glob("*.h")),
)
@pytest.mark.parametrize("home_z", [0.0, 100.0])
def test_every_native_corpus_program_executes_completely(name, fixture_text, home_z):
    source = fixture_text("milling/heidenhain/" + name)
    result, _tools, _ = execute_program(
        source,
        language="fanuc_mill",
        source_dialect="heidenhain",
        home_z=home_z,
        emulate_g28_home=True,
    )
    assert result.ok and result.complete, (name, result.diagnostics)
    assert result.motions
    assert all(d.severity != "error" for d in result.diagnostics)
    assert all(motion.source_raw == source.splitlines()[motion.source_block] for motion in result.motions)


def test_supplied_ellipse_preserves_datum_and_forty_parametric_contour_steps(fixture_text):
    result = run(fixture_text("milling/heidenhain/ellipse.h"))
    assert result.ok and result.complete and result.program_end == "M2", result.diagnostics
    contour = [motion for motion in result.motions if motion.move == 1 and motion.feed == 350]
    assert len(contour) == 40
    for motion in contour:
        assert ((motion.end_x - 50) / 50) ** 2 + ((motion.end_y - 50) / 30) ** 2 == pytest.approx(1)
        assert motion.end_z == -5
    exported = convert_resolved_program(result, "fanuc_mill", ExportOptions())
    replay = execute(exported, "fanuc_mill")
    assert replay.ok, replay.diagnostics
    assert len(replay.motions) == len(result.motions)
    for actual, expected in zip(replay.motions, result.motions, strict=True):
        assert (actual.end_x, actual.end_y, actual.end_z) == pytest.approx(
            (expected.end_x, expected.end_y, expected.end_z),
            abs=1e-5,
        )


def test_supplied_trigonometric_drilling_macro_executes_ten_holes(fixture_text):
    result = run(fixture_text("milling/heidenhain/itnc530_cycl200macro.h"))
    assert result.ok and result.complete and result.program_end == "M30", result.diagnostics
    operations = [event.drilling for event in result.events if event.drilling is not None]
    assert len(operations) == 10
    for index, operation in enumerate(operations):
        angle = math.radians(18 + 36 * index)
        assert operation.position == pytest.approx((100 * math.cos(angle), 100 * math.sin(angle), -20))


def test_native_datum_shift_and_rotation_preserve_position_and_transform_arc_vectors():
    result = run(
        "TOOL CALL Z\nL X1 Y2 Z3 FMAX\nCYCL DEF 7.0 DATUM SHIFT\nCYCL DEF 7.1 X10\n"
        "CYCL DEF 7.2 Y20\nCYCL DEF 10.0 ROTATION\nCYCL DEF 10.1 ROT90\n"
        "CC X0 Y0\nL X5 Y0 F100\nC X0 Y5 DR+\nCT X-5 Y0"
    )
    assert result.ok, result.diagnostics
    assert len(result.motions) == 4
    assert result.execution_steps[5].emitted_count == 0
    assert result.execution_steps[5].position == pytest.approx((1, 2, 3))
    assert [(m.end_x, m.end_y, m.end_z) for m in result.motions[1:]] == pytest.approx(
        [(10, 25, 3), (5, 20, 3), (10, 15, 3)]
    )
    assert all(
        m.arc.center == pytest.approx((10, 20, 3)) and m.arc.radius == pytest.approx(5) for m in result.motions[2:]
    )


def test_m91_and_m140_keep_machine_z_under_native_coordinate_transforms():
    source = (
        "TOOL CALL Z\nCYCL DEF 7.0\nCYCL DEF 7.1 X10\nCYCL DEF 7.2 Y20\nCYCL DEF 7.3 Z30\n"
        "CYCL DEF 10.0\nCYCL DEF 10.1 ROT90\nL X1 Y2 Z3 FMAX\nL Z0 FMAX M91\nL M140 MB MAX"
    )
    result = run(source, home_z=100, emulate_g28_home=True)
    assert result.ok, result.diagnostics
    assert (result.motions[-2].end_x, result.motions[-2].end_y, result.motions[-2].end_z) == pytest.approx((8, 21, 0))
    assert (result.motions[-1].end_x, result.motions[-1].end_y, result.motions[-1].end_z) == pytest.approx((8, 21, 100))
