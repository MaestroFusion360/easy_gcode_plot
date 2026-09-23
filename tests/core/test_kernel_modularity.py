"""Regression contracts for the modular cycle and compensation kernel."""

from __future__ import annotations

from app.gcode.kernel import milling_compensation as legacy_milling_compensation
from app.gcode.kernel import tool_compensation as legacy_tool_compensation
from app.gcode.kernel.api_types import TraceMotion
from app.gcode.kernel.compensation.milling import apply_milling_cutter_compensation_with_owners
from app.gcode.kernel.compensation.turning import apply_tool_nose_compensation
from app.gcode.kernel.milling.cycles import execute_milling_cycle
from app.gcode.kernel.milling.state import MillState
from app.gcode.kernel.model import Motion
from app.gcode.kernel.program import parse_program
from app.gcode.kernel.runtime.cycles import CycleContext, apply_cycle_outcome
from app.gcode.kernel.turning import cycles as turning_cycles
from app.gcode.kernel.turning.cycles import adapt_cycle_emission, g71, g72, g76, g90, g92, g94


def test_lathe_cycle_package_exports_cycle_specific_implementations():
    """Runtime-facing imports stay stable while implementation lives per cycle."""
    assert turning_cycles.build_g71_roughing is g71.build_g71_roughing
    assert turning_cycles.build_g72_facing is g72.build_g72_facing
    assert turning_cycles.build_g76_threading is g76.build_g76_threading
    assert turning_cycles.add_g90_longitudinal_pass is g90.add_g90_longitudinal_pass
    assert turning_cycles.add_g92_thread_pass is g92.add_g92_thread_pass
    assert turning_cycles.add_g94_facing_pass is g94.add_g94_facing_pass
    assert turning_cycles.adapt_cycle_emission is adapt_cycle_emission


def test_simple_turning_cycle_modules_preserve_exact_motion_sequence():
    motions: list[Motion] = []
    g90.add_g90_longitudinal_pass(motions, 40.0, 2.0, 30.0, -10.0, 0.2)
    assert [(motion.move, motion.end.x, motion.end.z) for motion in motions] == [
        (0, 30.0, 2.0),
        (1, 30.0, -10.0),
        (0, 40.0, -10.0),
        (0, 40.0, 2.0),
    ]

    motions.clear()
    g92.add_g92_thread_pass(motions, 40.0, 2.0, 30.0, -10.0, 1.5)
    assert [(motion.move, motion.end.x, motion.end.z) for motion in motions] == [
        (0, 30.0, 2.0),
        (1, 30.0, -10.0),
        (0, 40.0, -10.0),
        (0, 40.0, 2.0),
    ]
    assert motions[1].feed == 1.5


def test_compensation_packages_preserve_public_entry_points_and_owner_mapping():
    assert callable(apply_tool_nose_compensation)

    motions = [
        TraceMotion(1, 0.0, 0.0, 10.0, 0.0, start_y=0.0, end_y=0.0, plane=17, compensation_mode=41, tool="T1"),
        TraceMotion(1, 10.0, 0.0, 10.0, 0.0, start_y=0.0, end_y=10.0, plane=17, compensation_mode=41, tool="T1"),
        TraceMotion(1, 10.0, 0.0, 0.0, 0.0, start_y=10.0, end_y=10.0, plane=17, compensation_mode=40, tool="T1"),
    ]
    output, owners = apply_milling_cutter_compensation_with_owners(
        motions,
        {"T1": {"type": "mill_flat", "diameter": 2.0}},
        [10, 20, 30],
    )

    assert len(output) == len(owners)
    assert owners[0] == 10
    assert owners[-1] == 30
    assert all(owner in {10, 20, 30} for owner in owners)


def test_legacy_compensation_module_paths_reexport_public_entry_points():
    assert legacy_tool_compensation.apply_tool_nose_compensation is apply_tool_nose_compensation
    assert (
        legacy_milling_compensation.apply_milling_cutter_compensation_with_owners
        is apply_milling_cutter_compensation_with_owners
    )


def test_milling_cycle_outcome_keeps_expansion_and_state_commit_separate():
    block = parse_program("G84 X10 Y20 Z-5 R1 F100").blocks[0]
    state = MillState(z=5.0, cycle=80)
    outcome = execute_milling_cycle(
        CycleContext(
            block=block,
            words={"X": 10.0, "Y": 20.0, "Z": -5.0, "R": 1.0, "F": 100.0},
            codes=(84,),
            machine_state=state,
            modal_cycle_state=state,
            coordinate_context={},
        )
    )

    assert outcome.handled
    assert state.cycle == 80
    assert (state.x, state.y, state.z) == (0.0, 0.0, 5.0)
    assert [signal.kind for signal in outcome.signals] == ["spindle_sync", "spindle_reverse"]
    assert outcome.position_update == (("x", 10.0), ("y", 20.0), ("z", 1.0))

    apply_cycle_outcome(state, outcome)
    assert state.cycle == 84
    assert (state.x, state.y, state.z) == (10.0, 20.0, 1.0)
