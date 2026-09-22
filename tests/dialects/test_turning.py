from __future__ import annotations

import pytest
from gcode_samples import TURNING_PARTIAL_TRACE, TURNING_REFERENCE_AND_SIGNALS

from app.gcode.kernel import execute


def test_basic_turning_cycles_fixture_executes_facing_roughing_and_grooving(fixture_text):
    source = fixture_text("turning/basic_turning_cycles.NC")
    result = execute(source, language="fanuc_turn")
    assert result.ok, result.diagnostics

    cycle_motions = [motion for motion in result.motions if motion.cycle_generated]
    cycle_raw = {motion.source_raw for motion in cycle_motions if motion.source_raw}

    assert cycle_motions
    assert all(motion.source_kind == "cycle" for motion in cycle_motions)
    assert any(raw.startswith("G71") for raw in cycle_raw)
    assert any(raw.startswith("G72") for raw in cycle_raw)
    assert any(raw.startswith("G75") for raw in cycle_raw)
    assert min(motion.end_z for motion in result.motions) == pytest.approx(-224.7)


@pytest.mark.parametrize(
    ("stock_x", "profile_x", "finish_u", "expected_rough_x"),
    [
        (100.0, 80.0, 0.2, 80.2),
        (70.0, 90.0, -0.2, 89.8),
    ],
)
def test_g71_signed_u_leaves_allowance_on_the_od_or_id_material_side(stock_x, profile_x, finish_u, expected_rough_x):
    source = f"""\
G21 G18 G90
G0 X{stock_x:g} Z1
G71 U2 R0.2
G71 P10 Q20 U{finish_u:g} W0 F0.25
N10 G0 X{profile_x:g}
N20 G1 Z-10
M30
"""

    result = execute(source, language="fanuc_turn")
    assert result.ok, result.diagnostics
    contour_passes = [
        motion
        for motion in result.motions
        if motion.cycle_generated
        and motion.move == 1
        and abs(motion.end_z - motion.start_z) > 10.0
        and motion.start_x == pytest.approx(motion.end_x)
    ]
    assert contour_passes
    assert contour_passes[-1].end_x == pytest.approx(expected_rough_x)


def test_g70_uses_cycle_call_position_to_approach_the_finish_profile():
    source = """\
G21 G18 G90
G0 X200 Z220
G0 X160 Z180
G71 U7 R1
G71 P14 Q20 U4 W2 F0.3
N14 G0 X40
G1 W-40
X60 W-30
W-20
X100 W-10
W-20
N20 X140 W-20
G70 P14 Q20
M30
"""

    result = execute(source, language="fanuc_turn")
    assert result.ok, result.diagnostics

    finish = [
        motion
        for motion in result.motions
        if motion.source_kind == "cycle" and motion.source_raw and motion.source_raw.startswith("G70")
    ]
    assert finish
    assert finish[0].move == 0
    assert (finish[0].start_x, finish[0].start_z) == pytest.approx((160.0, 180.0))
    assert (finish[0].end_x, finish[0].end_z) == pytest.approx((40.0, 180.0))
    assert finish[1].move == 1
    assert (finish[1].start_x, finish[1].start_z) == pytest.approx((40.0, 180.0))
    assert (finish[1].end_x, finish[1].end_z) == pytest.approx((40.0, 140.0))


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
        "T0101": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.8, "tipOrientation": 3},
        "T0202": {"type": "diamond_80", "applications": ["od"], "noseRadius": 0.2, "tipOrientation": 3},
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


def test_turning_g53_uses_machine_coordinates_without_changing_active_wcs():
    source = """\
G21 G18 G54
G0 X20 Z0
G53 G0 X0 Z0
G1 X10 Z-5 F100
M30
"""
    result = execute(source, language="fanuc_turn", wcs_offsets={54: (100.0, 50.0)})

    assert result.ok, result.diagnostics
    assert len(result.motions) == 3
    assert (result.motions[0].end_x, result.motions[0].end_z) == pytest.approx((120.0, 50.0))
    assert result.motions[1].source_kind == "g53"
    assert (result.motions[1].end_x, result.motions[1].end_z) == pytest.approx((0.0, 0.0))
    assert result.execution_steps[2].active_wcs == 54
    assert (result.motions[2].end_x, result.motions[2].end_z) == pytest.approx((110.0, 45.0))


def test_turning_source_trace_applies_compact_a_c_r_direct_programming():
    source = "\n".join(
        [
            "G21G18G190",
            "G0X100Z1",
            "G1Z0F100",
            "X110C1",
            "Z-10",
            "X112A-45R1",
            "Z-20",
            "M30",
        ]
    )
    result = execute(source, language="fanuc_turn")

    assert result.ok, result.diagnostics

    chamfer = [motion for motion in result.motions if motion.source_raw == "X110C1"]
    actual_chamfer = [(motion.move, motion.start_x, motion.start_z, motion.end_x, motion.end_z) for motion in chamfer]
    assert actual_chamfer == pytest.approx(
        [
            (1, 100.0, 0.0, 109.0, 0.0),
            (1, 109.0, 0.0, 110.0, -1.0),
        ]
    )

    angled = [motion for motion in result.motions if motion.source_raw == "X112A-45R1"]
    assert any(motion.move == 1 and motion.end_z < -11.0 for motion in angled)
    fillet = next(motion for motion in angled if motion.move in (2, 3))
    assert fillet.radius == pytest.approx(1.0)
    assert fillet.arc is not None

    # A infers the missing Z coordinate before the following corner transition.
    next_axial = next(motion for motion in result.motions if motion.source_raw == "Z-20")
    assert next_axial.start_z < -12.0


def test_turning_direct_programming_chamfer_can_consume_following_segment_exactly():
    result = execute(
        "G21G18G190\nG0X10Z0\nG1X20C2F100\nZ-2\nM30",
        language="fanuc_turn",
    )

    assert result.ok, result.diagnostics
    chamfer = [motion for motion in result.motions if motion.source_raw == "G1X20C2F100"]
    assert [
        (motion.move, motion.start_x, motion.start_z, motion.end_x, motion.end_z) for motion in chamfer
    ] == pytest.approx(
        [
            (1, 10.0, 0.0, 18.0, 0.0),
            (1, 18.0, 0.0, 20.0, -2.0),
        ]
    )
    assert not [motion for motion in result.motions if motion.source_raw == "Z-2"]


def test_turning_direct_programming_r_does_not_reinterpret_g2_g3_arc_radius():
    result = execute(
        "G21G18G190\nG0X20Z0\nG3X40Z-10R10F100\nM30",
        language="fanuc_turn",
        source_arc_type=3,
    )

    assert result.ok, result.diagnostics
    arcs = [motion for motion in result.motions if motion.move in (2, 3)]
    assert len(arcs) == 1
    assert arcs[0].source_raw == "G3X40Z-10R10F100"
    assert arcs[0].radius == pytest.approx(10.0)


def test_threading_flag_follows_modal_g32_until_another_motion_code_cancels_it():
    result = execute(
        "G21 G18 G99\nG0 X20 Z0\nG32 Z-4 F2\nZ-6\nG1 Z-8\nZ-10\nM30\n",
        language="fanuc_turn",
    )
    assert result.ok, result.diagnostics

    cutting = [motion for motion in result.motions if motion.move == 1]
    assert [motion.threading for motion in cutting] == [True, True, False, False]
    assert [motion.feed for motion in cutting[:2]] == pytest.approx([2.0, 2.0])


def test_threading_flag_follows_modal_g92_depth_blocks():
    result = execute(
        "G21 G18 G99\nG0 X20 Z2\nG92 X18 Z-10 F1.5\nX17.5\nX17.0\nG0 X30\nM30\n",
        language="fanuc_turn",
    )
    assert result.ok, result.diagnostics

    thread_cuts = [motion for motion in result.motions if motion.move == 1]
    assert len(thread_cuts) == 3
    assert all(motion.threading for motion in thread_cuts)
    assert [motion.feed for motion in thread_cuts] == pytest.approx([1.5, 1.5, 1.5])


def test_g94_facing_cycle_is_not_published_as_threading():
    result = execute(
        "G21 G18 G99\nG0 X40 Z2\nG94 X20 F0.2\nM30\n",
        language="fanuc_turn",
    )
    assert result.ok, result.diagnostics

    assert any(motion.move == 1 for motion in result.motions)
    assert not any(motion.threading for motion in result.motions)
