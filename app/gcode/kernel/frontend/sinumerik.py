"""Small native SINUMERIK lexical extension; source text is never translated.

Unknown language constructs retain their original FANUC-neutral Block so the
controller gate can fail closed. Native addresses remain visible in the AST.
"""

import re
from dataclasses import replace

from ...comments import strip_comments
from ..api.resources import checkpointed
from .ast import NativeMillingSyntax, build_program_ast
from .lang import WordToken
from .model import Program
from .program import _parse_source_blocks

_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
_VALUE = rf"(?:{_NUMBER}|R\d+)"
_TOKEN = re.compile(
    rf"\s*(?:(CR|TURN)\s*=\s*({_VALUE})|(SUPA)\b|([XYZIJKFS])\s*=\s*({_VALUE})|"
    rf"([NOGXYZABCIJKRFSTHDPQLM])\s*({_NUMBER}))",
    re.I,
)
_PARAMETER = re.compile(rf"R(\d+)\s*=\s*({_NUMBER})\s*", re.I)
_LABEL = re.compile(r"^\s*(?:N\d+\s*)?", re.I)
_MESSAGE = re.compile(r'MSG\s*\(\s*"(?:[^"\n]|"")*"\s*\)\s*', re.I)
_WORKPIECE = re.compile(rf'WORKPIECE\s*\((?:\s*(?:{_NUMBER}|"[^"\n]*")?\s*,)*\s*(?:{_NUMBER}|"[^"\n]*")?\s*\)\s*', re.I)
_CYCLE = re.compile(r"MCALL\s+CYCLE(\d+)\s*\(([^()]*)\)\s*", re.I)


def _native_tokens(raw):
    code = raw.split(";", 1)[0].strip().lstrip("/").strip()
    body = _LABEL.sub("", code, count=1)
    assignment = _PARAMETER.fullmatch(body)
    if assignment is not None:
        return (), NativeMillingSyntax("parameter_assignment", parameter_assignment=(int(assignment[1]), assignment[2]))
    cycle = _cycle_syntax(body)
    if cycle is not None:
        return (), cycle
    if _MESSAGE.fullmatch(body):
        return (), NativeMillingSyntax("message")
    if _WORKPIECE.fullmatch(body):
        return (), NativeMillingSyntax("workpiece")
    return _word_tokens(code)


def _word_tokens(code):
    code = strip_comments(code)
    tokens, supa, position = [], False, 0
    while position < len(code):
        match = _TOKEN.match(code, position)
        if match is None:
            return None
        special, special_value, suppress, assigned_letter, assigned_value, letter, value = match.groups()
        if suppress:
            if supa:
                return None
            supa = True
        else:
            tokens.append(
                WordToken((special or assigned_letter or letter).upper(), special_value or assigned_value or value)
            )
        position = match.end()
    return tuple(tokens), NativeMillingSyntax(supa=supa)


def _cycle_syntax(body):
    if body.upper() == "MCALL":
        return NativeMillingSyntax("cycle_cancel")
    if re.fullmatch(r"CYCLE800\s*\(\s*\)", body, re.I):
        return NativeMillingSyntax("frame_reset")
    match = _CYCLE.fullmatch(body)
    if match is None:
        return None
    args = tuple(arg.strip() for arg in match.group(2).split(","))
    if any(arg and not re.fullmatch(_VALUE, arg, re.I) for arg in args):
        return None
    return NativeMillingSyntax("cycle", cycle_code=int(match.group(1)), cycle_args=args)


def parse_sinumerik_program(source):
    """Extend parsed blocks with explicit native lexical facts, keeping raw/index."""
    blocks = []
    for _, block in checkpointed(_parse_source_blocks(source)):
        parsed = _native_tokens(block.raw)
        if parsed is None:
            blocks.append(block)
            continue
        tokens, syntax = parsed
        motion = block.motion_node if syntax.kind == "words" else None
        if motion is not None:
            radius = next((token.expr for token in tokens if token.letter == "CR"), motion.r_expr)
            motion = replace(motion, r_expr=radius, c_expr=None if radius is not None else motion.c_expr)
        blocks.append(replace(block, parsed_words=tokens, motion_node=motion, native_syntax=syntax))
    blocks = tuple(blocks)
    return Program._from_canonical_ast(blocks, build_program_ast(blocks))  # pylint: disable=protected-access
