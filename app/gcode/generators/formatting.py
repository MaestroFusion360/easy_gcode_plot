"""Stable numeric formatting for calculator-generated NC fragments."""

from __future__ import annotations


def _number(value: float, decimals: int = 3) -> str:
    if abs(value) < 0.5 * 10**-decimals:
        value = 0.0
    return f"{value:.{decimals}f}".rstrip("0").rstrip(".") or "0"


def _signed_number(value: float, decimals: int = 3) -> str:
    """Klartext requires an explicit sign on every coordinate value."""
    text = _number(value, decimals)
    return text if text.startswith("-") else "+" + text
