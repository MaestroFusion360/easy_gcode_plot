"""Check that Qt UI modules and translation catalogs match their sources."""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "app/ui/generated"
PLACEHOLDER = re.compile(r"%(?:L?\d+|n)")
RESOURCE_FIELDS = ("qt_resource_data", "qt_resource_name", "qt_resource_struct")
RESOURCE_STRUCT_V3_RECORD_SIZE = 22
RESOURCE_STRUCT_V3_TIMESTAMP_OFFSET = 14
RESOURCE_STRUCT_V3_TIMESTAMP_SIZE = 8


def _resource_signature(source: Path) -> tuple[int, bytes, bytes, bytes]:
    """Return resource contents while ignoring RCC v3 file timestamps."""
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    values: dict[str, bytes] = {}
    version = None

    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        if name in RESOURCE_FIELDS:
            value = ast.literal_eval(node.value)
            if not isinstance(value, bytes):
                raise ValueError(f"{source}: {name} is not bytes")
            values[name] = value

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "qRegisterResourceData"
            and node.args
        ):
            candidate = ast.literal_eval(node.args[0])
            if isinstance(candidate, int):
                version = candidate
                break

    missing = [name for name in RESOURCE_FIELDS if name not in values]
    if missing or version is None:
        raise ValueError(f"{source}: invalid generated Qt resource module")

    resource_struct = bytearray(values["qt_resource_struct"])
    if version == 3:
        if len(resource_struct) % RESOURCE_STRUCT_V3_RECORD_SIZE:
            raise ValueError(f"{source}: invalid Qt resource v3 structure length")
        for offset in range(0, len(resource_struct), RESOURCE_STRUCT_V3_RECORD_SIZE):
            timestamp = offset + RESOURCE_STRUCT_V3_TIMESTAMP_OFFSET
            resource_struct[timestamp : timestamp + RESOURCE_STRUCT_V3_TIMESTAMP_SIZE] = b"\0" * (
                RESOURCE_STRUCT_V3_TIMESTAMP_SIZE
            )

    return version, values["qt_resource_data"], values["qt_resource_name"], bytes(resource_struct)


def check_translations(output: Path) -> list[str]:
    errors = []
    catalogs = sorted((ROOT / "translations").glob("*.ts"))
    if not catalogs:
        return ["No translation catalogs found"]
    for source in catalogs:
        try:
            tree = ET.parse(source)
        except ET.ParseError as exc:
            errors.append(f"{source}: invalid XML: {exc}")
            continue
        for message in tree.findall(".//message"):
            translation = message.find("translation")
            if (
                translation is None
                or translation.get("type") == "unfinished"
                or not "".join(translation.itertext()).strip()
            ):
                errors.append(f"{source}: missing translation for {message.findtext('source')!r}")
                continue
            original = sorted(PLACEHOLDER.findall(message.findtext("source") or ""))
            translated = sorted(PLACEHOLDER.findall("".join(translation.itertext())))
            if original != translated:
                errors.append(f"{source}: placeholder mismatch for {message.findtext('source')!r}")
        result = subprocess.run(
            [
                "uv",
                "run",
                "--locked",
                "--group",
                "dev",
                "pyside6-lrelease",
                str(source),
                "-qm",
                str(output / f"{source.stem}.qm"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            errors.append(f"{source}: lrelease failed: {result.stderr.strip()}")
        else:
            generated = output / f"{source.stem}.qm"
            committed = ROOT / "app/resources/translations" / generated.name
            if not committed.is_file() or generated.read_bytes() != committed.read_bytes():
                errors.append(f"{committed}: differs from {source}; regenerate translations")
    return errors


def check_ui_modules(output: Path) -> list[str]:
    if sys.platform == "win32":
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts/ps1/generate-ui.ps1"),
            "-ProjectRoot",
            str(ROOT),
            "-OutputDirectory",
            str(output),
        ]
    else:
        command = [
            "bash",
            str(ROOT / "scripts/sh/generate-ui.sh"),
            "--project-root",
            str(ROOT),
            "--output-directory",
            str(output),
        ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode:
        return [f"UI generation failed: {result.stderr.strip() or result.stdout.strip()}"]
    errors = []
    for source in sorted(UI_ROOT.rglob("*.ui")):
        name = "main_ui.py" if source.stem == "main_window" else f"{source.stem}.py"
        relative = source.relative_to(UI_ROOT).with_name(name)
        generated = output / relative
        committed = UI_ROOT / relative
        if not committed.is_file() or generated.read_text(encoding="utf-8") != committed.read_text(encoding="utf-8"):
            errors.append(f"{committed}: differs from {source}; run the UI generator")
    return errors


def check_resources(output: Path) -> list[str]:
    if sys.platform == "win32":
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts/ps1/generate-resources.ps1"),
            "-ProjectRoot",
            str(ROOT),
            "-OutputDirectory",
            str(output),
        ]
    else:
        command = [
            "bash",
            str(ROOT / "scripts/sh/generate-resources.sh"),
            "--project-root",
            str(ROOT),
            "--output-directory",
            str(output),
        ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode:
        return [f"Qt resource generation failed: {result.stderr.strip() or result.stdout.strip()}"]
    generated = output / "files_res.py"
    committed = ROOT / "app/resources/files_res.py"
    if not committed.is_file():
        return [f"{committed}: differs from files_res.qrc or embedded files; regenerate resources"]
    try:
        matches = _resource_signature(generated) == _resource_signature(committed)
    except (SyntaxError, ValueError):
        matches = False
    if not matches:
        return [f"{committed}: differs from files_res.qrc or embedded files; regenerate resources"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-resources", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="easy-gcode-plot-qt-check-") as directory:
        temporary = Path(directory)
        errors = [
            *check_translations(temporary),
            *check_ui_modules(temporary / "ui"),
        ]
        if args.check_resources:
            errors.extend(check_resources(temporary / "resources"))
    for error in errors:
        print(error)
    if errors:
        return 1
    print("Qt translations and generated UI modules are up to date")
    if args.check_resources:
        print("Qt resources are up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
