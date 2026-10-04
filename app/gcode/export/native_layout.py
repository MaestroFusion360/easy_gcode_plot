"""FANUC tool-change layout for normalized native source blocks."""

import re


def format_native_tool_changes(source):
    """Pair tool selection with M6 and length activation with a rapid Z move.

    Only unconditional, comment-free setup blocks may separate G43/H from Z.
    An intervening cutting move, optional block or other command flushes it.
    """
    lines = source.splitlines(keepends=True)
    output = []
    pending = None
    pending_index = 0
    for line in lines:
        code = line.strip()
        if pending is not None:
            match = re.fullmatch(r"G0 (Z[-+\d.]+)", code)
            if match:
                ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
                output.append(f"G0 G43 {match[1]} {pending.strip().split()[1]}{ending}")
                pending = None
                continue
            if not _length_setup_block(code):
                output.insert(pending_index, pending)
                pending = None
        if re.fullmatch(r"G43 H\d+", code):
            pending = line
            pending_index = len(output)
        elif code == "M6" and output and re.fullmatch(r"T\d+", output[-1].strip()):
            output[-1] = output[-1].rstrip("\r\n") + " " + line
        else:
            output.append(line)
    if pending is not None:
        output.insert(pending_index, pending)
    return "".join(output)


def _length_setup_block(code):
    return re.fullmatch(r"(?:S\d+(?: M[345])?|G17 G90 G94|G5[4-7]|G0 X[-+\d.]+(?: Y[-+\d.]+)?)", code) is not None
