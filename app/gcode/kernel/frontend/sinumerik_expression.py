"""Bounded Siemens expression trees; independent of FANUC Macro B.

Expressions use explicit operator precedence and trigonometry in degrees.
Undefined values, invalid domains and division by zero deliberately fail closed.
"""

import math
import operator
import re
from functools import lru_cache

from ..api.resources import SemanticError, checkpoint

_TOKEN = re.compile(r"\s*(\d+(?:\.\d*)?|\.\d+|R\d+|_[A-Z][A-Z0-9_]*|[A-Z]+|<=|>=|==|<>|!=|[+*/(),<>\-=])", re.I)
_PRECEDENCE = {"=": 1, "==": 1, "<>": 1, "!=": 1, "<": 1, ">": 1, "<=": 1, ">=": 1, "+": 2, "-": 2, "*": 3, "/": 3}
_FUNCTIONS = {"SIN", "COS", "ABS", "SQRT"}
_UNARY = {"+": operator.pos, "-": operator.neg}
_BINARY = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "=": operator.eq,
    "==": operator.eq,
    "<>": operator.ne,
    "!=": operator.ne,
    "<": operator.lt,
    ">": operator.gt,
    "<=": operator.le,
    ">=": operator.ge,
}
_CALLS = {
    "SIN": lambda x: math.sin(math.radians(x)),
    "COS": lambda x: math.cos(math.radians(x)),
    "ABS": abs,
    "SQRT": math.sqrt,
}


def _invalid(message):
    return SemanticError("INVALID_SINUMERIK_EXPRESSION", message)


def _tokenize(expression):
    if len(expression) > 4096:
        raise _invalid("Expression length exceeds 4096 characters")
    tokens, position = [], 0
    expression = expression.strip()
    while position < len(expression):
        match = _TOKEN.match(expression, position)
        if match is None:
            raise _invalid("Invalid Siemens expression token")
        tokens.append(match[1].upper())
        position = match.end()
        if len(tokens) > 256:
            raise _invalid("Expression exceeds 256 tokens")
    return tuple(tokens)


class _ExpressionParser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.cursor = 0

    def parse(self, minimum=1, depth=0):
        if depth > 32 or self.cursor >= len(self.tokens):
            raise _invalid("Missing operand or expression nesting exceeds 32")
        token = self.tokens[self.cursor]
        self.cursor += 1
        left = self._primary(token, depth)
        while self.cursor < len(self.tokens) and _PRECEDENCE.get(self.tokens[self.cursor], 0) >= minimum:
            operation = self.tokens[self.cursor]
            self.cursor += 1
            left = ("binary", operation, left, self.parse(_PRECEDENCE[operation] + 1, depth + 1))
        return left

    def _primary(self, token, depth):
        if token in ("+", "-"):
            return ("unary", token, self.parse(4, depth + 1))
        if token == "(" or token in _FUNCTIONS:
            return self._group(token, depth)
        if re.fullmatch(r"R\d+|_[A-Z][A-Z0-9_]{0,30}", token):
            if token.startswith("R") and (len(token) > 6 or int(token[1:]) > 9999):
                raise _invalid("R parameter index must be within 0..9999")
            return ("variable", token)
        try:
            value = float(token)
        except ValueError as error:
            raise _invalid("Unsupported function or operand") from error
        if not math.isfinite(value):
            raise _invalid("Numeric literal must be finite")
        return ("number", value)

    def _expect(self, token):
        if self.cursor >= len(self.tokens) or self.tokens[self.cursor] != token:
            raise _invalid(f"Expected {token}")
        self.cursor += 1

    def _group(self, token, depth):
        if token != "(":
            self._expect("(")
        inner = self.parse(1, depth + 1)
        self._expect(")")
        return inner if token == "(" else ("function", token, inner)


@lru_cache(maxsize=1024)
def compile_expression(expression):
    """Compile a fully consumed scalar expression into an immutable tree."""
    parser = _ExpressionParser(_tokenize(expression))
    tree = parser.parse()
    if parser.cursor != len(parser.tokens):
        raise _invalid("Unexpected trailing expression token")
    return tree


def _variable_value(name, parameters, variables):
    if name.startswith("R"):
        index = int(name[1:])
        if index not in parameters:
            raise SemanticError("UNDEFINED_SINUMERIK_PARAMETER", f"R{index} is not assigned", "unsupported")
        return parameters[index]
    if variables is None or name not in variables:
        raise SemanticError("UNDEFINED_SINUMERIK_VARIABLE", f"{name} is not declared", "unsupported")
    if variables[name] is None:
        raise SemanticError("UNINITIALIZED_SINUMERIK_VARIABLE", f"Assign {name} before use", "unsupported")
    return variables[name]


def evaluate_expression(tree, parameters, variables=None, depth=0):
    checkpoint()
    if depth > 64:
        raise _invalid("Expression tree depth exceeds 64")
    kind = tree[0]
    if kind == "number":
        return tree[1]
    if kind == "variable":
        return _variable_value(tree[1], parameters, variables)
    value = evaluate_expression(tree[2], parameters, variables, depth + 1)
    try:
        if kind == "unary":
            result = _UNARY[tree[1]](value)
        elif kind == "function":
            result = _CALLS[tree[1]](value)
        else:
            right = evaluate_expression(tree[3], parameters, variables, depth + 1)
            result = _BINARY[tree[1]](value, right)
    except (ValueError, OverflowError, ZeroDivisionError) as error:
        if isinstance(error, SemanticError):
            raise
        raise _invalid("Invalid arithmetic/function domain") from error
    if not math.isfinite(result):
        raise _invalid("Expression result must be finite")
    return float(result)
