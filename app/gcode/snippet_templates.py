"""Controller-independent text substitutions and a bounded arithmetic evaluator."""

from __future__ import annotations

import ast
import math
import operator
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

_TOKEN = re.compile(r"\{\{(.*?)\}\}", re.S)
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
_NUMBER = re.compile(r"[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?\Z")
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


class TemplateError(ValueError):
    """Stable message key and offending value, independent of UI translations."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class TemplateContext:
    file: Path | None = None
    selection: str = ""
    instant: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class Parameter:
    name: str
    default: str
    label: str
    kind: str = "text"
    minimum: float | str | None = None
    maximum: float | str | None = None
    greater_than: float | str | None = None
    less_than: float | str | None = None
    choices: tuple[str, ...] = ()
    optional: bool = False
    width: int = 0
    alternative: str = ""
    prefix: str = ""
    suffix: str = ""


@dataclass(frozen=True)
class RenderedSnippet:
    text: str
    cursor: int | None = None


def _tokens(source):
    matches = list(_TOKEN.finditer(source))
    remainder = _TOKEN.sub("", source)
    if "{{" in remainder or "}}" in remainder:
        raise TemplateError("Invalid placeholder")
    return matches


def _parameter_declaration(token):
    declaration, _, label = token[1:].partition("|")
    formatting = re.search(r":(\+\d*)\s*$", declaration)
    if formatting:
        return declaration[: formatting.start()], formatting[1], label
    return declaration, "", label


def parameters(source: str) -> tuple[Parameter, ...]:
    """Collect declarations once, allowing forward references and repeated fields."""
    found = {}
    for match in _tokens(source):
        token = match[1].strip()
        if not token.startswith("?"):
            continue
        declaration, _formatting, label = _parameter_declaration(token)
        name, _, default = declaration.partition("=")
        name = name.strip()
        if not _IDENTIFIER.fullmatch(name) or name.lower() in {
            "pi",
            "date",
            "time",
            "datetime",
            "selection",
            "cursor",
            "file",
        }:
            raise TemplateError("Invalid placeholder", name)
        parameter = _parameter_options(name, default.strip(), label)
        if name in found and found[name] != parameter:
            raise TemplateError("Conflicting parameter", name)
        found[name] = parameter
    return tuple(found.values())


def _parameter_options(name, default, declaration):
    parts = [part.strip() for part in declaration.split("|")]
    kinds = {"number", "int", "text", "contour"}
    label = name if parts[0] in kinds else parts.pop(0) or name
    options = {}
    for part in parts:
        if part:
            key, value = _parameter_option(part, name)
            options[key] = value
    return Parameter(name, default, label, **options)


def _parameter_option(part, name):
    key, _, value = part.partition("=")
    if key in {"number", "int", "text", "contour"}:
        return "kind", key
    if key in {"optional", "prefix", "suffix"}:
        return key, True if key == "optional" else value
    limits = {"min": "minimum", "max": "maximum", "gt": "greater_than", "lt": "less_than"}
    if key in limits:
        return limits[key], _number(value) if _NUMBER.fullmatch(value) else value
    if key == "oneof" and _IDENTIFIER.fullmatch(value):
        return "alternative", value
    if key == "choices":
        return key, tuple(item.strip() for item in value.split(","))
    if key == "width" and value.isdigit() and 1 <= int(value) <= 12:
        return key, int(value)
    raise TemplateError("Invalid placeholder", name)


def _validated_parameter(parameter, value, values):
    if not value:
        return _empty_parameter(parameter, values)
    if parameter.kind in {"number", "int"}:
        value = _validated_number(parameter, value, values)
    if parameter.choices and value not in parameter.choices:
        raise TemplateError("Invalid choice", parameter.name)
    if parameter.kind == "contour" and not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*:[A-Za-z_][A-Za-z_0-9]*", value):
        raise TemplateError("Invalid contour", parameter.name)
    return value.zfill(parameter.width) if parameter.width else value


def _empty_parameter(parameter, values):
    if parameter.optional and (not parameter.alternative or values.get(parameter.alternative)):
        return ""
    raise TemplateError("Missing value", parameter.name)


def _validated_number(parameter, value, values):
    try:
        number = _number(value)
    except TemplateError as exc:
        raise TemplateError("Invalid number", parameter.name) from exc
    if parameter.kind == "int" and not number.is_integer():
        raise TemplateError("Integer required", parameter.name)
    _validate_bounds(parameter, number, values)
    return _formatted(number)


def _validate_bounds(parameter, number, values):
    bounds = (
        (parameter.minimum, operator.ge),
        (parameter.maximum, operator.le),
        (parameter.greater_than, operator.gt),
        (parameter.less_than, operator.lt),
    )
    for bound, compare in bounds:
        if bound is not None:
            limit = formula(bound, values) if isinstance(bound, str) else bound
            if not compare(number, limit):
                raise TemplateError("Value out of range", parameter.name)


def _finite(value):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 1e100:
        raise TemplateError("Math error")
    return float(value)


def _number(value):
    if not _NUMBER.fullmatch(str(value).strip()):
        raise TemplateError("Invalid number", str(value))
    return _finite(float(str(value).replace(",", ".")))


def _tangent(angle):
    radians = math.radians(angle)
    if abs(math.cos(radians)) < 1e-12:
        raise TemplateError("Math error", "TAN")
    return math.tan(radians)


_FUNCTIONS = {
    "SIN": lambda x: math.sin(math.radians(x)),
    "COS": lambda x: math.cos(math.radians(x)),
    "TAN": _tangent,
    "ASIN": lambda x: math.degrees(math.asin(x)),
    "ACOS": lambda x: math.degrees(math.acos(x)),
    "ATAN": lambda x: math.degrees(math.atan(x)),
    "ATAN2": lambda y, x: math.degrees(math.atan2(y, x)),
    "ABS": abs,
    "SQRT": math.sqrt,
    "ROUND": lambda x, n=0: round(x, int(n)),
    "MIN": min,
    "MAX": max,
    "TO_MM": lambda x: x * 25.4,
    "TO_INCH": lambda x: x / 25.4,
    "TO_RAD": math.radians,
    "TO_DEG": math.degrees,
}


def _evaluate(node, values):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return _finite(node.value)
    if isinstance(node, ast.Name):
        if node.id.upper() == "PI":
            return math.pi
        if node.id not in values:
            raise TemplateError("Missing value", node.id)
        return _number(values[node.id])
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _evaluate(node.operand, values)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        left, right = _evaluate(node.left, values), _evaluate(node.right, values)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise TemplateError("Formula is too complex")
        return _finite(_OPERATORS[type(node.op)](left, right))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        function = _FUNCTIONS.get(node.func.id.upper())
        if function is None:
            raise TemplateError("Unknown function", node.func.id)
        return _finite(function(*[_evaluate(arg, values) for arg in node.args]))
    raise TemplateError("Invalid formula")


def formula(expression: str, values: dict[str, str]) -> float:
    """No eval, attributes, Python objects, imports, loops or CNC execution."""
    if len(expression) > 512:
        raise TemplateError("Formula is too complex")
    try:
        tree = ast.parse(expression.replace("^", "**"), mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 100:
            raise TemplateError("Formula is too complex")
        return _evaluate(tree.body, values)
    except (SyntaxError, RecursionError) as exc:
        raise TemplateError("Invalid formula", expression) from exc
    except (ArithmeticError, TypeError, ValueError) as exc:
        if isinstance(exc, TemplateError):
            raise
        raise TemplateError("Math error", expression) from exc


def _formatted(value, precision=""):
    if precision.startswith("+"):
        text = _formatted(_number(value), precision[1:])
        return text if text.startswith("-") else f"+{text}"
    if precision:
        if not precision.isdigit() or not 0 <= int(precision) <= 12:
            raise TemplateError("Invalid precision", precision)
        return f"{_number(value):.{int(precision)}f}"
    if isinstance(value, (float, int)):
        return f"{value:.10f}".rstrip("0").rstrip(".") if value else "0"
    text = str(value)
    return text.replace(",", ".") if _NUMBER.fullmatch(text) else text


def _date_time(name, pattern, context):
    pattern = pattern or {"date": "YYYY-MM-DD", "time": "HH:mm:ss", "datetime": "YYYY-MM-DD HH:mm:ss"}[name]
    codes = {"YYYY": "%Y", "YY": "%y", "MM": "%m", "DD": "%d", "HH": "%H", "mm": "%M", "ss": "%S"}
    result = re.sub(r"YYYY|YY|MM|DD|HH|mm|ss", lambda match: context.instant.strftime(codes[match[0]]), pattern)
    return result


def _file_value(name, context):
    path = context.file
    if path is None:
        raise TemplateError("Save the document first")
    if not path.is_file():
        raise TemplateError("File no longer exists", str(path))
    path = path.resolve()
    values = {"file.name": path.name, "file.stem": path.stem, "file.path": str(path), "file.dir": str(path.parent)}
    if name not in values:
        raise TemplateError("Unknown placeholder", name)
    return values[name]


def _replacement(token, values, context):
    if token.startswith("?"):
        declaration, formatting, label = _parameter_declaration(token)
        name, _, default = declaration.partition("=")
        parameter = _parameter_options(name.strip(), default.strip(), label)
        value = values[parameter.name]
        return parameter.prefix + _formatted(value, formatting) + parameter.suffix if value else ""
    name, _, precision = token.rpartition(":") if ":" in token else (token, "", "")
    # Date/time formats contain colons themselves; split only the first colon.
    base, _, pattern = token.partition(":")
    if base in {"date", "time", "datetime"}:
        return _date_time(base, pattern, context)
    if name.startswith("file."):
        return _file_value(name, context)
    if name == "selection":
        return context.selection
    if name.startswith("="):
        return _formatted(formula(name[1:].strip(), values), precision)
    if name in values:
        return _formatted(values[name], precision)
    raise TemplateError("Unknown placeholder", token)


def render(
    source: str, values: dict[str, str] | None = None, context: TemplateContext | None = None
) -> RenderedSnippet:
    """Resolve all fields before returning text; a failure never inserts partial NC."""
    supplied = values or {}
    requested = parameters(source)
    raw = {p.name: str(supplied.get(p.name, p.default)).strip() for p in requested}
    resolved = {p.name: _validated_parameter(p, raw[p.name], raw) for p in requested}
    context = context or TemplateContext()
    parts, cursor, end = [], None, 0
    for match in _tokens(source):
        parts.append(source[end : match.start()])
        token = match[1].strip()
        if token == "cursor":
            if cursor is not None:
                raise TemplateError("Only one cursor marker is allowed")
            cursor = sum(len(part) for part in parts)
        else:
            parts.append(_replacement(token, resolved, context))
        end = match.end()
    parts.append(source[end:])
    return RenderedSnippet("".join(parts), cursor)
