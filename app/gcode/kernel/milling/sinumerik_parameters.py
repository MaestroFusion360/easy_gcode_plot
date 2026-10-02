"""Minimal Siemens numeric literals/R references, independent of Macro B."""

import math

from ..api.resources import SemanticError


def parameter_value(expression, parameters):
    if expression.upper().startswith("R"):
        index = int(expression[1:])
        if index not in parameters:
            raise SemanticError("UNDEFINED_SINUMERIK_PARAMETER", f"R{index} is not assigned", "unsupported")
        value = parameters[index]
    else:
        value = float(expression)
    if not math.isfinite(value):
        raise SemanticError("INVALID_SINUMERIK_PARAMETER", "Siemens parameter must be finite", "unsupported")
    return value
