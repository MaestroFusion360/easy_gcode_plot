"""Toolbar membership is independent of menu actions, widgets and shortcuts."""

import json

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QKeySequence
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.settings import get_settings
from app.ui.dialogs.toolbar_settings import ToolbarSettingsDialog
from app.ui.support.hotkeys import ARC_MODE_ACTIONS
from app.ui.support.toolbar_settings import SETTINGS_KEY


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qt_app):
    owner = MainWindow()
    yield owner
    owner.deleteLater()
    qt_app.processEvents()


def test_static_commands_include_tools_and_exclude_dynamic_entries(window):
    settings = window.toolbarSettings
    assert {
        "actionToolLibrary",
        "actionWCS",
        "actionStock",
        "actionTokens",
        "actionStockPlayback",
    } <= settings.commands.keys()
    assert "actionCustomizeToolbars" not in settings.commands
    assert all(action.menu() is None for action, _bar, _category in settings.commands.values())
    assert not window.ui.commandsToolBar.actions()
    assert window.ui.commandsToolBar.isHidden()
    assert settings.action not in window.ui.menuSettings.actions()
    assert settings.action in window.createPopupMenu().actions()
    assert "actionCustomizeToolbars" not in window.hotkeyActions
    assert settings.commands.keys() <= window.hotkeyActions.keys()


def test_hiding_button_keeps_menu_shortcut_and_action_identity(window):
    manager = window.toolbarSettings
    action = window.ui.actionNew
    shortcut = action.shortcut()
    selected = dict(manager.selected, actionNew=False, actionToolLibrary=True, actionStock=True)
    manager.apply(selected, persist=True)
    assert action not in window.ui.fileToolBar.actions()
    assert action in window.ui.menu_File.actions()
    assert action.isVisible() and action.isEnabled() and action.shortcut() == shortcut
    assert window.ui.actionToolLibrary in window.ui.commandsToolBar.actions()
    assert window.ui.actionStock in window.ui.commandsToolBar.actions()
    assert not window.ui.commandsToolBar.isHidden()
    window.ui.actionToolLibrary.setEnabled(False)
    assert not manager.commands["actionToolLibrary"][0].isEnabled()


def test_optional_commands_follow_existing_menu_groups(window):
    commands = window.toolbarSettings.commands
    assert commands["actionAbout"][1] is window.ui.helpToolBar
    assert commands["actionExit"][1] is window.ui.fileToolBar
    assert commands["actionFAQ"][1] is window.ui.helpToolBar
    assert commands["actionToolLibrary"][1] is window.ui.commandsToolBar
    assert window.ui.commandsToolBar.windowTitle() == "Settings"
    assert commands["actionSaveStockStl"][1] is window.ui.fileToolBar
    assert commands["actionInsertStockMesh"][1] is window.ui.fileToolBar
    assert window.ui.actionSaveStockStl in window.ui.menu_File.actions()
    assert window.ui.actionInsertStockMesh in window.ui.menu_File.actions()


def test_numbering_and_arc_modes_use_dropdowns_without_individual_buttons(window):
    for key in ("actionRenumber", "actionNumbRemove"):
        assert key not in window.toolbarSettings.commands
        assert key in window.hotkeyActions
    assert not ARC_MODE_ACTIONS & window.toolbarSettings.commands.keys()
    assert not ARC_MODE_ACTIONS & window.hotkeyActions.keys()
    assert window.ui.menuBlockNumbers.menuAction() in window.ui.cncToolBar.actions()
    assert window.ui.actionRelative_to_start in window.ui.menuArc_Type.actions()


@pytest.mark.parametrize(
    "name",
    [
        "renumber",
        "remove_block_numbers",
        "arc_relative",
        "arc_absolute",
        "arc_radius",
        "save_stock_stl",
        "insert_stock_mesh",
        "clear_stl",
    ],
)
def test_command_icons_are_registered_32_pixel_pngs(name):
    image = QImage(f":/resource/icons/{name}.png")
    assert not image.isNull() and (image.width(), image.height()) == (32, 32)
    assert image.hasAlphaChannel()


def test_every_toolbar_command_can_receive_a_shortcut_without_its_button(window):
    window.toolbarSettings.apply({key: False for key in window.toolbarSettings.commands})
    window.optionsDlg.load_values()
    editor_keys = {key for key, _action, _category in window.optionsDlg.hotkeyEditor.commands}
    assert window.toolbarSettings.commands.keys() <= editor_keys
    for key, (action, _toolbar, _category) in window.toolbarSettings.commands.items():
        window.setHotkeys({key: "Ctrl+Alt+F12"})
        assert action.shortcut() == QKeySequence("Ctrl+Alt+F12"), key
        assert action in window.actions(), key


def test_toolbar_choices_round_trip_and_defaults_restore(window, qt_app):
    manager = window.toolbarSettings
    manager.apply(dict(manager.selected, actionNew=False, actionTokens=True), persist=True)
    restored = MainWindow()
    try:
        assert restored.ui.actionNew not in restored.ui.fileToolBar.actions()
        assert restored.ui.actionTokens in restored.ui.commandsToolBar.actions()
        restored.resetToolbarsToDefault()
        assert restored.ui.actionNew in restored.ui.fileToolBar.actions()
        assert restored.ui.actionTokens not in restored.ui.commandsToolBar.actions()
        assert restored.toolbarSettings.selected == restored.toolbarSettings.defaults
    finally:
        restored.deleteLater()
        qt_app.processEvents()


def test_dialog_cancel_search_and_defaults_are_staged(window):
    manager = window.toolbarSettings
    before = dict(manager.selected)
    dialog = ToolbarSettingsDialog(manager, window)
    dialog.items["actionToolLibrary"].setCheckState(0, Qt.CheckState.Checked)
    dialog.ui.searchEdit.setText("Tool Library")
    assert not dialog.items["actionToolLibrary"].isHidden()
    assert dialog.items["actionNew"].isHidden()
    dialog.reject()
    assert manager.selected == before
    manager.apply(dict(before, actionToolLibrary=True))
    dialog = ToolbarSettingsDialog(manager, window)
    dialog.restore_defaults()
    assert manager.selected["actionToolLibrary"]
    dialog.accept()
    assert manager.selected == manager.defaults


def test_source_chooser_and_speed_widget_survive_repeated_customization(window):
    manager = window.toolbarSettings
    source, speed = window.ui.fileTypeCombo, window.ui.playbackSpeedSlider
    for enabled in (False, True, False):
        manager.apply(dict(manager.selected, actionPlay=enabled, actionToolLibrary=True))
        assert window.ui.fileTypeCombo is source and source.parent() is not None
        assert window.ui.playbackSpeedSlider is speed and speed.parent() is not None
        assert source.count() > 0 and speed.minimum() == 1
        for toolbar in window.toolbars():
            actions = toolbar.actions()
            assert not actions or not actions[0].isSeparator() and not actions[-1].isSeparator()
    window.applyToolbarIconSize(32)
    assert all(toolbar.iconSize().width() == 32 for toolbar in window.toolbars())


def test_order_arrows_stage_apply_persist_and_restore(window, qt_app):
    manager = window.toolbarSettings
    name = window.ui.fileToolBar.objectName()
    original = list(manager.order[name])
    dialog = ToolbarSettingsDialog(manager, window)
    first = dialog.items[original[0]]
    dialog.ui.commandTree.setCurrentItem(first)
    assert not dialog.ui.upButton.isEnabled()
    assert dialog.ui.downButton.isEnabled()
    assert not dialog.ui.downButton.icon().isNull()
    dialog.ui.downButton.click()
    assert dialog.command_order()[name][:2] == original[1::-1]
    assert manager.order[name] == original
    dialog.reject()
    assert manager.order[name] == original
    dialog = ToolbarSettingsDialog(manager, window)
    dialog.ui.commandTree.setCurrentItem(dialog.items[original[0]])
    dialog.ui.downButton.click()
    dialog.ui.upButton.click()
    assert dialog.command_order()[name] == original
    dialog.ui.downButton.click()
    dialog.accept()
    expected = original[1::-1] + original[2:]
    assert manager.order[name] == expected
    actual = [action.objectName() for action in window.ui.fileToolBar.actions() if action.objectName() in original]
    assert actual == [key for key in expected if manager.selected[key]]
    restored = MainWindow()
    try:
        assert restored.toolbarSettings.order[name] == expected
    finally:
        restored.deleteLater()
        qt_app.processEvents()
    dialog = ToolbarSettingsDialog(manager, window)
    dialog.restore_defaults()
    assert dialog.command_order() == manager.default_order
    assert manager.order[name] == expected
    dialog.accept()
    assert manager.order == manager.default_order


def test_order_arrows_ignore_groups_and_filtered_search(window):
    dialog = ToolbarSettingsDialog(window.toolbarSettings, window)
    group = dialog.ui.commandTree.topLevelItem(0)
    dialog.ui.commandTree.setCurrentItem(group)
    assert not dialog.ui.upButton.isEnabled() and not dialog.ui.downButton.isEnabled()
    dialog.ui.commandTree.setCurrentItem(group.child(1))
    dialog.ui.searchEdit.setText(group.child(1).text(0))
    assert not dialog.ui.upButton.isEnabled() and not dialog.ui.downButton.isEnabled()
    dialog.reject()


def test_order_normalization_preserves_fixed_widgets(window):
    manager = window.toolbarSettings
    name = window.ui.fileToolBar.objectName()
    defaults = manager.default_order[name]
    order = manager.normalize_order({name: [defaults[1], defaults[1], "unknown", [], "actionPlay"]})
    assert order[name] == [defaults[1]] + [key for key in defaults if key != defaults[1]]
    source = window.ui.fileTypeCombo
    speed = window.ui.playbackSpeedSlider
    manager.apply(manager.selected, order=order)
    assert window.ui.fileTypeCombo is source and source.parent() is not None
    assert window.ui.playbackSpeedSlider is speed and speed.parent() is not None
    assert manager.normalize_order([]) == manager.default_order


@pytest.mark.parametrize("stored", ["broken", "[]", '{"actionNew":"false","actionUnknown":true}'])
def test_malformed_membership_uses_safe_defaults(qt_app, stored):
    settings = get_settings()
    settings.setValue(SETTINGS_KEY, stored)
    owner = MainWindow()
    try:
        assert owner.toolbarSettings.selected == owner.toolbarSettings.defaults
        assert "actionUnknown" not in owner.toolbarSettings.commands
        owner.toolbarSettings.restore_defaults()
        assert isinstance(json.loads(settings.value(SETTINGS_KEY, type=str)), dict)
    finally:
        owner.deleteLater()
        qt_app.processEvents()
