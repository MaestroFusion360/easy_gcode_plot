"""Native milling subset feeding the shared ISO geometry executor.

CR is a radius address; G710 selects metric geometry/feed; G64 selects
continuous path (logical trace has no blending simulation). MSG/WORKPIECE are
display metadata. SUPA is absolute and nonmodal; zero XYZ targets use the
application's configured reference return, shared with FANUC G53.
"""

import math
from dataclasses import replace

from ..api.resources import SemanticError
from ..api.types import Diagnostic, ExecutionEvent
from ..frontend.lang import WordToken
from ..frontend.program import EvaluatedWords
from ..runtime.execution import EvaluatedBlock, classify_block_codes
from ..runtime.signals import signals_for_words
from .cycles.sinumerik import compile_native_cycle
from .kinematics import TCP_TABLE_PROFILES
from .sinumerik_feed import native_feed_diagnostic
from .sinumerik_frame import apply_frame, compile_frame
from .sinumerik_iso import _diag, _normalize_g_codes
from .sinumerik_parameters import compile_variables, parameter_value
from .sinumerik_swivel import apply_swivel, compile_swivel
from .state import _activate_tcp, _cancel_tcp

IGNORED_NATIVE_G_CODES = frozenset(range(505, 600)) | {601, 641, 642, 645}
NATIVE_G_CODES = IGNORED_NATIVE_G_CODES | frozenset({41, 42, 60, 64, 70, 71, 93, 96, 97, 500, 700, 710, 961, 971})
IGNORED_CONTOUR_WORDS = frozenset({"CHF", "CHR", "RND", "RNDM", "FRC", "FRCM"})


def native_operation_code(block):
    """Describe native-only semantics for execution facts and export guards."""
    syntax = block.native_syntax
    if syntax is None or syntax.kind == "hsc_ignored":
        return None
    if syntax.kind != "words":
        return syntax.frame_command or syntax.kind.upper()
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
    trees = dict(block.native_syntax.scalar_expressions)
    for token in tokens:
        if token.letter in IGNORED_CONTOUR_WORDS:
            continue
        words.add(
            token, parameter_value(token.expr, state.siemens_parameters, state.siemens_variables, trees.get(token.expr))
        )
    _resolve_incremental_rotary(block, words, state)
    _resolve_incremental_linear(block, words, state)
    _resolve_direct_rotary(block, words, state)
    values = tuple((letter, value) for letter, entries in words._all.items() for value in entries)  # pylint: disable=protected-access
    return EvaluatedBlock(words, classify_block_codes(words), values, signals_for_words(block.index, words))


def native_ignored_mode_warnings(block):
    syntax = block.native_syntax
    if syntax is None:
        return []
    warnings = [
        Diagnostic(
            "IGNORED_SINUMERIK_DIAMETER_MODE",
            f"{mode} is not simulated; coordinates use DIAMOF semantics",
            "warning",
            "unverified",
            block.index + 1,
            block.raw,
        )
        for mode in syntax.ignored_diameter_modes
    ]
    for letter in dict.fromkeys(token.letter for token in block.parsed_words if token.letter in IGNORED_CONTOUR_WORDS):
        warnings.append(
            Diagnostic(
                f"UNMODELED_SINUMERIK_{letter}",
                f"{letter} is parsed but not simulated; "
                "programmed contour and feed are retained without corner treatment",
                "warning",
                "unverified",
                block.index + 1,
                block.raw,
            )
        )
    commands = list(syntax.ignored_native_commands)
    if any(t.letter == "G" and float(t.expr) == 4 for t in block.parsed_words) and any(
        t.letter == "S" for t in block.parsed_words
    ):
        commands.append("G4 S (spindle-revolution dwell)")
    commands.extend(
        f"G{int(float(t.expr))}"
        for t in block.parsed_words
        if t.letter == "G" and float(t.expr) in IGNORED_NATIVE_G_CODES
    )
    for command in dict.fromkeys(commands):
        warnings.append(
            Diagnostic(
                "UNMODELED_SINUMERIK_NATIVE",
                f"{command} is parsed but not simulated; current geometry and feed state are retained",
                "warning",
                "unverified",
                block.index + 1,
                block.raw,
            )
        )
    return warnings


def _resolve_incremental_linear(block, words, state):
    if block.native_syntax.incremental_linear and (
        block.native_syntax.supa or any(g in (28, 53) for g in words.all("G"))
    ):
        raise SemanticError(
            "UNSUPPORTED_SINUMERIK_IC_RETURN", "IC linear values cannot combine with machine returns", "unsupported"
        )
    absolute = next((g == 90 for g in reversed(words.all("G")) if g in (90, 91)), state.absolute)
    scale = next(
        (25.4 if g in (20, 70, 700) else 1.0 for g in reversed(words.all("G")) if g in (20, 21, 70, 71, 700, 710)),
        state.unit_scale,
    )
    if absolute:
        for axis in block.native_syntax.incremental_linear:
            target = getattr(state, axis.lower()) / scale + words[axis]
            words[axis] = target
            words._all[axis] = [target]  # pylint: disable=protected-access


def _resolve_incremental_rotary(block, words, state):
    axes = block.native_syntax.incremental_rotary
    if not axes:
        return
    gcodes = words.all("G")
    if any(g in (28, 53) for g in gcodes) or block.native_syntax.supa:
        raise SemanticError(
            "UNSUPPORTED_SINUMERIK_ROTARY", "IC rotary values cannot combine with machine returns", "unsupported"
        )
    absolute = next((g == 90 for g in reversed(gcodes) if g in (90, 91)), state.absolute)
    if absolute:
        for axis in axes:
            target = state.rotary_angles[axis] + words[axis]
            words[axis] = target
            words._all[axis] = [target]  # pylint: disable=protected-access


def _resolve_direct_rotary(block, words, state):
    if not block.native_syntax.direct_rotary:
        return
    absolute = next((g == 90 for g in reversed(words.all("G")) if g in (90, 91)), state.absolute)
    if block.native_syntax.supa:
        absolute = True
    for axis in block.native_syntax.direct_rotary:
        # Backplot compatibility with Fusion's signed DC angles. Keep a
        # source warning: a modulo controller may require the 0..360 form.
        value = words[axis] % 360
        delta = (value - state.rotary_angles[axis] + 180) % 360 - 180
        if abs(delta) == 180:
            raise SemanticError(
                "UNSUPPORTED_SINUMERIK_DC_TIE", "DC half-turn direction requires machine settings", "unsupported"
            )
        target = state.rotary_angles[axis] + delta if absolute else delta
        words[axis] = target
        words._all[axis] = [target]  # pylint: disable=protected-access


def native_dc_diagnostics(block, state):
    syntax = block.native_syntax
    if syntax is None or not syntax.direct_rotary:
        return []
    trees = dict(syntax.scalar_expressions)
    diagnostics = []
    for token in block.parsed_words:
        if token.letter not in syntax.direct_rotary:
            continue
        value = parameter_value(token.expr, state.siemens_parameters, state.siemens_variables, trees.get(token.expr))
        if not 0 <= value <= 360:
            diagnostics.append(
                Diagnostic(
                    "NORMALIZED_SINUMERIK_DC",
                    f"{token.letter}=DC({value:g}) plotted as DC({value % 360:g}); "
                    "controller DC syntax expects 0..360 degrees",
                    "warning",
                    "unverified",
                    block.index + 1,
                    block.raw,
                )
            )
    return diagnostics


def apply_native_tcp_edge(block, words, state):
    """D selects a cutting edge/offset without cancelling the TRAORI transform."""
    if block.native_syntax is not None and state.tcp_control and "D" in words:
        state.tool_length_comp = words["D"] > 0
        state.tool_length_h = int(words["D"]) if state.tool_length_comp else None


def native_edge_diagnostics(block, words):
    """Retain edge selection without inventing controller offset-table values."""
    if words.get("D", 0) <= 1:
        return []
    return [
        Diagnostic(
            "UNVERIFIED_SINUMERIK_EDGE_OFFSETS",
            "Cutting edge selected; controller-specific edge offsets are unavailable, using nominal tool geometry",
            "warning",
            "unverified",
            block.index + 1,
            block.raw,
        )
    ]


def normalize_native_block(block, evaluated, state):
    syntax = block.native_syntax
    if syntax is None:
        return evaluated, None
    diagnostic = (
        _native_syntax_diagnostic(block)
        or _native_spindle_mode_diagnostic(block, evaluated)
        or _cip_diagnostic(block, evaluated, state)
        or native_feed_diagnostic(block, evaluated, state)
        or _native_tcp_combination_diagnostic(block, evaluated, state)
    )
    if diagnostic is not None:
        return evaluated, diagnostic
    if syntax.kind != "words":
        return _normalize_native_declaration(block, evaluated, state)
    return _normalize_native_words(block, evaluated, state)


def _native_syntax_diagnostic(block):
    syntax = block.native_syntax
    if syntax.kind in ("invalid_expression", "unmodeled_geometry"):
        return _diag(
            block,
            "INVALID_SINUMERIK_EXPRESSION" if syntax.kind == "invalid_expression" else "UNMODELED_SINUMERIK_GEOMETRY",
            syntax.syntax_error or f"{', '.join(syntax.ignored_native_commands)} is recognized; geometry is unmodeled",
        )
    return None


def _native_spindle_mode_diagnostic(block, evaluated):
    modes = [g for g in evaluated.codes.all_g if g in (96, 97, 961, 971)]
    if len(modes) > 1:
        return _diag(block, "CONFLICTING_SINUMERIK_SPINDLE_MODES", "Select one native spindle mode per block")
    return None


def _cip_diagnostic(block, evaluated, state):
    syntax, words = block.native_syntax, evaluated.words
    explicit_move = any(g in (0, 1, 2, 3) for g in evaluated.codes.all_g)
    active = syntax.cip or (state.cip_mode and not explicit_move)
    intermediate = any(axis in words for axis in ("I1", "J1", "K1"))
    if not active and intermediate:
        return _diag(block, "INVALID_SINUMERIK_CIP", "Intermediate point addresses require CIP interpolation")
    if not active:
        return None
    if intermediate and not any(axis in words for axis in "XYZ"):
        return _diag(block, "INVALID_SINUMERIK_CIP", "CIP requires a distinct endpoint")
    incompatible = (
        state.cutter_comp != 40
        or state.native_cycle is not None
        or state.cycle != 80
        or any(g not in (17, 18, 19, 40, 54, 55, 56, 57, 58, 59, 90, 91, 94, 95) for g in evaluated.codes.all_g)
        or any(axis in words for axis in ("A", "B", "C", "I", "J", "K", "R", "TURN"))
        or syntax.supa
    )
    if incompatible:
        return _diag(
            block, "UNSUPPORTED_SINUMERIK_CIP", "CIP requires a fixed frame, G40 and no cycle or rotary motion"
        )
    if (syntax.cip or any(axis in words for axis in "XYZ")) and not intermediate:
        return _diag(block, "INVALID_SINUMERIK_CIP", "CIP requires a new intermediate point for each arc")
    return None


def _native_tcp_combination_diagnostic(block, evaluated, state):
    if not state.tcp_control:
        return None
    if block.native_syntax.kind == "cycle":
        return _diag(block, "UNSUPPORTED_TCP_CYCLE", "Cancel TRAORI before native MCALL cycles")
    if any(code in (41, 42) for code in evaluated.codes.all_g):
        return _diag(block, "UNSUPPORTED_TCP_CUTTER_COMPENSATION", "Native TCP cutter compensation is not modeled")
    return None


def _normalize_native_words(block, evaluated, state):
    syntax = block.native_syntax
    diagnostic = _native_modal_cycle_diagnostic(block, evaluated, state)
    if diagnostic is not None:
        return evaluated, diagnostic
    gcodes = evaluated.codes.all_g
    if syntax.supa and (
        not any(axis in evaluated.words for axis in ("X", "Y", "Z", "A", "B", "C"))
        or gcodes not in ((), (0,))
        or (not gcodes and state.move != 0)
    ):
        return evaluated, _diag(
            block, "UNSUPPORTED_SINUMERIK_SUPA", "Modeled SUPA requires rapid G0 and XYZ/ABC addresses"
        )
    radius = any(token.letter == "CR" for token in block.parsed_words)
    move = next((g for g in reversed(gcodes) if g in (0, 1, 2, 3)), state.move)
    turn_diagnostic = _native_turn_diagnostic(block, evaluated, state, move)
    if turn_diagnostic is not None:
        return evaluated, turn_diagnostic
    if radius and (move not in (2, 3) or any(axis in evaluated.words for axis in ("I", "J", "K"))):
        return evaluated, _diag(block, "INVALID_SINUMERIK_CR", "CR requires G2/G3 without I/J/K center addresses")
    d = evaluated.words.get("D")
    if d is not None and (not d.is_integer() or not 0 <= d <= 12):
        return evaluated, _diag(block, "UNSUPPORTED_SINUMERIK_D", "Native milling models cutting edge D0..D12 only")
    normalized = _normalize_g_codes(evaluated, {70: 20, 71: 21, 700: 20, 710: 21})
    # Remove path-control metadata and express nonmodal SUPA/D in existing
    # state/motion operations, without manufacturing another source program.
    words = normalized.words
    _remove_path_control(words)
    if syntax.supa:
        words.add(WordToken("G", "53"), 53.0)
    if d is not None and not state.tcp_control:
        words.add(WordToken("G", "49" if d == 0 else "43"), 49.0 if d == 0 else 43.0)
        if d > 0:
            words.add(WordToken("H", str(int(d))), d)
    values = tuple((letter, value) for letter, entries in words._all.items() for value in entries)  # pylint: disable=protected-access
    normalized = EvaluatedBlock(words, classify_block_codes(words), values, normalized.signals)
    return _normalize_native_dwell(normalized, block.index), None


def _normalize_native_dwell(evaluated, block_index):
    words = evaluated.words
    if 4 not in evaluated.codes.all_g:
        return evaluated
    if "S" in words:
        if any(letter not in ("N", "G", "S") for letter in words):
            raise SemanticError("UNSUPPORTED_SINUMERIK_DWELL", "G4 S must be a standalone dwell block", "unsupported")
        words.pop("S", None)
        words._all.pop("S", None)  # pylint: disable=protected-access
        words.pop("G", None)
        words._all.pop("G", None)  # pylint: disable=protected-access
        return EvaluatedBlock(
            words,
            classify_block_codes(words),
            tuple((letter, value) for letter, value in evaluated.values if letter not in ("G", "S")),
            (),
        )
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
    if any(g in {60, 64} | IGNORED_NATIVE_G_CODES for g in words.all("G")):
        words._all["G"] = [g for g in words.all("G") if g not in {60, 64} | IGNORED_NATIVE_G_CODES]  # pylint: disable=protected-access
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
    allowed = {0, 1, 17, 54, 55, 56, 57, 58, 59, 60, 64, 90, 91, 94, 500}
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
    if block.native_syntax.kind in ("real_declaration", "named_assignment"):
        return replace(evaluated, native_payload=compile_variables(block.native_syntax, state)), None
    if block.native_syntax.kind in ("swivel", "cycle", "programmed_frame"):
        return _compile_native_declaration(block, evaluated, state)
    if block.native_syntax.kind == "traori":
        return evaluated, _tcp_declaration_diagnostic(block, state)
    if block.native_syntax.kind == "parameter_assignment":
        index, value = block.native_syntax.parameter_assignment
        tree = dict(block.native_syntax.scalar_expressions).get(value)
        return replace(
            evaluated,
            native_payload=(index, parameter_value(value, state.siemens_parameters, state.siemens_variables, tree)),
        ), None
    if block.native_syntax.kind == "frame_reset" and (
        state.tcp_control or state.native_cycle is not None or state.cycle != 80 or state.cutter_comp != 40
    ):
        return evaluated, _diag(
            block, "UNSUPPORTED_SINUMERIK_CYCLE800", "Cancel TCP, cycles and compensation before CYCLE800 reset"
        )
    return evaluated, None


def _compile_native_declaration(block, evaluated, state):
    compiler = {"swivel": compile_swivel, "cycle": compile_native_cycle, "programmed_frame": compile_frame}[
        block.native_syntax.kind
    ]
    try:
        payload = compiler(block.native_syntax, state)
    except SemanticError as error:
        return evaluated, _diag(block, error.code, str(error))
    return replace(evaluated, native_payload=payload), None


def _tcp_declaration_diagnostic(block, state):
    if state.kinematics is None or state.kinematics.id not in TCP_TABLE_PROFILES:
        return _diag(block, "TCP_KINEMATICS_REQUIRED", "TRAORI requires a supported AC/BC table profile")
    transform_active = (
        state.transform.rotation_active
        or state.transform.scaling_active
        or state.transform.translation != (0.0, 0.0, 0.0)
    )
    if (
        state.twp.active
        or state.cycle != 80
        or state.native_cycle is not None
        or state.cutter_comp != 40
        or transform_active
    ):
        return _diag(
            block,
            "UNSUPPORTED_TCP_COMPOSITION",
            "Cancel programmed/tilted frames, cycles and cutter compensation before TRAORI",
        )
    return None


def apply_native_declaration(block, evaluated, state, events):
    syntax = block.native_syntax
    if syntax is None or syntax.kind not in (
        "cycle",
        "cycle_cancel",
        "frame_reset",
        "swivel",
        "parameter_assignment",
        "traori",
        "trafoof",
        "real_declaration",
        "named_assignment",
        "hsc_ignored",
        "unmodeled",
        "compof",
        "main_spindle",
        "programmed_frame",
    ):
        return False
    if syntax.kind in ("real_declaration", "named_assignment", "programmed_frame"):
        _apply_native_data(syntax, evaluated.native_payload, state)
    elif syntax.kind in ("hsc_ignored", "unmodeled", "compof", "main_spindle"):
        pass
    elif syntax.kind in ("swivel", "frame_reset"):
        apply_swivel(block, evaluated.native_payload, state, events)
    elif syntax.kind in ("traori", "trafoof"):
        was_tcp_active = state.tcp_control
        if syntax.kind == "traori":
            _activate_tcp(state)
        else:
            _cancel_tcp(state)
        if state.tcp_control != was_tcp_active:
            events.append(
                ExecutionEvent(
                    "TCP_CONTROL_ON" if state.tcp_control else "TCP_CONTROL_OFF",
                    block.index,
                    code=syntax.kind.upper(),
                    tool=state.active_tool,
                    length_offset=state.tool_length_h,
                    kinematics_profile=state.kinematics.id if state.kinematics else None,
                )
            )
    elif syntax.kind == "parameter_assignment":
        index, value = evaluated.native_payload
        state.siemens_parameters[index] = value
    elif syntax.kind != "frame_reset":
        state.native_cycle = evaluated.native_payload
    return True


def _apply_native_data(syntax, payload, state):
    if syntax.kind == "programmed_frame":
        apply_frame(payload, state)
    else:
        state.siemens_variables = payload
