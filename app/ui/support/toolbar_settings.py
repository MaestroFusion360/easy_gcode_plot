"""Toolbar membership preferences reuse the original static menu actions."""

import json

from app.ui.dialogs.toolbar_settings import ToolbarSettingsDialog
from app.ui.support.hotkeys import ARC_MODE_ACTIONS, menu_commands

SETTINGS_KEY = "GENERAL/TOOLBAR_COMMANDS"
ORDER_SETTINGS_KEY = "GENERAL/TOOLBAR_ORDER"
MENU_ONLY_ACTIONS = ARC_MODE_ACTIONS | {"actionRenumber", "actionNumbRemove"}


def _static_commands(window, toolbars):
    commands = list(menu_commands(window))
    seen = {key for key, _, _ in commands}
    extra = [(action, toolbar.windowTitle()) for toolbar in toolbars for action in toolbar.actions()]
    extra.extend(
        (action, window.ui.commandsToolBar.windowTitle())
        for action in (
            window.ui.actionSaveStockStl,
            window.ui.actionInsertStockMesh,
        )
    )
    for action, category in extra:
        key = action.objectName()
        if key.startswith("action") and key not in seen and not action.isSeparator() and action.menu() is None:
            commands.append((key, action, category))
            seen.add(key)
    return commands


class ToolbarSettings:
    def __init__(self, window):
        self.window = window
        self.toolbars = window.toolbars()
        self.templates = {toolbar: list(toolbar.actions()) for toolbar in self.toolbars}
        self.commands = {}
        self.defaults = {}
        self.action = window.ui.actionCustomizeToolbars
        self.action.triggered.connect(self.show)
        self._discover()
        self.default_order = {
            toolbar.objectName(): [action.objectName() for action in template if action.objectName() in self.commands]
            for toolbar, template in self.templates.items()
        }
        try:
            saved_order = json.loads(window.settings.value(ORDER_SETTINGS_KEY, "{}", type=str))
        except (ValueError, TypeError):
            saved_order = {}
        self.order = self.normalize_order(saved_order)
        self.selected = self._load()
        self.apply(self.selected)

    def _discover(self):
        ui = self.window.ui
        categories = {
            menu.title().replace("&", ""): toolbar
            for menu, toolbar in (
                (ui.menu_File, ui.fileToolBar),
                (ui.menu_Edit, ui.editToolBar),
                (ui.menu_View, ui.viewToolBar),
                (ui.menuCNC_Functions, ui.cncToolBar),
                (ui.menuSettings, ui.commandsToolBar),
                (ui.menu_Help, ui.helpToolBar),
            )
        }
        for key, action, category in _static_commands(self.window, self.toolbars):
            if action is self.action or key in MENU_ONLY_ACTIONS:
                continue
            toolbar = next((toolbar for toolbar, actions in self.templates.items() if action in actions), None)
            self.defaults[key] = toolbar is not None
            if toolbar is None:
                toolbar = categories.get(category, ui.commandsToolBar)
                self.templates[toolbar].append(action)
            self.commands[key] = (action, toolbar, category)
            self.window.registerToolbarIcon(action)

    def _load(self):
        try:
            values = json.loads(self.window.settings.value(SETTINGS_KEY, "{}", type=str))
        except (ValueError, TypeError):
            values = {}
        if not isinstance(values, dict):
            values = {}
        return {
            key: values[key] if isinstance(values.get(key), bool) else default for key, default in self.defaults.items()
        }

    def normalize_order(self, order):
        """Ignore stale entries and append newly available commands in their default order."""
        order = order if isinstance(order, dict) else {}
        result = {}
        for name, defaults in self.default_order.items():
            saved = order.get(name, [])
            saved = saved if isinstance(saved, list) else []
            result[name] = list(dict.fromkeys(key for key in saved if isinstance(key, str) and key in defaults))
            result[name].extend(key for key in defaults if key not in result[name])
        return result

    def apply(self, selected, *, order=None, persist=False):
        if order is not None:
            self.order = self.normalize_order(order)
        self.selected = {key: bool(selected.get(key, default)) for key, default in self.defaults.items()}
        allowed = {self.commands[key][0] for key, enabled in self.selected.items() if enabled}
        managed = {command[0] for command in self.commands.values()}
        for toolbar, template in self.templates.items():
            ordered = iter(self.commands[key][0] for key in self.order[toolbar.objectName()])
            arranged = [next(ordered) if action in managed else action for action in template]
            self._rebuild(toolbar, arranged, managed, allowed)
        self.window.ui.commandsToolBar.setVisible(bool(self.window.ui.commandsToolBar.actions()))
        self.window.ui.helpToolBar.setVisible(bool(self.window.ui.helpToolBar.actions()))
        if persist:
            self.window.settings.setValue(SETTINGS_KEY, json.dumps(self.selected, sort_keys=True))
            self.window.settings.setValue(ORDER_SETTINGS_KEY, json.dumps(self.order, sort_keys=True))
            self.window.settings.sync()

    @staticmethod
    def _rebuild(toolbar, template, managed, allowed):
        for action in toolbar.actions():
            toolbar.removeAction(action)
        separator = None
        for action in template:
            if action.isSeparator():
                separator = action
                continue
            if action in managed and action not in allowed:
                continue
            if separator is not None and toolbar.actions():
                toolbar.addAction(separator)
            separator = None
            toolbar.addAction(action)

    def restore_defaults(self):
        self.apply(self.defaults, order=self.default_order, persist=True)

    def show(self):
        dialog = ToolbarSettingsDialog(self, self.window)
        dialog.exec()
        dialog.deleteLater()
