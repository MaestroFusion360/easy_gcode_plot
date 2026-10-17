"""Native AST loop indexing and PC transitions inside the milling kernel."""

from ..frontend.ast import SinumerikFlowAstNode
from ..frontend.sinumerik_expression import evaluate_expression
from ..resources import SemanticError, checkpoint


def build_native_repeat_maps(program):
    """Index standalone-label REPEAT sections; ENDLABEL is reusable, not unique."""
    labels, ends, repeats = {}, [], []
    for pc, node in enumerate(program.ast.nodes):
        checkpoint()
        syntax = node.native_syntax
        if syntax is None:
            continue
        if syntax.kind == "label":
            if syntax.flow_label in labels:
                raise SemanticError(
                    "INVALID_SINUMERIK_FLOW", "Duplicate native section label", line=node.block_index + 1, raw=node.raw
                )
            labels[syntax.flow_label] = pc
        elif syntax.kind == "endlabel":
            ends.append(pc)
        elif syntax.kind == "repeat":
            repeats.append(pc)
    return {pc: _repeat_range(program.ast.nodes[pc], pc, labels, ends) for pc in repeats}


def _repeat_range(node, pc, labels, ends):
    start = labels.get(node.native_syntax.flow_label)
    if start is None:
        raise SemanticError(
            "FLOW_TARGET_MISSING", "Missing native REPEAT label", line=node.block_index + 1, raw=node.raw
        )
    end = next((end for end in ends if end > start), pc)
    if start < pc:
        end = min(end, pc)
    elif end == pc:
        raise SemanticError(
            "INVALID_SINUMERIK_FLOW", "Forward REPEAT requires ENDLABEL", line=node.block_index + 1, raw=node.raw
        )
    return start, end


def _repeat_destination(node, pc, state):
    stack, ranges = state.native_repeat_stack, state.native_repeat_ranges
    if stack and ranges[stack[-1][0]][1] == pc:
        caller, remaining = stack.pop()
        if remaining > 1:
            stack.append((caller, remaining - 1))
            checkpoint("macro_iterations")
            return ranges[caller][0]
        return caller + 1
    if node.native_syntax.kind != "repeat":
        return pc + 1
    syntax = node.native_syntax
    count = evaluate_expression(syntax.flow_condition, state.siemens_parameters, state.siemens_variables)
    if not count.is_integer() or count < 0:
        raise SemanticError("INVALID_SINUMERIK_FLOW", "REPEAT P must be a nonnegative integer")
    if count == 0:
        return pc + 1
    stack.append((pc, int(count)))
    checkpoint("macro_iterations")
    return ranges[pc][0]


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
    if syntax.kind in ("label", "endlabel", "repeat"):
        return _repeat_destination(node, pc, state)
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
