"""Shared native turning cycle argument validation, without cycle dispatch."""

from ..milling.sinumerik_parameters import parameter_value
from ..resources import SemanticError
from .sinumerik_state import unsupported


def arguments(state, syntax, minimum, maximum):
    if not minimum <= len(syntax.cycle_args) <= maximum:
        unsupported(
            f"CYCLE{syntax.cycle_code} expects {minimum}..{maximum} positional arguments", "UNSUPPORTED_SINUMERIK_CYCLE"
        )
    trees = dict(syntax.scalar_expressions)
    return tuple(
        parameter_value(value, state.siemens_parameters, state.siemens_variables, trees.get(value)) if value else 0.0
        for value in syntax.cycle_args
    ) + (0.0,) * (maximum - len(syntax.cycle_args))


def positive(*values):
    if any(value <= 0 for value in values):
        raise SemanticError("INVALID_SINUMERIK_CYCLE", "Cycle dimensions, feeds and pass counts must be positive")


def nonnegative(*values):
    if any(value < 0 for value in values):
        raise SemanticError("INVALID_SINUMERIK_CYCLE", "Cycle distances and allowances must be nonnegative")


def integer(value, minimum, maximum, name):
    if not value.is_integer() or not minimum <= value <= maximum:
        raise SemanticError("INVALID_SINUMERIK_CYCLE", f"{name} must be an integer within {minimum}..{maximum}")
    return int(value)
