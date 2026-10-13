"""Resolve profile defaults and source comments for NC output."""

from __future__ import annotations

from dataclasses import replace

from ..comments import extract_comments
from ..post_profiles import _FORMAT_WORD_TOKENS, _render
from .common import ExportOptions
from .preflight import _profile_axes


def _post_options(options, profile):
    defaults = profile["options"]
    arc = profile["format"]
    profile_unit_scale = 25.4 if defaults["units"] == "inch" else 1.0
    if options is None:
        default_arc_mode = (
            3 if not arc["outputArcs"] else 2 if arc["arcMode"] == "R" else int(arc["arcCenter"] == "absolute")
        )
        options = ExportOptions(
            delimiter=defaults["delimiter"],
            leading_zero=defaults["leadingZero"],
            incremental=defaults["incrementalMode"],
            output_unit_scale=profile_unit_scale,
            arc_mode=default_arc_mode,
        )
    elif not options.output_unit_scale_explicit and options.output_unit_scale == 1.0:
        options = replace(options, output_unit_scale=profile_unit_scale)
    if options.arc_mode not in range(4):
        raise ValueError("Arc output must be IJK relative, IJK absolute, radius or linearized")
    default_sign = (
        "always" if (options.plus_output if options.plus_output_explicit else defaults["plusOutput"]) else "auto"
    )
    word_formats, word_order, word_required = _resolve_format_words(
        arc.get("words"), defaults["decimalPlaces"], default_sign=default_sign
    )
    return replace(
        options,
        decimal_places=options.decimal_places if options.decimal_places_explicit else defaults["decimalPlaces"],
        force_decimal=options.force_decimal if options.force_decimal_explicit else defaults["forceDecimal"],
        plus_output=options.plus_output if options.plus_output_explicit else defaults["plusOutput"],
        absolute_arc_syntax=arc["absoluteCenterSyntax"] == "AC",
        multi_turn_arcs=arc["multiTurnArcs"],
        arc_mode=3 if not arc["outputArcs"] else options.arc_mode,
        word_formats=word_formats,
        word_order=word_order,
        word_required=word_required,
        rotary_axes=tuple(axis for axis in _profile_axes(profile) if axis in {"A", "B", "C"}),
        turns_word=str(arc.get("turnsWord", options.turns_word)),
        radius_split_angle=float(arc.get("radiusSplitAngle", options.radius_split_angle)),
        arc_split_angle=float(arc.get("arcSplitAngle", options.arc_split_angle)),
        full_circle=str(arc.get("fullCircle", options.full_circle)),
    )


def _resolve_format_words(words, default_decimals: int, *, default_sign="auto"):
    """Return ``(formats, order, required)`` from a ``format.words`` section.

    ``order`` is a tuple of internal motion-token names sorted by the profile's
    ``order`` field. ``turns`` keeps its legacy position immediately after
    ``motion`` so multi-turn arc serialization is unchanged.
    """
    if not words:
        return None, None, None
    ordered = sorted(words.items(), key=lambda item: item[1]["order"])
    order_tokens: list[str] = []
    required: dict[str, bool] = {}
    formats: dict[str, tuple[int, str]] = {}
    for key, spec in ordered:
        token = _FORMAT_WORD_TOKENS[key]
        order_tokens.append(token)
        required[token] = bool(spec["required"])
        if key != "motion" and ("decimals" in spec or "sign" in spec):
            formats[key] = (int(spec.get("decimals", default_decimals)), str(spec.get("sign", default_sign)))
    if "motion" in order_tokens:
        order_tokens.insert(order_tokens.index("motion") + 1, "turns")
    return formats or None, tuple(order_tokens), required


def _source_comment_lines(raw: str, options: ExportOptions, profile: dict) -> list[str]:
    if not options.include_comments:
        return []
    return [
        _render(profile.get("comment", {}).get("template", "({text})"), text=comment)
        for comment in extract_comments(raw)
        if comment.strip()
    ]
