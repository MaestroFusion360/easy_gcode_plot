"""Regression contracts pinning kernel public API and critical execution paths.

These tests assert observable behavior (motion sequences, step ownership, event
streams and re-export identity) so the structural refactor of
``app.gcode.kernel`` cannot silently change semantics.
"""

from __future__ import annotations

# Re-export identity is asserted with local imports.
# pylint: disable=import-outside-toplevel
from app.gcode import kernel
from app.gcode.kernel import execute

G71_ROUGHING = """\
G21 G18
T0101
G0 X40 Z2
G71 U1.5 R0.5
G71 P100 Q110 U0.5 W0.1 F0.2
N100 G0 X10
G1 Z-20
N110 G1 X40
G70 P100 Q110
M30
"""

MILLING_CYCLES = """\
G21 G90 G17
G0 X0 Y0 Z5
G81 X0 Y0 Z-2 R1 F100
X10 Y0
G80
G83 X30 Y0 Z-4 R1 Q1 F100
G80
M30
"""


def test_kernel_public_api_surface_is_stable():
    expected = {
        "AstNode",
        "AstWord",
        "ControlAstNode",
        "CycleAstNode",
        "Diagnostic",
        "ExecutionEvent",
        "ExecutionResult",
        "ExecutionStep",
        "FlowAstNode",
        "MachineSignal",
        "MetaAstNode",
        "Motion",
        "MotionAstNode",
        "Point2",
        "Program",
        "ProgramAst",
        "SemanticInstruction",
        "TraceMotion",
        "execute",
    }
    assert set(kernel.__all__) == expected
    for name in expected:
        assert hasattr(kernel, name), name


def test_model_and_api_type_reexports_are_identical_objects():
    from app.gcode.kernel import Motion, Point2, TraceMotion
    from app.gcode.kernel.api_types import TraceMotion as LegacyTraceMotion
    from app.gcode.kernel.model import Motion as LegacyMotion
    from app.gcode.kernel.model import Point2 as LegacyPoint2

    assert LegacyMotion is Motion
    assert LegacyPoint2 is Point2
    assert LegacyTraceMotion is TraceMotion


def test_turning_g71_g70_execution_path_is_stable():
    result = execute(G71_ROUGHING)

    assert result.ok, result.diagnostics
    assert result.complete is True
    assert result.program_end == "M30"
    assert len(result.motions) == 54
    assert sum(step.emitted_count for step in result.execution_steps) == len(result.motions)
    assert [(motion.move, round(motion.end_x, 3), round(motion.end_z, 3)) for motion in result.motions[-3:]] == [
        (1, 10.0, -20.0),
        (1, 40.0, -20.0),
        (0, 40.0, 2.0),
    ]
    assert {motion.tool for motion in result.motions} == {"T0101"}


def test_milling_drilling_cycle_execution_path_is_stable():
    result = execute(MILLING_CYCLES, "fanuc_mill")

    assert result.ok, result.diagnostics
    assert result.complete is True
    assert result.program_end == "M30"
    assert len(result.motions) == 18
    assert sum(step.emitted_count for step in result.execution_steps) == len(result.motions)
    assert all(motion.cycle_generated for motion in result.motions[1:])
    assert result.motions[0].source_kind == "motion"


def test_macro_b_while_loop_executes_expected_iterations():
    source = "#1=0\n#2=0\nWHILE[#1 LT 3] DO1\n#1=#1+1\n#2=#2+#1\nG1 X#1 F100\nEND1\nM30"
    result = execute(source)

    assert result.ok, result.diagnostics
    assert [(motion.move, motion.end_x) for motion in result.motions] == [(1, 1.0), (1, 2.0), (1, 3.0)]
    assert result.execution_steps[-1].source_block == 7


def test_milling_tool_change_emits_deterministic_events():
    result = execute("T1 M6\nG0 X10 Y0\nM30", "fanuc_mill")

    assert result.ok, result.diagnostics
    tool_changes = [event for event in result.events if event.kind == "tool_change"]
    assert len(tool_changes) == 1
    assert tool_changes[0].tool == "T1"
    assert result.motions[-1].tool == "T1"
