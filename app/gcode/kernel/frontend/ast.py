from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

from ..api.resources import checkpoint, checkpointed

if TYPE_CHECKING:
    from .lang import WordToken
    from .model import Block

WORD_CACHE_LIMIT = 4096


@dataclass(frozen=True, slots=True)
class AstWord:
    letter: str
    expr: str
    int_code: int | None = None


@dataclass(frozen=True, slots=True)
class NativeMillingSyntax:
    """Immutable SINUMERIK source facts, shared by Block and canonical AST."""

    kind: str = "words"
    supa: bool = False
    cycle_code: int | None = None
    cycle_args: tuple[str, ...] = ()
    parameter_assignment: tuple[int, str] | None = None
    incremental_rotary: tuple[str, ...] = ()
    direct_rotary: tuple[str, ...] = ()
    absolute_center: tuple[str, ...] = ()
    real_declarations: tuple[str, ...] = ()
    named_assignments: tuple[tuple[str, str], ...] = ()
    named_tool: str | None = None
    feed_normal: bool = False
    ignored_diameter_modes: tuple[str, ...] = ()
    ignored_native_commands: tuple[str, ...] = ()
    incremental_linear: tuple[str, ...] = ()
    cip: bool = False
    intermediate_absolute: tuple[str, ...] = ()
    intermediate_incremental: tuple[str, ...] = ()
    frame_command: str | None = None
    frame_values: tuple[tuple[str, str], ...] = ()
    flow_condition: tuple | None = None
    flow_target: int | None = None
    syntax_error: str | None = None
    scalar_expressions: tuple[tuple[str, tuple], ...] = ()


@dataclass(frozen=True, slots=True)
class AstNode:
    kind: str
    block_index: int
    raw: str
    nlabel: int | None = None
    olabel: int | None = None
    words: tuple[AstWord, ...] = ()
    native_syntax: NativeMillingSyntax | None = field(default=None, kw_only=True)


@dataclass(frozen=True, slots=True)
class SinumerikAstNode(AstNode):
    """Native declaration/metadata node; the source syntax is never lowered."""


@dataclass(frozen=True, slots=True)
class SinumerikFlowAstNode(SinumerikAstNode):
    """Native instruction-pointer operation, independent of Macro B."""


@dataclass(frozen=True, slots=True)
class MotionAstNode(AstNode):
    g_code: int | None = None
    x_expr: str | None = None
    z_expr: str | None = None
    u_expr: str | None = None
    w_expr: str | None = None
    i_expr: str | None = None
    k_expr: str | None = None
    r_expr: str | None = None
    f_expr: str | None = None
    a_expr: str | None = None
    c_expr: str | None = None
    y_expr: str | None = None
    v_expr: str | None = None
    j_expr: str | None = None
    b_expr: str | None = None


@dataclass(frozen=True, slots=True)
class CycleAstNode(AstNode):
    cycle: str = ""
    params: tuple[object, ...] = ()


@dataclass(frozen=True, slots=True)
class FlowAstNode(AstNode):
    flow_kind: str = ""
    condition: str | None = None
    target_label: int | None = None
    loop_id: int | None = None
    var_key: str | None = None
    value_expr: str | None = None


@dataclass(frozen=True, slots=True)
class ControlAstNode(AstNode):
    g_codes: tuple[int, ...] = ()
    m_codes: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class MetaAstNode(AstNode):
    # Non-motion/cycle/flow codes (for example N/O/T/S and other words).
    letters: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProgramAst:
    nodes: tuple[AstNode, ...]
    nlabel_to_index: Mapping[int, int]
    olabel_to_index: Mapping[int, int]

    def __post_init__(self):
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "nlabel_to_index", MappingProxyType(dict(self.nlabel_to_index)))
        object.__setattr__(self, "olabel_to_index", MappingProxyType(dict(self.olabel_to_index)))


def _int_code(expr: str | None) -> int | None:
    if expr is None:
        return None
    try:
        val = float(expr)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(val):
        return None
    rounded = round(val)
    return int(rounded) if abs(val - rounded) <= 1e-9 else None


def _build_ast_words(parsed_words: tuple[WordToken, ...], cache: dict) -> tuple[AstWord, ...]:
    """Intern immutable repeated words in a bounded, construction-local cache."""
    out = []
    for token in parsed_words:
        letter, expr = token.letter.upper(), token.expr
        key = (letter, expr)
        word = cache.get(key) if letter not in {"N", "O"} else None
        if word is None:
            word = AstWord(letter, expr, _int_code(expr))
            if letter not in {"N", "O"}:
                if len(cache) >= WORD_CACHE_LIMIT:
                    cache.clear()
                cache[key] = word
        out.append(word)
    return tuple(out)


def _motion_code(expr, cache):
    word = cache.get(("G", expr))
    return word.int_code if word is not None else _int_code(expr)


def build_ast_node(block: Block, *, _word_cache: dict | None = None) -> AstNode:
    """Derive an AST node directly from a concrete authoritative Block."""
    cache = {} if _word_cache is None else _word_cache
    words = _build_ast_words(block.parsed_words, cache)
    common = (block.index, block.raw, block.nlabel, block.olabel, words)
    if block.native_syntax is not None:
        return _build_native_ast_node(block, common, cache)
    return _build_address_ast_node(block, common, cache)


def _build_address_ast_node(block, common, cache):
    words = common[-1]
    flow, cycle, motion = block.flow_node, block.cycle_node, block.motion_node
    if flow is not None:
        return FlowAstNode(
            "flow",
            *common,
            flow.kind,
            flow.condition,
            flow.target_label,
            flow.loop_id,
            flow.var_key,
            flow.value_expr,
        )
    if cycle is not None:
        return CycleAstNode("cycle", *common, cycle.cycle, words)
    if motion is not None:
        return MotionAstNode(
            "motion",
            *common,
            _motion_code(motion.g_expr, cache),
            motion.x_expr,
            motion.z_expr,
            motion.u_expr,
            motion.w_expr,
            motion.i_expr,
            motion.k_expr,
            motion.r_expr,
            motion.f_expr,
            motion.a_expr,
            motion.c_expr,
            motion.y_expr,
            motion.v_expr,
            motion.j_expr,
            motion.b_expr,
        )
    return _control_or_meta_node(block, words)


def _build_native_ast_node(block, common, cache):
    """Retain native declarations and syntax without lowering source commands."""
    from dataclasses import replace  # pylint: disable=import-outside-toplevel

    syntax = block.native_syntax
    if syntax.kind in ("while", "endwhile", "goto", "if_goto", "invalid_flow"):
        return SinumerikFlowAstNode("sinumerik_flow", *common, native_syntax=syntax)
    if syntax.kind != "words":
        return SinumerikAstNode("sinumerik", *common, native_syntax=syntax)
    # Reuse the common motion/control builder for shared address semantics.
    node = _build_address_ast_node(block, common, cache)
    return replace(node, native_syntax=syntax)


def _control_or_meta_node(block, words):
    """Reuse parsed integer codes rather than evaluating each control word twice."""
    g_codes = tuple(word.int_code for word in words if word.letter == "G" and word.int_code is not None)
    m_codes = tuple(word.int_code for word in words if word.letter == "M" and word.int_code is not None)
    common = (block.index, block.raw, block.nlabel, block.olabel, words)
    if g_codes or m_codes:
        return ControlAstNode("control", *common, g_codes, () if 65 in g_codes else m_codes)
    if words:
        return MetaAstNode("meta", *common, tuple(word.letter for word in words))
    return AstNode("empty", *common)


def _build_program_ast_python(blocks: tuple[Block, ...]) -> ProgramAst:
    """Portable reference builder; nodes and both label maps share one pass."""
    nodes, nlabels, olabels, cache = [], {}, {}, {}
    for _position, block in checkpointed(blocks):
        nodes.append(build_ast_node(block, _word_cache=cache))
        if isinstance(block.nlabel, int):
            nlabels.setdefault(block.nlabel, block.index)
        if isinstance(block.olabel, int):
            olabels.setdefault(block.olabel, block.index)
    return ProgramAst(tuple(nodes), nlabels, olabels)


def build_program_ast(blocks: tuple[Block, ...]) -> ProgramAst:
    """Build the immutable view in Cython when available, with a portable fallback."""
    from app.native import native_symbol  # pylint: disable=import-outside-toplevel

    build_program_ast_native = native_symbol("parser", "build_program_ast_native")
    if build_program_ast_native is None:
        return _build_program_ast_python(blocks)
    return build_program_ast_native(blocks, checkpoint)
