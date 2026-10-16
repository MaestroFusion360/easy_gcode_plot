"""Independent Klartext syntax, canonical AST and source-location contracts."""

from dataclasses import FrozenInstanceError, replace

import pytest

from app.gcode.export.common import ExportOptions
from app.gcode.export.expanded import convert_resolved_program
from app.gcode.kernel import execute
from app.gcode.kernel.api.resources import ExecutionBudget, SemanticError, active_budget, checkpoint
from app.gcode.kernel.frontend.ast import (
    HeidenhainCenterNode,
    HeidenhainContourNode,
    HeidenhainCycleNode,
    HeidenhainLabelNode,
    HeidenhainMotionNode,
    HeidenhainParameterNode,
    HeidenhainProgramNode,
    HeidenhainStockNode,
    HeidenhainToolNode,
    _build_program_ast_python,
    build_ast_node,
)
from app.gcode.kernel.frontend.heidenhain import HeidenhainParseError, parse_heidenhain_program
from app.gcode.kernel.frontend.heidenhain_expression import (
    HeidenhainExpressionError,
    compile_heidenhain_expression,
)
from app.gcode.kernel.frontend.model import Program


def test_native_commands_remain_typed_without_iso_lowering():
    source = (
        "BEGIN PGM AST MM\nBLK FORM 0.1 Z X-10 Y-10 Z-10\nTOOL CALL 1 Z\n"
        "CC X0 Y0\nAPPR LT X5 Y0 LEN5\nCP IPA+450 IZ+3 DR+\nL X10 A+25\nEND PGM AST MM"
    )
    program = parse_heidenhain_program(source)
    assert len(program.blocks) == len(source.splitlines())
    assert isinstance(program.ast.nodes[0], HeidenhainProgramNode)
    assert isinstance(program.ast.nodes[1], HeidenhainStockNode)
    assert isinstance(program.ast.nodes[2], HeidenhainToolNode)
    assert isinstance(program.ast.nodes[3], HeidenhainCenterNode)
    assert isinstance(program.ast.nodes[4], HeidenhainContourNode)
    assert isinstance(program.ast.nodes[5], HeidenhainMotionNode)
    assert program.blocks[5].native_syntax.command == "CP"
    assert program.blocks[5].native_syntax.word("IPA").expression.source == "+450"
    assert program.blocks[5].native_syntax.word("IZ").expression.source == "+3"
    assert program.blocks[6].native_syntax.word("A").expression.source == "+25"
    assert all(block.parsed_words == () and block.motion_node is None for block in program.blocks)
    assert program.ast == _build_program_ast_python(program.blocks)


def test_label_and_program_block_numbers_are_separate():
    program = parse_heidenhain_program(
        '0 BEGIN PGM LABELS MM\n7 Q1=5\n2 Q2=SIN(Q1)\n3 LBL "finish"\n'
        '4 FN 9: IF Q1 EQU 5 GOTO LBL "finish"\n5 LBL 7\n6 END PGM LABELS MM'
    )
    assert isinstance(program.ast.nodes[1], HeidenhainParameterNode)
    assert isinstance(program.ast.nodes[3], HeidenhainLabelNode)
    assert program.ast.nlabel_to_index[7] == 1
    assert dict(program.ast.heidenhain_label_to_index) == {7: 5, "finish": 3}
    assert dict(program.ast.olabel_to_index) == {}
    assert program.blocks[4].native_syntax.condition.value == "EQU"
    assert program.blocks[4].native_syntax.label == "finish"
    assert program.blocks[2].native_syntax.assignment[1].kind == "function"


@pytest.mark.parametrize("code", [200, 201, 202, 203, 206, 207, 208, 209])
def test_multiline_cycle_retains_every_parameter_location_and_call_link(code):
    source = f"0 CYCL DEF {code} EXAMPLE ~\n1 Q200=+2 ~ ; clearance\n; note\n2 Q201=-Q1\n3 CYCL CALL M3"
    program = parse_heidenhain_program(source)
    definition = program.blocks[0].native_syntax
    assert isinstance(program.ast.nodes[0], HeidenhainCycleNode)
    assert definition.cycle_code == code
    assert [(p.name, p.block_index, p.column) for p in definition.cycle_parameters] == [("Q200", 1, 2), ("Q201", 3, 2)]
    assert definition.cycle_parameters[1].expression.source == "-Q1"
    assert program.blocks[1].raw == "1 Q200=+2 ~ ; clearance"
    assert program.blocks[1].native_syntax.continued
    assert program.blocks[3].native_syntax.cycle_definition_index == 0
    assert program.blocks[4].native_syntax.cycle_definition_index == 0
    assert program.blocks[4].native_syntax.cycle_code == code


def test_cycle_scope_ends_before_later_general_q_assignments():
    program = parse_heidenhain_program("CYCL DEF 200 DRILLING\nQ200=2\nCYCL CALL\nQ200=9")
    assert len(program.blocks[0].native_syntax.cycle_parameters) == 1
    assert program.blocks[3].native_syntax.cycle_definition_index is None


def test_legacy_cycle_subdefinition_and_m99_keep_definition_identity():
    program = parse_heidenhain_program("CYCL DEF 9.0 DWELL TIME\nCYCL DEF 9.1 Q1+2\nL X1 M99")
    assert program.blocks[1].native_syntax.cycle_definition_index == 0
    assert program.blocks[1].native_syntax.word("VALUE").expression.source == "Q1+2"
    assert program.blocks[2].native_syntax.cycle_definition_index == 0


def test_quoted_names_comments_optional_skip_and_address_columns():
    source = '  / 12 TOOL CALL "small; cutter" Z S+Q1 ; spindle\n13 L X-0.5Y+.25 FMAX ; end'
    program = parse_heidenhain_program(source)
    tool, motion = program.blocks
    assert tool.optional_skip and tool.nlabel == 12
    assert tool.native_syntax.tool == "small; cutter"
    assert tool.native_syntax.comment == " spindle"
    word = motion.native_syntax.word("Y")
    assert word.source == "Y+.25"
    assert motion.raw[word.column : word.column + len(word.source)] == word.source


def test_repeat_and_dynamic_label_are_retained_without_expansion():
    program = parse_heidenhain_program("LBL 3\nL X+Q1\nCALL LBL 3 REP Q2+1\nCALL LBL Q3")
    assert len(program.blocks) == 4
    assert program.blocks[2].native_syntax.repeat.source == "Q2+1"
    assert program.blocks[3].native_syntax.label_expression.value == "Q3"


def test_program_numbers_do_not_become_subprogram_labels():
    program = parse_heidenhain_program("12 LBL 7\n20 L X1\n30 CALL LBL 7")
    assert dict(program.ast.nlabel_to_index) == {12: 0, 20: 1, 30: 2}
    assert dict(program.ast.heidenhain_label_to_index) == {7: 0}


def test_len_address_is_not_swallowed_by_preceding_coordinate_expression():
    syntax = parse_heidenhain_program("APPR LT X+Q1 Y-2 LEN+7 RR F150").blocks[0].native_syntax
    assert syntax.word("Y").expression.source == "-2"
    assert syntax.word("LEN").expression.source == "+7"


def test_fn_div_and_parameter_scopes_keep_native_semantics():
    program = parse_heidenhain_program("FN 4: QL2=+Q1 DIV +3\nQR4=QL2+1")
    assert program.blocks[0].native_syntax.assignment[0] == "QL2"
    assert program.blocks[0].native_syntax.assignment[1].value == "DIV"
    assert program.blocks[1].native_syntax.assignment[0] == "QR4"


@pytest.mark.parametrize("source", ["Q2000=1", "QL500=2", "QR500=3", "L XQ2000", "999999999999 L X1"])
def test_out_of_range_parameters_and_block_numbers_have_controlled_diagnostics(source):
    with pytest.raises(HeidenhainParseError):
        parse_heidenhain_program(source)


def test_cycle_parameter_aliases_are_not_accepted_as_distinct_slots():
    with pytest.raises(HeidenhainParseError, match="Duplicate cycle parameter"):
        parse_heidenhain_program("CYCL DEF 200 DRILLING\nQ200=2\nQ0200=3")


def test_cycle_call_can_remain_unresolved_until_a_runtime_exists():
    syntax = parse_heidenhain_program("CYCL CALL M3").blocks[0].native_syntax
    assert syntax.command == "CYCL CALL"
    assert syntax.cycle_definition_index is None and syntax.cycle_code is None


def test_heidenhain_native_execution_is_enabled_for_supported_paths():
    result = execute("BEGIN PGM TEST MM\nL X1\nEND PGM TEST MM", "fanuc_mill", source_dialect="heidenhain")
    assert result.ok and result.complete and len(result.motions) == 1
    assert result.source_dialect == "heidenhain"


@pytest.mark.parametrize(
    "source",
    [
        "L X+Q1 Y-2.5 IZ+3 R0 FMAX M3",
        "l x+q1 y-2.5 iz+3 r0 fmax m3",
        "  42   L   X +Q1   Y -2.5   IZ +3   R0 FMAX M3 ; unchanged facts",
        "L IZ+3 Y-2.5 X+Q1 M3 FMAX R0",
    ],
)
def test_case_spacing_comments_and_address_order_keep_native_facts(source):
    syntax = parse_heidenhain_program(source).blocks[0].native_syntax
    assert syntax.command == "L"
    assert syntax.word("X").expression.operands[0].value == "Q1"
    assert syntax.word("Y").expression.operands[0].value == "2.5"
    assert syntax.word("IZ").expression.operands[0].value == "3"
    assert {word.address for word in syntax.words} == {"X", "Y", "IZ", "R0", "FMAX", "M"}


def test_operator_precedence_and_division_by_zero_remain_syntax_only():
    expression = compile_heidenhain_expression("Q1+2*Q2")
    assert expression.value == "+"
    assert expression.operands[1].value == "*"
    division = parse_heidenhain_program("FN 4: Q1=7 DIV 0").blocks[0].native_syntax.assignment[1]
    assert division.value == "DIV" and division.operands[1].value == "0"


def test_extremely_long_fn_code_is_reported_as_a_frontend_error():
    with pytest.raises(HeidenhainParseError):
        parse_heidenhain_program("FN " + "9" * 5000 + ": Q1=2")


def test_m_functions_and_their_parameters_are_separate_from_motion_addresses():
    syntax = parse_heidenhain_program("L X+5 RL F120 M120 LA+6 M3").blocks[0].native_syntax
    first, second = syntax.machine_functions
    assert first.code.value == "120" and second.code.value == "3"
    assert [word.address for word in first.parameters] == ["LA"]
    assert first.parameters[0].expression.source == "+6"
    assert second.parameters == ()
    assert syntax.word("F").expression.source == "120"


@pytest.mark.parametrize(
    "source,address",
    [
        ("L X5 F120 M140 MB+7 F600", "MB"),
        ("L X5 FMAX M140 MB MAX FMAX", "MB MAX"),
    ],
)
def test_m140_feed_is_scoped_to_retraction_without_overwriting_motion_feed(source, address):
    syntax = parse_heidenhain_program(source).blocks[0].native_syntax
    function = syntax.machine_functions[0]
    assert function.code.value == "140"
    assert function.parameters[0].address == address
    assert function.parameters[1].address in {"F", "FMAX"}
    assert len([word for word in syntax.words if word.address in {"F", "FMAX"}]) == 2


@pytest.mark.parametrize("source", ["L X1 LA3", "L X1 M3 LA4", "L X1 M120 MB5", "L X1 M140 MB2 MB MAX"])
def test_m_function_parameters_must_belong_to_their_function(source):
    with pytest.raises(HeidenhainParseError):
        parse_heidenhain_program(source)


@pytest.mark.parametrize("source", ["Q1=2 ~\nQ2=3", "CYCL CALL ~\nQ200=2"])
def test_continuation_markers_cannot_invent_a_cycle_definition(source):
    with pytest.raises(HeidenhainParseError) as caught:
        parse_heidenhain_program(source)
    assert caught.value.status == "unsupported"


@pytest.mark.parametrize("source", ["L X1 IX2", "LP PA30 IPA10", "LP PR10 IPR2"])
def test_absolute_and_incremental_forms_cannot_duplicate_one_coordinate(source):
    with pytest.raises(HeidenhainParseError, match="Duplicate Klartext address"):
        parse_heidenhain_program(source)


def test_quoted_program_name_keeps_semicolon_and_original_source():
    source = 'BEGIN PGM "part;one" MM\nEND PGM "part;one" MM'
    program = parse_heidenhain_program(source)
    assert program.blocks[0].native_syntax.program_name == "part;one"
    assert program.blocks[0].raw == source.splitlines()[0]


@pytest.mark.parametrize(
    "source",
    [
        "L X1 X2",
        "L X1 DR+",
        "C X1 Y2",
        "CR X1 DR+",
        "CR X1 R2 DR+ DR-",
        "L X1 R0 RR",
        "L X1 F100 FMAX",
        "L XNAN",
        'TOOL CALL "broken Z',
        "FN 1: Q1 = 3",
        "FN 9: IF Q1 GT 3 GOTO LBL 1\nLBL 1",
        "Q1=",
        "Q1=Q2+",
        "LBL 1\nLBL 1",
        "CALL LBL 8",
        "CALL LBL 0",
        "LBL 3 REP 2",
        "CYCL DEF 200 EXAMPLE ~",
        "CYCL DEF 200 EXAMPLE ~\nL X1",
        "CYCL DEF 200 EXAMPLE ~\nFN 0: Q1=2",
        "CYCL DEF 200 EXAMPLE\nQ200=2\nQ200=3",
        "BEGIN PGM A MM",
        "L X1\nBEGIN PGM A MM\nEND PGM A MM",
        "BLK FORM 0.1 Z X0 Y0",
    ],
)
def test_malformed_syntax_has_physical_source_diagnostic(source):
    with pytest.raises(HeidenhainParseError) as caught:
        parse_heidenhain_program(source)
    error = caught.value
    assert error.code == "INVALID_HEIDENHAIN_SYNTAX"
    assert error.line >= 1 and error.column >= 1
    assert error.raw == source.splitlines()[error.line - 1]


@pytest.mark.parametrize("source", ["G1 X1", "PLANE VECTOR BX0 BY0 BZ1", "FN 18: SYSREAD Q1=ID1", "FZ0.1"])
def test_unknown_constructs_fail_closed(source):
    with pytest.raises(HeidenhainParseError) as caught:
        parse_heidenhain_program(source)
    assert caught.value.code == "UNSUPPORTED_HEIDENHAIN_SYNTAX"
    assert caught.value.status == "unsupported"


def test_second_physical_line_reports_error_without_losing_cycle_lines():
    with pytest.raises(HeidenhainParseError) as caught:
        parse_heidenhain_program("CYCL DEF 200 DRILLING ~\n  Q200 = Q1 + ; missing operand")
    assert caught.value.line == 2
    assert caught.value.column > 9
    assert caught.value.raw == "  Q200 = Q1 + ; missing operand"


def test_blocks_ast_words_expressions_and_label_maps_are_immutable():
    program = parse_heidenhain_program("LBL 4\nL X+Q1")
    with pytest.raises(FrozenInstanceError):
        program.blocks[1].native_syntax.command = "G1"
    with pytest.raises(FrozenInstanceError):
        program.blocks[1].native_syntax.words[0].expression.value = "2"
    with pytest.raises(TypeError):
        program.ast.heidenhain_label_to_index[4] = 99
    assert Program(program.blocks, program.ast) == program
    changed = (program.blocks[0], replace(program.blocks[1], raw="L X999"))
    with pytest.raises(ValueError, match="does not match"):
        Program(changed, program.ast)


def test_python_and_compiled_ast_builders_share_native_nodes(fixture_text):
    native = pytest.importorskip("app.gcode.kernel.frontend._native_parser")
    program = parse_heidenhain_program(fixture_text("milling/heidenhain/1001.h"))
    assert native.build_program_ast_native(program.blocks, checkpoint) == _build_program_ast_python(program.blocks)
    assert [build_ast_node(block) for block in program.blocks] == list(program.ast.nodes)


def test_frontend_works_without_native_extension(monkeypatch):
    monkeypatch.setattr("app.native.native_symbol", lambda *_args: None)
    program = parse_heidenhain_program("CC X0 Y0\nCP IPA+360 DR+")
    assert program.ast == _build_program_ast_python(program.blocks)


def test_parsing_remains_cooperatively_cancellable():
    token = active_budget.set(ExecutionBudget(cancelled=lambda: True))
    try:
        with pytest.raises(SemanticError) as caught:
            parse_heidenhain_program("L X1\n" * 500)
    finally:
        active_budget.reset(token)
    assert caught.value.code == "EXECUTION_CANCELLED"


def test_cycle_max_is_a_native_symbol_and_not_a_numeric_q_assignment(fixture_text):
    program = parse_heidenhain_program(fixture_text("milling/heidenhain/cycles_itnc530.h"))
    block = next(block for block in program.blocks if "Q208=MAX" in block.raw)
    name, expression = block.native_syntax.assignment
    assert name == "Q208" and expression.kind == "cycle_feed" and expression.value == "MAX"
    assert block.native_syntax.cycle_code == 203
    native = pytest.importorskip("app.gcode.kernel.frontend._native_parser")
    assert native.build_program_ast_native(program.blocks, checkpoint) == _build_program_ast_python(program.blocks)


@pytest.mark.parametrize("source", ["Q208=MAX", "Q1=MAX", "FN 0: Q208=MAX", "CYCL DEF 203\nQ201=MAX"])
def test_max_is_not_accepted_as_an_arbitrary_scalar(source):
    with pytest.raises(HeidenhainParseError):
        parse_heidenhain_program(source)


@pytest.mark.parametrize("source", ["FN 6: Q1=COS Q2", "FN 7: Q1=SIN Q2", "FN 6: Q1=Q2"])
def test_trigonometric_fn_keeps_its_native_function_contract(source):
    with pytest.raises(HeidenhainParseError, match="trigonometric operation"):
        parse_heidenhain_program(source)


def test_legacy_coordinate_cycles_do_not_capture_following_general_q_assignments():
    program = parse_heidenhain_program(
        "CYCL DEF 7.0\nCYCL DEF 7.1 X50\nCYCL DEF 10.0\nCYCL DEF 10.1 ROT0\nQ35=9\nL XQ35"
    )
    assert program.blocks[2].native_syntax.cycle_parameters == ()
    assert program.blocks[4].native_syntax.cycle_definition_index is None
    assert program.blocks[4].native_syntax.cycle_code is None


@pytest.mark.parametrize("cycle", [81, 82, 83, 84, 85, 86])
def test_current_heidenhain_exporter_programs_parse_to_native_ast(cycle):
    result = execute(f"T2 M6\nS1200 M3\nG0 X0 Y0 Z5\nG{cycle} X12 Z-6 R2 F120\nG80\nM30", "fanuc_mill")
    assert result.ok
    source = convert_resolved_program(result, "heidenhain_itnc530", ExportOptions())
    program = parse_heidenhain_program(source)
    assert program.blocks[0].native_syntax.command == "BEGIN PGM"
    assert program.blocks[-1].native_syntax.command == "END PGM"
    assert any(isinstance(node, HeidenhainCycleNode) for node in program.ast.nodes)


@pytest.mark.parametrize("arc_mode", [0, 1, 2, 3])
def test_current_exporter_arcs_and_helices_parse_without_rewriting(arc_mode):
    result = execute("T1 M6\nG0 X9 Y0 Z0\nG3 X0 Y9 Z-2 I-9 J0 F100\nM30", "fanuc_mill")
    assert result.ok
    source = convert_resolved_program(result, "heidenhain_itnc530", ExportOptions(arc_mode=arc_mode))
    program = parse_heidenhain_program(source)
    assert all(block.motion_node is None for block in program.blocks)
    assert any(isinstance(node, HeidenhainMotionNode) for node in program.ast.nodes)


@pytest.mark.parametrize(
    "source,kind,value",
    [
        ("Q1+2*Q2", "binary", "+"),
        ("-2^2", "unary", "-"),
        ("SQRT(Q1^2 + Q2^2)", "function", "SQRT"),
        ("SIN +Q1", "function", "SIN"),
        ("(Q1+2)/[Q2-3]", "binary", "/"),
        ("QL1 MOD 3", "binary", "MOD"),
        ("LEN(Q1,Q2)", "function", "LEN"),
        ("Q1 LEN Q2", "binary", "LEN"),
        ("Q1 GE QR2", "binary", "GE"),
    ],
)
def test_q_expressions_preserve_structure_without_evaluation(source, kind, value):
    expression = compile_heidenhain_expression(source)
    assert (expression.kind, expression.value, expression.source) == (kind, value, source)


@pytest.mark.parametrize(
    "source", ["", "Q1+", "SIN()", "LEN(Q1)", "Q1 Q2", "Q1;M2", "__import__('os')", "(" * 80 + "1" + ")" * 80]
)
def test_bad_or_excessively_nested_expressions_fail_safely(source):
    with pytest.raises(HeidenhainExpressionError):
        compile_heidenhain_expression(source)
