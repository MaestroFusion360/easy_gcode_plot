"""Native milling subset feeding the shared ISO geometry executor.

CR is a radius address; G710 selects metric geometry/feed; G64 selects
continuous path (logical trace has no blending simulation). MSG/WORKPIECE are
display metadata. SUPA is a nonmodal machine-coordinate move, not G28.
"""

from dataclasses import replace

from ..api.resources import SemanticError
from ..frontend.lang import WordToken
from ..frontend.program import eval_words
from ..runtime.execution import EvaluatedBlock, classify_block_codes
from ..runtime.signals import signals_for_words
from .cycles.sinumerik import compile_native_cycle
from .sinumerik_iso import _diag, _normalize_g_codes

NATIVE_G_CODES = frozenset({41, 42, 64, 710})


def native_operation_code(block):
    """Describe native-only semantics for execution facts and export guards."""
    syntax = block.native_syntax
    if syntax is None:
        return None
    if syntax.kind != "words":
        return syntax.kind.upper()
    if syntax.supa:
        return "SUPA"
    for token in block.parsed_words:
        if token.letter in {"CR", "D"} or token.letter == "G" and float(token.expr) in NATIVE_G_CODES:
            return token.letter + token.expr
    return None


def evaluate_native_block(block, variables):
    tokens = tuple(WordToken("R" if token.letter == "CR" else token.letter, token.expr) for token in block.parsed_words)
    words = eval_words(tokens, variables)
    values = tuple((letter, value) for letter, entries in words._all.items() for value in entries)  # pylint: disable=protected-access
    return EvaluatedBlock(words, classify_block_codes(words), values, signals_for_words(block.index, words))


def normalize_native_block(block, evaluated, state):
    syntax = block.native_syntax
    if syntax is None:
        return evaluated, None
    if syntax.kind in ("cycle", "cycle_cancel", "frame_reset"):
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
    if 64 in words.all("G"):
        words._all["G"] = [g for g in words.all("G") if g != 64]  # pylint: disable=protected-access
        if words.all("G"):
            words["G"] = words.all("G")[-1]
        else:
            words.pop("G", None)
    if syntax.supa:
        words.add(WordToken("G", "53"), 53.0)
    if d is not None:
        words.add(WordToken("G", "49" if d == 0 else "43"), 49.0 if d == 0 else 43.0)
        if d == 1:
            words.add(WordToken("H", "1"), 1.0)
    values = tuple((letter, value) for letter, entries in words._all.items() for value in entries)  # pylint: disable=protected-access
    return EvaluatedBlock(words, classify_block_codes(words), values, normalized.signals), None


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
    if syntax is None or syntax.kind not in ("cycle", "cycle_cancel", "frame_reset"):
        return False
    if syntax.kind != "frame_reset":
        state.native_cycle = evaluated.native_payload
    return True
