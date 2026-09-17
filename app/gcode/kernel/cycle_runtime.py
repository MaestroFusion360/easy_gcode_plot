"""Shared policy helpers used while dispatching FANUC turning cycles."""

from __future__ import annotations

from dataclasses import replace

from .execution import classify_block_codes
from .program import eval_words
from .tool_compensation import compensate_profile_segments


def least_input_or_length_to_mm(
    value: float,
    unit_scale: float,
    *,
    direct_length: bool,
    expression: str | None = None,
) -> float:
    """Interpret G74/G75/G83/G84 P/Q using lexical FANUC conventions."""
    raw = abs(value * unit_scale)
    if direct_length:
        return raw
    if expression is not None and ("." in expression or "E" in expression.upper()):
        return raw
    increment_mm = 0.001 if abs(unit_scale - 1.0) <= 1e-12 else (0.0001 * 25.4)
    return abs(value) * increment_mm


def word_expression(block, letter: str) -> str | None:
    """Return the source expression for the last occurrence of an address."""
    for token in reversed(block.parsed_words):
        if token.letter.upper() == letter.upper():
            return token.expr
    return None


def profile_compensation_modes(blocks, state, p_index: int, q_index: int) -> dict[int, int]:
    """Resolve compensation mode at every block of a cycle profile."""
    mode = state.compensation_mode
    modes: dict[int, int] = {}
    for profile_index in range(p_index, q_index + 1):
        profile_words = eval_words(blocks[profile_index].parsed_words, state.clone_vars())
        profile_codes = classify_block_codes(profile_words)
        if 40 in profile_codes.all_g:
            mode = 40
        elif 41 in profile_codes.all_g:
            mode = 41
        elif 42 in profile_codes.all_g:
            mode = 42
        modes[profile_index] = mode
    return modes


def compensated_profile(profile, blocks, state, tools, p_index: int, q_index: int):
    """Apply configured nose compensation and report whether it was active."""
    if not tools:
        return profile, False
    modes = profile_compensation_modes(blocks, state, p_index, q_index)
    active = any(mode in (41, 42) for mode in modes.values())
    return (
        compensate_profile_segments(
            profile,
            compensation_mode=state.compensation_mode,
            compensation_modes=modes,
            tool_code=state.active_tool,
            tools=tools,
        ),
        active,
    )


def mark_compensated(motions, *, tools_configured: bool, profile_was_compensated: bool):
    """Publish compensation provenance on motions emitted from a profile."""
    if not tools_configured or not profile_was_compensated:
        return motions
    return [replace(motion, compensation_applied=True) for motion in motions]
