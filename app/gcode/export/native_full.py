"""Bounded Full Program normalization from authoritative Siemens execution."""

import re

from app.gcode.comments import extract_comments, strip_comments
from app.gcode.kernel.frontend.program import literal_codes
from app.gcode.kernel.runtime.events import TOOL_CHANGE

from .common import _execution_slices
from .native_cycles import NativeCycleEmitter
from .native_layout import format_native_tool_changes


def _guard_native_block(block):
    syntax = block.native_syntax
    if syntax is None:
        return
    if 4 in literal_codes(block.parsed_words, "G") and any(t.letter == "S" for t in block.parsed_words):
        raise ValueError("Full Program conversion cannot preserve unmodeled spindle-revolution dwell")
    unsafe = {"TRANS", "AROT", "ORIWKS", "ORIMKS", "ORIAXES", "ORIVECT", "ORIRESET", "CUT3DC", "CUT3DF", "CUT3DFF"}
    if (
        set(syntax.ignored_native_commands) & unsafe
        or set(syntax.ignored_diameter_modes) & {"DIAMON", "DIAM90"}
        or any(token.letter in {"CHF", "CHR", "RND", "RNDM", "FRC", "FRCM", "TURN"} for token in block.parsed_words)
    ):
        raise ValueError(f"Full Program conversion cannot preserve unmodeled SINUMERIK semantics: {block.raw}")
    if syntax.named_tool is not None or syntax.kind in {"swivel", "traori", "trafoof"}:
        raise ValueError(f"Full Program conversion has no FANUC representation for: {block.raw}")


def _supa_words(step, words):
    if step.programmed_position is None:
        raise ValueError("Full Program conversion requires a resolved programmed position for SUPA")
    addressed = {letter for letter, _value in words if letter in {"X", "Y", "Z"}}
    # Serialize the executor's resolved reference target, including configured
    # zero returns, after inversion of WCS and programmed transforms.
    words = [
        (letter, value)
        for letter, value in words
        if letter not in {"X", "Y", "Z"} and not (letter == "G" and value in {53, 90, 91})
    ]
    words.append(("G", 90))
    words.extend(
        (axis, value / step.unit_scale) for axis, value in zip("XYZ", step.programmed_position) if axis in addressed
    )
    return words


def _cutting_feed_words(step, words, motions, previous_feed):
    cutting = [motion for motion in motions if motion.move != 0]
    if not cutting:
        return words, next((value for letter, value in words if letter == "F"), previous_feed)
    feeds = {motion.feed for motion in cutting}
    if len(feeds) != 1:
        raise ValueError("Full Program conversion requires one feed per source motion block")
    feed = cutting[0].feed
    if feed is None:
        return words, previous_feed
    if step.feed_mode != "inverse_time":
        feed /= step.unit_scale
    explicit_feed = any(letter == "F" for letter, _value in words)
    words = [(letter, value) for letter, value in words if letter != "F"]
    if explicit_feed or feed != previous_feed or step.feed_mode == "inverse_time":
        words.append(("F", feed))
    return words, feed


def _fanuc_words(step, block, motions, active_tool=None, previous_feed=None):
    _guard_native_block(block)
    if block.flow_node is not None:
        raise ValueError("Full Program native conversion cannot replace source control flow with evaluated words")
    words = [
        (letter, value)
        for letter, value in step.words
        if letter not in {"N", "D"} and not (letter == "G" and value in {290, 291})
    ]
    if block.native_syntax is not None and block.native_syntax.kind == "compof":
        words.append(("G", 40))
    if active_tool is not None:
        offset = float(active_tool.lstrip("T"))
        if ("D", 1.0) in step.words:
            words = [(letter, offset if letter == "H" else value) for letter, value in words]
        if any(letter == "G" and value in {41, 42} for letter, value in words):
            words.append(("D", offset))
    restore_incremental = False
    if block.native_syntax is not None and block.native_syntax.supa:
        words = _supa_words(step, words)
        restore_incremental = not step.absolute
    words, next_feed = _cutting_feed_words(step, words, motions, previous_feed)
    line = " ".join(f"{letter}{value:.12f}".rstrip("0").rstrip(".") for letter, value in words)
    return (line + "\nG91" if restore_incremental else line), next_feed


def _unused_trailing_edge(step, block, last_motion_block):
    """A standalone native D1 after all motion needs no FANUC activation."""
    return (
        step.source_block > last_motion_block
        and block.native_syntax is not None
        and {token.letter for token in block.parsed_words} <= {"N", "D"}
        and ("D", 1.0) in step.words
    )


def _normalized_blocks(result):
    normalized = {}
    active_tool = None
    previous_feed = None
    cycles = NativeCycleEmitter(result)
    last_motion_block = max((step.source_block for step in result.execution_steps if step.emitted_count), default=-1)
    for step, block, motions in _execution_slices(result):
        for event in step.events:
            if event.kind == TOOL_CHANGE:
                active_tool = event.tool if event.tool and re.fullmatch(r"T\d+", event.tool) else None
        if block.index in normalized:
            raise ValueError("Full Program native conversion requires a single execution per source block")
        _guard_native_block(block)
        if block.flow_node is not None:
            raise ValueError("Full Program native conversion cannot replace source control flow with evaluated words")
        cycle_line = cycles.convert(step, block, motions)
        if cycle_line is None:
            normalized[block.index], previous_feed = _fanuc_words(step, block, motions, active_tool, previous_feed)
        else:
            normalized[block.index] = cycle_line
            feeds = [m.feed / step.unit_scale for m in motions if m.move != 0 and m.feed is not None]
            previous_feed = feeds[-1] if feeds else previous_feed
        if _unused_trailing_edge(step, block, last_motion_block):
            normalized[block.index] = ""
    return normalized


def normalize_native_full_program(source, result):
    """Keep source frames/comments, replacing native syntax with kernel words.

    Declarations become constants at their original use sites. Drilling holes
    retain canned cycles where equivalent; Siemens-specific pecks are expanded.
    """
    normalized = _normalized_blocks(result)
    lines = []
    for block, raw in zip(result.program.blocks, source.splitlines(keepends=True), strict=True):
        code = strip_comments(raw).strip()
        if not code or code.startswith("%"):
            lines.append(raw)
            continue
        if block.index not in normalized:
            raise ValueError(f"Full Program conversion cannot normalize an unexecuted native block: {block.raw}")
        newline = "\r\n" if raw.endswith("\r\n") else "\n" if raw.endswith("\n") else ""
        # Native function arguments are syntax, not parenthesized tool comments.
        code_part, separator, tail = raw.partition(";")
        comment_source = re.sub(
            r"\b(?:IC|AC|DC|SIN|COS|TAN|ASIN|ACOS|ATAN|SQRT|ABS|TRUNC|ROUND)\s*\([^()]*\)",
            "",
            code_part,
            flags=re.IGNORECASE,
        )
        kind = block.native_syntax.kind if block.native_syntax else None
        comments = [] if kind in {"workpiece", "hsc_ignored", "cycle"} else extract_comments(comment_source)
        if kind == "message":
            comments = [c.strip('"').replace('""', '"') for c in comments]
        if separator:
            comments.append(tail.rstrip("\r\n"))
        comment = " ;" + " | ".join(comments) if comments else ""
        if not normalized[block.index] and not comment:
            continue
        prefix = "/" if block.optional_skip else ""
        converted = normalized[block.index].replace("\n", (newline or "\n") + prefix)
        lines.append(prefix + converted + comment + newline)
    return format_native_tool_changes("".join(lines))
