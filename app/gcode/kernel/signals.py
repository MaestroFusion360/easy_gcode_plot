"""Machine-signal extraction from the already parsed source program."""

from __future__ import annotations

from .api_types import MachineSignal
from .lang import try_literal_int
from .model import Program


def collect_machine_signals(program: Program | None) -> tuple[MachineSignal, ...]:
    if program is None:
        return ()
    out: list[MachineSignal] = []
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
    for block in program.blocks:
        for word in block.parsed_words:
            if word.letter.upper() != "M":
                continue
            code = try_literal_int(word.expr)
            if code in kinds:
                out.append(MachineSignal(kinds[code], block.index, f"M{code:02d}"))
        if any(w.letter.upper() == "G" and try_literal_int(w.expr) == 4 for w in block.parsed_words):
            dwell = next((w for w in reversed(block.parsed_words) if w.letter.upper() in {"P", "X"}), None)
            value = None
            if dwell is not None:
                try:
                    value = float(dwell.expr)
                except ValueError:
                    value = None
            out.append(MachineSignal("dwell", block.index, "G04", value))
    return tuple(out)


def program_end_code(signals: tuple[MachineSignal, ...]) -> str | None:
    return next((item.code for item in reversed(signals) if item.kind == "program_end"), None)
