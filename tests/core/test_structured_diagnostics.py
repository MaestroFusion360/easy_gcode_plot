"""Diagnostic identity and location must not depend on English message wording."""

from app.gcode.kernel.api.resources import ExecutionError, SemanticError
from app.gcode.kernel.runtime.diagnostics import diagnostic_from_exception


def test_structured_evidence_wins_over_incidental_message_words():
    error = ExecutionError("FLOW_TARGET_MISSING", "M98 at line 999", line=7, raw="GOTO100")
    diagnostic = diagnostic_from_exception(error, None)
    assert diagnostic.code == "FLOW_TARGET_MISSING"
    assert diagnostic.line == 7
    assert diagnostic.raw == "GOTO100"
    assert diagnostic.message == "M98 at line 999"
    assert diagnostic.status == "malformed"


def test_wrapped_semantic_error_preserves_structured_evidence():
    cause = SemanticError("UNSUPPORTED_G53_MOTION", "Controller restriction", "unsupported", line=3, raw="G53 G2")
    error = ValueError("Execution stopped")
    error.__cause__ = cause
    diagnostic = diagnostic_from_exception(error, None)
    assert diagnostic.code == cause.code
    assert diagnostic.status == "unsupported"
    assert diagnostic.line == 3
    assert diagnostic.raw == "G53 G2"
    assert diagnostic.message == "Execution stopped"
