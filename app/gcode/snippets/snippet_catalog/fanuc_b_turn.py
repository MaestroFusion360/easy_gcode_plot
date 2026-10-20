"""Editable FANUC lathe G-code system B starter templates."""

from .fanuc_turn import SNIPPETS as TYPE_A_SNIPPETS

_CODE_RENAMES = {
    "Threading (G32)": ("Threading (G33)", "G32 ", "G33 "),
    "Simple Turning (G90)": ("Simple Turning (G77)", "G90 ", "G77 "),
    "Simple Threading (G92)": ("Simple Threading (G78)", "G92 ", "G78 "),
    "Simple Facing (G94)": ("Simple Facing (G79)", "G94 ", "G79 "),
}


def _type_b_entry(name: str, body: str) -> tuple[str, str]:
    if name == "Program Start":
        return name, body.replace("SYSTEM A", "SYSTEM B").replace("G99\n", "G90 G95\n")
    if name == "Program End":
        return name, body.replace("G28 W0", "G28 G91 Z0")
    if name == "Retract Home Z":
        return name, "G28 G91 Z0\n"
    replacement = _CODE_RENAMES.get(name)
    if replacement is not None:
        new_name, old_code, new_code = replacement
        return new_name, body.replace(old_code, new_code, 1)
    return name, body


SNIPPETS = tuple(_type_b_entry(name, body) for name, body in TYPE_A_SNIPPETS)
