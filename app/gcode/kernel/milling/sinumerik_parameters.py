"""Minimal Siemens numeric literals/R references, independent of Macro B."""

import math

from ..api.resources import SemanticError


def parameter_value(expression, parameters, variables=None):
    if expression.startswith("_"):
        name = expression.upper()
        if variables is None or name not in variables:
            raise SemanticError("UNDEFINED_SINUMERIK_VARIABLE", f"{name} is not declared", "unsupported")
        value = variables[name]
        if value is None:
            raise SemanticError("UNINITIALIZED_SINUMERIK_VARIABLE", f"Assign {name} before use", "unsupported")
    elif expression.upper().startswith("R"):
        index = int(expression[1:])
        if index not in parameters:
            raise SemanticError("UNDEFINED_SINUMERIK_PARAMETER", f"R{index} is not assigned", "unsupported")
        value = parameters[index]
    else:
        value = float(expression)
    if not math.isfinite(value):
        raise SemanticError("INVALID_SINUMERIK_PARAMETER", "Siemens parameter must be finite", "unsupported")
    return value


def compile_variables(syntax, state):
    """Validate all declaration/assignment effects before committing the block."""
    values = dict(state.siemens_variables)
    for name in syntax.real_declarations:
        if name in values:
            raise SemanticError("DUPLICATE_SINUMERIK_VARIABLE", f"{name} is already declared", "unsupported")
        values[name] = 0.0
    for name, expression in syntax.named_assignments:
        if name not in values:
            raise SemanticError("UNDEFINED_SINUMERIK_VARIABLE", f"{name} is not declared", "unsupported")
        values[name] = parameter_value(expression, state.siemens_parameters, values)
    return values
