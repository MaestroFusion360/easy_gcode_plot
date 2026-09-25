"""Shared program setup and CNC execution for the GUI and CLI."""

from copy import deepcopy

from app.gcode.kernel import execute
from app.tools.setup import refresh_setup


def execute_program(
    source,
    *,
    language,
    current_tools=None,
    previous_inference=None,
    correction_enabled=True,
    default_unit_scale=1.0,
    cancelled=None,
    **kernel_options,
):
    """Refresh temporary program tools, then execute the authoritative kernel."""
    turning = language == "fanuc_turn"
    tools = deepcopy(current_tools or {})
    inferred = refresh_setup(
        source,
        tools,
        previous_inference or {},
        turning=turning,
        default_unit_scale=default_unit_scale,
        cancelled=cancelled,
    )
    kernel_tools = deepcopy(tools) if correction_enabled else {}
    result = execute(
        source,
        language=language,
        default_unit_scale=default_unit_scale,
        cancelled=cancelled,
        tools=kernel_tools if turning else {},
        milling_tools=kernel_tools if not turning else {},
        **kernel_options,
    )
    return result, tools, inferred
