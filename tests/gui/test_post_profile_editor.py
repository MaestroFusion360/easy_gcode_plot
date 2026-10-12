"""Exercise the Designer form through the real profile editor and library."""

# pylint: disable=protected-access
import copy
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication, QDialog, QWidget

from app.gcode.post_profiles import POST_TARGETS, load_post_profile
from app.post_profile_library import PostProfileLibrary
from app.ui.dialogs.post_profile_editor import PostProfileEditor
from app.ui.generated.dialogs.post_profile_editor import Ui_PostProfileEditorDlg


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def make_editor(qt_app, tmp_path):
    dialogs = []
    library = PostProfileLibrary(tmp_path)

    def make(target="fanuc_mill", profile=None):
        path = library.save(profile or load_post_profile(target))
        dialog = PostProfileEditor(library, path)
        dialogs.append(dialog)
        return dialog

    yield make
    for dialog in dialogs:
        dialog.close()
        dialog.deleteLater()
    qt_app.processEvents()


def test_generated_form_is_embeddable(qt_app):
    widget = QWidget()
    ui = Ui_PostProfileEditorDlg()
    ui.setupUi(widget)
    assert ui.tabs.count() == 10
    assert ui.centerSplit.count() == ui.radiusSplit.count() == 6
    assert not isinstance(widget, QDialog)
    assert not hasattr(ui, "buttonBox")
    widget.deleteLater()
    qt_app.processEvents()


@pytest.mark.parametrize("target", POST_TARGETS)
def test_every_builtin_roundtrips_without_changing_fields(make_editor, target):
    dialog = make_editor(target)
    original = load_post_profile(target)
    assert dialog.current_profile() == original
    assert dialog._checked_profile() == original
    dialog.save()
    assert dialog.saved_path == dialog.path
    assert dialog.library.load(dialog.saved_path) == original


@pytest.mark.parametrize("angle", [22.5, 5400])
def test_custom_split_angle_is_displayed_and_can_be_changed(make_editor, angle):
    profile = load_post_profile("heidanhain_itnc530")
    profile["format"]["arcSplitAngle"] = angle
    dialog = make_editor(profile=profile)
    assert dialog.ui.centerSplit.currentText() == f"{angle:g}\N{DEGREE SIGN}"
    assert dialog.current_profile()["format"]["arcSplitAngle"] == angle
    dialog.ui.centerSplit.setCurrentIndex(2)
    assert dialog.current_profile()["format"]["arcSplitAngle"] == 90


def test_changes_to_text_numbers_lists_checks_and_combos_are_saved(make_editor):
    dialog = make_editor()
    original = copy.deepcopy(dialog.profile)
    dialog.ui.nameEdit.setText("Workshop")
    dialog.ui.precision.setCurrentIndex(5)
    dialog.ui.coordinates.setCurrentIndex(1)
    dialog.ui.plusSign.setChecked(True)
    dialog.ui.dwellScaleEdit.setText("1000")
    dialog.ui.preambleEdit.setPlainText("G17 G90\n\nM8")
    dialog.ui.arcs.setCurrentIndex(2)
    dialog.ui.radiusSplit.setCurrentIndex(3)
    changed = dialog.current_profile()
    assert dialog.profile == original
    assert changed["name"] == "Workshop"
    assert changed["options"]["decimalPlaces"] == 5
    assert changed["options"]["incrementalMode"] is True
    assert changed["options"]["plusOutput"] is True
    assert changed["dwell"]["scale"] == 1000
    assert changed["program"]["preamble"] == ["G17 G90", "M8"]
    assert changed["format"]["arcMode"] == "R"
    assert changed["format"]["radiusSplitAngle"] == 120
    dialog.save()
    assert dialog.library.load(dialog.path) == changed


def test_cancel_does_not_write_edits(make_editor):
    dialog = make_editor()
    before = Path(dialog.path).read_bytes()
    dialog.ui.nameEdit.setText("Discard this")
    dialog.close()
    assert dialog.saved_path is None
    assert Path(dialog.path).read_bytes() == before


@pytest.mark.parametrize("failure", ["invalid", "io"])
def test_save_failure_keeps_dialog_open_and_file_intact(make_editor, monkeypatch, failure):
    dialog = make_editor()
    before = Path(dialog.path).read_bytes()
    if failure == "invalid":
        dialog.ui.linearMoveEdit.setText("G1 {unknown}")
    else:

        def fail(*args):
            raise OSError("disk unavailable")

        monkeypatch.setattr(dialog.library, "save", fail)
    with pytest.raises((ValueError, OSError)):
        dialog.save()
    assert dialog.saved_path is None
    assert Path(dialog.path).read_bytes() == before


def test_address_order_precision_sign_and_required_are_independent(make_editor):
    dialog = make_editor()
    dialog._select_address("X")
    dialog.ui.addressPrecision.setCurrentIndex(dialog.ui.addressPrecision.findData(5))
    dialog.ui.addressSign.setCurrentIndex(dialog.ui.addressSign.findData("always"))
    dialog.ui.addressRequired.setCurrentIndex(dialog.ui.addressRequired.findData(True))
    dialog._move_address("X", 0)
    words = dialog._checked_profile()["format"]["words"]
    assert min(words, key=lambda key: words[key]["order"]) == "X"
    assert words["X"]["decimals"] == 5
    assert words["X"]["sign"] == "always"
    assert words["X"]["required"] is True
    assert "decimals" not in words["Y"]


def test_native_fields_and_constraints_match_writer(make_editor):
    dialog = make_editor("heidanhain_itnc530")
    assert dialog.ui.rapidMoveEdit.text() == "L"
    assert dialog.ui.linearMoveEdit.text() == "FMAX"
    assert dialog.ui.circularMoveCWEdit.text() == "CC"
    assert dialog.ui.arcs.currentIndex() == 0
    assert not dialog.ui.arcs.model().item(1).isEnabled()
    assert not dialog.ui.spaces.isEnabled()
    assert not dialog.ui.multiTurn.isEnabled()
    dialog.ui.circularMoveCWEdit.setText("CUSTOM_CC")
    changed = dialog.current_profile()
    assert changed["native"]["circleCenter"] == "CUSTOM_CC"
    assert changed["motion"] == dialog.profile["motion"]
    dialog._move_address("X", 0)
    with pytest.raises(ValueError, match="first"):
        dialog._checked_profile()


def test_editor_refuses_direct_builtin_file(make_editor):
    dialog = make_editor()
    builtin = Path(__file__).parents[2] / "app/gcode/export/posts/fanuc_mill.json"
    with pytest.raises(ValueError, match="user post-profile directory"):
        PostProfileEditor(dialog.library, builtin)
