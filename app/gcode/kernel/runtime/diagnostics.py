"""Construction of public diagnostics from parser and runtime evidence."""

from __future__ import annotations

import re

from ..api.resources import SemanticError
from ..api.types import Diagnostic
from ..frontend.lang import UndefinedMacroVariableError
from ..frontend.model import Program

SUPPORTED_TURNING_G_CODES = frozenset(
    {
        0,
        1,
        2,
        3,
        4,
        18,
        20,
        21,
        28,
        30,
        32,
        33,
        40,
        41,
        42,
        50,
        54,
        55,
        56,
        57,
        58,
        59,
        70,
        71,
        72,
        73,
        74,
        75,
        76,
        80,
        83,
        84,
        90,
        91,
        92,
        94,
        96,
        97,
        98,
        99,
        190,
        191,
    }
)

_LINE_RE = re.compile(r"\bline\s+(\d+)\b", re.IGNORECASE)


def diagnostic_from_exception(exc: Exception, program: Program | None) -> Diagnostic:
    """Translate an internal exception chain into a source-aware diagnostic."""
    message = str(exc)
    code = "EXECUTION_ERROR"
    lowered = message.lower()
    current: BaseException | None = exc
    seen: set[int] = set()
    undefined_macro = False
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, UndefinedMacroVariableError):
            undefined_macro = True
            break
        current = current.__cause__ or current.__context__
    if undefined_macro or "undefined macro variable" in lowered:
        code = "UNDEFINED_MACRO"
    elif "missing goto target" in lowered or "missing if/goto target" in lowered:
        code = "FLOW_TARGET_MISSING"
    elif "m98 targets missing" in lowered:
        code = "SUBPROGRAM_MISSING"
    elif "call depth exceeds" in lowered:
        code = "CALL_DEPTH_EXCEEDED"
    elif "m98" in lowered:
        code = "SUBPROGRAM_ERROR"
    elif "guard reached" in lowered:
        code = "EXECUTION_GUARD"
    elif "g83/g84 cycle remains active" in lowered:
        code = "UNCLOSED_CYCLE"

    line = None
    match = _LINE_RE.search(message)
    if match is not None:
        line = int(match.group(1))
    raw = None
    if program is not None and line is not None and 1 <= line <= len(program.blocks):
        raw = program.blocks[line - 1].raw

    current = exc
    while current is not None:
        if isinstance(current, SemanticError):
            return Diagnostic(current.code, message, status=current.status, line=line, raw=raw)
        current = current.__cause__
    return Diagnostic(code=code, message=message, status="malformed", line=line, raw=raw)


def unsupported_turning_g_diagnostics(program: Program) -> tuple[Diagnostic, ...]:
    """Report source words outside the modeled two-axis turning contract."""
    diagnostics: list[Diagnostic] = []
    for block in program.blocks:
        if any(word.letter == "Y" for word in block.parsed_words):
            diagnostics.append(
                Diagnostic(
                    code="UNSUPPORTED_AXIS",
                    message="Y-axis motion is not modeled for fanuc_turn",
                    severity="error",
                    status="unsupported",
                    line=block.index + 1,
                    raw=block.raw,
                )
            )
        for word in block.parsed_words:
            if word.letter != "G":
                continue
            try:
                value = float(word.expr)
            except ValueError:
                continue
            code = int(value)
            if value == code and code not in SUPPORTED_TURNING_G_CODES:
                affects_geometry = code in {17, 19} or any(
                    item.letter in {"X", "Z", "U", "W"} for item in block.parsed_words
                )
                diagnostics.append(
                    Diagnostic(
                        code="UNSUPPORTED_G_CODE",
                        message=f"G{code} is not modeled for fanuc_turn",
                        severity="error" if affects_geometry else "warning",
                        status="unsupported" if affects_geometry else "unverified",
                        line=block.index + 1,
                        raw=block.raw,
                    )
                )
    return tuple(diagnostics)


def fractional_code_diagnostics(program: Program, steps) -> tuple[Diagnostic, ...]:
    """Report evaluated fractional G/M words without integer coercion."""
    diagnostics: list[Diagnostic] = []
    seen: set[tuple[int, str, float]] = set()
    for step in steps:
        block_index = step.source_block
        if block_index is None or not 0 <= block_index < len(program.blocks):
            continue
        block = program.blocks[block_index]
        affects_geometry = any(item.letter in {"X", "Z", "U", "W"} for item in block.parsed_words)
        for letter, raw_value in step.words:
            if letter not in {"G", "M"}:
                continue
            value = float(raw_value)
            if value.is_integer():
                continue
            key = (block_index, letter, value)
            if key in seen:
                continue
            seen.add(key)
            is_g = letter == "G"
            diagnostics.append(
                Diagnostic(
                    code="UNSUPPORTED_G_CODE" if is_g else "UNSUPPORTED_M_CODE",
                    message=f"{letter}{value:g} is not modeled for fanuc_turn",
                    severity="error" if is_g and affects_geometry else "warning",
                    status="unsupported" if is_g and affects_geometry else "unverified",
                    line=block.index + 1,
                    raw=block.raw,
                )
            )
    return tuple(diagnostics)
