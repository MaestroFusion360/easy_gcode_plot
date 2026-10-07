"""Shared NC formatting, modal options and execution-block helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from ..comments import DEFAULT_COMMENT_STYLE, normalize_comment_style
from ..kernel import ExecutionResult, TraceMotion
from ..trace_tools import arc_geometry

EXPORT_LIMITATION_SUFFIX = "_EXPANDED_EXPORT"

DEFAULT_WORD_ORDER = ("motion", "turns", "x", "y", "z", "i", "j", "k", "r", "feed")

WORD_ORDER_TOKENS = frozenset(DEFAULT_WORD_ORDER)


def _compact_post_line(line, options):
    """Remove optional word spacing while retaining native keyword boundaries."""
    if options.delimiter:
        return line
    words = line.split()
    return "".join(
        (" " if index and (words[index - 1].isalpha() or word.isalpha()) else "") + word
        for index, word in enumerate(words)
    )


class ExportLimitation(ValueError):
    """A selected representation genuinely conflicts with a declared target capability.

    This is distinct from a malformed program or an internal failure: execution
    succeeded and the geometry is intact, but the chosen ISO/EXPANDED profile
    deliberately refuses a construct that is a real capability limit
    (multi-axis semantics, a missing axis, an unsupported modal state). It is
    NOT raised for user formatting choices such as G90/G91 coordinates, sequence
    numbering, signs, decimal precision, start/end program text, delimiters,
    leading zeros or modal feed. Callers classify it as ``UNSUPPORTED`` rather
    than ``ERRORS`` but still fail closed and never write partial output.
    """

    def __init__(self, message, code="UNSUPPORTED_EXPANDED_EXPORT"):
        super().__init__(message)
        self.code = code


def is_export_limitation(diagnostic) -> bool:
    """Return True for an EXPANDED exporter capability diagnostic."""
    return str(getattr(diagnostic, "code", "")).endswith(EXPORT_LIMITATION_SUFFIX)


TURN_FULL_PROGRAM_MODE = 0


MILL_FULL_PROGRAM_MODE = 1


EXPANDED_EXECUTION_MODE = 2


DXF_MODE = 3


@dataclass(frozen=True)
class ExportOptions:
    # 0: relative IJK, 1: absolute IJK, 2: R arcs, 3: linearized arcs,
    arc_mode: int = 0
    incremental: bool = False
    sequence_numbers: bool = False
    sequence_start: int = 1
    sequence_increment: int = 1
    sequence_spacing: bool = False
    delimiter: bool = False
    leading_zero: bool = False
    start_program: str = ""
    end_program: str = ""
    safety_line: bool = False
    linearization_tolerance: float = 0.0005
    comment_style: str = DEFAULT_COMMENT_STYLE
    include_comments: bool = True
    output_unit_scale: float = 1.0
    output_unit_scale_explicit: bool = False
    absolute_arc_syntax: bool = False
    multi_turn_arcs: bool = False
    decimal_places: int = 6
    decimal_places_explicit: bool = False
    force_decimal: bool = False
    force_decimal_explicit: bool = False
    plus_output: bool = False
    plus_output_explicit: bool = False
    modal_feed: bool = True
    word_formats: dict[str, tuple[int, str]] | None = None
    word_order: tuple[str, ...] | None = None
    word_required: dict[str, bool] | None = None
    rotary_axes: tuple[str, ...] = ()
    rotary_values: dict[str, float] | None = None
    rotary_start_values: dict[str, float] | None = None
    turns_word: str = "TURN={turns}"
    radius_split_angle: float = 90.0
    arc_split_angle: float = 180.0
    full_circle: str = "two_half"


def _window_export_options(window, *, arc_mode: int) -> ExportOptions:
    return ExportOptions(
        arc_mode=arc_mode,
        incremental=bool(window.incrMode),
        sequence_numbers=bool(window.seqNum),
        sequence_start=int(window.seqNumStart),
        sequence_increment=int(window.seqNumIncr),
        sequence_spacing=bool(window.seqNumSpacing),
        delimiter=bool(window.delim),
        leading_zero=bool(window.leadingZero),
        start_program=str(window.startPgmExp or ""),
        end_program=str(window.endPgmExp or ""),
        safety_line=bool(window.safLine),
        comment_style=normalize_comment_style(getattr(window, "commentStyle", DEFAULT_COMMENT_STYLE)),
    )


def _g(move: int, leading_zero: bool) -> str:
    return f"G{move:02d}" if leading_zero else f"G{move}"


def _word_format(letter: str, options: ExportOptions) -> tuple[int, str]:
    """Resolve per-address decimals/sign, falling back to global options."""
    decimals = options.decimal_places
    sign = "always" if options.plus_output else "auto"
    spec = (options.word_formats or {}).get(letter)
    if spec is not None:
        decimals, sign = spec
    return int(decimals), str(sign)


def _word(letter: str, value: float | None, options: ExportOptions | None = None) -> str | None:
    if value is None:
        return None
    options = options or ExportOptions()
    decimals, sign = _word_format(letter, options)
    number = f"{value:.{decimals}f}"
    if float(number) == 0:
        number = f"{0:.{decimals}f}"
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    if options.force_decimal and "." not in number:
        number += "."
    if sign == "always" and not number.startswith("-"):
        number = "+" + number
    elif sign == "never":
        number = number.removeprefix("+")
    return letter + number


def _axis_values(m: TraceMotion, options: ExportOptions) -> tuple[float, float, float]:
    if options.incremental:
        return m.end_x - m.start_x, m.end_y - m.start_y, m.end_z - m.start_z
    return m.end_x, m.end_y, m.end_z


def _center_tokens(m: TraceMotion, options: ExportOptions) -> dict[str, str]:
    geom = arc_geometry(m)

    if options.arc_mode == 2:
        if geom is not None:
            *_, sweep, radius = geom
            signed_radius = -radius if sweep > 3.141592653589793 + 1e-12 else radius
            word = _word("R", signed_radius, options)
            return {"r": word} if word else {}
        if m.radius is not None:
            word = _word("R", m.radius, options)
            return {"r": word} if word else {}

    if geom is not None:
        center = geom[4]
        if m.plane == 18:
            absolute = (("I", center[0]), ("K", center[1]))
            relative = (("I", center[0] - (m.start_x * m.x_scale)), ("K", center[1] - m.start_z))
        elif m.plane == 19:
            absolute = (("J", center[0]), ("K", center[1]))
            relative = (("J", center[0] - m.start_y), ("K", center[1] - m.start_z))
        else:
            absolute = (("I", center[0]), ("J", center[1]))
            relative = (("I", center[0] - m.start_x), ("J", center[1] - m.start_y))
        values = absolute if options.arc_mode == 1 and not options.incremental else relative
        return {letter.lower(): word for letter, value in values if (word := _word(letter, value, options))}

    if options.arc_mode == 1:
        if m.plane == 18:
            values = (("I", m.i), ("K", m.k))
        elif m.plane == 19:
            values = (("J", m.j), ("K", m.k))
        else:
            values = (("I", m.i), ("J", m.j))
        return {letter.lower(): word for letter, value in values if (word := _word(letter, value, options))}

    return {
        letter.lower(): word
        for letter, value in (("I", m.i), ("J", m.j), ("K", m.k))
        if (word := _word(letter, value, options))
    }


def _word_required(options: ExportOptions, token: str, *, default: bool = False) -> bool:
    """Return whether a frame word must be emitted regardless of unchanged value."""
    required = options.word_required
    if required is None:
        return default
    return bool(required.get(token, default))


def _rotary_tokens(options: ExportOptions) -> dict[str, str]:
    if not options.rotary_values:
        return {}
    return {
        axis.lower(): _word(axis, options.rotary_values[axis], options)
        for axis in ("A", "B", "C")
        if axis in options.rotary_axes and axis in options.rotary_values
    }


def _motion_tokens(
    m: TraceMotion,
    options: ExportOptions,
    move: int,
    x: float,
    y: float,
    z: float,
    include_feed: bool,
    include_motion: bool = True,
):
    tokens: dict[str, str | None] = {}
    if include_motion:
        tokens["motion"] = _g(move, options.leading_zero)
    if options.multi_turn_arcs and m.arc is not None:
        turns = max(0, math.ceil(m.arc.sweep / math.tau - 1e-10) - 1)
        if turns:
            tokens["turns"] = str(options.turns_word).format(turns=turns)

    show_y = _word_required(options, "y") or abs(y) > 1e-12 or abs(m.start_y) > 1e-12 or abs(m.end_y) > 1e-12
    tokens["x"] = _word("X", x, options)
    tokens["y"] = _word("Y", y if show_y else None, options)
    tokens["z"] = _word("Z", z, options)
    tokens.update(_rotary_tokens(options))

    if m.move in (2, 3) and move in (2, 3):
        for letter, word in _center_tokens(m, options).items():
            if (
                options.absolute_arc_syntax
                and options.arc_mode == 1
                and not options.incremental
                and letter in {"i", "j", "k"}
            ):
                word = f"{word[0]}=AC({word[1:]})"
            tokens[letter] = word

    if include_feed and move != 0 and m.feed is not None:
        tokens["feed"] = _word("F", m.feed, options)
    return tokens


def motion_line(
    m: TraceMotion,
    options: ExportOptions,
    *,
    override_move: int | None = None,
    include_feed: bool = True,
    include_motion: bool = True,
) -> str:
    move = m.move if override_move is None else override_move
    x, y, z = _axis_values(m, options)
    tokens = _motion_tokens(m, options, move, x, y, z, include_feed, include_motion)
    order = options.word_order or DEFAULT_WORD_ORDER
    words = [tokens[key] for key in order if tokens.get(key)]
    seen = set(order)
    words.extend(tokens[key] for key in DEFAULT_WORD_ORDER if key not in seen and tokens.get(key))
    sep = " " if options.delimiter else ""
    return sep.join(words)


def _integer_code(value: float) -> int | None:
    number = int(value)
    return number if abs(value - number) <= 1e-9 else None


def _expanded_word(letter: str, value: float, options: ExportOptions) -> str:
    code = _integer_code(value) if letter in {"G", "M"} else None
    if code is not None:
        if options.leading_zero and 0 <= code < 10:
            return f"{letter}{code:02d}"
        return f"{letter}{code}"
    return _word(letter, value, options)


def _check_cancelled(cancelled) -> None:
    if cancelled is not None and cancelled():
        raise InterruptedError("Export cancelled")


def _require_continuous_motions(
    result,
    *,
    allow_source_rapids=False,
    allow_reference_rapids=False,
    allow_rotary_index_gaps=False,
):
    verified_rapids = set()
    verified_rotary_gaps = set()
    cursor = 0
    for step in result.execution_steps:
        if allow_source_rapids and step.absolute and ("G", 0.0) in step.words and step.emitted_count:
            verified_rapids.add(cursor)
        if allow_rotary_index_gaps and any(event.kind in {"ROTARY_INDEX", "TOOL_AXIS_ORIENT"} for event in step.events):
            verified_rotary_gaps.add(cursor)
        cursor += step.emitted_count
    for index, (previous, motion) in enumerate(zip(result.motions, result.motions[1:]), 1):
        if index in verified_rotary_gaps:
            continue
        if motion.move == 0 and (
            index in verified_rapids or allow_reference_rapids and motion.source_kind == "reference_resume"
        ):
            continue
        if any(
            abs(end - start) > 1e-6
            for end, start in zip(
                (previous.end_x, previous.end_y, previous.end_z),
                (motion.start_x, motion.start_y, motion.start_z),
            )
        ):
            raise ValueError("Cannot export resolved motion with an unverified position gap")


def _execution_slices(result: ExecutionResult):
    if result.program is None or not result.execution_steps:
        raise ValueError("Expanded program export requires execution steps")
    blocks = {block.index: block for block in result.program.blocks}
    cursor = 0
    for step in result.execution_steps:
        block = blocks.get(step.source_block)
        if block is None:
            raise ValueError(f"Execution step references missing source block {step.source_block}")
        end = cursor + step.emitted_count
        if end > len(result.motions):
            raise ValueError("Execution step motion counts do not match the trace")
        motions = result.motions[cursor:end]
        cursor = end
        yield step, block, motions
    if cursor != len(result.motions):
        raise ValueError("Execution step motion counts do not consume the complete trace")


MM_PER_INCH = 25.4


def scale_motion(motion: TraceMotion, unit_scale: float) -> TraceMotion:
    """Return a motion expressed in units whose size is *unit_scale* mm."""
    if unit_scale == 1.0:
        return motion
    arc = motion.arc
    if arc is not None:
        arc = replace(
            arc,
            center=tuple(value / unit_scale for value in arc.center),
            radius=arc.radius / unit_scale,
        )
    return replace(
        motion,
        start_x=motion.start_x / unit_scale,
        start_y=motion.start_y / unit_scale,
        start_z=motion.start_z / unit_scale,
        end_x=motion.end_x / unit_scale,
        end_y=motion.end_y / unit_scale,
        end_z=motion.end_z / unit_scale,
        radius=None if motion.radius is None else motion.radius / unit_scale,
        feed=None if motion.feed is None else motion.feed / (1.0 if motion.feed_mode == "inverse_time" else unit_scale),
        i=None if motion.i is None else motion.i / unit_scale,
        j=None if motion.j is None else motion.j / unit_scale,
        k=None if motion.k is None else motion.k / unit_scale,
        orientation_offset=tuple(value / unit_scale for value in motion.orientation_offset),
        arc=arc,
    )
