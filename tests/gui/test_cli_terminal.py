"""External CLI launch contracts: argument boundaries, discovery and Qt wiring."""

import base64
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

from app.cli import _parser, main
from app.gcode.kernel import execute
from app.gcode.trace import trace_statistics
from app.main_window import MainWindow
from app.ui.support import cli_terminal as terminal
from app.ui.windows import cli_integration


@pytest.fixture
def context(tmp_path):
    file = tmp_path / "деталь with spaces ' $ ; &.nc"
    file.write_text("G0 X0 Y0 Z1\nM30", encoding="utf-8")
    return terminal.CliContext(file, ("--lang", "fanuc_mill", "--encoding", "utf-8", "--kinematics", "5ax_table_ac"))


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qt_app):
    owner = MainWindow()
    owner.autoUpdateEnabled = False
    owner.autoUpdateTimer.stop()
    yield owner
    owner.deleteLater()
    qt_app.processEvents()


def _platform(monkeypatch, name, **kwargs):
    monkeypatch.setattr(terminal, "sys", SimpleNamespace(platform=name, **kwargs))


@pytest.mark.parametrize("platform,name", [("win32", "easy_gcode_plot_cli.exe"), ("linux", "easy_gcode_plot_cli")])
def test_frozen_gui_uses_sibling_cli_without_relaunching_itself(tmp_path, monkeypatch, platform, name):
    cli = tmp_path / name
    cli.touch()
    _platform(monkeypatch, platform, frozen=True, executable=str(tmp_path / "easy_gcode_plot.exe"))
    assert terminal.cli_command() == (str(cli),)


def test_missing_frozen_cli_is_reported_and_path_install_is_supported(tmp_path, monkeypatch):
    _platform(monkeypatch, "linux", frozen=True, executable=str(tmp_path / "gui"))
    monkeypatch.setattr(terminal.shutil, "which", lambda _name: None)
    with pytest.raises(terminal.CliLaunchError, match="CLI not found"):
        terminal.cli_command()
    monkeypatch.setattr(terminal.shutil, "which", lambda _name: "/usr/bin/easy_gcode_plot_cli")
    assert terminal.cli_command() == ("/usr/bin/easy_gcode_plot_cli",)


def test_source_cli_uses_real_entrypoint():
    command = terminal.cli_command()
    assert len(command) == 2 and Path(command[1]).name == "cli_main.py"
    assert all(Path(part).is_file() for part in command)


@pytest.mark.parametrize("platform,name", [("win32", "powershell.exe"), ("linux", "xterm")])
def test_auto_detection_and_explicit_terminal_errors(monkeypatch, platform, name):
    _platform(monkeypatch, platform)
    monkeypatch.setattr(terminal.shutil, "which", lambda value: "/tools/" + name if value == name else None)
    assert terminal.terminal_path() == "/tools/" + name
    assert terminal.terminal_path(name) == "/tools/" + name
    with pytest.raises(terminal.CliLaunchError, match="configured terminal"):
        terminal.terminal_path("missing")
    monkeypatch.setattr(terminal.shutil, "which", lambda _value: None)
    with pytest.raises(terminal.CliLaunchError, match="No terminal"):
        terminal.terminal_path()


@pytest.mark.parametrize("name", ["powershell", "pwsh", "wt", "cmd"])
@pytest.mark.parametrize("shell", ["powershell.exe", r"C:\Program Files\PowerShell\7\pwsh.exe"])
def test_windows_terminal_keeps_powershell_open_and_encodes_paths(context, monkeypatch, name, shell):
    _platform(monkeypatch, "win32")
    monkeypatch.setattr(terminal.shutil, "which", lambda _name: shell)
    args = terminal.terminal_command(name + ".exe", ("C:/Program Files/App/cli.exe",), context)
    if name == "cmd":
        assert isinstance(args, str)
        assert args.startswith(f'cmd.exe /d /s /v:off /c ""{shell}" ')
        assert '\\"' not in args
        encoded = args.split()[-1].removesuffix('"')
    else:
        assert "-NoExit" in args and "-EncodedCommand" in args
        encoded = args[-1]
    script = base64.b64decode(encoded).decode("utf-16le")
    if name == "cmd":
        assert "EGP_CLI_STARTUP" in script and len(args) < 8191
        script = terminal.session_script(("C:/Program Files/App/cli.exe",), context, windows=True)
    assert "Set-Location -LiteralPath" in script
    assert str(context.file).replace("'", "''") in script
    assert "function global:egp" in script
    assert "--kinematics" in script and "--format" in script and "batch-export" in script


@pytest.mark.parametrize(
    "name,flag",
    [
        ("gnome-terminal", "--"),
        ("konsole", "-e"),
        ("xfce4-terminal", "--execute"),
        ("wezterm", "--"),
        ("terminator", "-x"),
        ("x-terminal-emulator", "-e"),
        ("kitty", "-e"),
        ("mate-terminal", "--"),
        ("alacritty", "-e"),
        ("foot", "-e"),
        ("lxterminal", "-e"),
    ],
)
def test_linux_terminal_passes_script_as_one_argument(context, monkeypatch, name, flag):
    _platform(monkeypatch, "linux")
    monkeypatch.setattr(terminal.shutil, "which", lambda _name: "/bin/bash")
    args = terminal.terminal_command("/usr/bin/" + name, ("/opt/Easy G-Code/cli",), context)
    assert flag in args
    assert args[-2] == "-c"
    assert 'exec "$BASH" --noprofile -i' in args[-1]
    assert "export -f egp" in args[-1]


def test_linux_script_really_preserves_hostile_argument_boundaries(context, tmp_path):
    bash = shutil.which("bash") if sys.platform != "win32" else r"C:\Program Files\Git\bin\bash.exe"
    if not bash or not Path(bash).is_file():
        pytest.skip("Bash unavailable")
    recorder = tmp_path / "record.py"
    output = tmp_path / "received.json"
    recorder.write_text(
        "import json,sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text(json.dumps(sys.argv[2:]))\n"
    )
    command = tuple(Path(item).as_posix() for item in (sys.executable, str(recorder), str(output)))
    script = terminal.session_script(command, context, windows=False).replace('exec "$BASH" --noprofile -i', "exit")
    # Git Bash on Windows truncates long -c arguments. Feed the complete source
    # through stdin so banner size cannot truncate the script under test.
    result = subprocess.run(
        [bash, "--noprofile", "--norc", "-s"],
        input=script,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not output.exists(), "Opening a session must not run CLI commands"
    manual = "egp " + shlex.join(["analyze", str(context.file), *context.options])
    script = terminal.session_script(command, context, windows=False).replace(
        'exec "$BASH" --noprofile -i', manual + "\nexit"
    )
    result = subprocess.run(
        [bash, "--noprofile", "--norc", "-s"],
        input=script,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == ["analyze", str(context.file), *context.options]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell session")
@pytest.mark.parametrize("backend", ["powershell.exe", "cmd.exe"])
def test_powershell_script_really_preserves_hostile_argument_boundaries(context, tmp_path, backend):
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not powershell:
        pytest.skip("PowerShell unavailable")
    recorder = tmp_path / "record.py"
    output = tmp_path / "received.json"
    recorder.write_text(
        "import json,sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text(json.dumps(sys.argv[2:]))\n"
    )
    command = (sys.executable, str(recorder), str(output))
    args = terminal.terminal_command(shutil.which(backend), command, context)
    if backend == "cmd.exe":
        args = args.replace(" -NoExit", "")
    else:
        args = [part for part in args if part != "-NoExit"]
    env = os.environ.copy()
    if backend == "cmd.exe":
        env["EGP_CLI_STARTUP"] = terminal.session_script(command, context, windows=True)
    result = subprocess.run(args, capture_output=True, timeout=20, check=False, env=env)
    assert result.returncode == 0, result.stderr
    assert not output.exists(), "Opening a session must not run CLI commands"
    encoded = args.split()[-1].removesuffix('"') if isinstance(args, str) else args[-1]
    script = base64.b64decode(encoded).decode("utf-16le")
    manual = "egp " + " ".join(
        "'" + str(part).replace("'", "''") + "'" for part in ["analyze", str(context.file), *context.options]
    )
    if backend == "cmd.exe":
        env["EGP_CLI_STARTUP"] += "\n" + manual
    else:
        replacement = base64.b64encode((script + "\n" + manual).encode("utf-16le")).decode("ascii")
        args[-1] = args[-1].replace(encoded, replacement)
    result = subprocess.run(args, capture_output=True, timeout=20, check=False, env=env)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == ["analyze", str(context.file), *context.options]


def test_every_displayed_recipe_is_accepted_by_existing_cli(context):
    parser, _ = _parser()
    for args in terminal.example_arguments(context):
        if args == ("--help",):
            continue
        parsed = parser.parse_args(args)
        assert parsed.lang == "fanuc_mill" and parsed.kinematics == "5ax_table_ac"


@pytest.mark.parametrize("format_name", ["dxf", "heidenhain_itnc530"])
def test_displayed_export_recipe_runs_existing_cli_and_preserves_geometry(context, fixture_text, format_name):
    source = fixture_text("milling/fanuc/helical_bore.nc")
    context.file.write_text(source, encoding="utf-8")
    args = list(terminal.example_arguments(context)[2])
    args[1] = str(context.file.parent)
    directory = context.file.parent.with_name(context.file.parent.name + "_export")
    args[args.index("-o") + 1] = str(directory)
    if format_name != "dxf":
        args[args.index("--format") + 1] = "nc"
        args += ["--target-dialect", format_name]
    assert main(args) == 0
    output = directory / (context.file.stem + (".dxf" if format_name == "dxf" else ".h"))
    assert output.is_file() and output.stat().st_size > 0
    if format_name == "dxf":
        import ezdxf  # pylint: disable=import-outside-toplevel

        assert len(ezdxf.readfile(output).modelspace()) > 0
    else:
        result = execute(output.read_text(encoding="utf-8"), "fanuc_mill", source_dialect="heidenhain")
        original = execute(source, "fanuc_mill")
        assert result.ok and result.complete, result.diagnostics
        assert trace_statistics(result)["total_length"] == pytest.approx(trace_statistics(original)["total_length"])


def test_welcome_is_colored_compact_help_and_two_batch_examples(context):
    lines = terminal.welcome_lines(context, windows=True)
    text = "\n".join(line for line, _color in lines)
    logo = Path(__file__).resolve().parents[2] / "app/resources/cli_logo.txt"
    assert logo.read_text(encoding="utf-8").strip() in text
    commands = [line for line, _color in lines if line.startswith("egp ")]
    assert len(commands) == 3 and commands[0] == "egp --help"
    assert commands[1].startswith("egp batch . ") and commands[2].startswith("egp batch-export . ")
    assert str(context.file.parent) not in text
    assert {color for _line, color in lines} == {"Cyan", "Gray", "Yellow", "Green"}


def test_packaged_linux_cleans_only_bundle_runtime_environment(monkeypatch):
    _platform(monkeypatch, "linux", frozen=True, _MEIPASS="/tmp/bundle")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/bundle/lib")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/system/lib")
    monkeypatch.setenv("QT_PLUGIN_PATH", "/tmp/bundle/plugins")
    env = terminal.terminal_environment()
    assert env["LD_LIBRARY_PATH"] == "/system/lib" and "QT_PLUGIN_PATH" not in env
    assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert os.environ["QT_PLUGIN_PATH"] == "/tmp/bundle/plugins"


def test_packaged_linux_without_original_library_path_preserves_system_qt_paths(monkeypatch):
    _platform(monkeypatch, "linux", frozen=True, _MEIPASS="/tmp/bundle")
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/bundle/lib")
    monkeypatch.setenv("QT_PLUGIN_PATH", "/usr/lib/qt6/plugins")
    monkeypatch.setenv("QT_QPA_PLATFORM_PLUGIN_PATH", "/tmp/bundle/platforms")
    monkeypatch.setenv("QML2_IMPORT_PATH", "/usr/lib/qt6/qml")
    env = terminal.terminal_environment()
    assert "LD_LIBRARY_PATH" not in env
    assert "QT_QPA_PLATFORM_PLUGIN_PATH" not in env
    assert env["QT_PLUGIN_PATH"] == "/usr/lib/qt6/plugins"
    assert env["QML2_IMPORT_PATH"] == "/usr/lib/qt6/qml"
    assert os.environ["LD_LIBRARY_PATH"] == "/tmp/bundle/lib"
    assert os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] == "/tmp/bundle/platforms"


@pytest.mark.parametrize("key", ["QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML2_IMPORT_PATH"])
def test_packaged_cli_removes_only_bundle_entries_from_mixed_qt_paths(monkeypatch, tmp_path, key):
    bundle = tmp_path / "bundle"
    sibling = str(tmp_path / "bundle-custom" / "plugins")
    system = str(tmp_path / "system" / "plugins")
    original = os.pathsep.join((str(bundle / "plugins"), sibling, system))
    _platform(monkeypatch, "linux", frozen=True, _MEIPASS=str(bundle))
    monkeypatch.setenv(key, original)
    env = terminal.terminal_environment()
    assert env[key] == os.pathsep.join((sibling, system))
    assert os.environ[key] == original


def test_launch_does_not_wait_for_cli_or_use_shell(context, monkeypatch):
    _platform(monkeypatch, "linux")
    monkeypatch.setattr(terminal, "cli_command", lambda: ("/opt/cli",))
    monkeypatch.setattr(terminal, "terminal_path", lambda _configured: "/usr/bin/xterm")
    monkeypatch.setattr(terminal.shutil, "which", lambda _name: "/bin/bash")
    calls = []
    monkeypatch.setattr(
        terminal.subprocess,
        "Popen",
        lambda args, **kwargs: calls.append((args, kwargs)) or SimpleNamespace(poll=lambda: None),
    )
    monkeypatch.setattr(terminal, "_PROCESSES", [])
    terminal.launch_cli(context)
    assert len(calls) == 1
    assert calls[0][1]["start_new_session"] and calls[0][1]["cwd"] == str(context.file.parent)
    assert not calls[0][1].get("shell")
    monkeypatch.setattr(
        terminal.subprocess, "Popen", lambda *_a, **_kw: (_ for _ in ()).throw(OSError("launch failed"))
    )
    with pytest.raises(terminal.CliLaunchError, match="launch failed"):
        terminal.launch_cli(context)


def test_action_reuses_menu_toolbar_hotkeys_and_icon(window):
    action = window.ui.actionOpenInCli
    assert action in window.ui.menu_File.actions() and action in window.ui.fileToolBar.actions()
    assert window.hotkeyActions["actionOpenInCli"] is action
    assert window.toolbarSettings.commands["actionOpenInCli"][1] is window.ui.fileToolBar
    assert not action.icon().isNull()
    window.toolbarSettings.apply(dict(window.toolbarSettings.selected, actionOpenInCli=False))
    assert action not in window.ui.fileToolBar.actions() and action in window.ui.menu_File.actions()


def test_action_forwards_current_saved_document_settings(window, context, monkeypatch):
    window.curFile = str(context.file)
    window.ui.editor.setModified(False)
    window.fileEncoding = "cp1251"
    window.latheMode = False
    window.rotaryKinematics = "5ax_table_ac"
    window.sinumerik840dSl = False
    window.cliTerminalPath = "my-terminal"
    calls = []
    monkeypatch.setattr(cli_integration, "launch_cli", lambda *args: calls.append(args))
    window.ui.actionOpenInCli.trigger()
    received, configured = calls[0]
    assert received.file == context.file and configured == "my-terminal"
    parser, _ = _parser()
    args = parser.parse_args(["analyze", str(received.file), *received.options])
    assert args.encoding == "cp1251" and args.sinumerik_cycles == "classic"
    assert args.kinematics == "5ax_table_ac" and args.lang == "fanuc_mill"


@pytest.mark.parametrize(
    "answer,saved,launched",
    [
        (QMessageBox.StandardButton.Cancel, True, False),
        (QMessageBox.StandardButton.Save, False, False),
        (QMessageBox.StandardButton.Save, True, True),
    ],
)
def test_unsaved_document_must_save_successfully(window, context, monkeypatch, answer, saved, launched):
    window.curFile = ""
    window.ui.editor.setModified(True)
    monkeypatch.setattr(cli_integration.QMessageBox, "question", lambda *_args: answer)

    def save():
        window.curFile = str(context.file) if saved else ""
        return saved

    monkeypatch.setattr(window, "save", save)
    calls = []
    monkeypatch.setattr(cli_integration, "launch_cli", lambda *args: calls.append(args))
    cli_integration.open_in_cli(window)
    assert bool(calls) == launched


def test_launch_failure_is_reported_by_gui(window, context, monkeypatch):
    window.curFile = str(context.file)
    window.ui.editor.setModified(False)

    def fail(*_args):
        raise terminal.CliLaunchError("CLI missing")

    monkeypatch.setattr(cli_integration, "launch_cli", fail)
    warnings = []
    monkeypatch.setattr(cli_integration.QMessageBox, "warning", lambda *args: warnings.append(args))
    cli_integration.open_in_cli(window)
    assert "CLI missing" in warnings[0][-1]


def test_terminal_setting_persists_and_reset_restores_auto_detection(window):
    dialog = window.optionsDlg
    dialog.load_values()
    dialog.ui.cliTerminalEdit.setText("my-terminal")
    dialog.accept()
    assert window.cliTerminalPath == "my-terminal"
    assert window.settings.value("GENERAL/CLI_TERMINAL") == "my-terminal"
    dialog.load_values()
    assert dialog.ui.cliTerminalEdit.text() == "my-terminal"
    dialog.restore_defaults()
    assert dialog.ui.cliTerminalEdit.text() == ""


def test_deleted_saved_file_is_reported_without_launch(window, tmp_path, monkeypatch):
    window.curFile = str(tmp_path / "missing.nc")
    window.ui.editor.setModified(False)
    calls, warnings = [], []
    monkeypatch.setattr(cli_integration, "launch_cli", lambda *args: calls.append(args))
    monkeypatch.setattr(cli_integration.QMessageBox, "warning", lambda *args: warnings.append(args))
    cli_integration.open_in_cli(window)
    assert not calls and "does not exist" in warnings[0][-1]


def test_source_pythonw_launches_console_python(tmp_path, monkeypatch):
    console = tmp_path / "python.exe"
    console.touch()
    _platform(monkeypatch, "win32", executable=str(tmp_path / "pythonw.exe"))
    assert terminal.cli_command()[0] == str(console)
    console.unlink()
    with pytest.raises(terminal.CliLaunchError, match="console Python is missing"):
        terminal.cli_command()


def test_configured_terminal_expands_environment_and_home_without_shell_arguments(monkeypatch):
    requested = []
    monkeypatch.setenv("EGP_TERMINAL_TEST", "terminal with spaces")
    monkeypatch.setattr(terminal.shutil, "which", lambda value: requested.append(value) or value)
    assert terminal.terminal_path("  $EGP_TERMINAL_TEST  ") == "terminal with spaces"
    terminal.terminal_path("~/terminal")
    assert requested[-1] == os.path.expanduser("~/terminal")


@pytest.mark.parametrize("platform,configured", [("linux", "xterm"), ("win32", "wt.exe")])
def test_missing_shell_reports_error_before_spawning(context, monkeypatch, platform, configured):
    _platform(monkeypatch, platform)
    monkeypatch.setattr(terminal.shutil, "which", lambda _name: None)
    with pytest.raises(terminal.CliLaunchError, match="required"):
        terminal.terminal_command(configured, ("cli",), context)


def test_finished_terminal_processes_are_pruned_without_waiting(context, monkeypatch):
    _platform(monkeypatch, "linux")
    monkeypatch.setattr(terminal, "cli_command", lambda: ("cli",))
    monkeypatch.setattr(terminal, "terminal_path", lambda _configured: "xterm")
    monkeypatch.setattr(terminal.shutil, "which", lambda _name: "/bin/bash")
    finished = SimpleNamespace(poll=lambda: 0)
    active = SimpleNamespace(poll=lambda: None)
    launched = SimpleNamespace(poll=lambda: None)
    processes = [finished, active]
    monkeypatch.setattr(terminal, "_PROCESSES", processes)
    monkeypatch.setattr(terminal.subprocess, "Popen", lambda *_args, **_kwargs: launched)
    terminal.launch_cli(context)
    assert processes == [active, launched]


def test_cli_action_forwards_turning_settings_without_rotary_milling_profile(window, context, monkeypatch):
    window.curFile = str(context.file)
    window.ui.editor.setModified(False)
    window.latheMode = True
    window.latheGcodeSystem = "B"
    window.sinumerik840dSl = True
    window.rotaryKinematics = "5ax_table_ac"
    calls = []
    monkeypatch.setattr(cli_integration, "launch_cli", lambda *args: calls.append(args))
    window.ui.actionOpenInCli.trigger()
    received, _configured = calls[0]
    parser, _ = _parser()
    args = parser.parse_args(["analyze", str(received.file), *received.options])
    assert received.turning
    assert args.lang == "fanuc_turn"
    assert args.lathe_gcode_system == "B" and args.sinumerik_cycles == "sl"
    assert "--kinematics" not in received.options


def test_cancel_save_of_modified_existing_document_preserves_buffer(window, context, monkeypatch):
    window.curFile = str(context.file)
    window.ui.editor.setText("UNSAVED EDIT")
    window.ui.editor.setModified(True)
    original = context.file.read_bytes()
    calls = []
    monkeypatch.setattr(cli_integration.QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Cancel)
    monkeypatch.setattr(window, "save", lambda: calls.append("save"))
    monkeypatch.setattr(cli_integration, "launch_cli", lambda *_args: calls.append("launch"))
    window.ui.actionOpenInCli.trigger()
    assert calls == []
    assert window.ui.editor.text() == "UNSAVED EDIT" and window.ui.editor.isModified()
    assert context.file.read_bytes() == original


@pytest.mark.parametrize("accepted", [False, True])
def test_terminal_browser_cancel_or_accept_keeps_draft_until_options_apply(window, monkeypatch, accepted):
    dialog = window.optionsDlg
    dialog.load_values()
    dialog.ui.cliTerminalEdit.setText("existing-terminal")
    monkeypatch.setattr(
        "app.ui.dialogs.options.QFileDialog.getOpenFileName",
        lambda *_args: ("selected-terminal" if accepted else "", ""),
    )
    dialog.ui.cliTerminalBrowseButton.click()
    assert dialog.ui.cliTerminalEdit.text() == ("selected-terminal" if accepted else "existing-terminal")
    assert window.cliTerminalPath == ""
    dialog.reject()
    dialog.load_values()
    assert dialog.ui.cliTerminalEdit.text() == ""


def test_unsupported_windows_terminal_is_reported(context, monkeypatch):
    _platform(monkeypatch, "win32")
    monkeypatch.setattr(terminal.shutil, "which", lambda _name: "powershell.exe")
    with pytest.raises(terminal.CliLaunchError, match="Supported Windows terminals"):
        terminal.terminal_command("unsupported.exe", ("cli.exe",), context)


def test_nonpackaged_cli_keeps_existing_runtime_environment(monkeypatch):
    _platform(monkeypatch, "linux")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/custom/lib")
    monkeypatch.setenv("QT_PLUGIN_PATH", "/custom/plugins")
    env = terminal.terminal_environment()
    assert env["LD_LIBRARY_PATH"] == "/custom/lib"
    assert env["QT_PLUGIN_PATH"] == "/custom/plugins"
    assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


def test_frozen_windows_success_restores_dll_directory_before_returning(context, tmp_path, monkeypatch):
    import ctypes  # pylint: disable=import-outside-toplevel

    calls = []
    kernel = SimpleNamespace(SetDllDirectoryW=lambda path: calls.append(path))
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(kernel32=kernel), raising=False)
    _platform(monkeypatch, "win32", frozen=True, _MEIPASS=str(tmp_path))
    child = object()
    processes = []
    monkeypatch.setattr(terminal, "_PROCESSES", processes)
    monkeypatch.setattr(terminal, "cli_command", lambda: ("cli.exe",))
    monkeypatch.setattr(terminal, "terminal_path", lambda _configured: "powershell.exe")
    monkeypatch.setattr(terminal, "terminal_command", lambda *_args: ["terminal.exe"])
    monkeypatch.setattr(terminal.subprocess, "CREATE_NEW_CONSOLE", 0x10, raising=False)

    def spawn(args, **kwargs):
        assert calls == [None]
        assert args == ["terminal.exe"] and kwargs["close_fds"] is True
        assert kwargs["creationflags"] == terminal.subprocess.CREATE_NEW_CONSOLE
        return child

    monkeypatch.setattr(terminal.subprocess, "Popen", spawn)
    terminal.launch_cli(context)
    assert processes == [child]
    assert calls == [None, str(tmp_path)]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows frozen DLL search path")
def test_frozen_windows_restores_dll_search_path_even_on_launch_error(context, tmp_path, monkeypatch):
    import ctypes  # pylint: disable=import-outside-toplevel

    calls = []
    kernel = SimpleNamespace(SetDllDirectoryW=lambda path: calls.append(path))
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(kernel32=kernel))
    _platform(monkeypatch, "win32", frozen=True, _MEIPASS=str(tmp_path))
    monkeypatch.setattr(terminal, "cli_command", lambda: ("cli.exe",))
    monkeypatch.setattr(terminal, "terminal_path", lambda _configured: "powershell.exe")
    monkeypatch.setattr(terminal, "_PROCESSES", [])

    def fail(*_args, **kwargs):
        assert kwargs["creationflags"] == subprocess.CREATE_NEW_CONSOLE
        raise OSError("Cannot start")

    monkeypatch.setattr(terminal.subprocess, "Popen", fail)
    with pytest.raises(terminal.CliLaunchError, match="Cannot start"):
        terminal.launch_cli(context)
    assert calls == [None, str(tmp_path)]
