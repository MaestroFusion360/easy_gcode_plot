from __future__ import annotations

# Expressions are parsed through a restricted AST before evaluation; explicit
# dispatch returns keep the Macro B grammar readable.
# pylint: disable=eval-used,too-many-return-statements,superfluous-parens
import ast
import math
import re
from dataclasses import dataclass

from ...comments import strip_comments as _strip_comments

ASSIGN_RE = re.compile(r"^\s*#(?:(\d+)|<([A-Z_][A-Z0-9_]*)>|\[(.+)\])\s*=\s*(.+?)\s*$", re.IGNORECASE)
IF_GOTO_RE = re.compile(r"^\s*IF\s*\[(.+)\]\s*GOTO\s*(\d+)\s*$", re.IGNORECASE)
GOTO_RE = re.compile(r"^\s*GOTO\s*(\d+)\s*$", re.IGNORECASE)
WHILE_RE = re.compile(r"^\s*WHILE\s*\[(.+)\]\s*DO\s*(\d+)\s*$", re.IGNORECASE)
END_RE = re.compile(r"^\s*END\s*(\d+)\s*$", re.IGNORECASE)
HASH_NUM_RE = re.compile(r"#(\d+)")
HASH_NAME_RE = re.compile(r"#<([A-Z_][A-Z0-9_]*)>", re.IGNORECASE)
NUMERIC_LITERAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
MAX_EXPRESSION_SIZE = 4096
MAX_EXPRESSION_NODES = 512
MAX_EXPRESSION_DEPTH = 64


class UndefinedMacroVariableError(ValueError):
    """Raised when a Macro B variable reference has no runtime value."""


class _MacroNull:
    """FANUC vacant value: distinct in comparisons, numeric zero in arithmetic."""

    def __float__(self):
        return 0.0

    def __int__(self):
        return 0

    def __bool__(self):
        return False

    def __str__(self):
        return "NULL"

    def __repr__(self):
        return "NULL"

    def __pos__(self):
        return 0.0

    def __neg__(self):
        return -0.0

    def __abs__(self):
        return 0.0

    def __add__(self, other):
        return 0.0 + other

    def __radd__(self, other):
        return other + 0.0

    def __sub__(self, other):
        return 0.0 - other

    def __rsub__(self, other):
        return other - 0.0

    def __mul__(self, other):
        return 0.0 * other

    def __rmul__(self, other):
        return other * 0.0

    def __truediv__(self, other):
        return 0.0 / other

    def __rtruediv__(self, other):
        return other / 0.0

    def __floordiv__(self, other):
        return 0.0 // other

    def __rfloordiv__(self, other):
        return other // 0.0

    def __mod__(self, other):
        return 0.0 % other

    def __rmod__(self, other):
        return other % 0.0

    def __pow__(self, other):
        return 0.0**other

    def __rpow__(self, other):
        return other**0.0

    def __lt__(self, other):
        return 0.0 < other

    def __le__(self, other):
        return 0.0 <= other

    def __gt__(self, other):
        return 0.0 > other

    def __ge__(self, other):
        return 0.0 >= other


MACRO_NULL = _MacroNull()


def strip_comments(line: str) -> str:
    """Strip both supported CNC comment syntaxes while parsing."""
    return _strip_comments(line)


@dataclass(frozen=True, slots=True)
class WordToken:
    letter: str
    expr: str


@dataclass(frozen=True, slots=True)
class FlowNode:
    kind: str
    condition: str | None = None
    target_label: int | None = None
    loop_id: int | None = None
    var_key: str | None = None
    var_expr: str | None = None
    value_expr: str | None = None


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


def _assignment_flow(text: str, condition: str | None = None) -> FlowNode | None:
    match = ASSIGN_RE.match(text)
    if match is None:
        return None
    num_key, name_key, var_expr, rhs = match.groups()
    key = num_key if num_key is not None else (name_key or "").upper()
    return FlowNode(
        kind="assign" if condition is None else "if_assign",
        condition=condition,
        var_key=key or None,
        var_expr=var_expr.strip() if var_expr is not None else None,
        value_expr=rhs.strip(),
    )


def _conditional_flow(text: str) -> FlowNode:
    match = IF_GOTO_RE.match(text)
    if match:
        cond, target = match.groups()
        return FlowNode(kind="if_goto", condition=cond.strip(), target_label=int(target))
    header = re.match(r"^IF\s*\[", text, re.IGNORECASE)
    if header:
        open_pos = header.end() - 1
        try:
            close_pos = _matching_square_bracket(text, open_pos)
        except ValueError:
            return FlowNode(kind="unsupported_if")
        tail = re.match(r"\s*THEN\s*(.+)$", text[close_pos + 1 :], re.IGNORECASE)
        if tail:
            if re.search(r"\bGOTO\s*\d", tail.group(1), re.IGNORECASE):
                return FlowNode(kind="unsupported_if")
            assignment = _assignment_flow(tail.group(1), text[open_pos + 1 : close_pos].strip())
            if assignment is not None:
                return assignment
    return FlowNode(kind="unsupported_if")


def parse_flow(clean: str) -> FlowNode | None:
    if not clean:
        return None

    # Flow statements may carry a normal N block label.  Strip only that label;
    # O labels remain program/subprogram declarations and are not flow prefixes.
    flow_text = re.sub(r"^\s*N[+-]?\d+(?:\.0+)?\s*", "", clean, count=1, flags=re.IGNORECASE)

    assignment = _assignment_flow(flow_text)
    if assignment is not None:
        return assignment
    if re.match(r"^IF\b", flow_text, re.IGNORECASE):
        return _conditional_flow(flow_text)

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


def _macro_variable_value(key: str, variables: dict[str, float], *, null_aware: bool = False) -> float | _MacroNull:
    if key == "0" or key not in variables:
        if null_aware:
            return MACRO_NULL
        if key == "0":
            raise UndefinedMacroVariableError("Macro variable #0 is vacant")
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


def _expand_variables(expr: str, variables: dict[str, float], *, null_aware: bool = False) -> str:
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
            if null_aware:
                return str(MACRO_NULL)
            raise UndefinedMacroVariableError(f"Undefined macro variable #<{name}>")
        return str(_macro_variable_value(name, variables, null_aware=null_aware))

    out = HASH_NAME_RE.sub(repl_name, out)

    def repl_num(mo: re.Match[str]) -> str:
        return str(_macro_variable_value(mo.group(1), variables, null_aware=null_aware))

    out = HASH_NUM_RE.sub(repl_num, out)
    return out


def _fanuc_round(value: float) -> float:
    """Round to nearest integer with .5 away from zero, matching FANUC Macro B."""
    return float(math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5))


def _fanuc_xor(left: float, right: float) -> float:
    return float(int(left) ^ int(right))


def _fanuc_and(left: float, right: float) -> float:
    return float(int(left) & int(right))


def _fanuc_or(left: float, right: float) -> float:
    return float(int(left) | int(right))


SAFE_FUNCS = {
    "ABS": abs,
    "SQRT": math.sqrt,
    "SIN": lambda x: math.sin(math.radians(x)),
    "COS": lambda x: math.cos(math.radians(x)),
    "TAN": lambda x: math.tan(math.radians(x)),
    "ATAN": lambda x: math.degrees(math.atan(x)),
    "ATAN2": lambda y, x: math.degrees(math.atan2(y, x)),
    "FIX": math.trunc,
    "FUP": lambda x: math.copysign(math.ceil(abs(x)), x),
    "ROUND": _fanuc_round,
    "MIN": min,
    "MAX": max,
    "XOR": _fanuc_xor,
    "AND": _fanuc_and,
    "OR": _fanuc_or,
    "LN": math.log,
    "EXP": math.exp,
}
SAFE_VALUES = {**SAFE_FUNCS, "NULL": MACRO_NULL}

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
    ast.Mod,
    ast.UAdd,
    ast.USub,
    ast.And,
    ast.Or,
    ast.Eq,
    ast.NotEq,
    ast.Gt,
    ast.GtE,
    ast.Lt,
    ast.LtE,
    ast.BitXor,
)


class _FanucExpressionTransformer(ast.NodeTransformer):
    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        # Float arithmetic prevents Python arbitrary-precision integer growth.
        return ast.copy_location(ast.Constant(value=float(node.value)), node)

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        node = self.generic_visit(node)
        operation = "AND" if isinstance(node.op, ast.And) else "OR"
        result = node.values[0]
        for value in node.values[1:]:
            result = ast.Call(func=ast.Name(id=operation, ctx=ast.Load()), args=[result, value], keywords=[])
        return ast.copy_location(result, node)

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


def _validate_expression_tree(tree: ast.AST) -> None:
    pending, count = [(tree, 0)], 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > MAX_EXPRESSION_NODES or depth > MAX_EXPRESSION_DEPTH:
            raise ValueError("Macro B expression complexity limit exceeded")
        pending.extend((child, depth + 1) for child in ast.iter_child_nodes(node))
        if not isinstance(node, SAFE_NODES):
            raise ValueError(f"Unsupported expression node: {type(node).__name__}")
        if isinstance(node, ast.Constant):
            _validate_numeric_constant(node.value)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Unsupported call target")
            if node.func.id not in SAFE_FUNCS:
                raise ValueError(f"Unsupported function: {node.func.id}")
        if isinstance(node, ast.Name) and node.id not in SAFE_VALUES:
            raise ValueError(f"Unsupported name: {node.id}")


def _validate_numeric_constant(value) -> None:
    if type(value) not in (int, float):
        raise ValueError("Macro B constants must be numeric")
    if not math.isfinite(float(value)):
        raise ValueError("Non-finite numeric constant")


def _safe_eval(expr: str) -> float:
    tree = ast.parse(expr, mode="eval")
    _validate_expression_tree(tree)
    tree = ast.fix_missing_locations(_FanucExpressionTransformer().visit(tree))
    _validate_expression_tree(tree)
    value = eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}}, SAFE_VALUES)
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if value is MACRO_NULL:
        return MACRO_NULL
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Non-finite expression result")
    return value


def _check_expression_limits(expr: str) -> None:
    if len(expr) > MAX_EXPRESSION_SIZE:
        raise ValueError("Macro B expression size limit exceeded")
    depth = 0
    for character in expr:
        if character in "[(":
            depth += 1
            if depth > MAX_EXPRESSION_DEPTH:
                raise ValueError("Macro B expression nesting limit exceeded")
        elif character in "])":
            depth -= 1


def evaluate_expression(expr: str, variables: dict[str, float], *, null_aware: bool = False) -> float | _MacroNull:
    _check_expression_limits(expr)
    raw = expr.strip()
    if not raw:
        return 0.0
    if NUMERIC_LITERAL_RE.fullmatch(raw):
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError("Non-finite numeric word")
        return value
    expanded = _expand_variables(raw, variables, null_aware=null_aware)
    translated = _translate_expr(expanded)
    return _safe_eval(translated)


def validate_expression_syntax(expr: str) -> None:
    """Validate a Macro B expression without requiring runtime variable values."""
    _check_expression_limits(expr)
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
    value = evaluate_expression(expr, variables, null_aware=True)
    return False if value is MACRO_NULL else abs(value) > 1e-12


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
