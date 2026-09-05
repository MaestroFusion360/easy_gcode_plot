from __future__ import annotations

# Expressions are parsed through a restricted AST before evaluation; explicit
# dispatch returns keep the Macro B grammar readable.
# pylint: disable=eval-used,too-many-return-statements,superfluous-parens
import ast
import math
import re
from dataclasses import dataclass

ASSIGN_RE = re.compile(r"^\s*#(?:(\d+)|<([A-Z_][A-Z0-9_]*)>)\s*=\s*(.+?)\s*$", re.IGNORECASE)
IF_GOTO_RE = re.compile(r"^\s*IF\s*\[(.+)\]\s*GOTO\s*(\d+)\s*$", re.IGNORECASE)
GOTO_RE = re.compile(r"^\s*GOTO\s*(\d+)\s*$", re.IGNORECASE)
WHILE_RE = re.compile(r"^\s*WHILE\s*\[(.+)\]\s*DO\s*(\d+)\s*$", re.IGNORECASE)
END_RE = re.compile(r"^\s*END\s*(\d+)\s*$", re.IGNORECASE)
HASH_NUM_RE = re.compile(r"#(\d+)")
HASH_NAME_RE = re.compile(r"#<([A-Z_][A-Z0-9_]*)>", re.IGNORECASE)
NUMERIC_LITERAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


class UndefinedMacroVariableError(ValueError):
    """Raised when a Macro B variable reference has no runtime value."""


@dataclass(frozen=True)
class WordToken:
    letter: str
    expr: str


@dataclass(frozen=True)
class FlowNode:
    kind: str
    condition: str | None = None
    target_label: int | None = None
    loop_id: int | None = None
    var_key: str | None = None
    value_expr: str | None = None


def strip_comments(line: str) -> str:
    out = []
    in_paren = False
    for ch in line:
        if ch == "(":
            in_paren = True
            continue
        if ch == ")":
            in_paren = False
            continue
        if ch == ";" and not in_paren:
            break
        if not in_paren:
            out.append(ch)
    return "".join(out).strip()


def _is_word_start(clean: str, pos: int) -> bool:
    """Return True when *pos* is a CNC address, not a letter in a keyword/function.

    FANUC programs freely concatenate words (``G18G21G40``), while Macro B uses
    identifiers such as ``SIN`` and flow keywords such as ``GOTO``.  Treat a
    letter as an address only when it is not part of an identifier and the text
    following the address begins like a FANUC word expression.
    """
    if pos < 0 or pos >= len(clean) or not ("A" <= clean[pos] <= "Z"):
        return False
    if pos > 0 and (clean[pos - 1].isalpha() or clean[pos - 1] == "_"):
        return False
    j = pos + 1
    while j < len(clean) and clean[j].isspace():
        j += 1
    if j >= len(clean):
        return False
    if clean[j] == "=":
        j += 1
        while j < len(clean) and clean[j].isspace():
            j += 1
        if j >= len(clean):
            return False
    return clean[j] in "+-.#0123456789["


def lex_words(line: str) -> tuple[WordToken, ...]:
    """Lex CNC address words while preserving Macro B expressions.

    The previous lexer split at every A-Z character.  That corrupted expressions
    such as ``X[#1+SIN[#2]]`` and misread ``GOTO100`` as an O word.  This scanner
    is bracket-aware and only recognizes real address starts at bracket depth 0.
    """
    clean = line.strip().upper()
    if not clean:
        return ()

    starts: list[int] = []
    depth = 0
    i = 0
    while i < len(clean):
        ch = clean[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth = max(0, depth - 1)
        elif depth == 0 and _is_word_start(clean, i):
            starts.append(i)
        i += 1

    if not starts:
        return ()

    out: list[WordToken] = []
    for idx, pos in enumerate(starts):
        nxt = starts[idx + 1] if idx + 1 < len(starts) else len(clean)
        letter = clean[pos]
        raw = clean[pos + 1 : nxt].strip()
        if raw.startswith("="):
            raw = raw[1:].strip()
        if letter in ("N", "O"):
            m_label = re.match(r"^[+-]?\d+(?:\.0+)?", raw)
            raw = m_label.group(0) if m_label else raw
        if raw:
            out.append(WordToken(letter=letter, expr=raw))
    return tuple(out)


def parse_flow(clean: str) -> FlowNode | None:
    if not clean:
        return None

    # Flow statements may carry a normal N block label.  Strip only that label;
    # O labels remain program/subprogram declarations and are not flow prefixes.
    flow_text = re.sub(r"^\s*N[+-]?\d+(?:\.0+)?\s*", "", clean, count=1, flags=re.IGNORECASE)

    m_assign = ASSIGN_RE.match(flow_text)
    if m_assign:
        num_key, name_key, rhs = m_assign.groups()
        key = num_key if num_key is not None else (name_key or "").upper()
        return FlowNode(kind="assign", var_key=key, value_expr=rhs.strip())

    m_if = IF_GOTO_RE.match(flow_text)
    if m_if:
        cond, target = m_if.groups()
        return FlowNode(kind="if_goto", condition=cond.strip(), target_label=int(target))

    m_goto = GOTO_RE.match(flow_text)
    if m_goto:
        return FlowNode(kind="goto", target_label=int(m_goto.group(1)))

    m_while = WHILE_RE.match(flow_text)
    if m_while:
        cond, loop_id = m_while.groups()
        return FlowNode(kind="while", condition=cond.strip(), loop_id=int(loop_id))

    m_end = END_RE.match(flow_text)
    if m_end:
        return FlowNode(kind="end", loop_id=int(m_end.group(1)))

    return None


def _matching_square_bracket(expr: str, open_pos: int) -> int:
    if open_pos >= len(expr) or expr[open_pos] != "[":
        raise ValueError("Expected '['")
    depth = 0
    for pos in range(open_pos, len(expr)):
        if expr[pos] == "[":
            depth += 1
        elif expr[pos] == "]":
            depth -= 1
            if depth == 0:
                return pos
    raise ValueError("Unclosed '[' in Macro B expression")


def _rewrite_fanuc_atan2(expr: str) -> str:
    """Rewrite FANUC ``ATAN[y]/[x]`` into a two-argument function call."""
    out = expr
    search_from = 0
    while True:
        upper = out.upper()
        start = upper.find("ATAN[", search_from)
        if start < 0:
            return out
        first_open = start + 4
        first_close = _matching_square_bracket(out, first_open)
        pos = first_close + 1
        while pos < len(out) and out[pos].isspace():
            pos += 1
        if pos >= len(out) or out[pos] != "/":
            search_from = first_close + 1
            continue
        pos += 1
        while pos < len(out) and out[pos].isspace():
            pos += 1
        if pos >= len(out) or out[pos] != "[":
            search_from = first_close + 1
            continue
        second_open = pos
        second_close = _matching_square_bracket(out, second_open)
        first = out[first_open + 1 : first_close]
        second = out[second_open + 1 : second_close]
        replacement = f"ATAN2[{first},{second}]"
        out = out[:start] + replacement + out[second_close + 1 :]
        search_from = start + len(replacement)


def _translate_expr(expr: str) -> str:
    t = _rewrite_fanuc_atan2(expr.upper().strip())
    t = t.replace("<>", "!=")
    # FANUC posts routinely omit spaces: ``#1LT#3`` and ``#7LE#3`` are
    # valid.  Python-style word boundaries therefore cannot be used here.
    for token, replacement in (
        ("XOR", "^"),
        ("AND", " and "),
        ("MOD", "%"),
        ("EQ", "=="),
        ("NE", "!="),
        ("GE", ">="),
        ("LE", "<="),
        ("GT", ">"),
        ("LT", "<"),
        ("OR", " or "),
    ):
        t = t.replace(token, replacement)
    t = t.replace("[", "(").replace("]", ")")
    return t


def _macro_variable_value(key: str, variables: dict[str, float]) -> float:
    if key == "0":
        return 0.0
    if key not in variables:
        raise UndefinedMacroVariableError(f"Undefined macro variable #{key}")
    return float(variables[key])


def _rightmost_indirect_span(expr: str) -> tuple[int, int, str] | None:
    """Return the rightmost balanced ``#[...]`` span and its inner expression."""
    start = expr.rfind("#[")
    if start < 0:
        return None

    depth = 0
    for pos in range(start + 1, len(expr)):
        ch = expr[pos]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return start, pos + 1, expr[start + 2 : pos]
    raise ValueError("Unclosed indirect macro variable reference")


def _indirect_variable_value(inner: str, variables: dict[str, float]) -> float:
    index_value = evaluate_expression(inner, variables)
    if not float(index_value).is_integer():
        raise ValueError(f"Indirect macro variable index must be integer: {index_value}")
    return _macro_variable_value(str(int(index_value)), variables)


def _expand_variables(expr: str, variables: dict[str, float]) -> str:
    out = expr
    guard = 0

    while (span := _rightmost_indirect_span(out)) is not None:
        guard += 1
        if guard > 128:
            raise ValueError("Indirect macro variable nesting is too deep")
        start, end, inner = span
        if not inner.strip():
            raise ValueError("Empty indirect macro variable reference")
        value = _indirect_variable_value(inner, variables)
        out = out[:start] + str(value) + out[end:]

    def repl_name(mo: re.Match[str]) -> str:
        name = mo.group(1).upper()
        if name not in variables:
            raise UndefinedMacroVariableError(f"Undefined macro variable #<{name}>")
        return str(variables[name])

    out = HASH_NAME_RE.sub(repl_name, out)

    def repl_num(mo: re.Match[str]) -> str:
        return str(_macro_variable_value(mo.group(1), variables))

    out = HASH_NUM_RE.sub(repl_num, out)
    return out


def _fanuc_round(value: float) -> float:
    """Round to nearest integer with .5 away from zero, matching FANUC Macro B."""
    return float(math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5))


def _fanuc_xor(left: float, right: float) -> float:
    return float(int(left) ^ int(right))


SAFE_FUNCS = {
    "ABS": abs,
    "SQRT": math.sqrt,
    "SIN": lambda x: math.sin(math.radians(x)),
    "COS": lambda x: math.cos(math.radians(x)),
    "TAN": lambda x: math.tan(math.radians(x)),
    "ATAN": lambda x: math.degrees(math.atan(x)),
    "ATAN2": lambda y, x: math.degrees(math.atan2(y, x)),
    "FIX": lambda x: math.floor(x),
    "FUP": lambda x: math.ceil(x),
    "ROUND": _fanuc_round,
    "MIN": min,
    "MAX": max,
    "XOR": _fanuc_xor,
}

SAFE_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.FloorDiv,
    ast.UAdd,
    ast.USub,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Gt,
    ast.GtE,
    ast.Lt,
    ast.LtE,
    ast.BitXor,
)


class _FanucExpressionTransformer(ast.NodeTransformer):
    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        node = self.generic_visit(node)
        if isinstance(node.op, ast.BitXor):
            return ast.copy_location(
                ast.Call(
                    func=ast.Name(id="XOR", ctx=ast.Load()),
                    args=[node.left, node.right],
                    keywords=[],
                ),
                node,
            )
        return node


def _safe_eval(expr: str) -> float:
    tree = ast.parse(expr, mode="eval")
    tree = ast.fix_missing_locations(_FanucExpressionTransformer().visit(tree))
    for node in ast.walk(tree):
        if not isinstance(node, SAFE_NODES):
            raise ValueError(f"Unsupported expression node: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Unsupported call target")
            if node.func.id not in SAFE_FUNCS:
                raise ValueError(f"Unsupported function: {node.func.id}")
        if isinstance(node, ast.Name) and node.id not in SAFE_FUNCS:
            raise ValueError(f"Unsupported name: {node.id}")

    value = eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}}, SAFE_FUNCS)
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Non-finite expression result")
    return value


def evaluate_expression(expr: str, variables: dict[str, float]) -> float:
    raw = expr.strip()
    if not raw:
        return 0.0
    if NUMERIC_LITERAL_RE.fullmatch(raw):
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError("Non-finite numeric word")
        return value
    expanded = _expand_variables(raw, variables)
    translated = _translate_expr(expanded)
    return _safe_eval(translated)


def validate_expression_syntax(expr: str) -> None:
    """Validate a Macro B expression without requiring runtime variable values."""
    raw = expr.strip()
    if not raw:
        raise ValueError("Empty expression")
    # FANUC numeric words commonly use zero-padded integer forms (G01, M03,
    # T0606, O0001).  Python's AST rejects those as decimal literals even though
    # they are perfectly valid CNC values, so accept plain numeric literals first.
    if NUMERIC_LITERAL_RE.fullmatch(raw):
        float(raw)
        return
    # Validate indirect references from the inside out.  Each ``#[expr]`` is a
    # variable lookup whose index is itself a normal Macro B expression.
    probe = raw
    guard = 0
    while (span := _rightmost_indirect_span(probe)) is not None:
        guard += 1
        if guard > 128:
            raise ValueError("Indirect macro variable nesting is too deep")
        start, end, inner = span
        if not inner.strip():
            raise ValueError("Empty indirect macro variable reference")
        validate_expression_syntax(inner)
        probe = probe[:start] + "0" + probe[end:]
    probe = HASH_NAME_RE.sub("0", probe)
    probe = HASH_NUM_RE.sub("0", probe)
    _safe_eval(_translate_expr(probe))


def eval_condition(expr: str, variables: dict[str, float]) -> bool:
    return abs(evaluate_expression(expr, variables)) > 1e-12


def pick_assign_expression(rhs: str, variables: dict[str, float]) -> str:
    candidate = rhs.strip()
    if not candidate:
        return candidate

    try:
        evaluate_expression(candidate, variables)
        return candidate
    except Exception:
        pass

    parts = candidate.split()
    for i in range(len(parts) - 1, 0, -1):
        probe = " ".join(parts[:i]).strip()
        if not probe:
            continue
        try:
            evaluate_expression(probe, variables)
            return probe
        except Exception:
            continue

    return parts[0] if parts else candidate


def try_literal_int(expr: str | None) -> int | None:
    if expr is None:
        return None
    s = expr.strip()
    if not s:
        return None
    if not re.fullmatch(r"[+-]?\d+(?:\.0+)?", s):
        return None
    return int(float(s))
