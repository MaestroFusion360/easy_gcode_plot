"""Lexed FANUC program construction and numeric word helpers."""

from __future__ import annotations

from .ast import build_program_ast
from .lang import (
    WordToken,
    evaluate_expression,
    lex_words,
    parse_flow,
    strip_comments,
    try_literal_int,
)
from .model import Block, CycleNode, ModalSnapshot, MotionNode, Program


def resolve_cycle_profile_indices(
    blocks: tuple[Block, ...] | list[Block],
    call_index: int,
    p_label: int,
    q_label: int,
    *,
    prefer_preceding: bool = False,
) -> tuple[int, int] | None:
    """Resolve repeated P/Q labels relative to the cycle call site."""
    p_indices = [i for i, block in enumerate(blocks) if block.nlabel == p_label]
    q_indices = [i for i, block in enumerate(blocks) if block.nlabel == q_label]
    pairs = [(p, q) for p in p_indices for q in q_indices if p <= q]
    if not pairs:
        return None
    preceding = [pair for pair in pairs if pair[1] < call_index]
    following = [pair for pair in pairs if pair[0] > call_index]
    if prefer_preceding and preceding:
        return max(preceding, key=lambda pair: pair[1])
    if following:
        return min(following, key=lambda pair: pair[0])
    if preceding:
        return max(preceding, key=lambda pair: pair[1])
    return min(pairs, key=lambda pair: abs(pair[0] - call_index))


def move_for_xz_plot(move: int) -> int:
    # ConvertPlot.cs behavior for G18: swap G2/G3 in XZ plane.
    if move == 2:
        return 3
    if move == 3:
        return 2
    return move


class EvaluatedWords(dict[str, float]):
    """Backward-compatible evaluated word map that also preserves repeats/errors."""

    def __init__(self) -> None:
        super().__init__()
        self._all: dict[str, list[float]] = {}
        self.errors: list[tuple[WordToken, Exception]] = []

    def add(self, token: WordToken, value: float) -> None:
        letter = token.letter.upper()
        self._all.setdefault(letter, []).append(value)
        self[letter] = value

    def all(self, letter: str) -> tuple[float, ...]:
        return tuple(self._all.get(letter.upper(), ()))


def word_values(words: object, letter: str) -> tuple[float, ...]:
    getter = getattr(words, "all", None)
    if callable(getter):
        return tuple(float(v) for v in getter(letter))
    if isinstance(words, dict) and letter in words:
        return (float(words[letter]),)
    return ()


def literal_codes(tokens: tuple[WordToken, ...], letter: str) -> tuple[int, ...]:
    out: list[int] = []
    for token in tokens:
        if token.letter.upper() != letter.upper():
            continue
        code = try_literal_int(token.expr)
        if code is not None:
            out.append(code)
    return tuple(out)


def parse_program(lines: list[str]) -> Program:
    blocks: list[Block] = []
    motion_codes = {0, 1, 2, 3, 32, 33}
    cycle_codes = {70, 71, 72, 73, 74, 75, 76, 80, 83, 84, 90, 92, 94}
    for i, raw in enumerate(lines):
        clean = strip_comments(raw).upper()
        optional_skip = False
        clean_l = clean.lstrip()
        while clean_l.startswith("/"):
            optional_skip = True
            clean_l = clean_l[1:].lstrip()
        clean = clean_l
        words = lex_words(clean)
        word_map = {w.letter: w.expr for w in words}
        flow = parse_flow(clean)

        g_words = [w for w in words if w.letter.upper() == "G"]
        g_codes = [(w, try_literal_int(w.expr)) for w in g_words]
        motion_g_word = next((w for w, code in reversed(g_codes) if code in motion_codes), None)
        cycle_g_word = next((w for w, code in reversed(g_codes) if code in cycle_codes), None)
        cycle_g_lit = try_literal_int(cycle_g_word.expr) if cycle_g_word is not None else None

        modal = ModalSnapshot(
            g_expr=(motion_g_word.expr if motion_g_word is not None else (g_words[-1].expr if g_words else None)),
            x_expr=word_map.get("X"),
            z_expr=word_map.get("Z"),
            u_expr=word_map.get("U"),
            w_expr=word_map.get("W"),
            f_expr=word_map.get("F"),
        )

        motion_node: MotionNode | None = None
        if any(k in word_map for k in ("X", "Z", "U", "W")) or motion_g_word is not None:
            motion_node = MotionNode(
                g_expr=motion_g_word.expr if motion_g_word is not None else None,
                x_expr=word_map.get("X"),
                z_expr=word_map.get("Z"),
                u_expr=word_map.get("U"),
                w_expr=word_map.get("W"),
                i_expr=word_map.get("I"),
                k_expr=word_map.get("K"),
                r_expr=word_map.get("R"),
                f_expr=word_map.get("F"),
                a_expr=word_map.get("A"),
                c_expr=word_map.get("C"),
            )

        cycle_node: CycleNode | None = None
        if cycle_g_lit is not None:
            cycle_node = CycleNode(cycle=f"G{cycle_g_lit}", params=words)

        # N/O labels are taken only from genuine address tokens.  The bracket-aware
        # lexer therefore cannot invent O100 from the keyword GOTO100.
        nlabel = next(
            (try_literal_int(w.expr) for w in words if w.letter == "N" and try_literal_int(w.expr) is not None),
            None,
        )
        olabel = next(
            (try_literal_int(w.expr) for w in words if w.letter == "O" and try_literal_int(w.expr) is not None),
            None,
        )

        blocks.append(
            Block(
                index=i,
                raw=raw.rstrip("\n"),
                parsed_words=words,
                modal_snapshot=modal,
                motion_node=motion_node,
                cycle_node=cycle_node,
                flow_node=flow,
                nlabel=nlabel,
                olabel=olabel,
                optional_skip=optional_skip,
            )
        )

    block_tuple = tuple(blocks)
    return Program(blocks=block_tuple, ast=build_program_ast(block_tuple))


def eval_words(tokens: tuple[WordToken, ...], variables: dict[str, float]) -> EvaluatedWords:
    out = EvaluatedWords()
    for token in tokens:
        try:
            value = evaluate_expression(token.expr, variables)
        except Exception as exc:
            out.errors.append((token, exc))
            continue
        out.add(token, value)
    return out


def scaled_word(words: dict[str, float], key: str, unit_scale: float) -> float:
    return words[key] * unit_scale


def scaled_word_or(words: dict[str, float], key: str, default: float, unit_scale: float) -> float:
    if key not in words:
        return default
    return words[key] * unit_scale


def x_value_to_diameter(value: float, x_is_diameter: bool) -> float:
    return value if x_is_diameter else (value * 2.0)


def x_delta_to_diameter(value: float, x_is_diameter: bool) -> float:
    return value if x_is_diameter else (value * 2.0)


def radius_to_diameter(value: float) -> float:
    return value * 2.0


def micron_or_mm_to_mm(value: float) -> float:
    # OTC-style programs use micron integers (e.g. 10000 => 10.0 mm),
    # while many training examples already use mm-scale decimal values.
    return value / 1000.0 if abs(value) >= 100.0 else value


def try_wcs_from_gcode(gcode: int | float | None) -> int | None:
    if gcode is None:
        return None
    numeric = float(gcode)
    if not numeric.is_integer():
        return None
    code = int(numeric)
    return code if 54 <= code <= 59 else None
