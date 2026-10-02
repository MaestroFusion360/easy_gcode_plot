# cython: language_level=3, boundscheck=False, wraparound=False, initializedcheck=False
"""Cython frontend for ordinary FANUC blocks.

The whole source crosses the extension boundary once.  Lines containing Macro B
or comments use the authoritative Python fallback; ordinary numeric ISO blocks
are tokenized and materialized here in one compiled loop.
"""

from cpython.bytes cimport PyBytes_AS_STRING, PyBytes_GET_SIZE
from cpython.object cimport PyObject_GenericSetAttr
from libc.math cimport fabs, isfinite, round as c_round

from .ast import (
    AstNode, AstWord, ControlAstNode, CycleAstNode, FlowAstNode, MetaAstNode,
    MotionAstNode, ProgramAst, WORD_CACHE_LIMIT,
    build_ast_node,
)

from .lang import WordToken
from .model import Block, CycleNode, ModalSnapshot, MotionNode, Program


cdef object _ast_int_code(object expr):
    cdef double value, rounded
    if expr is None:
        return None
    try:
        value = float(expr)
    except (TypeError, ValueError, OverflowError):
        return None
    if not isfinite(value):
        return None
    rounded = c_round(value)
    return int(rounded) if fabs(value - rounded) <= 1e-9 else None


cdef tuple _ast_words(tuple tokens, dict cache):
    cdef list words = []
    cdef object token, letter, expr, key, word
    for token in tokens:
        letter, expr = token.letter.upper(), token.expr
        key = (letter, expr)
        word = cache.get(key) if letter != "N" and letter != "O" else None
        if word is None:
            word = object.__new__(AstWord)
            PyObject_GenericSetAttr(word, "letter", letter)
            PyObject_GenericSetAttr(word, "expr", expr)
            PyObject_GenericSetAttr(word, "int_code", _ast_int_code(expr))
            if letter != "N" and letter != "O":
                if len(cache) >= WORD_CACHE_LIMIT:
                    cache.clear()
                cache[key] = word
        words.append(word)
    return tuple(words)


cdef object _common_ast(object cls, str kind, object block, tuple words):
    # Populate immutable dataclass slots before exposing the node. GenericSetAttr
    # avoids Python frozen-dataclass __init__/__setattr__ calls for every field.
    cdef object node = object.__new__(cls)
    PyObject_GenericSetAttr(node, "kind", kind)
    PyObject_GenericSetAttr(node, "block_index", block.index)
    PyObject_GenericSetAttr(node, "raw", block.raw)
    PyObject_GenericSetAttr(node, "nlabel", block.nlabel)
    PyObject_GenericSetAttr(node, "olabel", block.olabel)
    PyObject_GenericSetAttr(node, "words", words)
    PyObject_GenericSetAttr(node, "native_syntax", block.native_syntax)
    return node


cdef object _motion_ast(object block, tuple words, dict cache):
    cdef object motion = block.motion_node
    cdef object node = _common_ast(MotionAstNode, "motion", block, words)
    cdef object g_word = cache.get(("G", motion.g_expr))
    cdef object code = g_word.int_code if g_word is not None else _ast_int_code(motion.g_expr)
    PyObject_GenericSetAttr(node, "g_code", code)
    PyObject_GenericSetAttr(node, "x_expr", motion.x_expr)
    PyObject_GenericSetAttr(node, "z_expr", motion.z_expr)
    PyObject_GenericSetAttr(node, "u_expr", motion.u_expr)
    PyObject_GenericSetAttr(node, "w_expr", motion.w_expr)
    PyObject_GenericSetAttr(node, "i_expr", motion.i_expr)
    PyObject_GenericSetAttr(node, "k_expr", motion.k_expr)
    PyObject_GenericSetAttr(node, "r_expr", motion.r_expr)
    PyObject_GenericSetAttr(node, "f_expr", motion.f_expr)
    PyObject_GenericSetAttr(node, "a_expr", motion.a_expr)
    PyObject_GenericSetAttr(node, "c_expr", motion.c_expr)
    PyObject_GenericSetAttr(node, "y_expr", motion.y_expr)
    PyObject_GenericSetAttr(node, "v_expr", motion.v_expr)
    PyObject_GenericSetAttr(node, "j_expr", motion.j_expr)
    PyObject_GenericSetAttr(node, "b_expr", motion.b_expr)
    return node


cdef object _control_or_meta_ast(object block, tuple words):
    cdef list g_codes = [], m_codes = []
    cdef object word, node
    for word in words:
        if word.int_code is not None:
            if word.letter == "G":
                g_codes.append(word.int_code)
            elif word.letter == "M":
                m_codes.append(word.int_code)
    if g_codes or m_codes:
        node = _common_ast(ControlAstNode, "control", block, words)
        PyObject_GenericSetAttr(node, "g_codes", tuple(g_codes))
        PyObject_GenericSetAttr(node, "m_codes", () if 65 in g_codes else tuple(m_codes))
    elif words:
        node = _common_ast(MetaAstNode, "meta", block, words)
        PyObject_GenericSetAttr(node, "letters", tuple(word.letter for word in words))
    else:
        node = _common_ast(AstNode, "empty", block, words)
    return node


cdef object _ast_node(object block, dict cache):
    if block.native_syntax is not None:
        return build_ast_node(block, _word_cache=cache)
    cdef tuple words = _ast_words(block.parsed_words, cache)
    cdef object node, flow = block.flow_node, cycle = block.cycle_node
    if flow is not None:
        node = _common_ast(FlowAstNode, "flow", block, words)
        PyObject_GenericSetAttr(node, "flow_kind", flow.kind)
        PyObject_GenericSetAttr(node, "condition", flow.condition)
        PyObject_GenericSetAttr(node, "target_label", flow.target_label)
        PyObject_GenericSetAttr(node, "loop_id", flow.loop_id)
        PyObject_GenericSetAttr(node, "var_key", flow.var_key)
        PyObject_GenericSetAttr(node, "value_expr", flow.value_expr)
        return node
    if cycle is not None:
        node = _common_ast(CycleAstNode, "cycle", block, words)
        PyObject_GenericSetAttr(node, "cycle", cycle.cycle)
        PyObject_GenericSetAttr(node, "params", words)
        return node
    if block.motion_node is not None:
        return _motion_ast(block, words, cache)
    return _control_or_meta_ast(block, words)


def build_program_ast_native(tuple blocks, object checkpoint):
    """Compiled Block -> AST pass, including first-occurrence N/O label maps."""
    cdef list nodes = []
    cdef dict nlabels = {}, olabels = {}, cache = {}
    cdef object block
    cdef Py_ssize_t position = 0
    for block in blocks:
        if position % 256 == 0:
            checkpoint()
        nodes.append(_ast_node(block, cache))
        if isinstance(block.nlabel, int):
            nlabels.setdefault(block.nlabel, block.index)
        if isinstance(block.olabel, int):
            olabels.setdefault(block.olabel, block.index)
        position += 1
    return ProgramAst(tuple(nodes), nlabels, olabels)


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


cdef object _native_block(Py_ssize_t index, str raw, bytes clean):
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
    cdef object letter
    cdef bytes expr_bytes
    cdef object expr
    cdef object int_code
    cdef object token
    cdef object last_g_expr = None
    cdef object motion_expr = None
    cdef object cycle_expr = None
    cdef object cycle_code = None
    cdef object x_expr = None
    cdef object y_expr = None
    cdef object z_expr = None
    cdef object u_expr = None
    cdef object v_expr = None
    cdef object w_expr = None
    cdef object i_expr = None
    cdef object j_expr = None
    cdef object k_expr = None
    cdef object r_expr = None
    cdef object f_expr = None
    cdef object a_expr = None
    cdef object b_expr = None
    cdef object c_expr = None
    cdef bint g65_call = False
    cdef object nlabel = None
    cdef object olabel = None
    cdef object modal
    cdef object motion = None
    cdef object cycle = None
    cdef object block
    cdef tuple token_tuple

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
        if letter == "G":
            last_g_expr = expr
            if int_code is not None:
                if int_code == 65:
                    g65_call = True
                if int_code in (0, 1, 2, 3, 32, 33):
                    motion_expr = expr
                if int_code in (70, 71, 72, 73, 74, 75, 76, 80, 83, 84):
                    cycle_expr = expr
                    cycle_code = int_code
        elif letter == "N" and nlabel is None and int_code is not None:
            nlabel = int_code
        elif letter == "O" and olabel is None and int_code is not None:
            olabel = int_code
        elif letter == "X":
            x_expr = expr
        elif letter == "Y":
            y_expr = expr
        elif letter == "Z":
            z_expr = expr
        elif letter == "U":
            u_expr = expr
        elif letter == "V":
            v_expr = expr
        elif letter == "W":
            w_expr = expr
        elif letter == "I":
            i_expr = expr
        elif letter == "J":
            j_expr = expr
        elif letter == "K":
            k_expr = expr
        elif letter == "R":
            r_expr = expr
        elif letter == "F":
            f_expr = expr
        elif letter == "A":
            a_expr = expr
        elif letter == "B":
            b_expr = expr
        elif letter == "C":
            c_expr = expr

    if g65_call:
        modal = ModalSnapshot(None, None, None, None, None, None, None, None)
    else:
        modal = ModalSnapshot(
            motion_expr if motion_expr is not None else last_g_expr,
            x_expr, z_expr, u_expr, w_expr, f_expr,
            y_expr, v_expr,
        )
    if not g65_call and (
        motion_expr is not None or x_expr is not None or y_expr is not None or z_expr is not None
        or u_expr is not None or v_expr is not None or w_expr is not None
        or a_expr is not None or b_expr is not None or c_expr is not None
    ):
        motion = MotionNode(
            motion_expr,
            x_expr, z_expr, u_expr, w_expr,
            i_expr, k_expr, r_expr, f_expr, a_expr, c_expr,
            y_expr, v_expr, j_expr, b_expr,
        )
    token_tuple = tuple(tokens)
    if not g65_call and cycle_expr is not None:
        cycle = CycleNode("G" + str(cycle_code), token_tuple)

    block = Block(index, raw, token_tuple, modal, motion, cycle, None, nlabel, olabel, optional_skip)
    return block


def _parse_source_blocks(str source, object fallback_block, object checkpoint):
    """Compiled tokenization seam, shared by parsing and relative benchmarks."""
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
    cdef object parsed
    cdef list blocks = []

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
        else:
            parsed = _native_block(index, raw, clean)
            if parsed is None:
                block = fallback_block(index, raw)
            else:
                block = parsed
        blocks.append(block)
        index += 1
        line_start = line_end + 1

    return tuple(blocks)


def parse_source(str source, object fallback_block, object checkpoint):
    """Derive the AST from parsed blocks once, without public revalidation."""
    blocks = _parse_source_blocks(source, fallback_block, checkpoint)
    ast = build_program_ast_native(blocks, checkpoint)
    return Program._from_canonical_ast(blocks, ast)


def parse_source_blocks(str source, object fallback_block, object checkpoint):
    """Internal blocks-only entry point; canonical AST is built after augmentation."""
    return _parse_source_blocks(source, fallback_block, checkpoint)
