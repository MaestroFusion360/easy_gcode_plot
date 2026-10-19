"""Connect the File action to the standalone CLI without running CNC in Qt."""

from pathlib import Path

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QMessageBox

from app.ui.support.cli_terminal import CliContext, CliLaunchError, launch_cli


def open_in_cli(window):
    title = QCoreApplication.translate("MainWindow", "Open in CLI")
    if not window.curFile or window.ui.editor.isModified():
        answer = QMessageBox.question(
            window,
            title,
            QCoreApplication.translate("MainWindow", "Save the document before opening it in CLI?"),
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer != QMessageBox.StandardButton.Save or not window.save():
            return
    if not window.curFile or not Path(window.curFile).is_file():
        QMessageBox.warning(window, title, QCoreApplication.translate("MainWindow", "The NC file does not exist."))
        return
    options = [
        "--lang",
        "fanuc_turn" if window.latheMode else "fanuc_mill",
        "--encoding",
        window.fileEncoding,
        "--lathe-gcode-system",
        window.latheGcodeSystem,
        "--sinumerik-cycles",
        "sl" if window.sinumerik840dSl else "classic",
    ]
    if not window.latheMode and window.rotaryKinematics:
        options += ["--kinematics", window.rotaryKinematics]
    context = CliContext(Path(window.curFile).resolve(), tuple(options), window.latheMode)
    try:
        launch_cli(context, window.cliTerminalPath)
    except CliLaunchError as exc:
        QMessageBox.warning(
            window,
            title,
            QCoreApplication.translate(
                "MainWindow", "Could not open CLI. Check the CLI installation and terminal path in Options."
            )
            + "\n\n"
            + str(exc),
        )
