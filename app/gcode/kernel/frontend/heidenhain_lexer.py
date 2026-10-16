"""Location-preserving Klartext block and address lexing."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from ..api.resources import SemanticError
from .heidenhain_expression import HeidenhainExpressionError, parse_expression_prefix
from .heidenhain_syntax import HeidenhainWord

_ADDRESSES = tuple(
    sorted(
        (
            *"XYZABCUVWFSRL",
            *("I" + axis for axis in "XYZABCUVW"),
            "IPA",
            "IPR",
            "PA",
            "PR",
            "CCA",
            "LEN",
            "DR2",
            "DR",
            "DL",
            "M",
            "LA",
            "MB",
            "ROT",
            "SPA",
            "SPB",
            "SPC",
            "T",
        ),
        key=len,
        reverse=True,
    )
)
_ADDRESS = re.compile("|".join(_ADDRESSES), re.I)
_FLAGS = re.compile(r"(?:MB\s+MAX|FMAX|FAUTO|RL|RR|R0)(?=\s|[A-Z]|$)", re.I)
_COORDINATE_KEYS = {"I" + axis: axis for axis in "XYZABCUVW"}
_COORDINATE_KEYS.update(IPA="PA", IPR="PR")


class HeidenhainParseError(SemanticError):
    """Frontend diagnostic; line and column are one-based physical locations."""

    def __init__(self, message, line, column=1, *, code="INVALID_HEIDENHAIN_SYNTAX", status="malformed"):
        super().__init__(code, message, status, line=line.index + 1, raw=line.raw)
        self.column = column


@dataclass(frozen=True, slots=True)
class HeidenhainLine:
    index: int
    raw: str
    body: str
    column: int
    number: int | None = None
    optional: bool = False
    comment: str | None = None
    continued: bool = False


def _comment_start(raw):
    quoted, position = False, 0
    while position < len(raw):
        char = raw[position]
        if char == '"':
            if quoted and raw[position : position + 2] == '""':
                position += 2
                continue
            quoted = not quoted
        elif char == ";" and not quoted:
            return position, False
        position += 1
    return len(raw), quoted


def lex_heidenhain_line(raw, index):
    end, quoted = _comment_start(raw)
    code = raw[:end]
    position = len(code) - len(code.lstrip())
    optional = code[position : position + 1] == "/"
    if optional:
        position += 1
        position += len(code[position:]) - len(code[position:].lstrip())
    number = re.match(r"(?:N)?(\d+)\s*", code[position:], re.I)
    if number is not None:
        position += number.end()
    body = code[position:].rstrip()
    continued = body.endswith("~")
    if continued:
        body = body[:-1].rstrip()
    number_value = int(number[1]) if number and len(number[1]) <= 9 else None
    line = HeidenhainLine(
        index, raw, body, position, number_value, optional, raw[end + 1 :] if end < len(raw) else None, continued
    )
    if number and number_value is None:
        raise HeidenhainParseError("Block number exceeds nine digits", line)
    if quoted and not body.startswith("*"):
        raise HeidenhainParseError("Unterminated Klartext string", line, len(raw) + 1)
    return line


def scalar_prefix(source, line, column, *, stop_operators=()):
    try:
        comma = re.match(r"\s*[+-]?(?:\d+,\d*|,\d+)(?=\s|[A-Z]|$)", source, re.I)
        if comma is not None:
            text = comma[0]
            expression, _ = parse_expression_prefix(text.replace(",", "."), stop_operators=stop_operators)
            return replace(expression, source=text.strip()), comma.end()
        return parse_expression_prefix(source, stop_operators=stop_operators)
    except HeidenhainExpressionError as exc:
        raise HeidenhainParseError(str(exc), line, column + exc.column + 1) from exc


def lex_heidenhain_words(body, line, *, offset=0, direction=True, flags=True):
    words, seen, position = [], set(), 0
    while position < len(body):
        position += len(body[position:]) - len(body[position:].lstrip())
        if position == len(body):
            break
        start = position
        flag = _FLAGS.match(body, position) if flags else None
        if flag is not None:
            address, expression, position = " ".join(flag[0].upper().split()), None, flag.end()
        else:
            address, expression, position = _address_word(body, position, line, offset, direction)
        key = _COORDINATE_KEYS.get(address, address)
        if key in seen and address not in {"M", "F", "FMAX", "FAUTO"}:
            raise HeidenhainParseError("Duplicate Klartext address: " + address, line, line.column + offset + start + 1)
        seen.add(key)
        words.append(HeidenhainWord(address, body[start:position], line.column + offset + start, expression))
    return tuple(words)


def _address_word(body, position, line, offset, direction):
    match = _ADDRESS.match(body, position)
    column = line.column + offset
    if match is None:
        raise HeidenhainParseError("Unknown Klartext address", line, column + position + 1)
    address, position = match[0].upper(), match.end()
    if address == "DR" and direction:
        sign = re.match(r"\s*([+-])(?=\s|[A-Z]|$)", body[position:], re.I)
        if sign is None:
            raise HeidenhainParseError("DR requires + or -", line, column + position + 1)
        position += sign.end()
        return "DR" + sign[1], None, position
    expression, length = scalar_prefix(body[position:], line, column + position, stop_operators={"LEN"})
    return address, expression, position + length
