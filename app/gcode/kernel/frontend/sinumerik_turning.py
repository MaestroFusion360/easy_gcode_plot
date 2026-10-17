"""Native Siemens turning facts; original MPF/SPF text is never lowered to ISO."""

import re
from dataclasses import dataclass

from ..resources import SemanticError
from .ast import NativeMillingSyntax
from .sinumerik import _native_tokens, parse_sinumerik_program


@dataclass(frozen=True, slots=True)
class SinumerikTurningSyntax(NativeMillingSyntax):
    label: str | None = None


def _arguments(text):
    values, start, depth, quoted = [], 0, 0, False
    for index, char in enumerate(text):
        if char == '"':
            quoted = not quoted
        elif not quoted:
            depth += (char == "(") - (char == ")")
            if depth < 0:
                raise SemanticError("INVALID_SINUMERIK_CYCLE", "Unbalanced cycle arguments")
            if char == "," and depth == 0:
                values.append(text[start:index].strip())
                start = index + 1
    if quoted or depth:
        raise SemanticError("INVALID_SINUMERIK_CYCLE", "Unbalanced cycle arguments")
    return tuple((*values, text[start:].strip()))


def _turning_tokens(raw):
    code = raw.split(";", 1)[0].strip().lstrip("/").strip()
    body = re.sub(r"^N\d+\s*", "", code, flags=re.I)
    label = re.fullmatch(r"([A-Z_][A-Z0-9_]*)\s*:\s*", body, re.I)
    if label:
        return (), SinumerikTurningSyntax("turning_label", label=label[1].upper())
    cycle = re.fullmatch(r"(MCALL\s+)?CYCLE(\d+)\s*\((.*)\)\s*", body, re.I)
    if cycle:
        return (), SinumerikTurningSyntax(
            "turning_modal_cycle" if cycle[1] else "turning_cycle",
            cycle_code=int(cycle[2]),
            cycle_args=_arguments(cycle[3]),
        )
    if body.upper() == "RET":
        return (), SinumerikTurningSyntax("turning_return")
    return _native_tokens(raw)


def parse_sinumerik_turning_program(source):
    """Use the common Siemens lexer/AST builder with turning cycle declarations."""
    return parse_sinumerik_program(source, token_parser=_turning_tokens)
