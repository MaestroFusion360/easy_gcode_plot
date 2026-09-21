# pylint: disable=wrong-import-position,protected-access
from io import StringIO

import pytest

pytest.importorskip("app.gcode.kernel.frontend._native_parser")
pytest.importorskip("app.gcode.kernel.milling._native_executor")

from app.gcode.kernel import execute
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
