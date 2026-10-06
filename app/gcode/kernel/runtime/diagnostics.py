"""Construction of public diagnostics from parser and runtime evidence."""

from __future__ import annotations

import re

from ..api.resources import SemanticError
from ..api.types import Diagnostic
from ..frontend.lang import UndefinedMacroVariableError
from ..frontend.model import Program
from ..geometry.coordinates import is_extended_wcs_gcode
from ..turning.dialect import supported_codes
from ..turning.type_a import TYPE_A_SUPPORTED_G_CODES
from .execution import modal_group_conflicts

SUPPORTED_TURNING_G_CODES = TYPE_A_SUPPORTED_G_CODES

_LINE_RE = re.compile(r"\bline\s+(\d+)\b", re.IGNORECASE)


def modal_conflict_diagnostics(gcodes, language: str, block) -> tuple[Diagnostic, ...]:
    """Build source-aware diagnostics for every modal-group conflict."""
    return tuple(
        Diagnostic(
            "MODAL_GROUP_CONFLICT",
            f"Conflicting {group} codes in one block: {', '.join(f'G{code:g}' for code in codes)}",
            "error",
            "malformed",
            block.index + 1,
            block.raw,
        )
        for group, codes in modal_group_conflicts(gcodes, language)
    )


def unsupported_g53_motion_diagnostic(block, modal_move: int) -> Diagnostic:
    """Report a turning G53 block whose effective motion mode is unsupported."""
    return Diagnostic(
        "UNSUPPORTED_G53_MOTION",
        f"Turning G53 supports only G0/G1 machine-coordinate motion; G{modal_move} block skipped",
        "error",
        "unsupported",
        block.index + 1,
        block.raw,
    )


def _runtime_error_code(message: str, undefined_macro: bool) -> str:
    if undefined_macro or "undefined macro variable" in message:
        return "UNDEFINED_MACRO"
    rules = (
        (("cannot assign to permanent vacant variable #0",), "INVALID_MACRO_ASSIGNMENT"),
        (("missing goto target", "missing if/goto target"), "FLOW_TARGET_MISSING"),
        (("m98 targets missing", "g65 targets missing"), "SUBPROGRAM_MISSING"),
        (("call depth exceeds", "macro nesting exceeds"), "CALL_DEPTH_EXCEEDED"),
        (("m98",), "SUBPROGRAM_ERROR"),
        (("g65",), "MACRO_CALL_ERROR"),
        (("guard reached",), "EXECUTION_GUARD"),
        (("g83/g84 cycle remains active",), "UNCLOSED_CYCLE"),
    )
    return next((code for fragments, code in rules if any(item in message for item in fragments)), "EXECUTION_ERROR")


def diagnostic_from_exception(exc: Exception, program: Program | None) -> Diagnostic:
    """Translate an internal exception chain into a source-aware diagnostic."""
    message = str(exc)
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
    code = _runtime_error_code(lowered, undefined_macro)

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


TURNING_MODELED_M_CODES = frozenset({0, 1, 2, 3, 4, 5, 8, 9, 30, 98, 99})


def turning_code_diagnostics(block, evaluated, system="A") -> tuple[Diagnostic, ...]:
    """Diagnose actually executed source codes after macro evaluation."""
    if 65 in evaluated.source_gcodes:
        return ()  # CNC-looking words here are macro arguments.
    diagnostics = []
    if "Y" in evaluated.words:
        diagnostics.append(
            Diagnostic(
                "UNSUPPORTED_AXIS",
                "Y-axis motion is not modeled for fanuc_turn",
                "error",
                "unsupported",
                block.index + 1,
                block.raw,
            )
        )
    position = any(axis in evaluated.words for axis in ("X", "Z", "U", "W"))
    for code in dict.fromkeys(evaluated.source_gcodes):
        if code in supported_codes(system) or is_extended_wcs_gcode(code):
            continue
        other_system = "B" if system == "A" else "A"
        wrong_system = code in supported_codes(other_system)
        geometric = position or code in {17, 19} or wrong_system
        diagnostics.append(
            Diagnostic(
                "UNSUPPORTED_G_CODE",
                f"G{code:g} belongs to FANUC lathe Type {other_system}; selected source is Type {system}"
                if wrong_system
                else f"G{code:g} is not modeled for fanuc_turn",
                "error" if geometric else "warning",
                "unsupported" if geometric else "unverified",
                block.index + 1,
                block.raw,
            )
        )
    for code in dict.fromkeys(evaluated.codes.all_m):
        if code not in TURNING_MODELED_M_CODES:
            diagnostics.append(
                Diagnostic(
                    "UNSUPPORTED_M_CODE",
                    f"M{code:g} is not modeled for fanuc_turn; ignored for trace execution",
                    "warning",
                    "unverified",
                    block.index + 1,
                    block.raw,
                )
            )
    return tuple(diagnostics)
