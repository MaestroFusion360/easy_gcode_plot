import re
from types import SimpleNamespace

import pytest
from PyQt6.Qsci import QsciScintilla
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox

from app.gcode.generators import PocketParameters, hole_circle, hole_grid, pocket_preview_geometry, pocket_program
from app.ui.dialogs import snippets as snippets_module
from app.ui.dialogs.calculators import HoleCalculatorDialog, PocketCalculatorDialog
from app.ui.dialogs.snippets import SnippetsDialog


@pytest.fixture(scope="module", autouse=True)
def application():
    return QApplication.instance() or QApplication([])


def test_hole_generators_create_circle_and_serpentine_grid():
    circle = hole_circle(diameter=20, start_angle=0, center_x=1, center_y=2, count=4)
    assert circle.splitlines() == ["X11 Y2", "X1 Y12", "X-9 Y2", "X1 Y-8"]

    grid = hole_grid(start_x=0, start_y=0, step_x=10, step_y=5, count_x=3, count_y=2)
    assert grid.splitlines() == ["X0 Y0", "X10 Y0", "X20 Y0", "X20 Y5", "X10 Y5", "X0 Y5"]


def test_hole_dialog_inserts_at_editor_caret():
    parent = QMainWindow()
    parent.ui = SimpleNamespace(editor=QsciScintilla(parent))
    parent.ui.editor.setText("G90")
    dialog = HoleCalculatorDialog(parent)
    dialog.ui.holeCountSpin.setValue(2)

    dialog.calculate_and_insert()

    assert parent.ui.editor.text().startswith("G90\nX50 Y0\nX-50 Y0")


def test_hole_dialog_is_compact_and_has_live_preview():
    dialog = HoleCalculatorDialog()

    assert dialog.minimumHeight() == 0
    assert dialog.ui.insertButton.text() == "Insert"
    assert dialog.preview.minimumWidth() >= 240
    assert dialog.preview.points

    dialog.ui.patternTabs.setCurrentWidget(dialog.ui.gridTab)
    dialog.ui.countXSpin.setValue(3)
    dialog.ui.countYSpin.setValue(2)

    assert len(dialog.preview.points) == 6


def _xy_coordinates(program: str):
    pattern = re.compile(r"X(-?\d+(?:\.\d+)?)\s+Y(-?\d+(?:\.\d+)?)")
    return [
        (float(match.group(1)), float(match.group(2))) for match in map(pattern.search, program.splitlines()) if match
    ]


def test_rectangular_spiral_clears_inside_and_finishes_outer_contour():
    params = PocketParameters(
        circular=False,
        pocket_width=100.0,
        pocket_height=100.0,
        tool_diameter=10.0,
        stepover=5.0,
        z_end=-1.0,
        z_step=1.0,
        spiral=True,
    )

    program = pocket_program(params)
    coordinates = _xy_coordinates(program)

    assert len(coordinates) > 100
    assert any(abs(x_value) < 10 and abs(y_value) < 10 for x_value, y_value in coordinates)
    assert any(abs(abs(x_value) - 45.0) < 1e-6 and abs(abs(y_value) - 45.0) < 1e-6 for x_value, y_value in coordinates)
    assert all(abs(x_value) <= 45.001 and abs(y_value) <= 45.001 for x_value, y_value in coordinates)

    geometry = pocket_preview_geometry(params)
    assert len(geometry.paths) == 2
    assert len(geometry.paths[0]) > 100


def test_pocket_generator_supports_shape_direction_and_options():
    program = pocket_program(
        PocketParameters(
            circular=False,
            ccw=False,
            spiral=True,
            helix=True,
            correction=True,
            stock_xy=1.0,
        )
    )

    assert "G2 " in program
    assert "G42" not in program
    assert "G41" not in program
    assert "X45 Y-45" in program
    assert "Z-2" in program
    assert len(_xy_coordinates(program)) > 100


def test_pocket_helix_never_rapids_below_uncut_depth():
    params = PocketParameters(z_end=-10, z_step=5, helix=True)
    lines = pocket_program(params).splitlines()
    assert "G0 Z0" in lines
    assert "G0 Z-5" in lines
    assert "G0 Z-2" not in lines
    assert lines.index("G0 Z10 M8") < lines.index("G0 X0 Y0")


def test_pocket_rejects_excessive_path_before_preview_or_generation():
    params = PocketParameters(pocket_diameter=1000, stepover=0.001)
    with pytest.raises(ValueError, match="point limit"):
        pocket_preview_geometry(params)
    with pytest.raises(ValueError, match="point limit"):
        pocket_program(params)


def test_pocket_rejects_unsafe_z_setup():
    with pytest.raises(ValueError, match="Z reference"):
        pocket_program(PocketParameters(z_reference=-1))
    with pytest.raises(ValueError, match="Z reference"):
        pocket_program(PocketParameters(z_end=1))


def test_pocket_dialog_uses_compact_columns_and_switches_dimension_controls():
    dialog = PocketCalculatorDialog()

    assert dialog.minimumHeight() == 0
    assert dialog.ui.insertButton.text() == "Insert"
    assert dialog.ui.cuttingForm.getWidgetPosition(dialog.ui.zReferenceLabel)[0] == 1
    assert dialog.ui.geometryForm.getLayoutPosition(dialog.ui.optionsLayout)[0] == 10
    assert not dialog.ui.pocketDiameterSpin.isHidden()
    assert dialog.ui.pocketWidthSpin.isHidden()
    assert dialog.preview.minimumWidth() >= 240

    dialog.ui.rectangularRadio.setChecked(True)

    assert dialog.ui.pocketDiameterSpin.isHidden()
    assert not dialog.ui.pocketWidthSpin.isHidden()


def test_pocket_dialog_disables_insert_for_excessive_path():
    dialog = PocketCalculatorDialog()
    dialog.ui.pocketDiameterSpin.setValue(1000)
    dialog.ui.stepoverSpin.setValue(0.001)
    assert not dialog.ui.insertButton.isEnabled()
    assert "point limit" in dialog.ui.insertButton.toolTip()
    dialog.ui.stepoverSpin.setValue(5)
    assert dialog.ui.insertButton.isEnabled()


def _snippets_dialog(tmp_path, monkeypatch):
    monkeypatch.setattr(snippets_module, "config_path", lambda: str(tmp_path / "config.ini"))
    directory = tmp_path / "snippets"
    directory.mkdir()
    (directory / "A.txt").write_text("A original", encoding="utf-8")
    (directory / "B.txt").write_text("B original", encoding="utf-8")
    return SnippetsDialog(), directory


def test_snippet_selection_change_prompts_and_cancel_preserves_editor(tmp_path, monkeypatch):
    dialog, _directory = _snippets_dialog(tmp_path, monkeypatch)
    dialog.ui.snippetEditor.setPlainText("A changed")
    prompts = []

    def cancel(*args, **kwargs):
        prompts.append((args, kwargs))
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(snippets_module.QMessageBox, "question", cancel)
    dialog.ui.snippetList.setCurrentRow(1)

    assert prompts
    assert dialog.ui.snippetList.currentRow() == 0
    assert dialog.ui.snippetEditor.toPlainText() == "A changed"
    assert dialog.library.list_snippets()[0].body == "A original"


def test_snippet_selection_change_can_save_before_switching(tmp_path, monkeypatch):
    dialog, directory = _snippets_dialog(tmp_path, monkeypatch)
    dialog.ui.snippetEditor.setPlainText("A changed")
    monkeypatch.setattr(
        snippets_module.QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Save,
    )

    dialog.ui.snippetList.setCurrentRow(1)

    assert dialog.ui.snippetList.currentRow() == 1
    assert dialog.ui.snippetEditor.toPlainText() == "B original"
    assert dialog.library.list_snippets()[0].body == "A changed"
    assert (directory / "A.txt").read_text(encoding="utf-8") == "A original"


def test_snippet_order_survives_dialog_reload(tmp_path, monkeypatch):
    dialog, _directory = _snippets_dialog(tmp_path, monkeypatch)
    assert [item.name for item in dialog.snippets] == ["A", "B"]

    dialog.move_current(1)
    reloaded = SnippetsDialog()

    assert [item.name for item in reloaded.snippets] == ["B", "A"]
