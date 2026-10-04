"""Metadata preprocessing errors retain their original diagnostic."""

from app.gcode.kernel import execute
from app.gcode.kernel.api import engine
from app.gcode.kernel.api.resources import SemanticError


def test_failure_before_geometry_iteration_preserves_original_exception(monkeypatch):
    def failure(_steps):
        raise SemanticError("METADATA_FAILURE", "threading metadata failed", "unsupported")

    monkeypatch.setattr(engine, "_threading_step_flags", failure)
    result = execute("G0 X20 Z0\nG1 X30 Z-5 F100\nM30", "fanuc_turn")
    assert not result.ok and not result.complete and not result.motions
    assert any(d.code == "METADATA_FAILURE" and d.message == "threading metadata failed" for d in result.diagnostics)
    assert not any("step_index" in d.message for d in result.diagnostics)
