from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AstWord:
    letter: str
    expr: str
    int_code: int | None = None


@dataclass(frozen=True)
class AstNode:
    kind: str
    block_index: int
    raw: str
    nlabel: int | None = None
    olabel: int | None = None
    words: tuple[AstWord, ...] = ()


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class CycleAstNode(AstNode):
    cycle: str = ""
    params: tuple[object, ...] = ()


@dataclass(frozen=True)
class FlowAstNode(AstNode):
    flow_kind: str = ""
    condition: str | None = None
    target_label: int | None = None
    loop_id: int | None = None
    var_key: str | None = None
    value_expr: str | None = None


@dataclass(frozen=True)
class ControlAstNode(AstNode):
    g_codes: tuple[int, ...] = ()
    m_codes: tuple[int, ...] = ()


@dataclass(frozen=True)
class MetaAstNode(AstNode):
    # Non-motion/cycle/flow codes (for example N/O/T/S and other words).
    letters: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProgramAst:
    nodes: tuple[AstNode, ...]
    nlabel_to_index: dict[int, int]
    olabel_to_index: dict[int, int]


def _int_code(expr: str | None) -> int | None:
    if expr is None:
        return None
    try:
        val = float(expr)
    except Exception:
        return None
    if abs(val - round(val)) > 1e-9:
        return None
    return int(round(val))


def _build_ast_words(parsed_words: tuple[object, ...]) -> tuple[AstWord, ...]:
    out: list[AstWord] = []
    for w in parsed_words:
        letter = str(getattr(w, "letter", "")).upper()
        expr = str(getattr(w, "expr", ""))
        out.append(AstWord(letter=letter, expr=expr, int_code=_int_code(expr)))
    return tuple(out)


def build_program_ast(blocks: tuple[object, ...]) -> ProgramAst:
    nodes: list[AstNode] = []
    nlabel_to_index: dict[int, int] = {}
    olabel_to_index: dict[int, int] = {}
    for block in blocks:
        idx = int(getattr(block, "index"))
        raw = str(getattr(block, "raw", ""))
        nlabel = getattr(block, "nlabel", None)
        olabel = getattr(block, "olabel", None)
        flow = getattr(block, "flow_node", None)
        cycle = getattr(block, "cycle_node", None)
        motion = getattr(block, "motion_node", None)
        words = tuple(getattr(block, "parsed_words", ()))
        ast_words = _build_ast_words(words)

        if isinstance(nlabel, int) and nlabel not in nlabel_to_index:
            nlabel_to_index[nlabel] = idx
        if isinstance(olabel, int) and olabel not in olabel_to_index:
            olabel_to_index[olabel] = idx

        if flow is not None:
            nodes.append(
                FlowAstNode(
                    kind="flow",
                    block_index=idx,
                    raw=raw,
                    nlabel=nlabel,
                    olabel=olabel,
                    words=ast_words,
                    flow_kind=str(getattr(flow, "kind", "")),
                    condition=getattr(flow, "condition", None),
                    target_label=getattr(flow, "target_label", None),
                    loop_id=getattr(flow, "loop_id", None),
                    var_key=getattr(flow, "var_key", None),
                    value_expr=getattr(flow, "value_expr", None),
                )
            )
            continue

        if cycle is not None:
            nodes.append(
                CycleAstNode(
                    kind="cycle",
                    block_index=idx,
                    raw=raw,
                    nlabel=nlabel,
                    olabel=olabel,
                    words=ast_words,
                    cycle=str(getattr(cycle, "cycle", "")),
                    params=ast_words,
                )
            )
            continue

        if motion is not None:
            nodes.append(
                MotionAstNode(
                    kind="motion",
                    block_index=idx,
                    raw=raw,
                    nlabel=nlabel,
                    olabel=olabel,
                    words=ast_words,
                    g_code=_int_code(getattr(motion, "g_expr", None)),
                    x_expr=getattr(motion, "x_expr", None),
                    z_expr=getattr(motion, "z_expr", None),
                    u_expr=getattr(motion, "u_expr", None),
                    w_expr=getattr(motion, "w_expr", None),
                    i_expr=getattr(motion, "i_expr", None),
                    k_expr=getattr(motion, "k_expr", None),
                    r_expr=getattr(motion, "r_expr", None),
                    f_expr=getattr(motion, "f_expr", None),
                    a_expr=getattr(motion, "a_expr", None),
                    c_expr=getattr(motion, "c_expr", None),
                )
            )
            continue

        g_codes: list[int] = []
        m_codes: list[int] = []
        for w in words:
            letter = str(getattr(w, "letter", ""))
            expr = getattr(w, "expr", None)
            code = _int_code(expr)
            if code is None:
                continue
            if letter == "G":
                g_codes.append(code)
            elif letter == "M":
                m_codes.append(code)
        if g_codes or m_codes:
            nodes.append(
                ControlAstNode(
                    kind="control",
                    block_index=idx,
                    raw=raw,
                    nlabel=nlabel,
                    olabel=olabel,
                    words=ast_words,
                    g_codes=tuple(g_codes),
                    m_codes=tuple(m_codes),
                )
            )
            continue

        if ast_words:
            nodes.append(
                MetaAstNode(
                    kind="meta",
                    block_index=idx,
                    raw=raw,
                    nlabel=nlabel,
                    olabel=olabel,
                    words=ast_words,
                    letters=tuple(w.letter for w in ast_words),
                )
            )
        else:
            nodes.append(
                AstNode(
                    kind="empty",
                    block_index=idx,
                    raw=raw,
                    nlabel=nlabel,
                    olabel=olabel,
                    words=(),
                )
            )

    return ProgramAst(
        nodes=tuple(nodes),
        nlabel_to_index=nlabel_to_index,
        olabel_to_index=olabel_to_index,
    )
