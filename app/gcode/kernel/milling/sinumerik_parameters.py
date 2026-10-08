"""Bounded Siemens scalar expressions and variables, independent of Macro B."""

import math

from ..api.resources import SemanticError
from ..frontend.sinumerik_expression import compile_expression, evaluate_expression


def parameter_value(expression, parameters, variables=None, tree=None):
    value = evaluate_expression(compile_expression(expression) if tree is None else tree, parameters, variables)
    if not math.isfinite(value):
        raise SemanticError("INVALID_SINUMERIK_PARAMETER", "Siemens parameter must be finite", "unsupported")
    return value


def compile_variables(syntax, state):
    """Validate all declaration/assignment effects before committing the block."""
    values = dict(state.siemens_variables)
    trees = dict(syntax.scalar_expressions)
    for name in syntax.real_declarations:
        if name in values:
            raise SemanticError("DUPLICATE_SINUMERIK_VARIABLE", f"{name} is already declared", "unsupported")
        values[name] = 0.0
    for name, expression in syntax.named_assignments:
        if name not in values:
            raise SemanticError("UNDEFINED_SINUMERIK_VARIABLE", f"{name} is not declared", "unsupported")
        values[name] = parameter_value(expression, state.siemens_parameters, values, trees.get(expression))
    return values
