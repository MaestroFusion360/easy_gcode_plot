"""Shared program setup and CNC execution for the GUI and CLI."""

from copy import deepcopy

from app.gcode.kernel import execute
from app.gcode.kernel.api.resources import SemanticError
from app.tools.setup import refresh_setup


def execute_program(
    source,
    *,
    language,
    current_tools=None,
    previous_inference=None,
    library_tools=None,
    correction_enabled=True,
    default_unit_scale=1.0,
    cancelled=None,
    **kernel_options,
):
    """Resolve temporary tools from the kernel's single parsed Program, then execute."""
    turning = language == "fanuc_turn"
    tools = deepcopy(current_tools or {})
    inferred = {}

    def resolve_tools(program):
        nonlocal inferred
        try:
            inferred = refresh_setup(
                source,
                tools,
                previous_inference or {},
                turning=turning,
                default_unit_scale=default_unit_scale,
                cancelled=cancelled,
                library_tools=library_tools,
                source_dialect=kernel_options.get("source_dialect", "fanuc"),
                program=program,
            )
        except InterruptedError as exc:
            raise SemanticError("EXECUTION_CANCELLED", "Tool discovery cancelled", "resource_limit") from exc
        return deepcopy(tools) if correction_enabled else {}

    result = execute(
        source,
        language=language,
        default_unit_scale=default_unit_scale,
        cancelled=cancelled,
        tool_resolver=resolve_tools,
        **kernel_options,
    )
    return result, tools, inferred
