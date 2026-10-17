"""Native source facts survive construction for each shared address node kind."""

import dataclasses
from dataclasses import replace

import pytest

from app.gcode.kernel.frontend.ast import NativeMillingSyntax, build_ast_node
from app.gcode.kernel.frontend.program import parse_program


@pytest.mark.parametrize(
    "source,kind",
    [
        ("G1 X2", "motion"),
        ("G71 P10 Q20", "cycle"),
        ("#1=2", "flow"),
        ("M30", "control"),
        ("T1", "meta"),
        ("", "empty"),
    ],
)
def test_shared_address_nodes_retain_native_syntax_without_changing_address_fields(source, kind, monkeypatch):
    block = parse_program(source + "\n").blocks[0]
    expected = build_ast_node(block)
    syntax = NativeMillingSyntax(supa=True, absolute_center=("I",))
    native_block = replace(block, native_syntax=syntax)
    replacements = []

    def counted_replace(*args, **kwargs):
        replacements.append(type(args[0]))
        return replace(*args, **kwargs)

    monkeypatch.setattr(dataclasses, "replace", counted_replace)
    actual = build_ast_node(native_block)
    assert actual.kind == kind
    assert actual.native_syntax is syntax
    assert actual == replace(expected, native_syntax=syntax)
    assert not replacements, "Shared native AST nodes must be constructed once"
