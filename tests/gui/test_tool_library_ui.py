"""Tool Library button labels and bundled icons."""

import pytest
from PyQt6.QtWidgets import QApplication, QDialog

from app.ui.generated.editors.tool_library import Ui_ToolLibraryDialog


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_tool_library_buttons_have_short_labels_tooltips_and_icons(qt_app):
    dialog = QDialog()
    ui = Ui_ToolLibraryDialog()
    ui.setupUi(dialog)

    for prefix in ("milling", "turning"):
        for suffix, label in (
            ("EditProgram", "Edit Geometry"),
            ("Assign", "Assign from Library"),
            ("Save", "Save to Library"),
            ("AddLibrary", "Add"),
            ("EditLibrary", "Edit"),
            ("DuplicateLibrary", "Duplicate"),
            ("ExportLibrary", "Export"),
            ("RemoveLibrary", "Remove"),
        ):
            button = getattr(ui, f"{prefix}{suffix}Button")
            assert button.text() == label
            assert button.toolTip() == label
            assert button.iconSize().width() == 16
            assert not button.icon().isNull()
        preview = getattr(ui, f"{prefix}PreviewPane")
        for name, label in (
            ("zoomOutButton", "Zoom out"),
            ("fitButton", "Fit preview"),
            ("zoomInButton", "Zoom in"),
        ):
            button = getattr(preview.ui, name)
            assert button.text() == ""
            assert button.toolTip() == label
            assert button.iconSize().width() == 16
            assert not button.icon().isNull()
    assert qt_app is not None
