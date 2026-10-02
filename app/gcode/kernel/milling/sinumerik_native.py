"""Native milling subset feeding the shared ISO geometry executor.

CR is a radius address; G710 selects metric geometry/feed; G64 selects
continuous path (logical trace has no blending simulation). MSG/WORKPIECE are
display metadata. SUPA is a nonmodal machine-coordinate move, not G28.
"""

import math
from dataclasses import replace

from ..api.resources import SemanticError
from ..frontend.lang import WordToken
from ..frontend.program import EvaluatedWords
from ..runtime.execution import EvaluatedBlock, classify_block_codes
from ..runtime.signals import signals_for_words
from .cycles.sinumerik import compile_native_cycle
from .sinumerik_iso import _diag, _normalize_g_codes
from .sinumerik_parameters import parameter_value

NATIVE_G_CODES = frozenset({41, 42, 64, 710})


def native_operation_code(block):
    """Describe native-only semantics for execution facts and export guards."""
    syntax = block.native_syntax
    if syntax is None:
        return None
    if syntax.kind != "words":
        return syntax.kind.upper()
    if any(token.letter == "G" and float(token.expr) == 4 for token in block.parsed_words) and any(
        token.letter == "F" for token in block.parsed_words
    ):
        return "DWELL_F"
    if syntax.supa:
        return "SUPA"
    for token in block.parsed_words:
        if token.letter in {"CR", "D", "TURN"} or token.letter == "G" and float(token.expr) in NATIVE_G_CODES:
            return token.letter + token.expr
    return None


def evaluate_native_block(block, state):
    tokens = tuple(WordToken("R" if token.letter == "CR" else token.letter, token.expr) for token in block.parsed_words)
    words = EvaluatedWords()
    for token in tokens:
        words.add(token, parameter_value(token.expr, state.siemens_parameters))
    values = tuple((letter, value) for letter, entries in words._all.items() for value in entries)  # pylint: disable=protected-access
    return EvaluatedBlock(words, classify_block_codes(words), values, signals_for_words(block.index, words))


def normalize_native_block(block, evaluated, state):
    syntax = block.native_syntax
    if syntax is None:
        return evaluated, None
    if syntax.kind in ("cycle", "cycle_cancel", "frame_reset", "parameter_assignment"):
        return _normalize_native_declaration(block, evaluated, state)
    return _normalize_native_words(block, evaluated, state)


def _normalize_native_words(block, evaluated, state):
    syntax = block.native_syntax
    diagnostic = _native_modal_cycle_diagnostic(block, evaluated, state)
    if diagnostic is not None:
        return evaluated, diagnostic
    gcodes = evaluated.codes.all_g
    if syntax.supa and (not any(axis in evaluated.words for axis in ("X", "Y", "Z")) or gcodes != (0,)):
        return evaluated, _diag(
            block, "UNSUPPORTED_SINUMERIK_SUPA", "Modeled SUPA requires explicit G0 and XYZ addresses"
        )
    radius = any(token.letter == "CR" for token in block.parsed_words)
    move = next((g for g in reversed(gcodes) if g in (0, 1, 2, 3)), state.move)
    turn_diagnostic = _native_turn_diagnostic(block, evaluated, state, move)
    if turn_diagnostic is not None:
        return evaluated, turn_diagnostic
    if radius and (move not in (2, 3) or any(axis in evaluated.words for axis in ("I", "J", "K"))):
        return evaluated, _diag(block, "INVALID_SINUMERIK_CR", "CR requires G2/G3 without I/J/K center addresses")
    d = evaluated.words.get("D")
    if d is not None and (not d.is_integer() or d not in (0, 1)):
        return evaluated, _diag(
            block, "UNSUPPORTED_SINUMERIK_D", "Native milling currently models cutting edge D0/D1 only"
        )
    normalized = _normalize_g_codes(evaluated, {710: 21})
    # Remove path-control metadata and express nonmodal SUPA/D in existing
    # state/motion operations, without manufacturing another source program.
    words = normalized.words
    _remove_path_control(words)
    if syntax.supa:
        words.add(WordToken("G", "53"), 53.0)
    if d is not None:
        words.add(WordToken("G", "49" if d == 0 else "43"), 49.0 if d == 0 else 43.0)
        if d == 1:
            words.add(WordToken("H", "1"), 1.0)
    values = tuple((letter, value) for letter, entries in words._all.items() for value in entries)  # pylint: disable=protected-access
    normalized = EvaluatedBlock(words, classify_block_codes(words), values, normalized.signals)
    return _normalize_native_dwell(normalized, block.index), None


def _normalize_native_dwell(evaluated, block_index):
    words = evaluated.words
    if 4 not in evaluated.codes.all_g:
        return evaluated
    if "S" in words:
        raise SemanticError("UNSUPPORTED_SINUMERIK_DWELL", "G4 spindle-revolution dwell is not modeled", "unsupported")
    if "F" not in words:
        return evaluated
    milliseconds = words["F"] * 1000
    if (
        set(words) - {"N", "G", "F"}
        or evaluated.codes.all_g != (4,)
        or milliseconds < 0
        or not math.isfinite(milliseconds)
    ):
        raise SemanticError(
            "UNSUPPORTED_SINUMERIK_DWELL", "Native G4 F requires a standalone nonnegative seconds dwell", "unsupported"
        )
    words.pop("F")
    words._all.pop("F")  # pylint: disable=protected-access
    words.add(WordToken("P", str(milliseconds)), milliseconds)
    values = tuple((letter, value) for letter, entries in words._all.items() for value in entries)  # pylint: disable=protected-access
    return replace(evaluated, values=values, signals=signals_for_words(block_index, words))


def _remove_path_control(words):
    if 64 in words.all("G"):
        words._all["G"] = [g for g in words.all("G") if g != 64]  # pylint: disable=protected-access
        if words.all("G"):
            words["G"] = words.all("G")[-1]
        else:
            words.pop("G", None)


def _native_turn_diagnostic(block, evaluated, state, move):
    gcodes = evaluated.codes.all_g
    turn = evaluated.words.get("TURN")
    invalid_geometry = (
        move not in (2, 3)
        or any(code in (4, 28, 53) for code in gcodes)
        or not any(address in evaluated.words for address in ("I", "J", "K", "R"))
    )
    incompatible_state = state.native_cycle is not None or state.cutter_comp != 40 or any(g in (41, 42) for g in gcodes)
    if turn is not None and (not turn.is_integer() or not 0 <= turn <= 999 or invalid_geometry or incompatible_state):
        return _diag(block, "UNSUPPORTED_SINUMERIK_TURN", "TURN requires G2/G3, integer 0..999, G40 and no MCALL")
    return None


def _native_modal_cycle_diagnostic(block, evaluated, state):
    if state.native_cycle is None:
        return None
    allowed = {0, 1, 17, 54, 55, 56, 57, 58, 59, 90, 91, 94}
    incompatible = (
        "Z" in evaluated.words
        or block.native_syntax.supa
        or any(g not in allowed for g in evaluated.codes.all_g)
        or any(m in (2, 30) for m in evaluated.codes.all_m)
    )
    if incompatible:
        return _diag(
            block, "UNSUPPORTED_SINUMERIK_CYCLE", "Cancel MCALL before changing drilling plane, depth or execution mode"
        )
    return None


def _normalize_native_declaration(block, evaluated, state):
    if block.native_syntax.kind == "parameter_assignment":
        index, value = block.native_syntax.parameter_assignment
        return replace(evaluated, native_payload=(index, parameter_value(value, {}))), None
    if block.native_syntax.kind == "cycle":
        try:
            cycle = compile_native_cycle(block.native_syntax, state)
        except SemanticError as error:
            return evaluated, _diag(block, error.code, str(error))
        return replace(evaluated, native_payload=cycle), None
    if block.native_syntax.kind == "frame_reset" and (state.twp.active or any(state.rotary_angles.values())):
        return evaluated, _diag(
            block, "UNSUPPORTED_SINUMERIK_CYCLE800", "CYCLE800 reset of an active rotary frame is not modeled"
        )
    return evaluated, None


def apply_native_declaration(block, evaluated, state):
    syntax = block.native_syntax
    if syntax is None or syntax.kind not in ("cycle", "cycle_cancel", "frame_reset", "parameter_assignment"):
        return False
    if syntax.kind == "parameter_assignment":
        index, value = evaluated.native_payload
        state.siemens_parameters[index] = value
    elif syntax.kind != "frame_reset":
        state.native_cycle = evaluated.native_payload
    return True
