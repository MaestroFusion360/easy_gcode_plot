"""SINUMERIK 840D ISO-Dialect-M compatibility checks for the FANUC mill core.

The module deliberately does not implement a second milling executor.  G291
blocks are validated/normalized here and then delegated to the existing
``fanuc_mill`` semantics.  Native Siemens language selected by G290 remains
fail-closed until it has its own execution model.
"""

from __future__ import annotations

from dataclasses import replace

from ..api.types import Diagnostic
from ..frontend.program import EvaluatedWords
from ..runtime.execution import EvaluatedBlock, classify_block_codes

SINUMERIK_MODE_SIEMENS = "siemens"
SINUMERIK_MODE_ISO = "iso"

_MODE_CODES = frozenset({290, 291})
ISO_M_EXECUTABLE_G_CODES = frozenset(
    {
        0,
        1,
        2,
        3,
        4,
        10,
        17,
        18,
        19,
        20,
        21,
        28,
        70,
        71,
        40,
        49,
        50,
        51,
        52,
        53,
        54,
        55,
        56,
        57,
        58,
        59,
        68,
        69,
        73,
        80,
        81,
        82,
        83,
        84,
        85,
        86,
        90,
        91,
        94,
        95,
        98,
        99,
    }
)
_ISO_M_UNIT_ALIASES = {70: 20, 71: 21}


def _diag(block, code: str, message: str, *, status: str = "unsupported") -> Diagnostic:
    return Diagnostic(
        code=code,
        message=message,
        severity="error",
        status=status,
        line=int(getattr(block, "index", 0)) + 1,
        raw=str(getattr(block, "raw", "")),
    )


def mode_switch_code(evaluated_block: EvaluatedBlock) -> int | None:
    """Return G290/G291 when this block requests a SINUMERIK language switch."""
    switches = [int(code) for code in evaluated_block.codes.all_g if code in _MODE_CODES]
    return switches[-1] if switches else None


def mode_switch_diagnostic(block, evaluated_block: EvaluatedBlock) -> Diagnostic | None:
    """Require G290/G291 to be standalone CNC commands (N labels are allowed)."""
    switches = [code for code in evaluated_block.codes.all_g if code in _MODE_CODES]
    if not switches:
        return None
    if len(switches) != 1:
        return _diag(block, "INVALID_SINUMERIK_MODE_SWITCH", "G290/G291 must be programmed one at a time")

    other_g = [code for code in evaluated_block.codes.all_g if code not in _MODE_CODES]
    other_words = [letter for letter, _value in evaluated_block.values if letter not in {"N", "G"}]
    if other_g or other_words or evaluated_block.codes.all_m:
        return _diag(
            block,
            "INVALID_SINUMERIK_MODE_SWITCH",
            f"G{int(switches[0])} must be programmed in its own NC block",
        )
    return None


def is_siemens_metadata_block(block, evaluated_block: EvaluatedBlock) -> bool:
    """Return True for non-executable MPF/SPF header/comment/blank blocks."""
    if evaluated_block.values or getattr(block, "flow_node", None) is not None:
        return False
    raw = str(getattr(block, "raw", "")).strip()
    return not raw or raw.startswith((";", "%", "("))


def unsupported_siemens_mode_diagnostic(block) -> Diagnostic:
    return _diag(
        block,
        "UNSUPPORTED_SINUMERIK_MODE",
        "G290 selects native SINUMERIK language, which is not modeled yet",
    )


def unsupported_iso_macro_diagnostic(block) -> Diagnostic:
    return _diag(
        block,
        "UNSUPPORTED_SINUMERIK_ISO_MACRO",
        "FANUC Macro B flow semantics are not modeled for SINUMERIK ISO mode",
    )


def _unsupported_iso_g_diagnostic(block, gcode: int | float) -> Diagnostic:
    return _diag(
        block,
        "UNSUPPORTED_SINUMERIK_ISO_G_CODE",
        f"G{gcode:g} is not in the executable SINUMERIK ISO Dialect M whitelist",
    )


def _normalize_g_codes(evaluated_block: EvaluatedBlock, aliases: dict[float, float]) -> EvaluatedBlock:
    """Replace selected G words while retaining the rest of the evaluated block."""
    words = EvaluatedWords()
    for letter, value in evaluated_block.values:
        normalized = aliases.get(float(value), value) if letter == "G" else value
        # EvaluatedWords.add() requires a token only for its letter.  Rebuild the
        # internal repeated-word storage directly to avoid manufacturing parser
        # tokens after numeric evaluation.
        words._all.setdefault(letter, []).append(float(normalized))  # pylint: disable=protected-access
        words[letter] = float(normalized)
    return replace(
        evaluated_block,
        words=words,
        codes=classify_block_codes(words),
        values=tuple(
            (letter, aliases.get(float(value), value) if letter == "G" else value)
            for letter, value in evaluated_block.values
        ),
    )


def _iso_m_whitelist_diagnostic(block, evaluated_block: EvaluatedBlock) -> Diagnostic | None:
    for gcode in evaluated_block.codes.all_g:
        if gcode not in ISO_M_EXECUTABLE_G_CODES:
            return _unsupported_iso_g_diagnostic(block, gcode)
    return None


def _extended_wcs_diagnostic(block, evaluated_block: EvaluatedBlock) -> Diagnostic | None:
    gcodes = evaluated_block.codes.all_g
    if 54 in gcodes and "P" in evaluated_block.words:
        p_value = float(evaluated_block.words["P"])
        if not p_value.is_integer() or not 1 <= int(p_value) <= 48:
            return _diag(
                block,
                "INVALID_SINUMERIK_ISO_EXTENDED_WCS",
                "SINUMERIK ISO G54 P requires integer P1 through P48",
            )
    return None


def _g10_diagnostic(block, evaluated_block: EvaluatedBlock) -> Diagnostic | None:
    if 10 not in evaluated_block.codes.all_g:
        return None
    l_value = evaluated_block.words.get("L")
    p_value = evaluated_block.words.get("P")
    if l_value is None or p_value is None:
        return _diag(
            block,
            "UNSUPPORTED_SINUMERIK_ISO_G10",
            "SINUMERIK ISO G10 requires an explicitly modeled work-offset target",
        )
    l_code = float(l_value)
    p_number = float(p_value)
    valid_l2 = l_code == 2.0 and p_number.is_integer() and 1 <= int(p_number) <= 6
    valid_l20 = l_code == 20.0 and p_number.is_integer() and 1 <= int(p_number) <= 99
    if not (valid_l2 or valid_l20):
        return _diag(
            block,
            "UNSUPPORTED_SINUMERIK_ISO_G10",
            "SINUMERIK ISO G10 supports L2 P1..P6 or modeled L20 P1..P99 work offsets",
        )
    return None


def _g68_diagnostic(
    block, evaluated_block: EvaluatedBlock, absolute_mode: bool, active_plane: int
) -> Diagnostic | None:
    gcodes = evaluated_block.codes.all_g
    if 68 not in gcodes:
        return None
    if len(gcodes) != 1:
        return _diag(
            block,
            "INVALID_SINUMERIK_ISO_G68",
            "SINUMERIK ISO G68 must not share its block with another G code",
        )
    if any(axis in evaluated_block.words for axis in ("I", "J", "K")):
        return _unsupported_iso_g_diagnostic(block, 68)
    if not absolute_mode:
        return _unsupported_iso_g_diagnostic(block, 68)
    plane_axes = {17: {"X", "Y"}, 18: {"X", "Z"}, 19: {"Y", "Z"}}.get(active_plane, set())
    allowed_words = plane_axes | {"N", "G", "R"}
    extra_words = set(evaluated_block.words) - allowed_words
    if extra_words:
        return _diag(
            block,
            "INVALID_SINUMERIK_ISO_G68",
            "SINUMERIK ISO G68 accepts only the active-plane center axes and R angle",
        )
    return None


def _iso_gcode_diagnostic(
    block, evaluated_block: EvaluatedBlock, absolute_mode: bool, active_plane: int
) -> Diagnostic | None:
    diagnostic = _iso_m_whitelist_diagnostic(block, evaluated_block)
    if diagnostic is not None:
        return diagnostic
    diagnostic = _extended_wcs_diagnostic(block, evaluated_block)
    if diagnostic is not None:
        return diagnostic
    diagnostic = _g10_diagnostic(block, evaluated_block)
    if diagnostic is not None:
        return diagnostic

    return _g68_diagnostic(block, evaluated_block, absolute_mode, active_plane)


def validate_and_normalize_iso_block(
    block, evaluated_block: EvaluatedBlock, *, absolute_mode: bool = True, active_plane: int = 17
) -> tuple[EvaluatedBlock, Diagnostic | None]:
    """Validate one G291 ISO-Dialect-M block and normalize safe syntax differences."""
    diagnostic = _iso_gcode_diagnostic(block, evaluated_block, absolute_mode, active_plane)
    if diagnostic is not None:
        return evaluated_block, diagnostic

    gcodes = evaluated_block.codes.all_g
    if 70 in gcodes or 71 in gcodes:
        evaluated_block = _normalize_g_codes(evaluated_block, _ISO_M_UNIT_ALIASES)
        gcodes = evaluated_block.codes.all_g

    if 54 in gcodes and "P" in evaluated_block.words:
        return _normalize_g_codes(evaluated_block, {54: 54.1}), None

    return evaluated_block, None
