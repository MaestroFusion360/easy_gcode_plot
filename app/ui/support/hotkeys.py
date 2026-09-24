"""Discover named menu commands and their configurable shortcuts."""

from PyQt6.QtGui import QKeySequence

LEGACY_KEYS = {
    "actionRefresh": "REFRESH",
    "action3D": "VIEW_3D",
    "actionTop": "VIEW_TOP",
    "actionFront": "VIEW_FRONT",
    "actionLeft": "VIEW_LEFT",
}


def portable_shortcut(sequence):
    """Return a stable representation for settings and duplicate checks."""
    return sequence.toString(QKeySequence.SequenceFormat.PortableText)


def menu_commands(window):
    """Yield each named command reachable from the main menu, once."""
    seen = set()
    for top_action in window.ui.menubar.actions():
        menu = top_action.menu()
        if menu is None:
            continue
        category = menu.title().replace("&", "")
        yield from _menu_commands(menu, category, seen)


def _menu_commands(menu, category, seen):
    for action in menu.actions():
        submenu = action.menu()
        if submenu is not None:
            # Recent-file entries change with the file list and have no stable command ID.
            if submenu.objectName().startswith("menu"):
                yield from _menu_commands(submenu, category, seen)
            continue
        key = action.objectName()
        if action.isSeparator() or not key.startswith("action") or key in seen:
            continue
        seen.add(key)
        yield key, action, category
