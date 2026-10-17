"""Native/ISO-T evaluated block geometry and modal operations, independent of cycles."""

from dataclasses import replace

from ..frontend.model import Point2
from ..milling.sinumerik_parameters import parameter_value
from ..resources import SemanticError
from ..types import ExecutionEvent, MachineSignal
from .sinumerik_state import unsupported

_NATIVE_CODES = {
    0,
    1,
    2,
    3,
    4,
    18,
    33,
    40,
    41,
    42,
    53,
    54,
    55,
    56,
    57,
    58,
    59,
    60,
    64,
    70,
    71,
    90,
    91,
    94,
    95,
    96,
    97,
    153,
    500,
    700,
    710,
}
_ISO_COMMON = {0, 1, 2, 3, 4, 18, 20, 21, 28, 40, 41, 42, 53, 54, 55, 56, 57, 58, 59, 96, 97}


def evaluate(block, state):
    syntax = block.native_syntax
    if syntax is None:
        unsupported("Unsupported or malformed Siemens turning source")
    if syntax.kind == "invalid_expression":
        raise SemanticError("INVALID_SINUMERIK_EXPRESSION", syntax.syntax_error)
    trees = dict(syntax.scalar_expressions)
    values = [
        (
            word.letter,
            parameter_value(word.expr, state.siemens_parameters, state.siemens_variables, trees.get(word.expr)),
        )
        for word in block.parsed_words
    ]
    words = dict(values)
    words["_G"] = tuple(value for letter, value in values if letter == "G")
    words["_M"] = tuple(value for letter, value in values if letter == "M")
    return words, tuple(values)


def _switch_mode(state, block, words):
    switches = set(words["_G"]) & {290, 291}
    if not switches:
        return False
    if (
        len(switches) != 1
        or any(letter not in {"N", "G"} for letter in words if not letter.startswith("_"))
        or len(words["_G"]) != 1
    ):
        raise SemanticError("SINUMERIK_MODE_SWITCH_MUST_BE_STANDALONE", "G290/G291 must be alone in an NC block")
    state.native = 290 in switches
    state.events.append(ExecutionEvent("source_mode_change", block.index, "G290" if state.native else "G291"))
    return True


def _check_words(state, words, syntax):
    codes = set(words["_G"])
    iso_modes = {32, 50, 98, 99} if state.iso_system == "A" else {33, 90, 91, 92, 94, 95}
    allowed = _NATIVE_CODES if state.native else _ISO_COMMON | iso_modes
    if codes - allowed:
        unsupported("Unsupported turning G codes: " + ", ".join(f"G{value:g}" for value in sorted(codes - allowed)))
    axes = {"X", "Z", "I", "K", "CR", "F", "S", "T", "D", "N", "G", "M", "LIMS"}
    if not state.native:
        axes |= {"U", "W", "R", "P"}
    unknown = set(words) - axes - {"_G", "_M"}
    if unknown or syntax.ignored_native_commands or syntax.cip:
        unsupported(
            "Unsupported turning addresses or modifiers: "
            + ", ".join(sorted(unknown | set(syntax.ignored_native_commands)))
        )
    native_modifiers = (
        syntax.ignored_diameter_modes
        or syntax.incremental_linear
        or syntax.absolute_center
        or syntax.supa
        or "LIMS" in words
        or "CR" in words
    )
    if not state.native and native_modifiers:
        unsupported("Native Siemens modifiers require G290")


def _coordinate_modes(state, words, syntax):
    codes = set(words["_G"])
    if state.native or state.iso_system == "B":
        if {90, 91} <= codes:
            raise SemanticError("CONFLICTING_DISTANCE_MODES", "G90 and G91 cannot share a block")
        if codes & {90, 91}:
            state.absolute = 90 in codes
    for code in words["_G"]:
        if state.native and code in {70, 71, 700, 710} or not state.native and code in {20, 21}:
            state.unit_scale = 25.4 if code in {70, 700, 20} else 1.0
            if code in {700, 710, 20, 21}:
                state.feed_scale = state.unit_scale
        if 54 <= code <= 59 or state.native and code == 500:
            state.rebase(wcs=int(code))
    if len(syntax.ignored_diameter_modes) > 1:
        raise SemanticError("CONFLICTING_DIAMETER_MODES", "Use one diameter mode per block")
    if syntax.ignored_diameter_modes:
        state.diameter_mode = syntax.ignored_diameter_modes[0]


def _feed_and_compensation(state, words):
    codes = set(words["_G"])
    minute, revolution = (94, 95) if state.native or state.iso_system == "B" else (98, 99)
    if {minute, revolution} <= codes:
        raise SemanticError("CONFLICTING_FEED_MODES", "Conflicting turning feed modes")
    if minute in codes:
        state.feed_mode = "per_minute"
    elif revolution in codes:
        state.feed_mode = "per_revolution"
    if "F" in words and 4 not in codes:
        if words["F"] <= 0:
            raise SemanticError("INVALID_FEED", "Turning feed must be positive")
        state.feed = words["F"] * state.feed_scale
    comp = codes & {40, 41, 42}
    if len(comp) > 1:
        raise SemanticError("CONFLICTING_COMPENSATION", "Conflicting G40/G41/G42")
    if comp:
        state.cutter_comp = int(next(iter(comp)))


def _iso_spindle_clamp(state, words):
    code = 50 if state.iso_system == "A" else 92
    if state.native or code not in words["_G"]:
        return False
    if "S" not in words or any(axis in words for axis in "XZUW") or words["S"] <= 0:
        unsupported(f"ISO G{code} supports a positive S spindle clamp only")
    state.spindle_limit_rpm = words["S"]
    return True


def position_block(state, words, syntax, block):
    _check_words(state, words, syntax)
    _coordinate_modes(state, words, syntax)
    _feed_and_compensation(state, words)
    state.select_tool(words, syntax, block)
    if not _iso_spindle_clamp(state, words):
        state.spindle(words, words["_G"])
    state.machine_functions(words, block)
    if 4 in words["_G"]:
        _dwell(state, words, block)
        return
    _motion(state, words, syntax, block)


def _dwell(state, words, block):
    address = "F" if state.native else "X" if "X" in words else "P"
    if address not in words or "S" in words:
        unsupported("Dwell requires native G4 F seconds or ISO G4 X seconds / P milliseconds")
    seconds = words[address] / (1000 if address == "P" else 1)
    if seconds < 0:
        raise SemanticError("INVALID_DWELL", "Dwell must be nonnegative")
    state.signals.append(MachineSignal("dwell", block.index, "G4", seconds))


def _motion(state, words, syntax, block):
    explicit = set(words["_G"]) & {0, 1, 2, 3, 32, 33}
    if len(explicit) > 1:
        raise SemanticError("CONFLICTING_MOTION", "Conflicting motion codes")
    if explicit:
        state.modal_move = int(next(iter(explicit)))
    if not any(axis in words for axis in "XZUW"):
        return
    machine = syntax.supa or bool(set(words["_G"]) & {53, 153})
    if 28 in words["_G"]:
        unsupported("ISO G28 reference return is not implemented for Siemens turning")
    move = state.modal_move
    if machine and move not in {0, 1}:
        unsupported("Machine positioning supports G0/G1 only")
    target = state.target(words, syntax, machine=machine)
    radius = words.get("CR", words.get("R"))
    i, k = _arc_center(state, words, syntax) if move in {2, 3} else (None, None)
    threading = move in {32, 33}
    feed = _thread_pitch(state, words) if threading else state.feed
    count = len(state.motions)
    state.emit(
        target,
        block,
        move=1 if threading else move,
        feed=feed,
        radius=None if radius is None else radius * state.unit_scale,
        i=i,
        k=k,
        threading=threading,
    )
    if machine and len(state.motions) > count:
        state.motions[-1] = replace(state.motions[-1], source_kind="supa" if syntax.supa else "g53")


def _arc_center(state, words, syntax):
    output = []
    for axis, coordinate in (("I", state.position.x), ("K", state.position.z)):
        value = words.get(axis)
        if value is not None:
            value *= state.unit_scale
            if axis in syntax.absolute_center:
                value -= coordinate
        output.append(value)
    return tuple(output)


def _thread_pitch(state, words):
    names = ("I", "K") if state.native else ("F",)
    leads = [abs(words[name]) * state.unit_scale for name in names if name in words]
    if len(leads) != 1 or leads[0] <= 0:
        unsupported("Thread motion requires one positive native I/K lead or ISO F lead")
    return leads[0]


def _frame(state, syntax):
    if syntax.frame_command not in {"TRANS", "ATRANS"}:
        unsupported("Turning supports TRANS/ATRANS translations; rotary/scaled frames are not modeled")
    values = {
        axis: parameter_value(expr, state.siemens_parameters, state.siemens_variables) * state.unit_scale
        for axis, expr in syntax.frame_values
    }
    if set(values) - {"X", "Z"}:
        unsupported("Turning frame supports X/Z only")
    before = state.shift if syntax.frame_command == "ATRANS" else Point2(0, 0)
    state.rebase(shift=Point2(before.x + values.get("X", 0), before.z + values.get("Z", 0)))
