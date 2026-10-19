"""Launch the existing CLI in an independent, persistent system terminal."""

from __future__ import annotations

import base64
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QFile, QIODevice

import app.resources.files_res  # noqa: F401  # pylint: disable=unused-import  # Registers Qt resources.
from app import get_version


@dataclass(frozen=True)
class CliContext:
    file: Path
    options: tuple[str, ...]
    turning: bool = False


class CliLaunchError(OSError):
    """An external CLI or terminal could not be located or started."""


def cli_command() -> tuple[str, ...]:
    """Never run a frozen GUI executable as if it were the console entrypoint."""
    if getattr(sys, "frozen", False):
        name = "easy_gcode_plot_cli.exe" if sys.platform == "win32" else "easy_gcode_plot_cli"
        sibling = Path(sys.executable).parent / name
        if sibling.is_file():
            return (str(sibling),)
        installed = shutil.which(name)
        if installed:
            return (installed,)
        raise CliLaunchError("CLI not found. Install easy_gcode_plot_cli beside the GUI or add it to PATH.")
    entrypoint = Path(__file__).resolve().parents[3] / "cli_main.py"
    python = Path(sys.executable)
    if python.name.casefold() == "pythonw.exe":
        python = python.with_name("python.exe")
    if not python.is_file() or not entrypoint.is_file():
        raise CliLaunchError("CLI entrypoint or console Python is missing.")
    return str(python), str(entrypoint)


def terminal_path(configured: str = "") -> str:
    if configured.strip():
        path = shutil.which(os.path.expandvars(os.path.expanduser(configured.strip())))
        if path:
            return path
        raise CliLaunchError("The configured terminal is missing or is not executable: " + configured)
    names = (
        ("wt.exe", "pwsh.exe", "powershell.exe", "cmd.exe")
        if sys.platform == "win32"
        else (
            "x-terminal-emulator",
            "gnome-terminal",
            "konsole",
            "xfce4-terminal",
            "mate-terminal",
            "kitty",
            "alacritty",
            "xterm",
            "foot",
            "wezterm",
            "terminator",
            "lxterminal",
        )
    )
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    raise CliLaunchError("No terminal found. Set its executable in Options / General / CLI terminal.")


def _powershell_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def example_arguments(context):
    common = []
    defaults = {"--encoding": "utf-8", "--lathe-gcode-system": "A", "--sinumerik-cycles": "sl"}
    for option, value in zip(context.options[::2], context.options[1::2], strict=True):
        if defaults.get(option) != value:
            common.extend((option, value))
    return (
        ("--help",),
        ("batch", ".", *common, "-o", "../egp-reports"),
        ("batch-export", ".", *common, "--format", "dxf", "-o", "../egp-dxf"),
    )


def _example_text(args, *, windows):
    quote = _powershell_quote if windows else shlex.quote
    return "egp " + " ".join(part if re.fullmatch(r"[A-Za-z0-9_./:-]+", part) else quote(part) for part in args)


def welcome_lines(context, *, windows):
    """Short, colored help screen; examples are text, never startup commands."""
    logo = QFile(":/resource/cli_logo.txt")
    lines = []
    if logo.open(QIODevice.OpenModeFlag.ReadOnly):
        lines.extend((line, "Cyan") for line in bytes(logo.readAll()).decode("utf-8").splitlines())
        logo.close()
    lines += [
        ("Easy G-Code Plot CLI " + get_version(), "Cyan"),
        (QCoreApplication.translate("CliTerminal", "Enter a command to begin. Nothing runs automatically."), "Gray"),
        ("", "Gray"),
    ]
    labels = (
        QCoreApplication.translate("CliTerminal", "Help"),
        QCoreApplication.translate("CliTerminal", "Analyze a folder"),
        QCoreApplication.translate("CliTerminal", "Export a folder to DXF"),
    )
    for label, args in zip(labels, example_arguments(context), strict=True):
        lines += [(label, "Yellow"), (_example_text(args, windows=windows), "Green")]
    lines += [
        (
            QCoreApplication.translate(
                "CliTerminal", "Use egp batch --help or egp batch-export --help for more options."
            ),
            "Gray",
        ),
        ("", "Gray"),
    ]
    return lines


def session_script(command, context, *, windows):
    """Only shell quoting and forwarding: all CNC work remains in app.cli."""
    quote = _powershell_quote if windows else shlex.quote
    invocation = " ".join(quote(part) for part in command)
    welcome = welcome_lines(context, windows=windows)
    if windows:
        lines = [
            "$env:PYINSTALLER_RESET_ENVIRONMENT = '1'",
            "function global:egp { & " + invocation + " @args }",
            "Set-Location -LiteralPath " + quote(context.file.parent),
            "$EGP_FILE = " + quote(context.file),
        ]
        lines += ["Write-Host " + quote(line) + " -ForegroundColor " + color for line, color in welcome]
    else:
        # Bash's command mode never reads NC text as shell source. exec below
        # replaces this shell with an interactive shell, retaining only egp.
        lines = [
            "export PYINSTALLER_RESET_ENVIRONMENT=1",
            "function egp() { " + invocation + ' "$@"; }',
            "export -f egp",
            "export EGP_FILE=" + quote(str(context.file)),
        ]
        colors = {"Cyan": 36, "Gray": 37, "Yellow": 33, "Green": 32}
        lines += ["printf '\\033[" + str(colors[color]) + "m%s\\033[0m\\n' " + quote(line) for line, color in welcome]
        lines.append('exec "$BASH" --noprofile -i')
    return "\n".join(lines)


def terminal_command(terminal, command, context):
    """Build terminal-specific commands without shell=True or interpolating NC text."""
    windows = sys.platform == "win32"
    name = Path(terminal).stem.casefold()
    script = session_script(command, context, windows=windows)
    if windows:
        return _windows_terminal(terminal, name, script)
    bash = shutil.which("bash")
    if not bash:
        raise CliLaunchError("Bash is required for the Linux CLI session.")
    args = [bash, "--noprofile", "--norc", "-c", script]
    flags = {
        "gnome-terminal": ("--",),
        "mate-terminal": ("--",),
        "xfce4-terminal": ("--disable-server", "--execute"),
        "wezterm": ("start", "--"),
        "terminator": ("-x",),
    }.get(name, ("-e",))
    return [terminal, *flags, *args]


def _windows_terminal(terminal, name, script):
    shell = terminal if name in {"pwsh", "powershell"} else (shutil.which("pwsh.exe") or shutil.which("powershell.exe"))
    if not shell:
        raise CliLaunchError("PowerShell is required for the Windows CLI session.")
    if name == "cmd":
        # cmd has an 8191-character limit. Keep the Unicode welcome payload in
        # this child's environment rather than expanding it on the command line.
        script = (
            "try { . ([scriptblock]::Create($env:EGP_CLI_STARTUP)) } "
            "finally { Remove-Item Env:EGP_CLI_STARTUP -ErrorAction SilentlyContinue }"
        )
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    args = [shell, "-NoLogo", "-NoProfile", "-NoExit", "-EncodedCommand", encoded]
    if name == "wt":
        return [terminal, "-w", "new", "new-tab", "--", *args]
    if name == "cmd":
        # Popen would re-escape a nested command passed in an argument list.
        # cmd /s /c needs literal outer quotes, not the C-runtime \" convention.
        invocation = f'"{shell}" ' + subprocess.list2cmdline(args[1:])
        return subprocess.list2cmdline([terminal]) + ' /d /s /v:off /c "' + invocation + '"'
    if name not in {"pwsh", "powershell"}:
        raise CliLaunchError("Supported Windows terminals: Windows Terminal, PowerShell and cmd.")
    return args


def terminal_environment():
    env = os.environ.copy()
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    if getattr(sys, "frozen", False) and sys.platform != "win32":
        if "LD_LIBRARY_PATH_ORIG" in env:
            env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
        else:
            env.pop("LD_LIBRARY_PATH", None)
        bundle = str(getattr(sys, "_MEIPASS", ""))
        for key in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML2_IMPORT_PATH"):
            if bundle and key in env:
                root = Path(bundle)
                paths = [path for path in env[key].split(os.pathsep) if not Path(path).is_relative_to(root)]
                if paths:
                    env[key] = os.pathsep.join(paths)
                else:
                    env.pop(key, None)
    return env


_PROCESSES = []


def launch_cli(context: CliContext, configured_terminal=""):
    """Return immediately; the independent terminal owns execution and lifetime."""
    command = cli_command()
    terminal = terminal_path(configured_terminal)
    args = terminal_command(terminal, command, context)
    kwargs = {"cwd": str(context.file.parent), "env": terminal_environment(), "close_fds": True}
    if sys.platform == "win32":
        if Path(terminal).stem.casefold() == "cmd":
            kwargs["env"]["EGP_CLI_STARTUP"] = session_script(command, context, windows=True)
        kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW if Path(terminal).stem.casefold() == "wt" else subprocess.CREATE_NEW_CONSOLE
        )
    else:
        kwargs["start_new_session"] = True
    _PROCESSES[:] = [process for process in _PROCESSES if process.poll() is None]
    try:
        process = _spawn(args, kwargs)
    except OSError as exc:
        raise CliLaunchError(str(exc)) from exc
    _PROCESSES.append(process)


def _spawn(args, kwargs):
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return subprocess.Popen(args, **kwargs)
    # PyInstaller's DLL directory must not contaminate external system tools.
    import ctypes  # pylint: disable=import-outside-toplevel

    kernel = ctypes.windll.kernel32
    kernel.SetDllDirectoryW(None)
    try:
        return subprocess.Popen(args, **kwargs)
    finally:
        kernel.SetDllDirectoryW(getattr(sys, "_MEIPASS", None))
