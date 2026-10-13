"""Report the kinematics definition captured by the executed kernel result."""

import json

from app.gcode.kernel import ExecutionResult


def kinematics_report_fields(result: ExecutionResult) -> dict[str, object]:
    return {
        "kinematics_definition": json.loads(result.kinematics_definition) if result.kinematics_definition else None,
        "kinematics_fingerprint": result.kinematics_fingerprint,
    }
