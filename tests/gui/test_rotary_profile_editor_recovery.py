"""The built-in JSON editor can repair a damaged override on Save."""

import json

from PyQt6.QtWidgets import QApplication, QDialog

from app.gcode.kernel.milling.kinematics import load_catalog, user_catalog_path
from app.ui.dialogs.options import RotaryKinematicsJsonDialog


def test_rotary_json_editor_opens_and_saves_after_corrupt_override():
    application = QApplication.instance() or QApplication([])
    path = user_catalog_path()
    path.write_text("{broken", encoding="utf-8")
    dialog = RotaryKinematicsJsonDialog("4ax_table_b")
    edited = json.loads(dialog.editor.toPlainText())
    edited["table"][0]["axis"] = [0, -1, 0]
    dialog.editor.setPlainText(json.dumps(edited))
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert load_catalog()["4ax_table_b"].table_rotary_axes[0].axis == (0, -1, 0)
    dialog.deleteLater()
    application.processEvents()
