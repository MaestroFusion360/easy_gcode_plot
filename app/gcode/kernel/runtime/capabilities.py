"""Controller policy boundary before expression evaluation and runtime dispatch.

Blocks/AST remain source descriptions, SemanticInstruction is a public view,
and ExecutionEvent records execution. Controller policy belongs to runtime.
The two phases of this gate protect both Macro B evaluation and numeric dispatch.
"""

import re

from ...comments import strip_comments
from ..milling.sinumerik_iso import (
    _diag,
    mode_switch_code,
    mode_switch_diagnostic,
    unsupported_iso_macro_diagnostic,
    unsupported_siemens_mode_diagnostic,
    validate_and_normalize_iso_block,
)
from ..milling.sinumerik_native import NATIVE_G_CODES, normalize_native_block
from .execution import BlockCodes, EvaluatedBlock

COMMON_ISO_G_CODES = frozenset(
    {0, 1, 2, 3, 4, 17, 18, 19, 20, 21, 28, 40, 43, 49, 53, 54, 55, 56, 57, 58, 59, 90, 91, 94, 95}
)
COMMON_ISO_M_CODES = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 30})
_NUMERIC_BLOCK = re.compile(r"(?:\s*[NOGXYZABCIJKRFSTHDPQLM]\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+))*\s*", re.I)
_MACRO = re.compile(r"#|\b(?:IF|THEN|GOTO|WHILE|DO|END)\b", re.I)
_HEADER = re.compile(r"%_N_[A-Z0-9_]+_(?:MPF|SPF)", re.I)


def _source_diagnostic(block, mode):
    code = strip_comments(block.raw).lstrip("/").strip()
    if mode == "sinumerik_native" and block.native_syntax is not None:
        return None
    if block.flow_node is not None or _MACRO.search(code):
        return unsupported_iso_macro_diagnostic(block)
    if code == "%" or _HEADER.fullmatch(code):
        return None
    if not _NUMERIC_BLOCK.fullmatch(code):
        return unsupported_siemens_mode_diagnostic(block)
    return None


def _numeric_diagnostic(block, evaluated, mode):
    for code in evaluated.codes.all_m:
        if code not in COMMON_ISO_M_CODES:
            return _diag(
                block,
                "UNSUPPORTED_SINUMERIK_M_CODE",
                f"M{code:g} is not supported in {mode}",
                cnc_codes=(f"M{code:g}",),
            )
    if any(axis in evaluated.words for axis in ("A", "B", "C")):
        return _diag(block, "UNSUPPORTED_SINUMERIK_ROTARY", "SINUMERIK rotary semantics are not modeled")
    if mode == "sinumerik_native":
        for code in evaluated.codes.all_g:
            if code not in COMMON_ISO_G_CODES | NATIVE_G_CODES:
                return _diag(
                    block,
                    "UNSUPPORTED_SINUMERIK_MODE",
                    f"G{code:g} is not supported in native mode",
                    cnc_codes=(f"G{code:g}",),
                )
    return None


_POSITION_CODES = BlockCodes((), (), None, None)


def common_iso_fast_block(block, runtime, state, words):
    """Validate one literal position block before compiled state mutation.

    The compiled loop accepts only N/XYZ/IJK/R here; controller declarations,
    mode switches and all G/M words stay on the reference execution path.
    A rejection stops the run so Python can emit the authoritative diagnostic.
    """
    _, diagnostic, _ = controller_capability_gate(runtime, block, state=state)
    if diagnostic is not None:
        return False
    evaluated = EvaluatedBlock(words, _POSITION_CODES, (), ())
    _, diagnostic, switch = controller_capability_gate(runtime, block, evaluated, state=state)
    return diagnostic is None and switch is None


def _native_state_diagnostic(block, state):
    transform = state.transform
    incompatible = (
        state.cycle != 80
        or state.native_cycle is not None
        or transform.rotation_active
        or transform.scaling_active
        or transform.translation != (0.0, 0.0, 0.0)
        or any(state.rotary_angles.values())
        or state.active_wcs >= 1000
    )
    if incompatible:
        return _diag(
            block,
            "UNSUPPORTED_SINUMERIK_MODE",
            "Cancel ISO-M cycles, transforms, extended offsets and rotary indexing before G290",
        )
    return None


def controller_capability_gate(runtime, block, evaluated=None, *, state):
    """Return normalized block, rejection, and committed standalone switch.

    Call without evaluated words before Macro B dispatch/evaluation, then with
    evaluated words before G65, M flow, tool/modal, cycles and geometry dispatch.
    FANUC policy is deliberately transparent to preserve existing behavior.
    """
    mode = runtime.controller_mode
    if mode == "fanuc":
        return evaluated, None, None
    diagnostic = _source_diagnostic(block, mode)
    if diagnostic is not None or evaluated is None:
        return evaluated, diagnostic, None
    switch = mode_switch_code(evaluated)
    if switch is not None:
        diagnostic = mode_switch_diagnostic(block, evaluated)
        if diagnostic is None and switch == 290:
            diagnostic = _native_state_diagnostic(block, state)
        if diagnostic is None and switch == 291 and state.cutter_comp != 40:
            diagnostic = _diag(block, "UNSUPPORTED_SINUMERIK_ISO_G_CODE", "Cancel native G41/G42 with G40 before G291")
        if diagnostic is None and switch == 291 and state.native_cycle is not None:
            diagnostic = _diag(block, "UNSUPPORTED_SINUMERIK_CYCLE", "Cancel native MCALL before G291")
        if diagnostic is not None:
            return evaluated, diagnostic, None
        runtime.controller_mode = "sinumerik_iso" if switch == 291 else "sinumerik_native"
        return evaluated, None, switch
    diagnostic = _numeric_diagnostic(block, evaluated, mode)
    if diagnostic is not None or mode == "sinumerik_native":
        if diagnostic is None:
            evaluated, diagnostic = normalize_native_block(block, evaluated, state)
        return evaluated, diagnostic, None
    gcodes = evaluated.codes.all_g
    absolute = next((g == 90 for g in reversed(gcodes) if g in (90, 91)), state.absolute)
    plane = next((int(g) for g in reversed(gcodes) if g in (17, 18, 19)), state.plane)
    normalized, diagnostic = validate_and_normalize_iso_block(
        block, evaluated, absolute_mode=absolute, active_plane=plane
    )
    return normalized, diagnostic, None
