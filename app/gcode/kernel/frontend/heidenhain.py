"""Independent Klartext frontend for iTNC 530 source.

Source commands and Q expressions remain native. Every physical line retains
its Block and diagnostic location, including multiline cycle definitions.
"""

from __future__ import annotations

import re
from dataclasses import replace

from ..resources import checkpointed
from .ast import build_program_ast
from .heidenhain_expression import HeidenhainExpression, HeidenhainExpressionError, compile_heidenhain_expression
from .heidenhain_lexer import HeidenhainParseError, lex_heidenhain_line, lex_heidenhain_words, scalar_prefix
from .heidenhain_plane import parse_plane, parse_tcp
from .heidenhain_syntax import HeidenhainCycleParameter, HeidenhainMachineFunction, HeidenhainSyntax, HeidenhainWord
from .model import Block, ModalSnapshot, Program

_AXES = frozenset((*"XYZABCUVW", *("I" + axis for axis in "XYZABCUVW")))
_CONTROLS = frozenset(("F", "FMAX", "FAUTO", "S", "RL", "RR", "R0", "M", "LA", "MB", "MB MAX"))
_COMMANDS = {
    "L": ("motion", _AXES | _CONTROLS),
    "C": ("motion", _AXES | _CONTROLS | {"DR+", "DR-"}),
    "CR": ("motion", _AXES | _CONTROLS | {"R", "DR+", "DR-"}),
    "CT": ("motion", _AXES | _CONTROLS),
    "LP": ("motion", _AXES | _CONTROLS | {"PR", "IPR", "PA", "IPA"}),
    "CP": ("motion", _AXES | _CONTROLS | {"PA", "IPA", "DR+", "DR-"}),
    "CC": ("center", _AXES),
    "RND": ("contour", frozenset(("R", "F"))),
    "CHF": ("contour", frozenset(("L", "F"))),
}
_CONTOUR = _AXES | _CONTROLS | {"R", "LEN", "CCA"}


def _expression(source, line, column):
    try:
        return compile_heidenhain_expression(source)
    except HeidenhainExpressionError as exc:
        raise HeidenhainParseError(str(exc), line, column + exc.column + 1) from exc


def _words(body, line, offset, allowed, *, direction=True, flags=True):
    words = lex_heidenhain_words(body, line, offset=offset, direction=direction, flags=flags)
    for word in words:
        if word.address not in allowed:
            raise HeidenhainParseError(
                "Address is not valid for this Klartext command: " + word.address, line, word.column + 1
            )
    return words


def _label(source, line, offset):
    quoted = re.match(r'"((?:[^"\n]|"")+)"', source)
    if quoted is not None:
        return quoted[1].replace('""', '"'), None, quoted.end()
    expression, end = scalar_prefix(source, line, line.column + offset)
    if expression.kind == "number" and expression.value.isdigit():
        if len(expression.value) > 9:
            raise HeidenhainParseError("Label number exceeds nine digits", line, line.column + offset + 1)
        return int(expression.value), None, end
    if expression.kind != "parameter":
        raise HeidenhainParseError(
            "LBL requires an integer, quoted name or Q parameter", line, line.column + offset + 1
        )
    return None, expression, end


def _motion(line, command, offset):
    kind, allowed = _COMMANDS[command]
    body = line.body[offset:]
    # CHF takes a positional side length, unlike the addressed radius in RND.
    if command == "CHF" and not body.lstrip().upper().startswith("L"):
        leading = len(body) - len(body.lstrip())
        expression, length = scalar_prefix(body[leading:], line, line.column + offset + leading)
        end = leading + length
        words = (HeidenhainWord("L", body[leading:end], line.column + offset + leading, expression),)
        words += _words(body[end:], line, offset + end, allowed, flags=False)
    else:
        words = _words(body, line, offset, allowed, flags=kind == "motion")
    syntax = _machine_functions(HeidenhainSyntax(kind, command, words), line)
    addresses = {word.address for word in syntax.positioning_words}
    if command not in {"CC", "L"} and not words:
        raise HeidenhainParseError("Klartext command requires addresses", line, line.column + offset + 1)
    required = {"CR": {"R"}, "RND": {"R"}, "CHF": {"L"}}.get(command, set())
    if not required <= addresses:
        raise HeidenhainParseError(
            "Missing required Klartext address: " + ", ".join(sorted(required - addresses)), line
        )
    if {"DR+", "DR-"} <= addresses or len(addresses & {"RL", "RR", "R0"}) > 1:
        raise HeidenhainParseError("Conflicting Klartext direction or compensation modes", line)
    if len(addresses & {"F", "FMAX", "FAUTO"}) > 1:
        raise HeidenhainParseError("Conflicting Klartext feed modes", line)
    if command in {"C", "CR", "CP"} and not addresses & {"DR+", "DR-"}:
        raise HeidenhainParseError("Circular Klartext motion requires DR+ or DR-", line)
    return syntax


def _contour(line):
    match = re.match(r"(APPR|DEP)\s+(LCT|LT|LN|CT)\b", line.body, re.I)
    if match is None:
        raise HeidenhainParseError("Unknown Klartext approach/departure form", line)
    words = _words(line.body[match.end() :], line, match.end(), _CONTOUR)
    required = {"LT": {"LEN"}, "LN": {"LEN"}, "CT": {"R", "CCA"}, "LCT": {"R"}}[match[2].upper()]
    if not required <= {word.address for word in words}:
        raise HeidenhainParseError("Missing approach/departure geometry: " + ", ".join(sorted(required)), line)
    return HeidenhainSyntax("contour", match[1].upper() + " " + match[2].upper(), words)


def _boundary(line):
    match = re.fullmatch(r'(BEGIN|END)\s+PGM\s+("(?:[^"\n]|"")+"|[^"\n]+?)(?:\s+(MM|INCH))?', line.body, re.I)
    if match is None:
        raise HeidenhainParseError("Expected BEGIN/END PGM name MM/INCH", line)
    name = match[2]
    if name.startswith('"'):
        name = name[1:-1].replace('""', '"')
    warnings = () if match[3] else ("Program boundary omits MM/INCH; configured units are used",)
    return HeidenhainSyntax(
        "program",
        match[1].upper() + " PGM",
        program_name=name,
        units=match[3].upper() if match[3] else None,
        warnings=warnings,
    )


def _stock(line):
    match = re.match(r"BLK\s+FORM\s+(0\.[12])\s+(?:([XYZ])\s+)?", line.body, re.I)
    if match is None:
        raise HeidenhainParseError("Expected rectangular BLK FORM 0.1/0.2", line)
    words = _words(line.body[match.end() :], line, match.end(), frozenset("XYZ"), flags=False)
    if {word.address for word in words} != set("XYZ"):
        raise HeidenhainParseError("BLK FORM requires X, Y and Z bounds", line)
    return HeidenhainSyntax("stock", "BLK FORM " + match[1], words, spindle_axis=match[2].upper() if match[2] else None)


def _tool(line):
    match = re.match(r"TOOL\s+(CALL|DEF)\s+", line.body, re.I)
    if match is None:
        raise HeidenhainParseError("Expected TOOL CALL or TOOL DEF", line)
    position = match.end()
    axis_only = re.match(r"([XYZ])(?=\s|$)", line.body[position:], re.I) if match[1].upper() == "CALL" else None
    quoted = re.match(r'"((?:[^"\n]|"")+)"', line.body[position:])
    if axis_only:
        tool, length = None, 0
    elif quoted:
        tool, length = quoted[1].replace('""', '"'), quoted.end()
    else:
        tool, length = scalar_prefix(line.body[position:], line, line.column + position)
    position += length
    axis = re.match(r"\s*([XYZ])(?=\s|$)", line.body[position:], re.I)
    if axis is not None:
        position += axis.end()
    allowed = frozenset(("S", "F", "DL", "DR", "DR2", "M")) if match[1].upper() == "CALL" else frozenset(("L", "R"))
    words = _words(line.body[position:], line, position, allowed, direction=False, flags=False)
    return HeidenhainSyntax(
        "tool", "TOOL " + match[1].upper(), words, tool=tool, spindle_axis=axis[1].upper() if axis else None
    )


def _label_command(line):
    match = re.match(r"(CALL\s+LBL|LBL)\s+", line.body, re.I)
    if match is None:
        raise HeidenhainParseError("Expected LBL or CALL LBL target", line)
    value, expression, end = _label(line.body[match.end() :], line, match.end())
    position = match.end() + end
    tail = line.body[position:].strip()
    repeat = None
    if tail:
        rep = re.fullmatch(r"REP\s*(.+)", tail, re.I) if match[1].upper().startswith("CALL") else None
        if rep is None:
            raise HeidenhainParseError("Unexpected tokens after label", line, line.column + position + 1)
        repeat = _expression(rep[1], line, line.body.index(rep[1], position) + line.column)
    return HeidenhainSyntax(
        "label",
        "CALL LBL" if match[1].upper().startswith("CALL") else "LBL",
        label=value,
        label_expression=expression,
        repeat=repeat,
    )


def _parameter(line):
    body, offset, fn = line.body, 0, None
    if body.upper().startswith("FN"):
        match = re.match(r"FN\s*(\d{1,2})\s*:\s*", body, re.I)
        if match is None:
            raise HeidenhainParseError("Malformed FN instruction", line)
        fn, offset = int(match[1]), match.end()
        if fn in {9, 10, 11, 12}:
            return _conditional(line, fn, offset)
        if fn not in {0, 1, 2, 3, 4, 6, 7}:
            raise HeidenhainParseError(
                "Unsupported Klartext FN operation", line, code="UNSUPPORTED_HEIDENHAIN_SYNTAX", status="unsupported"
            )
    match = re.match(r"((?:QL|QR|Q)\d+)\s*=\s*(.+)", body[offset:], re.I)
    if match is None:
        raise HeidenhainParseError("Expected Q parameter assignment", line, line.column + offset + 1)
    expression = (
        HeidenhainExpression("cycle_feed", "MAX", source=match[2])
        if fn is None and match[1].upper() in {"Q208", "Q253"} and match[2].strip().upper() in {"MAX", "FMAX"}
        else _expression(match[2], line, line.column + offset + match.start(2))
    )
    parameter = _expression(match[1], line, line.column + offset + match.start(1))
    operators = {1: {"+"}, 2: {"-"}, 3: {"*"}, 4: {"/", "DIV"}}.get(fn)
    if operators is not None and (expression.kind != "binary" or expression.value not in operators):
        raise HeidenhainParseError("FN arithmetic operation does not match its expression", line)
    function = {6: "SIN", 7: "COS"}.get(fn)
    if function is not None and (expression.kind != "function" or expression.value != function):
        raise HeidenhainParseError("FN trigonometric operation does not match its expression", line)
    return HeidenhainSyntax(
        "parameter",
        "FN " + str(fn) if fn is not None else "Q ASSIGN",
        fn_code=fn,
        assignment=(parameter.value, expression),
    )


def _conditional(line, fn, offset):
    match = re.fullmatch(r"IF\s+(.+?)\s+GOTO\s+LBL\s+(.+)", line.body[offset:], re.I)
    if match is None:
        raise HeidenhainParseError("Expected FN conditional IF ... GOTO LBL ...", line)
    condition = _expression(match[1], line, line.column + offset + match.start(1))
    expected = {9: "EQU", 10: "NE", 11: "GT", 12: "LT"}[fn]
    if condition.kind != "binary" or condition.value != expected:
        raise HeidenhainParseError("FN condition does not match its comparison", line)
    value, expression, end = _label(match[2], line, offset + match.start(2))
    if match[2][end:].strip():
        raise HeidenhainParseError("Unexpected tokens after conditional label", line)
    return HeidenhainSyntax(
        "label", "FN " + str(fn), fn_code=fn, condition=condition, label=value, label_expression=expression
    )


def _cycle(line):
    definition = re.match(r"CYCL\s+DEF\s+(\d{1,4})(?:\.(\d{1,2}))?(?=\s|$)\s*", line.body, re.I)
    if definition is not None:
        tail = line.body[definition.end() :]
        words = ()
        if tail and definition[2] is not None and int(definition[2]) > 0:
            if int(definition[1]) == 32:
                words = _words(tail, line, definition.end(), {"T"}, flags=False)
            elif int(definition[1]) in {7, 10}:
                allowed = {"X", "Y", "Z", "IX", "IY", "IZ"} if int(definition[1]) == 7 else {"ROT"}
                words = _words(tail, line, definition.end(), allowed, flags=False)
            else:
                value = re.sub(r"^(?:SET\s*UP|SET-UP|DEPTH|PECKG|PECKING|DWELL|FEED|PITCH)\s*", "", tail, flags=re.I)
                expression = _expression(value, line, line.column + definition.end() + len(tail) - len(value))
                words = (
                    HeidenhainWord("VALUE", value, line.column + definition.end() + len(tail) - len(value), expression),
                )
        return HeidenhainSyntax(
            "cycle",
            "CYCL DEF",
            words,
            cycle_code=int(definition[1]),
            cycle_subcode=int(definition[2]) if definition[2] is not None else None,
            cycle_name=tail if not words else None,
        )
    call = re.match(r"CYCL\s+CALL(?:\s+(POS|PAT)(?=\s|$))?(?=\s|$)\s*", line.body, re.I)
    if call is None:
        raise HeidenhainParseError("Expected CYCL DEF or CYCL CALL", line)
    allowed = _AXES | {"F", "FMAX", "M"} if call[1] and call[1].upper() == "POS" else {"M"}
    words = _words(line.body[call.end() :], line, call.end(), allowed)
    return HeidenhainSyntax("cycle", "CYCL CALL" + (" " + call[1].upper() if call[1] else ""), words)


def _syntax(line):
    if not line.body or line.body.startswith("*"):
        return HeidenhainSyntax("comment" if line.body or line.comment is not None else "empty", "")
    head = re.match(r"[A-Z]+", line.body, re.I)
    command = head[0].upper() if head else ""
    if command in _COMMANDS:
        return _motion(line, command, head.end())
    if command in _AXES:
        # CAM posts can omit L on a coordinate-only straight positioning block.
        return _motion(line, "L", 0)
    handler = {
        "BEGIN": _boundary,
        "END": _boundary,
        "BLK": _stock,
        "TOOL": _tool,
        "APPR": _contour,
        "DEP": _contour,
        "LBL": _label_command,
        "CALL": _label_command,
        "FN": _parameter,
        "Q": _parameter,
        "QL": _parameter,
        "QR": _parameter,
        "CYCL": _cycle,
        "PLANE": parse_plane,
        "FUNCTION": parse_tcp,
    }.get(command)
    if handler is not None:
        return handler(line)
    if command == "STOP":
        return HeidenhainSyntax("control", "STOP", _words(line.body[head.end() :], line, head.end(), {"M"}))
    if command in {"M", "S", "F", "FMAX", "FAUTO", "RL", "RR", "R"}:
        return HeidenhainSyntax("control", "CONTROL", _words(line.body, line, 0, _CONTROLS | {"S"}))
    raise HeidenhainParseError(
        "Unknown Klartext command", line, line.column + 1, code="UNSUPPORTED_HEIDENHAIN_SYNTAX", status="unsupported"
    )


def _literal_function_code(expression):
    if expression.kind == "unary" and expression.value == "+":
        expression = expression.operands[0]
    if expression.kind == "number" and expression.value.isdigit() and len(expression.value) <= 4:
        return int(expression.value)
    return None


def _parameter_category(address):
    if address in {"MB", "MB MAX"}:
        return "MB"
    return "FEED" if address in {"F", "FMAX", "FAUTO"} else address


def _function_parameter(function, word, line):
    expected = {"LA": 120, "MB": 140, "MB MAX": 140}.get(word.address)
    code = _literal_function_code(function.code)
    if expected is not None and code is not None and code != expected:
        raise HeidenhainParseError("Parameter belongs to M" + str(expected), line, word.column + 1)
    category = _parameter_category(word.address)
    existing = {_parameter_category(p.address) for p in function.parameters}
    if category in existing:
        raise HeidenhainParseError("Duplicate M-function parameter", line, word.column + 1)
    return replace(function, parameters=(*function.parameters, word))


def _machine_functions(syntax, line):
    functions = []
    for word in syntax.words:
        if word.address == "M":
            functions.append(HeidenhainMachineFunction(word.expression, word.column))
        elif word.address in {"LA", "MB", "MB MAX"}:
            if not functions:
                raise HeidenhainParseError("M-function parameter has no preceding M word", line, word.column + 1)
            functions[-1] = _function_parameter(functions[-1], word, line)
        elif word.address in {"F", "FMAX", "FAUTO"}:
            move_back = functions and any(p.address in {"MB", "MB MAX"} for p in functions[-1].parameters)
            if move_back:
                functions[-1] = _function_parameter(functions[-1], word, line)
    return replace(syntax, machine_functions=tuple(functions))


class _ProgramParser:
    def __init__(self):
        self.blocks, self.lines = [], []
        self.labels, self.references = {}, []
        self.definition = None
        self.parameters = {}
        self.accept_parameters = False
        self.pending_continuation = None

    def append(self, line):
        syntax = _machine_functions(_syntax(line), line)
        if syntax.kind not in {"empty", "comment"}:
            self._continuation(line, syntax)
            syntax = self._cycle_context(line, syntax)
            self._labels(line, syntax)
        syntax = replace(syntax, comment=line.comment, continued=line.continued)
        self.lines.append(line)
        self.blocks.append(
            Block(
                line.index,
                line.raw,
                (),
                ModalSnapshot(None, None, None, None, None, None, None),
                None,
                None,
                None,
                line.number,
                None,
                line.optional,
                syntax,
            )
        )

    def _continuation(self, line, syntax):
        if self.pending_continuation is not None and syntax.command != "Q ASSIGN":
            raise HeidenhainParseError("Expected the next Q cycle parameter after ~", line)
        cycle_continuation = syntax.command == "CYCL DEF" or (syntax.command == "Q ASSIGN" and self.accept_parameters)
        if line.continued and not cycle_continuation:
            raise HeidenhainParseError(
                "Only cycle parameter continuations are supported",
                line,
                code="UNSUPPORTED_HEIDENHAIN_SYNTAX",
                status="unsupported",
            )
        self.pending_continuation = line if line.continued else None

    def _cycle_context(self, line, syntax):
        if syntax.assignment is not None and syntax.assignment[1].kind == "cycle_feed" and not self.accept_parameters:
            name, expression = syntax.assignment
            raise HeidenhainParseError(f"{name}={expression.source} is only valid as a cycle feed parameter", line)
        if syntax.command == "CYCL DEF":
            previous = self.blocks[self.definition].native_syntax if self.definition is not None else None
            if syntax.cycle_subcode and previous is not None and previous.cycle_code == syntax.cycle_code:
                return replace(syntax, cycle_definition_index=self.definition)
            self.definition = line.index
            self.accept_parameters = syntax.cycle_code not in {7, 10}
            self.parameters[self.definition] = []
            return replace(syntax, cycle_definition_index=line.index)
        if syntax.command == "Q ASSIGN" and self.accept_parameters:
            name, expression = syntax.assignment
            parameters = self.parameters[self.definition]
            if any(parameter.name == name for parameter in parameters):
                raise HeidenhainParseError("Duplicate cycle parameter: " + name, line)
            parameters.append(HeidenhainCycleParameter(name, expression, line.index, line.column))
            return replace(
                syntax,
                cycle_definition_index=self.definition,
                cycle_code=self.blocks[self.definition].native_syntax.cycle_code,
            )
        self.accept_parameters = False
        calls_cycle = syntax.command.startswith("CYCL CALL") or any(
            word.address == "M" and word.expression.kind == "number" and word.expression.value in {"89", "99"}
            for word in syntax.words
        )
        if calls_cycle:
            if self.definition is None:
                # A definition can be reached through a label call at runtime.
                # Record only a lexical candidate, not an execution decision.
                return syntax
            return replace(
                syntax,
                cycle_definition_index=self.definition,
                cycle_code=self.blocks[self.definition].native_syntax.cycle_code,
            )
        return syntax

    def _labels(self, line, syntax):
        if syntax.kind != "label" or syntax.label is None:
            return
        if syntax.command == "LBL":
            if syntax.label == 0:
                return
            if syntax.label in self.labels:
                raise HeidenhainParseError("Duplicate Klartext label: " + str(syntax.label), line)
            self.labels[syntax.label] = line.index
        else:
            if syntax.label == 0:
                raise HeidenhainParseError("LBL 0 is a return marker, not a call target", line)
            self.references.append((line, syntax.label))

    def finish(self):
        if self.pending_continuation is not None:
            raise HeidenhainParseError("Unfinished Q cycle parameter continuation", self.pending_continuation)
        for line, label in self.references:
            if label not in self.labels:
                raise HeidenhainParseError("Undefined Klartext label: " + str(label), line)
        self._boundaries()
        for index, parameters in self.parameters.items():
            block = self.blocks[index]
            self.blocks[index] = replace(
                block, native_syntax=replace(block.native_syntax, cycle_parameters=tuple(parameters))
            )
        blocks = tuple(self.blocks)
        return Program._from_canonical_ast(blocks, build_program_ast(blocks))  # pylint: disable=protected-access

    def _boundaries(self):
        content = [
            (line, block.native_syntax)
            for line, block in zip(self.lines, self.blocks)
            if block.native_syntax.kind not in {"empty", "comment"}
        ]
        boundaries = [(line, syntax) for line, syntax in content if syntax.kind == "program"]
        if not boundaries:
            return
        if len(boundaries) != 2 or boundaries[0][1].command != "BEGIN PGM" or boundaries[1][1].command != "END PGM":
            raise HeidenhainParseError("Expected exactly one BEGIN/END PGM pair", boundaries[0][0])
        first, last = boundaries[0][1], boundaries[1][1]
        if (first.program_name, first.units) != (last.program_name, last.units):
            index = boundaries[0][0].index
            block = self.blocks[index]
            self.blocks[index] = replace(
                block,
                native_syntax=replace(
                    first,
                    warnings=(*first.warnings, "BEGIN/END PGM names or units do not match; geometry remains available"),
                ),
            )
        if boundaries[0] != content[0] or boundaries[-1] != content[-1]:
            raise HeidenhainParseError("Executable blocks lie outside BEGIN/END PGM", content[0][0])


def parse_heidenhain_program(source: str) -> Program:
    """Parse a Klartext program or fragment; unsupported syntax fails closed.

    The native runtime evaluates expressions and binds cycles in execution
    order; the AST retains parameters and physical source locations unchanged.
    """
    parser = _ProgramParser()
    for index, raw in checkpointed(source.splitlines()):
        parser.append(lex_heidenhain_line(raw, index))
    return parser.finish()
