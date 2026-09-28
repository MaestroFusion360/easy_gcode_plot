"""FANUC lathe source-code systems mapped onto the existing Type A executor."""

from __future__ import annotations

from ..frontend.program import EvaluatedWords
from .type_a import TYPE_A_SUPPORTED_G_CODES, TurningOperation, type_a_operation
from .type_b import TYPE_B_SUPPORTED_G_CODES, TYPE_B_TO_CANONICAL, type_b_operation

TYPE_A = "A"
TYPE_B = "B"


def validate_system(system: str) -> str:
    selected = str(system).strip().upper()
    if selected not in (TYPE_A, TYPE_B):
        raise ValueError(f"Unsupported FANUC lathe G-code system: {system}")
    return selected


def supported_codes(system: str) -> frozenset[int]:
    return TYPE_A_SUPPORTED_G_CODES if validate_system(system) == TYPE_A else TYPE_B_SUPPORTED_G_CODES


def canonical_code(code: int | float, system: str) -> int | float | None:
    """Return the executor code; Type B G90/G91 are distance-state commands."""
    if validate_system(system) == TYPE_A:
        return code
    if code in (90, 91):
        return None
    return TYPE_B_TO_CANONICAL.get(code, code)


def canonical_operation(code: int | float, system: str) -> TurningOperation | None:
    """Map a source code to a dialect-independent turning operation."""
    return type_a_operation(code) if validate_system(system) == TYPE_A else type_b_operation(code)


def canonical_words(
    source: EvaluatedWords, system: str, absolute: bool
) -> tuple[EvaluatedWords, bool, tuple[int | float, ...]]:
    """Normalize one evaluated occurrence without modifying source tokens or raw text."""
    if validate_system(system) == TYPE_A:
        return source, absolute, source.all("G")
    source_codes = source.all("G")
    if 90 in source_codes and 91 in source_codes:
        raise ValueError("Conflicting Type B G90/G91 distance modes in one block")
    if 90 in source_codes:
        absolute = True
    if 91 in source_codes:
        absolute = False
    words = EvaluatedWords()
    words.errors.extend(source.errors)
    for letter, values in source._all.items():  # pylint: disable=protected-access
        for value in values:
            if letter == "G":
                value = canonical_code(value, system)
                if value is None:
                    continue
            incremental_axis = not absolute and not any(code in source_codes for code in (10, 65, 92))
            target = {"X": "U", "Z": "W"}.get(letter, letter) if incremental_axis else letter
            words._all.setdefault(target, []).append(value)  # pylint: disable=protected-access
            words[target] = value
    return words, absolute, source_codes
