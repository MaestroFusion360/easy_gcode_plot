"""Machine-signal extraction from the already parsed source program."""

from __future__ import annotations

from .api_types import MachineSignal


def signals_for_words(block_index, words):
    """Signals from evaluated words of this occurrence, never from source order."""
    kinds = {
        0: "stop",
        1: "optional_stop",
        2: "program_end",
        3: "spindle_cw",
        4: "spindle_ccw",
        5: "spindle_stop",
        8: "coolant_on",
        9: "coolant_off",
        30: "program_end",
    }
    out = [MachineSignal(kinds[int(m)], block_index, f"M{int(m):02d}") for m in words.all("M") if m in kinds]
    if 4 in words.all("G"):
        value = words.get("X", words.get("P", 0.0) / 1000.0)
        if value < 0:
            raise ValueError("Dwell duration must not be negative")
        out.append(MachineSignal("dwell", block_index, "G04", value))
    return tuple(out)


def program_end_code(signals: tuple[MachineSignal, ...]) -> str | None:
    return next((item.code for item in reversed(signals) if item.kind == "program_end"), None)
