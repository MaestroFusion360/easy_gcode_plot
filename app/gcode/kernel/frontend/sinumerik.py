"""Small native SINUMERIK lexical extension; source text is never translated.

Unknown language constructs retain their original FANUC-neutral Block so the
controller gate can fail closed. Native addresses remain visible in the AST.
"""

import re
from dataclasses import replace

from ..api.resources import SemanticError, checkpointed
from .ast import NativeMillingSyntax, build_program_ast
from .lang import WordToken
from .model import Program
from .program import _parse_source_blocks
from .sinumerik_expression import compile_expression

_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
_NAME = r"_[A-Z][A-Z0-9_]{0,30}"
_VALUE = rf"(?:{_NUMBER}|R\d+|{_NAME})"
_TOKEN = re.compile(
    rf"\s*(?:(CR|TURN|CHF|CHR|RND|RNDM|FRC|FRCM)\s*=\s*({_VALUE})|"
    rf"(SUPA|FNORM|DIAMON|DIAMOF|DIAM90|ORIWKS|ORIMKS|ORIAXES|ORIVECT|FFWON|FFWOF|UPATH|SOFT|"
    rf"COMPCAD|COMPCURV|ORIRESET|CUT3DFF|CUT3DF|CUT3DC)\b|([XYZABCIJKFS])\s*=\s*({_VALUE})|"
    rf"([NOGXYZABCIJKRFSTHDPQLM])\s*({_NUMBER}))",
    re.I,
)
_PARAMETER = re.compile(r"R(\d+)\s*=\s*(.+)\s*", re.I)
_REAL = re.compile(rf"DEF\s+REAL\s+({_NAME}(?:\s*,\s*{_NAME})*)\s*", re.I)
_NAMED_ASSIGNMENT = re.compile(rf"\s*({_NAME})\s*=\s*({_VALUE})", re.I)
_NAMED_TOOL = re.compile(r'\s*T\s*=\s*"([^"\n]{1,32})"', re.I)
_HSC = re.compile(r"CYCLE832\s*\(([^()]*)\)\s*", re.I)
_LABEL = re.compile(r"^\s*(?:N\d+\s*)?", re.I)
_MESSAGE = re.compile(r'MSG\s*\(\s*(?:"(?:[^"\n]|"")*")?\s*\)\s*', re.I)
_WORKPIECE = re.compile(rf'WORKPIECE\s*\((?:\s*(?:{_NUMBER}|"[^"\n]*")?\s*,)*\s*(?:{_NUMBER}|"[^"\n]*")?\s*\)\s*', re.I)
_CYCLE = re.compile(r"MCALL\s+CYCLE(\d+)\s*\((.*)\)\s*", re.I)
_SWIVEL = re.compile(r"CYCLE800\s*\(([^()]*)\)\s*", re.I)
_INCREMENT = re.compile(rf"\s*([XYZABCIJK])\s*=\s*(IC|DC|AC)\s*\(\s*({_VALUE})\s*\)", re.I)
_NATIVE_COMMENT = re.compile(r"\b(?:IC|DC|AC)\s*\([^()]*\)|\([^()]*\)", re.I)


def _native_tokens(raw):
    code = raw.split(";", 1)[0].strip().lstrip("/").strip()
    body = _LABEL.sub("", code, count=1)
    flow = _native_flow(body)
    if flow is not None:
        return (), flow
    declaration = _native_declaration(body)
    if declaration is not None:
        return (), declaration
    cycle = _cycle_syntax(body)
    if cycle is not None:
        return (), cycle
    if _MESSAGE.fullmatch(body):
        return (), NativeMillingSyntax("message")
    if _WORKPIECE.fullmatch(body):
        return (), NativeMillingSyntax("workpiece")
    return _word_tokens(code)


def _native_flow(body):
    if body.upper() == "ENDWHILE":
        return NativeMillingSyntax("endwhile")
    match = re.fullmatch(r"WHILE\s+(.+)", body, re.I)
    if match:
        return NativeMillingSyntax("while", flow_condition=compile_expression(match[1]))
    match = re.fullmatch(r"(?:(IF)\s+(.+?)\s+)?GOTO\s+N?(\d{1,9})", body, re.I)
    if match:
        return NativeMillingSyntax(
            "if_goto" if match[1] else "goto",
            flow_condition=compile_expression(match[2]) if match[1] else None,
            flow_target=int(match[3]),
        )
    # Directional jump and subroutine-return semantics are outside this subset.
    if re.match(r"(?:WHILE|ENDWHILE|IF|GOTO[ FBC]*|RET)\b", body, re.I):
        return NativeMillingSyntax("invalid_flow", syntax_error="Unsupported or malformed native control flow")
    return None


def _native_declaration(body):
    real = _REAL.fullmatch(body)
    if real is not None:
        return NativeMillingSyntax(
            "real_declaration", real_declarations=tuple(name.strip().upper() for name in real[1].split(","))
        )
    assignments = _named_assignments(body)
    if assignments is not None:
        return NativeMillingSyntax("named_assignment", named_assignments=assignments)
    assignment = _PARAMETER.fullmatch(body)
    if assignment is not None:
        compile_expression(assignment[2])
        if len(assignment[1]) > 4:
            raise SemanticError("INVALID_SINUMERIK_PARAMETER", "R index must be within 0..9999")
        return NativeMillingSyntax("parameter_assignment", parameter_assignment=(int(assignment[1]), assignment[2]))
    return _native_metadata(body)


def _native_metadata(body):
    unmodeled = re.match(r"(SCALE|ASCALE|MIRROR|AMIRROR)\b", body, re.I)
    if unmodeled is not None:
        return NativeMillingSyntax("unmodeled_geometry", ignored_native_commands=(unmodeled[1].upper(),))
    return _native_supported_metadata(body)


def _native_supported_metadata(body):
    group = re.fullmatch(r"FGROUP\s*\(\s*[XYZABC](?:\s*,\s*[XYZABC])*\s*\)\s*", body, re.I)
    if group is not None:
        return NativeMillingSyntax("unmodeled", ignored_native_commands=("FGROUP",))
    if body.upper() in {"TRAORI", "TRAFOOF", "COMPOF"}:
        return NativeMillingSyntax(body.lower())
    if re.fullmatch(r"TRAORI\s*\(\s*1\s*\)", body, re.I):
        return NativeMillingSyntax("traori")
    hsc = _HSC.fullmatch(body)
    if hsc is not None:
        args = tuple(arg.strip() for arg in hsc[1].split(",")) if hsc[1].strip() else ()
        if len(args) <= 3 and all(re.fullmatch(_VALUE, arg, re.I) for arg in args):
            return NativeMillingSyntax("hsc_ignored", cycle_code=832, cycle_args=args)
    if re.fullmatch(r"SETMS\s*\(\s*1\s*\)", body, re.I):
        return NativeMillingSyntax("main_spindle")
    return _programmed_frame_syntax(body)


def _programmed_frame_syntax(body):
    command = re.match(r"(TRANS|ATRANS|ROT|AROT)\b", body, re.I)
    if command is None:
        return None
    values, position = [], command.end()
    while position < len(body):
        match = re.match(rf"\s*(RPL\s*=|[XYZ]\s*=?)\s*({_VALUE})", body[position:], re.I)
        if match is None:
            return None
        axis = match[1].replace("=", "").strip().upper()
        if any(item[0] == axis for item in values):
            return None
        values.append((axis, match[2]))
        position += match.end()
    if any(axis == "RPL" for axis, _ in values) and (len(values) != 1 or command[1].upper().endswith("TRANS")):
        return None
    return NativeMillingSyntax("programmed_frame", frame_command=command[1].upper(), frame_values=tuple(values))


def _named_assignments(body):
    assignments, position = [], 0
    while position < len(body):
        match = _NAMED_ASSIGNMENT.match(body, position)
        if match is None:
            return None
        assignments.append((match[1].upper(), match[2]))
        position = match.end()
        if position < len(body) and not body[position].isspace():
            return None
    return tuple(assignments) if assignments else None


def _word_tokens(code):
    # Parentheses in native address expressions are arithmetic/function syntax.
    code = code.strip()
    tokens, position = [], 0
    options = {
        "supa": False,
        "feed_normal": False,
        "named_tool": None,
        "ignored_diameter_modes": (),
        "ignored_native_commands": (),
        "cip": False,
        "intermediate_absolute": (),
        "intermediate_incremental": (),
    }
    modes = {"IC": [], "DC": [], "AC": []}
    while position < len(code):
        assigned = re.match(r"\s*(ANG|CR|TURN|CHF|CHR|RNDM?|FRCM?|[XYZABCIJKFS])\s*=\s*", code[position:], re.I)
        if assigned and not re.match(r"(?:IC|DC|AC)\s*\(", code[position + assigned.end() :], re.I):
            start = position + assigned.end()
            end = _expression_end(code, start)
            expression = code[start:end].strip()
            compile_expression(expression)
            if assigned[1].upper() == "ANG":
                return (), NativeMillingSyntax("unmodeled_geometry", ignored_native_commands=("ANG",))
            tokens.append(WordToken(assigned[1].upper(), expression))
            position = end
            continue
        special_end, valid = _scan_special_word(code, position, tokens, options, modes)
        if not valid:
            return None
        if special_end is not None:
            position = special_end
            continue
        match = _TOKEN.match(code, position)
        if match is None:
            return None
        special, special_value, suppress, assigned_letter, assigned_value, letter, value = match.groups()
        if suppress:
            if not _apply_marker(suppress.upper(), options):
                return None
        else:
            tokens.append(
                WordToken((special or assigned_letter or letter).upper(), special_value or assigned_value or value)
            )
        position = match.end()
    if not _valid_word_tokens(tokens, options, modes):
        return None
    return tuple(tokens), NativeMillingSyntax(
        incremental_rotary=tuple(axis for axis in modes["IC"] if axis in "ABC"),
        incremental_linear=tuple(axis for axis in modes["IC"] if axis in "XYZ"),
        direct_rotary=tuple(modes["DC"]),
        absolute_center=tuple(modes["AC"]),
        **options,
    )


def _expression_end(code, start):
    depth = 0
    for position in range(start, len(code)):
        char = code[position]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if depth == 0 and position > start:
            rest = code[position:]
            if re.match(r"\s+(?:[A-Z][A-Z0-9_]*(?:\s*=|\s*[+-]?\d)|SUPA\b|FNORM\b|M\d)", rest, re.I):
                return position
            if re.match(r"[GMNXYZABCIJKFSDT]\s*(?:=|[+-]?\d)", rest, re.I):
                return position
    return len(code)


def _scan_special_word(code, position, tokens, options, modes):
    spatial = _scan_spatial_word(code, position, tokens, options)
    return spatial if spatial is not None else _scan_other_special_word(code, position, tokens, options, modes)


def _scan_spatial_word(code, position, tokens, options):
    cip = re.match(r"\s*CIP\b", code[position:], re.I)
    if cip is not None:
        valid = not options["cip"]
        options["cip"] = True
        return position + cip.end(), valid
    intermediate = re.match(rf"\s*([IJK]1)\s*=\s*(?:(AC|IC)\s*\(\s*({_VALUE})\s*\)|({_VALUE}))", code[position:], re.I)
    if intermediate is not None:
        axis, mode = intermediate[1].upper(), (intermediate[2] or "").upper()
        if any(token.letter == axis for token in tokens):
            return position + intermediate.end(), False
        tokens.append(WordToken(axis, intermediate[3] or intermediate[4]))
        if mode:
            key = "intermediate_absolute" if mode == "AC" else "intermediate_incremental"
            options[key] += (axis,)
        return position + intermediate.end(), True
    return None


def _scan_other_special_word(code, position, tokens, options, modes):
    ignored = re.match(rf"\s*(FL\[[XYZABC]\]|FGREF\[[XYZABC]\]|SPOS)\s*=\s*({_VALUE})", code[position:], re.I)
    if ignored is not None:
        options["ignored_native_commands"] += (ignored[1].upper(),)
        return position + ignored.end(), True
    tool = _NAMED_TOOL.match(code, position)
    if tool is not None:
        if options["named_tool"] is not None:
            return tool.end(), False
        options["named_tool"] = tool[1]
        return tool.end(), True
    rotary = _INCREMENT.match(code, position)
    if rotary is not None:
        axis = rotary[1].upper()
        allowed = {"IC": "XYZABC", "DC": "ABC", "AC": "IJK"}[rotary[2].upper()]
        if any(axis in axes for axes in modes.values()) or axis not in allowed:
            return rotary.end(), False
        tokens.append(WordToken(axis, rotary[3]))
        modes[rotary[2].upper()].append(axis)
        return rotary.end(), True
    return None, True


def _apply_marker(marker, options):
    if marker not in ("SUPA", "FNORM", "DIAMON", "DIAMOF", "DIAM90"):
        options["ignored_native_commands"] += (marker,)
        return True
    if marker in ("DIAMON", "DIAMOF", "DIAM90"):
        options["ignored_diameter_modes"] += (marker,)
        return True
    if marker == "SUPA" and options["supa"]:
        return False
    options["supa" if marker == "SUPA" else "feed_normal"] = True
    return True


def _valid_word_tokens(tokens, options, modes):
    if any(sum(token.letter == axis for token in tokens) != 1 for axis in (*modes["IC"], *modes["DC"], *modes["AC"])):
        return False
    return options["named_tool"] is None or not any(token.letter == "T" for token in tokens)


def _cycle_syntax(body):
    if body.upper() == "MCALL":
        return NativeMillingSyntax("cycle_cancel")
    if body.upper() == "CYCLE800" or re.fullmatch(r"CYCLE800\s*\(\s*\)", body, re.I):
        return NativeMillingSyntax("frame_reset")
    swivel = _SWIVEL.fullmatch(body)
    if swivel is not None:
        return _swivel_syntax(swivel[1])
    match = _CYCLE.fullmatch(body)
    if match is None:
        return None
    args = tuple(arg.strip() for arg in match.group(2).split(","))
    for arg in args:
        if arg:
            compile_expression(arg)
    return NativeMillingSyntax("cycle", cycle_code=int(match.group(1)), cycle_args=args)


def _swivel_syntax(arguments):
    args = tuple(arg.strip() for arg in arguments.split(","))
    if len(args) not in (14, 15, 16) or not re.fullmatch(r'"[^"\n]{0,32}"', args[1]):
        return None
    if any(arg and not re.fullmatch(_VALUE, arg, re.I) for i, arg in enumerate(args) if i != 1):
        return None
    return NativeMillingSyntax("swivel", cycle_code=800, cycle_args=args + ("",) * (16 - len(args)))


def parse_sinumerik_program(source):
    """Extend parsed blocks with explicit native lexical facts, keeping raw/index."""
    blocks = []
    for _, block in checkpointed(_parse_source_blocks(source)):
        label = re.match(r"\s*/?\s*N(\d+)", block.raw, re.I)
        # A jump operand N99 is a target, never a source sequence label.
        block = replace(block, nlabel=int(label[1]) if label else None)
        try:
            parsed = _native_tokens(block.raw)
        except SemanticError as error:
            parsed = (), NativeMillingSyntax("invalid_expression", syntax_error=str(error))
        if parsed is None:
            blocks.append(block)
            continue
        tokens, syntax = parsed
        expressions = [token.expr for token in tokens]
        if syntax.parameter_assignment:
            expressions.append(syntax.parameter_assignment[1])
        expressions.extend(value for _, value in syntax.named_assignments)
        expressions.extend(arg for arg in syntax.cycle_args if arg and not arg.startswith('"'))
        try:
            syntax = replace(syntax, scalar_expressions=tuple((expr, compile_expression(expr)) for expr in expressions))
        except SemanticError as error:
            tokens, syntax = (), NativeMillingSyntax("invalid_expression", syntax_error=str(error))
        motion = block.motion_node if syntax.kind == "words" else None
        if motion is not None:
            radius = next((token.expr for token in tokens if token.letter == "CR"), motion.r_expr)
            motion = replace(motion, r_expr=radius, c_expr=None if radius is not None else motion.c_expr)
        blocks.append(replace(block, parsed_words=tokens, motion_node=motion, flow_node=None, native_syntax=syntax))
    blocks = tuple(blocks)
    return Program._from_canonical_ast(blocks, build_program_ast(blocks))  # pylint: disable=protected-access
