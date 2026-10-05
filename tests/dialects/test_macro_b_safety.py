"""Regression coverage for arithmetic semantics and bounded expression evaluation."""

import math
import subprocess
import sys

import pytest

from app.gcode.kernel import execute
from app.gcode.kernel.frontend.lang import evaluate_expression


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("1 AND 2", 0),
        ("1 OR 2", 3),
        ("1 XOR 3", 2),
        ("7 AND 3", 3),
        ("4 OR 1", 5),
        ("[7 AND 3] OR [4 XOR 1]", 7),
        ("[3 GT 2] AND [7 EQ 7]", 1),
    ],
)
@pytest.mark.parametrize("language", ["fanuc_mill", "fanuc_turn"])
def test_macro_bitwise_assignments(expression, expected, language):
    result = execute(f"#1={expression}\nG1 X#1 Z1 F100\nM30\n", language=language)
    assert result.ok, result.diagnostics
    assert result.motions[-1].end_x == expected


@pytest.mark.parametrize("language", ["fanuc_mill", "fanuc_turn"])
def test_bitwise_if_and_while_preserve_relational_conditions(language):
    source = """#1=7
#2=0
IF[[1 OR 2] EQ 3] GOTO10
#2=100
N10 WHILE[[#1 AND 3] GT 0] DO1
#2=#2+1
#1=#1-1
END1
G1 X#2 F100
M30
"""
    result = execute(source, language=language)
    assert result.ok, result.diagnostics
    assert result.motions[-1].end_x == 3


@pytest.mark.parametrize(
    "expression",
    [
        "9**9",
        "9**9**9",
        "9**9**9**9",
        "'a'",
        "'a' * 1000000",
        "b'abc'",
        "[1,2,3]",
        '{"x":1}',
        "True",
        "False",
        "1//2",
        "ABS.__class__",
        "EXP[1,2]",
        "1e999",
    ],
)
@pytest.mark.parametrize("language", ["fanuc_mill", "fanuc_turn"])
def test_unsafe_python_input_fails_closed(expression, language):
    result = execute(f"#1={expression}\nG1 X#1 F100\nM30", language=language)
    assert not result.ok
    assert not result.motions
    assert result.diagnostics


@pytest.mark.parametrize("expression", ["LN[0]", "LN[-1]", "EXP[1000]"])
def test_function_domain_and_overflow_are_diagnostics(expression):
    result = execute(f"#1={expression}\nG1 X#1 F100\n", language="fanuc_mill")
    assert not result.ok and result.diagnostics
    assert not result.motions


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("LN[1]", 0),
        ("EXP[1]", math.e),
        ("LN[EXP[#1]]", 2),
        ("EXP[LN[#1]]", 2),
    ],
)
def test_ln_exp_with_variables_and_nested_arguments(expression, expected):
    assert evaluate_expression(expression, {"1": 2}) == pytest.approx(expected)


@pytest.mark.parametrize("expression", ["+" * 100 + "1", "[" * 100 + "1" + "]" * 100, "1+" * 3000 + "1"])
def test_pathological_depth_and_size_are_bounded(expression):
    with pytest.raises(ValueError, match="limit"):
        evaluate_expression(expression, {})


def test_pathological_power_and_string_repetition_finish_in_isolated_process():
    script = """from app.gcode.kernel import execute
for expression in ('9**9**9**9', "'a' * 999999999"):
    result=execute('#1='+expression+'\\nG1 X#1 F100\\n', language='fanuc_mill')
    assert not result.ok and result.diagnostics and not result.motions
"""
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=10, check=False)
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("function", ["BIN", "BCD", "ADP"])
def test_unverified_functions_remain_explicitly_unsupported(function):
    with pytest.raises(ValueError, match="Unsupported"):
        evaluate_expression(f"{function}[1]", {})


@pytest.mark.parametrize("value", [-2, -1.5, -1.2, -0.5, 0, 0.5, 1.2, 1.5, 2])
def test_fix_truncates_towards_zero_and_fup_rounds_away_from_zero(value):
    assert evaluate_expression(f"FIX[{value}]", {}) == math.trunc(value)
    assert evaluate_expression(f"FUP[{value}]", {}) == math.copysign(math.ceil(abs(value)), value)


@pytest.mark.parametrize("language", ["fanuc_mill", "fanuc_turn"])
@pytest.mark.parametrize("condition,expected", [("1 GT 2", 3), ("2 GT 1", 9), ("[2+3] EQ 5", 9)])
def test_if_then_assignment_is_conditional(language, condition, expected):
    result = execute(f"#2=3\nN10 IF[{condition}]THEN#2=9\nG1 X#2 F100\nM30", language)
    assert result.ok, result.diagnostics
    assert result.motions[-1].end_x == expected


@pytest.mark.parametrize("language", ["fanuc_mill", "fanuc_turn"])
def test_false_then_does_not_evaluate_rhs_or_indirect_variable(language):
    result = execute("IF[1 GT 2]THEN#[#100]=1/0\nG1 X1 F100\nM30", language)
    assert result.ok, result.diagnostics
    assert result.motions[-1].end_x == 1


def test_true_then_supports_indirect_and_named_assignment():
    result = execute("#1=2\nIF[1 EQ 1]THEN#[#1+1]=7\nIF[#3 EQ 7]THEN#<VALUE>=9\nG1 X#<VALUE> F100\nM30", "fanuc_mill")
    assert result.ok, result.diagnostics
    assert result.motions[-1].end_x == 9


@pytest.mark.parametrize(
    "statement",
    [
        "IF[1 GT 2]THEN G0 X50",
        "IF[2 GT 1]THEN G0 X50",
        "IF 1 THEN G0 X50",
        "IF[1 GT 2] G0 X50",
        "IF[1 GT 2]THEN",
        "IF [#1 GT 3] THEN #2=9 GOTO10",
        "IF [4 GT 3] THEN #2=9 goto 10",
    ],
)
@pytest.mark.parametrize("language", ["fanuc_mill", "fanuc_turn"])
def test_unmodeled_or_malformed_if_never_executes_embedded_motion(statement, language):
    result = execute(statement + "\nG0 X99\nM30", language)
    assert not result.ok and not result.motions
    assert any(d.code == "UNSUPPORTED_MACRO_IF" and d.status == "unsupported" for d in result.diagnostics)
