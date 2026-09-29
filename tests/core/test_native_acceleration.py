# pylint: disable=wrong-import-position,protected-access
from io import StringIO

import pytest

pytest.importorskip("app.gcode.kernel.frontend._native_parser")
pytest.importorskip("app.gcode.kernel.milling._native_executor")

from app.gcode.kernel import execute
from app.gcode.kernel.ast import ControlAstNode, MotionAstNode
from app.gcode.kernel.frontend.program import _parse_program_python, parse_program
from app.gcode.kernel.milling import executor as milling_executor


def test_native_parser_matches_python_program_graph():
    source = """%
(mixed ordinary and Macro B blocks)
O100
N10 G90 G94 G17 G40 G80
N20 G1 X1.25 Y-2.5 F100
#1=3
N30 WHILE[#1 GT 0] DO1
N40 G2 X2 Y3 I0.5 J0
#1=#1-1
N50 END1
G65 P9000 A1. B2. I3. I4. D5. F100. M8 T7 X6. Y7. Z8.
M30
O9000
M99
%
"""

    assert parse_program(source) == _parse_program_python(StringIO(source))


def test_shared_ast_keeps_milling_modes_out_of_turning_cycle_nodes():
    program = parse_program("G21 G90 G17\nG94 G01 X10 Y20 F100\nY30\nV2 J1\n")

    assert isinstance(program.ast.nodes[0], ControlAstNode)
    assert isinstance(program.ast.nodes[1], MotionAstNode)
    assert program.ast.nodes[1].g_code == 1
    assert program.ast.nodes[1].y_expr == "20"
    assert isinstance(program.ast.nodes[2], MotionAstNode)
    assert program.ast.nodes[2].g_code is None
    assert program.ast.nodes[2].y_expr == "30"
    assert isinstance(program.ast.nodes[3], MotionAstNode)
    assert program.ast.nodes[3].v_expr == "2"
    assert program.ast.nodes[3].j_expr == "1"


def test_native_milling_loop_matches_python_fallback(monkeypatch):
    source = """G21 G17 G90 G94
G0 X0 Y0 Z5
G1 Z0 F100
X1 Y0
X2 Y1
G2 X3 Y0 I0.5 J-0.5
X4 Y-1 I0.5 J-0.5
M30
"""
    accelerated = execute(source, language="fanuc_mill")
    assert milling_executor._execute_simple_blocks is not None

    monkeypatch.setattr(milling_executor, "_execute_simple_blocks", None)
    fallback = execute(source, language="fanuc_mill")

    assert accelerated == fallback


def test_native_milling_first_simple_block_preserves_program_start_event(monkeypatch):
    source = """X1
Y2
M30
"""
    accelerated = execute(source, language="fanuc_mill")
    assert milling_executor._execute_simple_blocks is not None

    monkeypatch.setattr(milling_executor, "_execute_simple_blocks", None)
    fallback = execute(source, language="fanuc_mill")

    assert accelerated == fallback
    assert [event.kind for event in accelerated.events].count("program_start") == 1
    assert accelerated.events[0].source_block == 0


@pytest.mark.parametrize(
    "source",
    [
        "G21 G90 G94\nG0 X0 Y0 Z2\nG1 X5 F120\nY-3\nG91 X2\nG90 Y0\nM30\n",
        "G20 G90 G94\nG0 X0 Y0 Z0.5\nG1 X1 F12\nY1\nG21 X30 F300\nM30\n",
        "G21 G90 G54\nG0 X1 Y2\nG55 X3\nG1 Y4 F100\nG54 X5\nM30\n",
        "X1\nY2\nG1 X3 F100\nM30\n",
    ],
)
def test_native_milling_modal_transitions_match_python_fallback(monkeypatch, source):
    accelerated = execute(source, language="fanuc_mill")
    assert milling_executor._execute_simple_blocks is not None

    monkeypatch.setattr(milling_executor, "_execute_simple_blocks", None)
    fallback = execute(source, language="fanuc_mill")

    assert accelerated == fallback


def test_native_milling_g65_matches_python_fallback(monkeypatch):
    source = """G21 G17 G90 G94
G0 X0 Y0 Z5
G65 P9000 A10. B2. X100. F500. T7 M8
G1 X20 Y0 F100
M30
O9000
G1 X#1 Y#2 F100
M99
"""
    accelerated = execute(source, language="fanuc_mill")
    assert milling_executor._execute_simple_blocks is not None

    monkeypatch.setattr(milling_executor, "_execute_simple_blocks", None)
    fallback = execute(source, language="fanuc_mill")

    assert accelerated == fallback


def test_native_milling_polar_fallback_matches_python_execution(monkeypatch):
    source = """G21 G17 G90
G0 X5 Y5 Z2
G16
G0 X10 Y30
G91 Y120
Y120
G15 G90
G1 X2 Y3 F100
M30
"""
    accelerated = execute(source, language="fanuc_mill")
    assert milling_executor._execute_simple_blocks is not None

    monkeypatch.setattr(milling_executor, "_execute_simple_blocks", None)
    fallback = execute(source, language="fanuc_mill")

    assert accelerated == fallback
