"""Editable starter examples, kept separate from persistence and controller execution."""

from app.gcode.snippets.snippet_catalog.fanuc_b_turn import SNIPPETS as FANUC_B_TURN
from app.gcode.snippets.snippet_catalog.fanuc_mill import SNIPPETS as FANUC_MILL
from app.gcode.snippets.snippet_catalog.fanuc_turn import SNIPPETS as FANUC_TURN
from app.gcode.snippets.snippet_catalog.heidenhain import SNIPPETS as HEIDENHAIN
from app.gcode.snippets.snippet_catalog.sinumerik_mill import SNIPPETS as SINUMERIK_MILL
from app.gcode.snippets.snippet_catalog.sinumerik_turn import SNIPPETS as SINUMERIK_TURN
from app.gcode.snippets.snippet_examples import formula_examples

LANGUAGES = (
    ("fanuc_mill", "Fanuc"),
    ("sinumerik_mill", "Sinumerik"),
    ("heidenhain", "Heidenhain"),
    ("fanuc_turn", "Fanuc Lathe"),
    ("sinumerik_turn", "Sinumerik Lathe"),
    ("fanuc_b_turn", "Fanuc Lathe (B)"),
)

_DEFAULTS = {
    "fanuc_mill": FANUC_MILL,
    "sinumerik_mill": SINUMERIK_MILL,
    "heidenhain": HEIDENHAIN,
    "fanuc_turn": FANUC_TURN,
    "sinumerik_turn": SINUMERIK_TURN,
    "fanuc_b_turn": FANUC_B_TURN,
}


def default_snippets(language_id: str) -> tuple[tuple[str, str], ...]:
    """Return ready-to-edit templates exactly as written, followed by formula examples."""
    return _DEFAULTS[language_id] + formula_examples(language_id)
