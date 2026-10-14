"""Discover static commands and their configurable shortcuts."""

from PyQt6.QtGui import QKeySequence

BLOCK_SKIP_SHORTCUT = "Ctrl+/"
REMOVE_BLOCK_SKIP_SHORTCUT = "Ctrl+Shift+/"
ARC_MODE_ACTIONS = frozenset({"actionRelative_to_start", "actionAbsolute", "actionRadius_value"})

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


def is_reserved_shortcut(sequence: str) -> bool:
    """Keep the editor's fixed block-skip shortcut out of menu assignments."""
    parsed = QKeySequence(str(sequence), QKeySequence.SequenceFormat.PortableText)
    return portable_shortcut(parsed) in {
        portable_shortcut(QKeySequence(BLOCK_SKIP_SHORTCUT)),
        portable_shortcut(QKeySequence(REMOVE_BLOCK_SKIP_SHORTCUT)),
    }


def menu_commands(window):
    """Yield each static menu, toolbar or context command once."""
    seen = set()
    for top_action in window.ui.menubar.actions():
        menu = top_action.menu()
        if menu is None:
            continue
        category = menu.title().replace("&", "")
        yield from _menu_commands(menu, category, seen)
    for action, category in _additional_commands(window):
        key = action.objectName()
        if (
            key.startswith("action")
            and key not in seen
            and key not in ARC_MODE_ACTIONS
            and action.menu() is None
            and not action.isSeparator()
        ):
            seen.add(key)
            yield key, action, category


def _additional_commands(window):
    for toolbar in getattr(window, "toolbars", lambda: ())():
        for action in toolbar.actions():
            yield action, toolbar.windowTitle()
    for name in (
        "actionStockPlayback",
        "actionSaveStockStl",
        "actionInsertStockMesh",
        "actionStep_Backward",
        "actionPlay",
        "actionStop",
        "actionStep_Forward",
    ):
        action = getattr(window.ui, name, None)
        if action is not None:
            yield action, window.ui.playbackToolBar.windowTitle()


def _menu_commands(menu, category, seen):
    for action in menu.actions():
        submenu = action.menu()
        if submenu is not None:
            # Recent-file entries change with the file list and have no stable command ID.
            if submenu.objectName().startswith("menu"):
                yield from _menu_commands(submenu, category, seen)
            continue
        key = action.objectName()
        if action.isSeparator() or not key.startswith("action") or key in seen or key in ARC_MODE_ACTIONS:
            continue
        seen.add(key)
        yield key, action, category
