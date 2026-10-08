"""Native AST loop indexing and PC transitions inside the milling kernel."""

from ..api.resources import SemanticError, checkpoint
from ..frontend.ast import SinumerikFlowAstNode
from ..frontend.sinumerik_expression import evaluate_expression


def build_native_loop_maps(program):
    """Pair nested WHILE/ENDWHILE nodes by stack, rejecting malformed flow."""
    stack, pairs, native_mode = [], {}, True
    for position, node in enumerate(program.ast.nodes):
        checkpoint()
        switch = next(
            (word.int_code for word in node.words if word.letter == "G" and word.int_code in (290, 291)), None
        )
        if switch is not None:
            native_mode = switch == 290
        if not native_mode:
            continue
        if node.native_syntax is not None and node.native_syntax.kind == "invalid_expression":
            raise SemanticError(
                "INVALID_SINUMERIK_EXPRESSION", f"{node.native_syntax.syntax_error} at line {node.block_index + 1}"
            )
        if not isinstance(node, SinumerikFlowAstNode):
            continue
        if node.native_syntax.kind == "while":
            stack.append(position)
        elif node.native_syntax.kind == "endwhile":
            if not stack:
                raise SemanticError("INVALID_SINUMERIK_FLOW", f"Unmatched ENDWHILE at line {node.block_index + 1}")
            start = stack.pop()
            pairs[start], pairs[position] = position, start
    if stack:
        raise SemanticError("INVALID_SINUMERIK_FLOW", f"Missing ENDWHILE at line {program.blocks[stack[-1]].index + 1}")
    return pairs


def native_flow_destination(node, pc, program, state, pairs):
    syntax = node.native_syntax
    checkpoint()
    if syntax.kind == "invalid_flow":
        raise SemanticError("UNSUPPORTED_SINUMERIK_FLOW", syntax.syntax_error, "unsupported")
    if syntax.kind == "endwhile":
        checkpoint("macro_iterations")
        return pairs[pc]
    if syntax.kind == "while":
        value = evaluate_expression(syntax.flow_condition, state.siemens_parameters, state.siemens_variables)
        return pc + 1 if abs(value) > 1e-12 else pairs[pc] + 1
    target = program.ast.nlabel_to_index.get(syntax.flow_target)
    if target is None:
        raise SemanticError("FLOW_TARGET_MISSING", f"Missing native GOTO target N{syntax.flow_target}")
    if sum(block.nlabel == syntax.flow_target for block in program.blocks) != 1:
        raise SemanticError("INVALID_SINUMERIK_FLOW", "Duplicate native GOTO target label")
    if syntax.kind == "if_goto":
        value = evaluate_expression(syntax.flow_condition, state.siemens_parameters, state.siemens_variables)
        if abs(value) <= 1e-12:
            return pc + 1
    checkpoint("macro_iterations")
    return target
