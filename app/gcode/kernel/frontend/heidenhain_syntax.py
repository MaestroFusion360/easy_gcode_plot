"""Native immutable Klartext facts shared by parsed blocks and their AST."""

from __future__ import annotations

from dataclasses import dataclass

from .heidenhain_expression import HeidenhainExpression


@dataclass(frozen=True, slots=True)
class HeidenhainWord:
    address: str
    source: str
    column: int
    expression: HeidenhainExpression | None = None


@dataclass(frozen=True, slots=True)
class HeidenhainCycleParameter:
    name: str
    expression: HeidenhainExpression
    block_index: int
    column: int


@dataclass(frozen=True, slots=True)
class HeidenhainMachineFunction:
    code: HeidenhainExpression
    column: int
    parameters: tuple[HeidenhainWord, ...] = ()


@dataclass(frozen=True, slots=True)
class HeidenhainSyntax:
    kind: str
    command: str
    words: tuple[HeidenhainWord, ...] = ()
    comment: str | None = None
    continued: bool = False
    program_name: str | None = None
    units: str | None = None
    tool: HeidenhainExpression | str | None = None
    spindle_axis: str | None = None
    label: int | str | None = None
    label_expression: HeidenhainExpression | None = None
    repeat: HeidenhainExpression | None = None
    fn_code: int | None = None
    assignment: tuple[str, HeidenhainExpression] | None = None
    condition: HeidenhainExpression | None = None
    cycle_code: int | None = None
    cycle_subcode: int | None = None
    cycle_name: str | None = None
    cycle_definition_index: int | None = None
    cycle_parameters: tuple[HeidenhainCycleParameter, ...] = ()
    machine_functions: tuple[HeidenhainMachineFunction, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def positioning_words(self):
        """Exclude separately scoped M-function parameters from motion controls."""
        parameters = {word.column for function in self.machine_functions for word in function.parameters}
        return tuple(word for word in self.words if word.column not in parameters)

    def word(self, address):
        """Return the original typed address without evaluating its expression."""
        return next((word for word in self.words if word.address == address.upper()), None)
