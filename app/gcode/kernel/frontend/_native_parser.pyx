# cython: language_level=3, boundscheck=False, wraparound=False, initializedcheck=False
"""Cython frontend for ordinary FANUC blocks.

The whole source crosses the extension boundary once.  Lines containing Macro B
or comments use the authoritative Python fallback; ordinary numeric ISO blocks
are tokenized and materialized here in one compiled loop.
"""

from cpython.bytes cimport PyBytes_AS_STRING, PyBytes_GET_SIZE

from .ast import (
    AstNode,
    AstWord,
    ControlAstNode,
    CycleAstNode,
    MetaAstNode,
    MotionAstNode,
    ProgramAst,
    build_ast_node,
)
from .lang import WordToken
from .model import Block, CycleNode, ModalSnapshot, MotionNode, Program


cdef inline bint _alpha(unsigned char ch) noexcept:
    return (65 <= ch <= 90) or (97 <= ch <= 122)


cdef inline bint _expr_start(unsigned char ch) noexcept:
    return ch == 43 or ch == 45 or ch == 46 or ch == 35 or ch == 91 or 48 <= ch <= 57


cdef object _literal_int(bytes value):
    cdef const unsigned char* data = <const unsigned char*>PyBytes_AS_STRING(value)
    cdef Py_ssize_t size = PyBytes_GET_SIZE(value)
    cdef Py_ssize_t pos = 0
    cdef long long number = 0
    cdef int sign = 1
    cdef bint digit = False

    if size == 0:
        return None
    if data[pos] == 43 or data[pos] == 45:
        if data[pos] == 45:
            sign = -1
        pos += 1
    while pos < size and 48 <= data[pos] <= 57:
        digit = True
        number = number * 10 + data[pos] - 48
        pos += 1
    if not digit:
        return None
    if pos < size and data[pos] == 46:
        pos += 1
        if pos == size:
            return sign * number
        while pos < size and data[pos] == 48:
            pos += 1
    if pos != size:
        return None
    return sign * number


cdef bytes _label_prefix(bytes value):
    cdef const unsigned char* data = <const unsigned char*>PyBytes_AS_STRING(value)
    cdef Py_ssize_t size = PyBytes_GET_SIZE(value)
    cdef Py_ssize_t pos = 0
    cdef Py_ssize_t integer_end

    if pos < size and (data[pos] == 43 or data[pos] == 45):
        pos += 1
    while pos < size and 48 <= data[pos] <= 57:
        pos += 1
    integer_end = pos
    if pos < size and data[pos] == 46:
        pos += 1
        if pos < size and data[pos] == 48:
            while pos < size and data[pos] == 48:
                pos += 1
            return value[:pos]
    return value[:integer_end]


cdef bint _requires_fallback(bytes clean):
    cdef const unsigned char* data = <const unsigned char*>PyBytes_AS_STRING(clean)
    cdef Py_ssize_t size = PyBytes_GET_SIZE(clean)
    cdef Py_ssize_t pos
    cdef unsigned char ch
    if b"GOTO" in clean or b"WHILE" in clean or b"END" in clean:
        return True
    for pos in range(size):
        ch = data[pos]
        if ch == 35 or ch == 91 or ch == 93 or ch == 40 or ch == 41 or ch == 59:
            return True
        if ch >= 128:
            return True
        if 97 <= ch <= 122:
            return True
    return False


cdef tuple _native_block(Py_ssize_t index, str raw, bytes clean):
    cdef const unsigned char* data = <const unsigned char*>PyBytes_AS_STRING(clean)
    cdef Py_ssize_t size = PyBytes_GET_SIZE(clean)
    cdef Py_ssize_t pos = 0
    cdef Py_ssize_t depth = 0
    cdef Py_ssize_t probe
    cdef Py_ssize_t word_index
    cdef Py_ssize_t start
    cdef Py_ssize_t finish
    cdef Py_ssize_t start_count = 0
    cdef Py_ssize_t starts[128]
    cdef unsigned char ch
    cdef bint optional_skip = False
    cdef list tokens = []
    cdef list ast_words = []
    cdef list g_codes = []
    cdef list m_codes = []
    cdef object letter
    cdef bytes expr_bytes
    cdef object expr
    cdef object int_code
    cdef object token
    cdef object last_g_expr = None
    cdef object motion_expr = None
    cdef object motion_code = None
    cdef object cycle_expr = None
    cdef object cycle_code = None
    cdef object x_expr = None
    cdef object z_expr = None
    cdef object u_expr = None
    cdef object w_expr = None
    cdef object i_expr = None
    cdef object k_expr = None
    cdef object r_expr = None
    cdef object f_expr = None
    cdef object a_expr = None
    cdef object c_expr = None
    cdef bint g65_call = False
    cdef object nlabel = None
    cdef object olabel = None
    cdef object modal
    cdef object motion = None
    cdef object cycle = None
    cdef object block
    cdef object node
    cdef tuple token_tuple
    cdef tuple ast_tuple

    while pos < size and data[pos] <= 32:
        pos += 1
    while pos < size and data[pos] == 47:
        optional_skip = True
        pos += 1
        while pos < size and data[pos] <= 32:
            pos += 1

    while pos < size:
        ch = data[pos]
        if _alpha(ch) and not (pos > 0 and (_alpha(data[pos - 1]) or data[pos - 1] == 95)):
            probe = pos + 1
            while probe < size and data[probe] <= 32:
                probe += 1
            if probe < size and data[probe] == 61:
                probe += 1
                while probe < size and data[probe] <= 32:
                    probe += 1
            if probe < size and _expr_start(data[probe]):
                if start_count == 128:
                    return None
                starts[start_count] = pos
                start_count += 1
        pos += 1

    for word_index in range(start_count):
        start = starts[word_index]
        finish = starts[word_index + 1] if word_index + 1 < start_count else size
        letter = chr(data[start]).upper()
        start += 1
        while start < finish and data[start] <= 32:
            start += 1
        if start < finish and data[start] == 61:
            start += 1
            while start < finish and data[start] <= 32:
                start += 1
        while finish > start and data[finish - 1] <= 32:
            finish -= 1
        expr_bytes = clean[start:finish]
        if letter == "N" or letter == "O":
            expr_bytes = _label_prefix(expr_bytes)
        if not expr_bytes:
            continue
        expr = expr_bytes.decode("ascii")
        int_code = _literal_int(expr_bytes)
        token = WordToken(letter, expr)
        tokens.append(token)
        ast_words.append(AstWord(letter, expr, int_code))
        if letter == "G":
            last_g_expr = expr
            if int_code is not None:
                g_codes.append(int_code)
                if int_code == 65:
                    g65_call = True
                if int_code in (0, 1, 2, 3, 32, 33):
                    motion_expr = expr
                    motion_code = int_code
                if int_code in (70, 71, 72, 73, 74, 75, 76, 80, 83, 84, 90, 92, 94):
                    cycle_expr = expr
                    cycle_code = int_code
        elif letter == "M" and int_code is not None:
            m_codes.append(int_code)
        elif letter == "N" and nlabel is None and int_code is not None:
            nlabel = int_code
        elif letter == "O" and olabel is None and int_code is not None:
            olabel = int_code
        elif letter == "X":
            x_expr = expr
        elif letter == "Z":
            z_expr = expr
        elif letter == "U":
            u_expr = expr
        elif letter == "W":
            w_expr = expr
        elif letter == "I":
            i_expr = expr
        elif letter == "K":
            k_expr = expr
        elif letter == "R":
            r_expr = expr
        elif letter == "F":
            f_expr = expr
        elif letter == "A":
            a_expr = expr
        elif letter == "C":
            c_expr = expr

    if g65_call:
        modal = ModalSnapshot(None, None, None, None, None, None)
    else:
        modal = ModalSnapshot(
            motion_expr if motion_expr is not None else last_g_expr,
            x_expr, z_expr, u_expr, w_expr, f_expr,
        )
    if not g65_call and (
        motion_expr is not None or x_expr is not None or z_expr is not None or u_expr is not None or w_expr is not None
    ):
        motion = MotionNode(
            motion_expr,
            x_expr, z_expr, u_expr, w_expr,
            i_expr, k_expr, r_expr, f_expr, a_expr, c_expr,
        )
    token_tuple = tuple(tokens)
    ast_tuple = tuple(ast_words)
    if not g65_call and cycle_expr is not None:
        cycle = CycleNode("G" + str(cycle_code), token_tuple)

    block = Block(index, raw, token_tuple, modal, motion, cycle, None, nlabel, olabel, optional_skip)
    if cycle is not None:
        node = CycleAstNode("cycle", index, raw, nlabel, olabel, ast_tuple, "G" + str(cycle_code), ast_tuple)
    elif motion is not None:
        node = MotionAstNode(
            "motion", index, raw, nlabel, olabel, ast_tuple,
            motion_code,
            x_expr, z_expr, u_expr, w_expr,
            i_expr, k_expr, r_expr, f_expr, a_expr, c_expr,
        )
    elif g_codes or m_codes:
        node = ControlAstNode(
            "control", index, raw, nlabel, olabel, ast_tuple, tuple(g_codes), () if g65_call else tuple(m_codes)
        )
    elif ast_tuple:
        node = MetaAstNode("meta", index, raw, nlabel, olabel, ast_tuple, tuple(word.letter for word in ast_tuple))
    else:
        node = AstNode("empty", index, raw, nlabel, olabel, ())
    return block, node


def parse_source(str source, object fallback_block, object checkpoint):
    """Parse one complete source string and return the existing Program graph."""
    cdef bytes encoded = source.encode("utf-8")
    cdef const unsigned char* data = <const unsigned char*>PyBytes_AS_STRING(encoded)
    cdef Py_ssize_t size = PyBytes_GET_SIZE(encoded)
    cdef Py_ssize_t line_start = 0
    cdef Py_ssize_t line_end
    cdef Py_ssize_t index = 0
    cdef bytes raw_bytes
    cdef bytes clean
    cdef str raw
    cdef object block
    cdef object node
    cdef object parsed
    cdef list blocks = []
    cdef list nodes = []
    cdef dict nlabels = {}
    cdef dict olabels = {}

    while line_start < size:
        if index % 256 == 0:
            checkpoint()
        line_end = line_start
        while line_end < size and data[line_end] != 10:
            line_end += 1
        raw_bytes = encoded[line_start:line_end]
        raw = raw_bytes.decode("utf-8")
        clean = raw_bytes
        if _requires_fallback(clean):
            block = fallback_block(index, raw)
            node = build_ast_node(block)
        else:
            parsed = _native_block(index, raw, clean)
            if parsed is None:
                block = fallback_block(index, raw)
                node = build_ast_node(block)
            else:
                block, node = parsed
        blocks.append(block)
        nodes.append(node)
        if node.nlabel is not None and node.nlabel not in nlabels:
            nlabels[node.nlabel] = node.block_index
        if node.olabel is not None and node.olabel not in olabels:
            olabels[node.olabel] = node.block_index
        index += 1
        line_start = line_end + 1

    return Program(tuple(blocks), ProgramAst(tuple(nodes), nlabels, olabels))
