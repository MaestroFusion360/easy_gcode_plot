"""Canonical AST parity, cancellation and relative large-program speed guards."""

# pylint: disable=protected-access

import gc
import sys
from dataclasses import FrozenInstanceError, replace
from statistics import median
from time import perf_counter

import pytest

from app.gcode.kernel.api.resources import ExecutionBudget, SemanticError, active_budget, checkpoint
from app.gcode.kernel.frontend import model as model_module
from app.gcode.kernel.frontend.ast import _build_program_ast_python, build_ast_node, build_program_ast
from app.gcode.kernel.frontend.model import Program
from app.gcode.kernel.frontend.program import _parse_fallback_block, _parse_program_python, parse_program

MIXED_SOURCE = """%
O100
N10 G21 G90 G17
N20 G1 X1.25 Y2 Z-3 A4 B5 C6 U7 V8 W9 I10 J11 K12 R13 F100
N30 G71 P10 Q20 U1 W2
#1=3
N40 IF[#1 EQ 3] GOTO50
N50 WHILE[#1 GT 0] DO1
#1=#1-1
END1
G65 P9000 X20 F300 T7 M8
T2 S1000
M30
O9000
M99
%
"""


@pytest.fixture
def native():
    return pytest.importorskip("app.gcode.kernel.frontend._native_parser")


def test_compiled_ast_matches_portable_builder_for_every_node_kind(native):
    program = parse_program(MIXED_SOURCE)
    reference = _build_program_ast_python(program.blocks)
    assert program.ast == reference
    assert native.build_program_ast_native(program.blocks, checkpoint) == reference
    assert {node.kind for node in program.ast.nodes} == {"empty", "meta", "control", "motion", "cycle", "flow"}
    for block, node in zip(program.blocks, reference.nodes):
        assert build_ast_node(block) == node


def test_compiled_nodes_and_shared_words_remain_frozen(native):
    program = parse_program("G1 X1 F100\nG1 X2 F100")
    first, second = program.ast.nodes
    assert first.words[0] is second.words[0]
    assert first.words[-1] is second.words[-1]
    with pytest.raises(FrozenInstanceError):
        first.x_expr = "999"
    with pytest.raises(FrozenInstanceError):
        first.words[0].expr = "2"
    with pytest.raises(TypeError):
        program.ast.nlabel_to_index[10] = 1


def test_first_label_maps_are_built_from_block_indices_in_both_builders(native):
    original = parse_program("O100\nN10 G1 X1\nN10 G1 X2\nO100\nN20 M30").blocks
    blocks = tuple(replace(block, index=block.index * 3 + 7) for block in original)
    for ast in (build_program_ast(blocks), _build_program_ast_python(blocks)):
        assert dict(ast.nlabel_to_index) == {10: 10, 20: 19}
        assert dict(ast.olabel_to_index) == {100: 7}


def test_native_parser_does_not_rebuild_ast_in_public_program_constructor(native, monkeypatch):
    def forbidden(_blocks):
        pytest.fail("Parser rebuilt an already canonical AST")

    monkeypatch.setattr(model_module, "build_program_ast", forbidden)
    program = parse_program(MIXED_SOURCE)
    assert len(program.ast.nodes) == len(program.blocks)
    assert program.ast == _build_program_ast_python(program.blocks)


def test_public_program_constructor_still_checks_supplied_ast(native):
    program = parse_program("G1 X1\nM30")
    assert Program(program.blocks, program.ast) == program
    changed = (replace(program.blocks[0], raw="G1 X999"), *program.blocks[1:])
    with pytest.raises(ValueError, match="does not match"):
        Program(changed, program.ast)


def test_python_parser_and_ast_work_without_native_extension(monkeypatch):
    # Import failure covers source installations without a compiled extension.
    monkeypatch.setitem(sys.modules, "app.gcode.kernel.frontend._native_parser", None)
    program = parse_program(MIXED_SOURCE)
    assert program == _parse_program_python(MIXED_SOURCE.splitlines())
    assert program.ast == _build_program_ast_python(program.blocks)


@pytest.mark.parametrize("builder", [build_program_ast, _build_program_ast_python])
def test_ast_builders_preserve_cooperative_cancellation(builder):
    blocks = parse_program("G1 X1\n" * 600).blocks
    checks = 0

    def cancelled():
        nonlocal checks
        checks += 1
        return checks == 2

    token = active_budget.set(ExecutionBudget(cancelled=cancelled))
    try:
        with pytest.raises(SemanticError, match="cancelled"):
            builder(blocks)
    finally:
        active_budget.reset(token)
    assert checks == 2


def _paired_medians(first, second, repeats=5):
    """Alternate order, collect outside timings and preserve global GC settings."""
    samples = [[], []]
    for repeat in range(repeats):
        order = (0, 1) if repeat % 2 == 0 else (1, 0)
        for index in order:
            gc.collect()
            start = perf_counter()
            result = (first, second)[index]()
            samples[index].append(perf_counter() - start)
            del result
    return tuple(median(values) for values in samples)


def _parse_with_portable_ast(native, source):
    """Same tokenizer and final graph, replacing only compiled AST construction."""
    blocks = native._parse_source_blocks(source, _parse_fallback_block, checkpoint)
    return Program._from_canonical_ast(blocks, _build_program_ast_python(blocks))


@pytest.mark.performance
@pytest.mark.parametrize("unique_coordinates", [False, True])
def test_large_program_keeps_compiled_ast_speedup(native, unique_coordinates, record_property):
    count = 20_000
    source = "O100\n" + "".join(
        f"N{i} G1 X{i if unique_coordinates else i % 100}.125 Y{i % 37}.25 Z-2 F100\n" for i in range(count)
    )
    blocks = native._parse_source_blocks(source, _parse_fallback_block, checkpoint)
    native_ast = native.build_program_ast_native(blocks, checkpoint)
    assert native_ast == _build_program_ast_python(blocks)
    ast_time, reference_time = _paired_medians(
        lambda: build_program_ast(blocks), lambda: _build_program_ast_python(blocks)
    )
    parse_time, reference_parse_time = _paired_medians(
        lambda: parse_program(source), lambda: _parse_with_portable_ast(native, source)
    )
    ast_ratio, parse_ratio = ast_time / reference_time, parse_time / reference_parse_time
    record_property("native_ast_seconds", ast_time)
    record_property("portable_ast_seconds", reference_time)
    record_property("native_parse_seconds", parse_time)
    record_property("portable_ast_parse_seconds", reference_parse_time)
    record_property("native_ast_to_python_ratio", ast_ratio)
    record_property("native_parse_to_portable_ast_parse_ratio", parse_ratio)
    assert ast_ratio < 0.80, f"Compiled AST lost its speedup: ratio={ast_ratio:.3f}"
    assert parse_ratio < 1.05, f"Compiled parse lost its end-to-end speedup: ratio={parse_ratio:.3f}"
