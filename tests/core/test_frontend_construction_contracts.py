"""Source labels, native facts and repeated G words survive frontend construction."""

import pytest

from app.gcode.kernel.frontend.ast import _build_program_ast_python
from app.gcode.kernel.frontend.program import _parse_program_python
from app.gcode.kernel.frontend.sinumerik import parse_sinumerik_program


@pytest.mark.parametrize("portable", [False, True])
def test_sinumerik_block_augmentation_preserves_labels_and_native_identity(portable, monkeypatch):
    if portable:
        from app import native  # pylint: disable=import-outside-toplevel

        # Disable the cached extension only for this portable-backend contract.
        # pylint: disable-next=protected-access
        monkeypatch.setitem(native._extensions, "parser", native.NativeExtension(None, "portable contract check"))
    source = "/N10 G1 X=R1+2 F100\nIF R1>0 GOTO N20\nN20 M30"
    program = parse_sinumerik_program(source)
    assert [b.raw for b in program.blocks] == source.splitlines()
    assert [b.index for b in program.blocks] == [0, 1, 2]
    assert [b.nlabel for b in program.blocks] == [10, None, 20]
    assert [b.optional_skip for b in program.blocks] == [True, False, False]
    assert dict(program.ast.nlabel_to_index) == {10: 0, 20: 2}
    assert program.ast == _build_program_ast_python(program.blocks)
    assert dict((word.letter, word.expr) for word in program.blocks[0].parsed_words)["X"] == "R1+2"
    assert program.blocks[1].native_syntax.flow_target == 20
    for block, node in zip(program.blocks, program.ast.nodes, strict=True):
        assert node.native_syntax is block.native_syntax
        assert [(w.letter, w.expr) for w in node.words] == [(w.letter, w.expr) for w in block.parsed_words]


def test_sinumerik_custom_parser_fallback_does_not_treat_jump_operand_as_source_label():
    source = "N10 G1 X2\nGOTO N20\nN20 M30"
    program = parse_sinumerik_program(source, token_parser=lambda _raw: None)
    assert [b.nlabel for b in program.blocks] == [10, None, 20]
    assert all(b.native_syntax is None for b in program.blocks)
    assert dict(program.ast.nlabel_to_index) == {10: 0, 20: 2}


@pytest.mark.parametrize(
    "source,cycle,motion",
    [
        ("N1 G71 G70 P10 Q20", "G70", None),
        ("N2 G70 G1 X2", "G70", "1"),
        ("N3 G71.0 P10 Q20", "G71", None),
        ("N4 G71.5 G#1 X2", None, None),
        ("N5 G71 G65 P9000 X2", None, None),
    ],
)
def test_python_parser_retains_last_literal_cycle_and_g65_precedence(source, cycle, motion):
    block = _parse_program_python([source]).blocks[0]
    assert (block.cycle_node.cycle if block.cycle_node is not None else None) == cycle
    assert (block.motion_node.g_expr if block.motion_node is not None else None) == motion
    if "G65" in source:
        assert block.motion_node is None and block.modal_snapshot.x_expr is None
