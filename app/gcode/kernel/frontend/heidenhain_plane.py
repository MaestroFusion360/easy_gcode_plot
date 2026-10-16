"""Native tilted-plane and TCP declarations emitted by Klartext CAM posts."""

import re

from .heidenhain_lexer import HeidenhainParseError, lex_heidenhain_words
from .heidenhain_syntax import HeidenhainPlane, HeidenhainSyntax


def parse_plane(line):
    match = re.match(r"PLANE\s+(SPATIAL|RESET)\b", line.body, re.I)
    if match is None:
        raise HeidenhainParseError(
            "Only PLANE SPATIAL and PLANE RESET are modeled",
            line,
            code="UNSUPPORTED_HEIDENHAIN_SYNTAX",
            status="unsupported",
        )
    mode = re.search(r"\b(STAY|TURN|MOVE)\b", line.body[match.end() :], re.I)
    if mode is None:
        raise HeidenhainParseError("PLANE requires STAY, TURN or MOVE positioning", line)
    position = match.end() + mode.start()
    words = lex_heidenhain_words(line.body[match.end() : position], line, offset=match.end(), flags=False)
    expected = {"SPA", "SPB", "SPC"} if match[1].upper() == "SPATIAL" else set()
    if {word.address for word in words} != expected:
        raise HeidenhainParseError("PLANE SPATIAL requires SPA/SPB/SPC; RESET takes no angles", line)
    options = re.fullmatch(
        r"(STAY|TURN|MOVE)(?:\s+(FMAX|F\s*[+]?(?:\d+(?:\.\d*)?|\.\d+)))?"
        r"(?:\s+SEQ([+-]))?(?:\s+TABLE\s+(ROT|COORD))?\s*",
        line.body[position:],
        re.I,
    )
    if options is None:
        raise HeidenhainParseError("Unsupported PLANE positioning options", line)
    positioning, feed, sequence, table = options.groups()
    if positioning.upper() == "STAY" and any((feed, sequence, table)):
        raise HeidenhainParseError("PLANE STAY takes no positioning feed, SEQ or TABLE options", line)
    return HeidenhainSyntax(
        "transform",
        "PLANE " + match[1].upper(),
        words,
        plane=HeidenhainPlane(
            positioning.upper(), {"+": 1, "-": -1}.get(sequence, 0), table.upper() if table else None
        ),
    )


def parse_tcp(line):
    command = " ".join(line.body.upper().split())
    if command not in {"FUNCTION TCPM F TCP AXIS POS PATHCTRL AXIS", "FUNCTION RESET TCPM"}:
        raise HeidenhainParseError(
            "Only TCPM F TCP AXIS POS PATHCTRL AXIS and RESET TCPM are modeled",
            line,
            code="UNSUPPORTED_HEIDENHAIN_SYNTAX",
            status="unsupported",
        )
    return HeidenhainSyntax("transform", command)
