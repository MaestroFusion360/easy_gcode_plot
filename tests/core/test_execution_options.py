"""Contract tests for the public execution option channel.

A misspelled or renamed option used to reach the generic exception handler and
surface as an ``EXECUTION_ERROR`` diagnostic on a valid NC program.  Option
names are now validated before any NC work starts, so call-site mistakes fail
loudly and stay out of the user's diagnostic list.
"""

import pytest

from app.gcode.execution.program import execute_program
from app.gcode.kernel.api.engine import execute

PROGRAM = "G0 X10 Z5\nG1 X0 F100"


def test_unknown_execution_option_is_rejected_before_execution():
    with pytest.raises(TypeError, match="unexpected execution option"):
        execute(PROGRAM, "fanuc_turn", milling_correction_enabld=False)


def test_internal_geometry_tolerance_cannot_be_forwarded_twice():
    with pytest.raises(TypeError, match="geometry_tolerance"):
        execute(PROGRAM, "fanuc_turn", geometry_tolerance=0.01)


def test_message_names_every_unknown_option():
    with pytest.raises(TypeError) as raised:
        execute(PROGRAM, "fanuc_turn", arc_tolerence=0.01, bogus=True)

    message = str(raised.value)
    assert "arc_tolerence" in message and "bogus" in message


def test_unknown_option_is_rejected_at_the_application_seam():
    with pytest.raises(TypeError, match="unexpected execution option"):
        execute_program(PROGRAM, language="fanuc_turn", arc_tolerence=0.01)


def test_documented_options_still_reach_the_implementation():
    result = execute(
        PROGRAM,
        "fanuc_turn",
        autodetect_arc_type=True,
        tool_resolver=None,
        turning_correction_enabled=True,
    )

    assert result.ok, result.diagnostics
    assert len(result.motions) == 2
