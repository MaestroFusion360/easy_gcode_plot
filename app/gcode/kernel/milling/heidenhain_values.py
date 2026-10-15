"""Evaluate native immutable Klartext expressions against a Q parameter frame."""

import math
import operator

from ..api.resources import SemanticError, checkpoint

_BINARY = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "DIV": operator.truediv,
    "MOD": operator.mod,
    "^": operator.pow,
    "**": operator.pow,
    "EQU": operator.eq,
    "NE": operator.ne,
    "GT": operator.gt,
    "LT": operator.lt,
    "GE": operator.ge,
    "LE": operator.le,
    "AND": lambda a, b: bool(a) and bool(b),
    "OR": lambda a, b: bool(a) or bool(b),
    "XOR": lambda a, b: bool(a) != bool(b),
    "LEN": math.hypot,
    "ANG": lambda a, b: math.degrees(math.atan2(b, a)),
}
_FUNCTIONS = {
    "SIN": lambda a: math.sin(math.radians(a)),
    "COS": lambda a: math.cos(math.radians(a)),
    "TAN": lambda a: math.tan(math.radians(a)),
    "ASIN": lambda a: math.degrees(math.asin(a)),
    "ACOS": lambda a: math.degrees(math.acos(a)),
    "ATAN": lambda a: math.degrees(math.atan(a)),
    "SQRT": math.sqrt,
    "ABS": abs,
    "INT": math.trunc,
    "FIX": math.trunc,
    "FUP": math.ceil,
    "FRAC": lambda a: a - math.trunc(a),
    "ROUND": lambda a: math.copysign(math.floor(abs(a) + 0.5), a),
    "LN": math.log,
    "LOG": math.log10,
    "EXP": math.exp,
    "SGN": lambda a: (a > 0) - (a < 0),
    "LEN": math.hypot,
    "ANG": lambda a, b: math.degrees(math.atan2(b, a)),
}


def scalar(expression, parameters):
    """Evaluate the AST without compiling source text or sharing mutable globals."""
    checkpoint()
    try:
        kind, value = expression.kind, expression.value
        if kind == "number":
            result = float(value)
        elif kind == "parameter":
            result = parameters.get(value, 0.0)
        elif kind == "group":
            result = scalar(expression.operands[0], parameters)
        elif kind == "unary":
            result = scalar(expression.operands[0], parameters) * (-1 if value == "-" else 1)
        else:
            args = tuple(scalar(arg, parameters) for arg in expression.operands)
            operation = (_BINARY if kind == "binary" else _FUNCTIONS).get(value)
            if operation is None:
                raise SemanticError("INVALID_HEIDENHAIN_EXPRESSION", "Unknown expression operation: " + value)
            result = operation(*args)
        if isinstance(result, complex) or not math.isfinite(result):
            raise ValueError("result is not a finite real number")
        return float(result)
    except (ValueError, OverflowError, ZeroDivisionError) as exc:
        raise SemanticError(
            "INVALID_HEIDENHAIN_EXPRESSION", f"Invalid Klartext expression {expression.source}: {exc}"
        ) from exc
