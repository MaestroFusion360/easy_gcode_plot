"""Mandatory batch-export semantic regression gate for the four conversion scenarios.

Each scenario mirrors a shipped conversion script (``scripts/ps1/batch`` and
``scripts/sh/batch``) and runs the real directory export API used by
``batch-export``. Every program that exported successfully is re-executed and
compared with the source execution using the strict per-motion trajectory
signature from ``tests/export_signatures.py``.

Release criterion
-----------------
* Each scenario completes with a known status category (CLEAN / WARNINGS /
  UNSUPPORTED / ERRORS) and a non-empty file set.
* Every exported program must re-execute and reproduce the same ordered logical
  motions (type, plane, feed mode, start/end position, feed and resolved arc
  geometry). A conversion that cannot preserve the trajectory must fail closed as
  UNSUPPORTED instead of exporting; there is no allow-list.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from export_signatures import motion_traces_match

from app.gcode.batch_export import export_directory
from app.gcode.export_file import ExportRequest
from app.gcode.kernel import execute
from app.gcode.kernel.frontend.io import read_nc_text
from app.gcode.program_execution import execute_program
from app.gcode.source_mode import source_dialect_for_path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

# (root, source_language, target_dialect, replay_language, replay_dialect,
#  source_lathe_system, replay_lathe_system, extensions)
SCENARIOS = (
    ("milling/fanuc", "fanuc_mill", "sinumerik_iso", "fanuc_mill", "sinumerik", None, None, (".nc",)),
    ("milling/fanuc", "fanuc_mill", "sinumerik_840d", "fanuc_mill", "sinumerik", None, None, (".nc",)),
    ("milling/sinumerik", "fanuc_mill", "fanuc_mill", "fanuc_mill", "fanuc", None, None, (".mpf",)),
    ("turning", "fanuc_turn", "fanuc_lathe_b", "fanuc_turn", "fanuc", "A", "B", (".nc", ".NC")),
)


@pytest.mark.parametrize(
    "scenario",
    SCENARIOS,
    ids=[f"{root}-{target}" for root, _l, target, *_rest in SCENARIOS],
)
def test_batch_export_preserves_motion_traces(scenario, tmp_path):
    (
        relative_root,
        language,
        target,
        replay_language,
        replay_dialect,
        source_system,
        replay_system,
        extensions,
    ) = scenario
    root = FIXTURES / relative_root
    request = ExportRequest(
        language=language,
        target_dialect=target,
        mode="expanded",
        lathe_gcode_system=source_system or "A",
    )

    report = export_directory(root, tmp_path / target, request, extensions=extensions)

    assert report["status"] in {"CLEAN", "WARNINGS", "UNSUPPORTED", "ERRORS"}
    assert report["summary"]["files_total"] > 0

    verified = 0
    for item in report["files"]:
        if item["status"] not in {"EXPORTED", "WARNINGS"}:
            continue
        input_path = Path(item["input_path"])
        source = read_nc_text(input_path, encoding="utf-8")
        original, _tools, _inferred = execute_program(
            source,
            language=language,
            lathe_gcode_system=source_system or "A",
            autodetect_arc_type=True,
            source_dialect=source_dialect_for_path(input_path, source),
        )
        generated = read_nc_text(Path(item["output_path"]), encoding="utf-8")
        replay_options = {"lathe_gcode_system": replay_system} if replay_system else {}
        replay = execute(
            generated,
            language=replay_language,
            source_dialect=replay_dialect,
            autodetect_arc_type=True,
            **replay_options,
        )

        assert replay.ok and replay.complete, (
            f"{relative_root} -> {target}: {input_path.name} did not re-execute: "
            f"{[diagnostic.code for diagnostic in replay.diagnostics]}"
        )
        assert motion_traces_match(original, replay), (
            f"{relative_root} -> {target}: semantic trajectory changed for {input_path.name} "
            f"({len(original.motions)} -> {len(replay.motions)} motions)"
        )
        verified += 1

    assert verified > 0, f"{relative_root} -> {target}: no exported program was verified"
