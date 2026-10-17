"""Immutable Klartext scalar expressions; parsing never evaluates Q parameters."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..resources import checkpoint

_TOKEN = re.compile(r"\s*(?:(\d+(?:\.\d*)?|\.\d+)|((?:QL|QR|Q)\d+)|([A-Z]+)|(\*\*|[+*/^(),\[\]-]))", re.I)
_BINDING = {
    "OR": (2, 3),
    "XOR": (4, 5),
    "AND": (6, 7),
    "EQU": (8, 9),
    "NE": (8, 9),
    "GT": (8, 9),
    "LT": (8, 9),
    "GE": (8, 9),
    "LE": (8, 9),
    "+": (10, 11),
    "-": (10, 11),
    "*": (20, 21),
    "/": (20, 21),
    "DIV": (20, 21),
    "MOD": (20, 21),
    "LEN": (20, 21),
    "ANG": (20, 21),
    "^": (40, 40),
    "**": (40, 40),
}
_FUNCTIONS = {
    "SIN": 1,
    "COS": 1,
    "TAN": 1,
    "ASIN": 1,
    "ACOS": 1,
    "ATAN": 1,
    "SQRT": 1,
    "ABS": 1,
    "INT": 1,
    "FRAC": 1,
    "ROUND": 1,
    "FIX": 1,
    "FUP": 1,
    "LN": 1,
    "LOG": 1,
    "EXP": 1,
    "SGN": 1,
    "LEN": 2,
    "ANG": 2,
}


class HeidenhainExpressionError(ValueError):
    """A malformed scalar expression with a zero-based character offset."""

    def __init__(self, message, column):
        super().__init__(message)
        self.column = column


@dataclass(frozen=True, slots=True)
class HeidenhainExpression:
    kind: str
    value: str
    operands: tuple[HeidenhainExpression, ...] = ()
    source: str = ""


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    value: str
    start: int
    end: int


def _tokens(source):
    result, position = [], 0
    while position < len(source):
        if len(result) % 256 == 0:
            checkpoint()
        match = _TOKEN.match(source, position)
        if match is None:
            if not source[position:].strip():
                break
            raise HeidenhainExpressionError("Unexpected character in Klartext expression", position)
        kind = ("number", "parameter", "name", "symbol")[match.lastindex - 1]
        result.append(_Token(kind, match[match.lastindex].upper(), match.start(match.lastindex), match.end()))
        position = match.end()
    return tuple(result)


class _ExpressionReader:
    def __init__(self, source, stop_operators=()):
        self.source = source
        self.tokens = _tokens(source)
        self.position = 0
        self.stop_operators = stop_operators

    def peek(self):
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self):
        token = self.peek()
        if token is None:
            raise HeidenhainExpressionError("Expected a Klartext scalar value", len(self.source))
        self.position += 1
        return token

    def node(self, kind, value, operands, start):
        end = self.tokens[self.position - 1].end
        return HeidenhainExpression(kind, value, operands, self.source[start:end])

    def expression(self, minimum=0, depth=0):
        if depth > 64:
            token = self.peek()
            raise HeidenhainExpressionError(
                "Klartext expression nesting exceeds 64 levels", token.start if token else 0
            )
        token = self.take()
        left = self.prefix(token, depth)
        while self.peek() is not None:
            operator = self.peek().value
            if depth == 0 and operator in self.stop_operators:
                break
            binding = _BINDING.get(operator)
            if binding is None or binding[0] < minimum:
                break
            self.take()
            right = self.expression(binding[1], depth + 1)
            left = self.node("binary", operator, (left, right), token.start)
        return left

    def prefix(self, token, depth):
        if token.kind == "parameter":
            match = re.fullmatch(r"(QL|QR|Q)(\d+)", token.value)
            maximum = 1999 if match[1] == "Q" else 499
            if len(match[2]) > 4 or int(match[2]) > maximum:
                raise HeidenhainExpressionError("Q parameter is outside the iTNC 530 range", token.start)
            return self.node("parameter", match[1] + str(int(match[2])), (), token.start)
        if token.kind == "number":
            return self.node(token.kind, token.value, (), token.start)
        if token.value in {"+", "-"}:
            return self.node("unary", token.value, (self.expression(30, depth + 1),), token.start)
        if token.value in {"(", "["}:
            result = self.expression(0, depth + 1)
            closing = ")" if token.value == "(" else "]"
            if self.take().value != closing:
                raise HeidenhainExpressionError("Unbalanced Klartext expression", token.start)
            return self.node("group", token.value, (result,), token.start)
        if token.value in _FUNCTIONS:
            return self.function(token, depth)
        raise HeidenhainExpressionError("Unknown Klartext scalar name or missing operand", token.start)

    def function(self, token, depth):
        arity = _FUNCTIONS[token.value]
        if self.peek() is None or self.peek().value != "(":
            if arity != 1:
                raise HeidenhainExpressionError("Binary function requires two parenthesized arguments", token.start)
            arguments = (self.expression(30, depth + 1),)
        else:
            self.take()
            arguments = []
            for index in range(arity):
                if index and self.take().value != ",":
                    raise HeidenhainExpressionError("Expected a function argument separator", token.start)
                arguments.append(self.expression(0, depth + 1))
            if self.take().value != ")":
                raise HeidenhainExpressionError("Invalid Klartext function argument count", token.start)
            arguments = tuple(arguments)
        return self.node("function", token.value, arguments, token.start)


def parse_expression_prefix(source, *, stop_operators=()):
    """Read one scalar, returning its tree and consumed source length.

    A following address such as Y or FMAX is left for the block lexer.
    """
    reader = _ExpressionReader(source, stop_operators)
    expression = reader.expression()
    return expression, reader.tokens[reader.position - 1].end


def compile_heidenhain_expression(source):
    expression, end = parse_expression_prefix(source)
    if source[end:].strip():
        raise HeidenhainExpressionError("Unexpected trailing Klartext expression tokens", end)
    return expression
