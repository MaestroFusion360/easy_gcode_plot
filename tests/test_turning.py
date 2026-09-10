from __future__ import annotations

import pytest
from gcode_samples import TURNING_PARTIAL_TRACE, TURNING_REFERENCE_AND_SIGNALS

from app.gcode.kernel import execute


def test_basic_turning_cycles_fixture_executes_facing_roughing_and_grooving(fixture_text):
    source = fixture_text("turning/basic_turning_cycles.NC")
    result = execute(source, language="fanuc_turn")
    assert result.ok, result.diagnostics

    cycle_raw = {motion.source_raw for motion in result.motions if motion.source_kind == "cycle" and motion.source_raw}
    assert any(raw.startswith("G71") for raw in cycle_raw)
    assert any(raw.startswith("G72") for raw in cycle_raw)
    assert any(raw.startswith("G75") for raw in cycle_raw)
    assert sum(motion.cycle_generated for motion in result.motions) == 3500
    assert min(motion.end_z for motion in result.motions) == pytest.approx(-224.7)


@pytest.mark.parametrize(
    ("x_mode", "start_x", "end_x", "source_arc_type", "arc_words"),
    [
        ("G190", 20, 40, 1, "I0 K-10"),
        ("G190", 20, 40, 2, "I10 K-10"),
        ("G190", 20, 40, 3, "R10"),
        ("G191", 10, 20, 1, "I0 K-10"),
        ("G191", 10, 20, 2, "I10 K-10"),
        ("G191", 10, 20, 3, "R10"),
    ],
)
def test_turning_arcs_share_physical_geometry_across_x_and_arc_programming_modes(
    x_mode, start_x, end_x, source_arc_type, arc_words
):
    source = f"G21 G18 {x_mode}\nG0 X{start_x} Z0\nG3 X{end_x} Z-10 {arc_words} F100\nM30"
    result = execute(source, language="fanuc_turn", source_arc_type=source_arc_type)
    assert result.ok, result.diagnostics

    motion = next(item for item in result.motions if item.move in (2, 3))
    assert motion.arc is not None
    assert (motion.end_x * motion.x_scale, motion.end_y, motion.end_z) == pytest.approx((20.0, 0.0, -10.0))
    assert motion.arc.center == pytest.approx((10.0, 0.0, -10.0))
    assert motion.arc.radius == pytest.approx(10.0)
    assert motion.arc.sweep == pytest.approx(3.141592653589793 / 2.0)
    assert motion.arc.clockwise is True
    assert motion.x_scale == pytest.approx(0.5)


@pytest.mark.parametrize(("g_code", "clockwise"), [("G2", False), ("G3", True)])
def test_turning_g18_arc_direction_is_resolved_in_physical_geometry(g_code, clockwise):
    source = f"G21 G18 G190\nG0 X20 Z0\n{g_code} X40 Z-10 R10 F100\nM30"
    result = execute(source, language="fanuc_turn", source_arc_type=3)
    assert result.ok, result.diagnostics

    motion = next(item for item in result.motions if item.move in (2, 3))
    assert motion.arc is not None
    assert motion.arc.clockwise is clockwise


def test_turning_drill_fixture_executes_g83_and_g84_as_axial_cycles(fixture_text):
    result = execute(fixture_text("turning/drill.nc"), language="fanuc_turn")
    assert result.ok, result.diagnostics

    cycle_raw = {motion.source_raw for motion in result.motions if motion.source_kind == "cycle" and motion.source_raw}
    assert {raw.split()[0] for raw in cycle_raw} == {"G83", "G84"}
    assert all(
        motion.start_x == pytest.approx(motion.end_x) for motion in result.motions if motion.source_kind == "cycle"
    )
    assert min(motion.end_z for motion in result.motions) == pytest.approx(-19.09)


def test_g83_without_q_does_not_invent_pecks_and_g84_is_one_tapping_stroke_each_way():
    g83 = execute("G21 G18 G90\nG0 X10 Z0\nG83 Z-1 F10\nM30", "fanuc_turn")
    g84 = execute("G21 G18 G90\nG0 X10 Z0\nG84 Z-1 Q0.2 F10\nM30", "fanuc_turn")

    assert [(motion.move, motion.end_z) for motion in g83.motions[-2:]] == [(1, -1.0), (0, 0.0)]
    assert [(motion.move, motion.end_z) for motion in g84.motions[-2:]] == [(1, -1.0), (1, 0.0)]


def test_turning_thread_fixture_covers_g32_and_g76(fixture_text):
    result = execute(fixture_text("turning/thread.nc"), language="fanuc_turn")
    assert result.ok, result.diagnostics

    g32 = [motion for motion in result.motions if motion.source_raw and motion.source_raw.startswith("G32")]
    g76 = [
        motion
        for motion in result.motions
        if motion.source_kind == "cycle" and motion.source_raw and motion.source_raw.startswith("G76")
    ]
    assert len(g32) == 10
    assert g76
    assert {(motion.end_x, motion.end_z) for motion in g76 if motion.move == 1} >= {(59.64, -48.0), (56.0, -52.0)}


def test_turning_control_compensation_matches_computer_compensated_reference(fixture_text):
    tools = {
        "T0101": {"type": "turning", "noseRadius": 0.8, "tipOrientation": 3},
        "T0202": {"type": "turning", "noseRadius": 0.2, "tipOrientation": 3},
    }

    def finish_trace(name: str):
        result = execute(fixture_text(f"turning/{name}"), language="fanuc_turn", tools=tools)
        assert result.ok, result.diagnostics
        return [motion for motion in result.motions if motion.tool == "T0202" and motion.move == 1]

    computer = finish_trace("compensation_control_off.nc")
    control = finish_trace("compensation_control_on.nc")
    assert len(control) == len(computer)
    assert len(control) > 0

    for actual, expected in zip(control, computer):
        assert (actual.start_x, actual.start_z, actual.end_x, actual.end_z) == pytest.approx(
            (expected.start_x, expected.start_z, expected.end_x, expected.end_z), abs=0.001
        )


def test_unsupported_turning_cycle_preserves_valid_trace_and_resumes_only_from_absolute_position():
    result = execute(TURNING_PARTIAL_TRACE, language="fanuc_turn")

    assert result.ok is False
    assert [item.message.split()[0] for item in result.diagnostics] == ["G123", "G82"]
    assert [item.status for item in result.diagnostics] == ["unverified", "unsupported"]

    assert [(motion.end_x, motion.end_z) for motion in result.motions] == pytest.approx(
        [(20, 5), (18, 2), (30, 10), (25, 0)]
    )
    assert result.motions[2].source_kind == "position_resume"
    assert (result.motions[2].start_x, result.motions[2].start_z) == pytest.approx((30, 10))


def test_reference_return_and_machine_signals_are_part_of_execution_result():
    result = execute(
        TURNING_REFERENCE_AND_SIGNALS,
        language="fanuc_turn",
        emulate_g28_home=True,
        home_x=100,
        home_z=50,
        wcs_offsets={54: (100.0, 0.0), 55: (200.0, 5.0)},
    )
    assert result.ok, result.diagnostics
    assert (result.motions[0].end_x, result.motions[0].end_z) == pytest.approx((110, 0))
    assert (result.motions[1].end_x, result.motions[1].end_z) == pytest.approx((211, 6))
    assert (result.motions[-1].end_x, result.motions[-1].end_z) == pytest.approx((100, 50))
    assert [signal.kind for signal in result.signals] == [
        "spindle_cw",
        "coolant_on",
        "dwell",
        "coolant_off",
        "spindle_stop",
        "program_end",
    ]
    assert result.program_end == "M30"


def test_g30_does_not_reuse_configured_g28_reference():
    result = execute(
        "G0 X10 Z5\nG30 U0 W0\nG0 X20 Z10\nM30",
        language="fanuc_turn",
        emulate_g28_home=True,
        home_x=100,
        home_z=50,
    )
    assert result.ok, result.diagnostics
    assert all(motion.source_kind != "g30" for motion in result.motions)
    assert result.motions[-1].source_kind == "reference_resume"
    assert (result.motions[-1].end_x, result.motions[-1].end_z) == pytest.approx((20, 10))
