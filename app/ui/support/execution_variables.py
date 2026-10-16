"""Controller-neutral variable snapshots for the execution inspector."""

import re

_NUMBERED_VARIABLE = re.compile(r"(R|Q|QL|QR)(\d+)$")
_FAMILY_ORDER = {"R": 1, "Q": 2, "QL": 3, "QR": 4}


def variable_name(key, dialect="fanuc"):
    name = str(key)
    if name.startswith("#"):
        return name
    if name.isdigit():
        return "#" + name
    return name if dialect in {"sinumerik", "heidenhain"} else f"#<{name}>"


def variable_sort_key(item):
    plain = str(item[0]).removeprefix("#")
    if plain.isdigit():
        return 0, int(plain)
    match = _NUMBERED_VARIABLE.fullmatch(plain)
    if match is not None:
        return _FAMILY_ORDER[match[1]], int(match[2])
    return 5, plain.removeprefix("<").removesuffix(">").casefold()


def step_for_playback(result, movements, playback_value, at_program_end=False):
    """Locate the captured execution, including programs containing only assignments."""
    if result is None or not result.execution_steps:
        return None
    steps = result.execution_steps
    movements = tuple(movements)
    if at_program_end or not movements:
        return steps[-1]
    if playback_value <= 0:
        return None
    playback_index = min(int(playback_value), len(movements)) - 1
    target_motion = movements[playback_index].motion_end - 1
    emitted_end = 0
    for step in steps:
        emitted_end += step.emitted_count
        if step.emitted_count and target_motion < emitted_end:
            return step
    return None


def variables_for_step(step, dialect):
    if step is None:
        return ()
    values = step.variables
    if dialect == "sinumerik":
        # Keep Macro B and Siemens identifiers distinct in mixed ISO/native input.
        values = tuple((variable_name(key), value) for key, value in values)
        values += tuple((f"R{number}", value) for number, value in step.sinumerik_parameters)
        values += step.sinumerik_variables
    return tuple(sorted(values, key=variable_sort_key))


def variables_for_playback(execution_result, playback_movements, playback_value, at_program_end=False):
    step = step_for_playback(execution_result, playback_movements, playback_value, at_program_end)
    dialect = getattr(execution_result, "source_dialect", "fanuc")
    return variables_for_step(step, dialect)
