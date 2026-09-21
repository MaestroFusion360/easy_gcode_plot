# cython: language_level=3, boundscheck=False, wraparound=False, initializedcheck=False
"""Single-pass native scanner for conservative tool discovery."""

import re

from cpython.bytes cimport PyBytes_AS_STRING, PyBytes_FromStringAndSize, PyBytes_GET_SIZE
from libc.stdlib cimport free, malloc, realloc


cdef object _COMMENT_TOOL = re.compile(r"\bT\s*(\d+)\b", re.IGNORECASE)
cdef object _LITERAL_TOOL = re.compile(br"[+-]?\d+(?:\.0*)?")
cdef object _LITERAL_G65 = re.compile(br"\+?0*65(?:\.0*)?")
cdef object _TOOL_HINT = re.compile(
    r"\b(?:TAP(?:PING)?|THREAD(?:ING)?|GROOV(?:E|ING)|DRILL(?:ING)?|BALL|"
    r"FACE MILL|SLOT MILL|CHAMFER|BULL|FLAT(?: END)? MILL|TOOL|OD|ID)\b",
    re.IGNORECASE,
)


cdef inline bint _alpha(unsigned char ch) noexcept:
    return (65 <= ch <= 90) or (97 <= ch <= 122)


cdef inline bint _space(unsigned char ch) noexcept:
    return ch in (9, 10, 11, 12, 13, 32)


cdef inline bint _expr_start(unsigned char ch) noexcept:
    return ch == 43 or ch == 45 or ch == 46 or ch == 35 or ch == 91 or 48 <= ch <= 57


def _tool_key(bytes value, bint turning):
    cdef object number
    if _LITERAL_TOOL.fullmatch(value) is None:
        return None
    number = int(float(value))
    if turning:
        number = abs(number)
    if number < 1 or number > (9999 if turning else 99):
        return None
    key_number = str(number)
    return "T" + (key_number.zfill(4) if turning else key_number)


cdef object _normalized_comment(bytes source, Py_ssize_t start, Py_ssize_t end):
    return " ".join(source[start:end].decode("utf-8").split())


cdef void _remember_headers(dict headers, list comments, bint turning):
    cdef object comment
    cdef object match
    cdef object key
    for comment in comments:
        for match in _COMMENT_TOOL.finditer(comment):
            key = _tool_key(match.group(1).encode("ascii"), turning)
            if key is not None:
                headers.setdefault(key, comment)


cdef inline bint _word_start(unsigned char* clean, Py_ssize_t size, Py_ssize_t pos) noexcept:
    cdef Py_ssize_t probe
    if not _alpha(clean[pos]):
        return False
    if pos > 0 and (_alpha(clean[pos - 1]) or clean[pos - 1] == 95):
        return False
    probe = pos + 1
    while probe < size and _space(clean[probe]):
        probe += 1
    if probe >= size:
        return False
    if clean[probe] == 61:
        probe += 1
        while probe < size and _space(clean[probe]):
            probe += 1
        if probe >= size:
            return False
    return _expr_start(clean[probe])


cdef tuple _scan_words(unsigned char* clean, Py_ssize_t size, bint turning, double scale):
    cdef Py_ssize_t pos = 0
    cdef Py_ssize_t start = -1
    cdef Py_ssize_t expr_start
    cdef Py_ssize_t expr_end
    cdef Py_ssize_t depth = 0
    cdef unsigned char ch
    cdef unsigned char letter
    cdef bytes expr
    cdef object key
    cdef list selected = []
    cdef bint has_words = False
    cdef bint has_t = False
    cdef bint has_xyz = False
    cdef object operation = None
    cdef bint g65_call = False
    cdef double initial_scale = scale

    while pos <= size:
        if pos == size or (depth == 0 and _word_start(clean, size, pos)):
            if start >= 0:
                letter = clean[start]
                if 97 <= letter <= 122:
                    letter -= 32
                expr_start = start + 1
                expr_end = pos
                while expr_start < expr_end and _space(clean[expr_start]):
                    expr_start += 1
                if expr_start < expr_end and clean[expr_start] == 61:
                    expr_start += 1
                    while expr_start < expr_end and _space(clean[expr_start]):
                        expr_start += 1
                while expr_end > expr_start and _space(clean[expr_end - 1]):
                    expr_end -= 1
                if expr_end > expr_start:
                    has_words = True
                    expr = <bytes>PyBytes_FromStringAndSize(<char*>(clean + expr_start), expr_end - expr_start)
                    if letter == 84:
                        has_t = True
                        key = _tool_key(expr, turning)
                        if key is not None:
                            selected.append(key)
                    elif letter == 71:
                        if _LITERAL_G65.fullmatch(expr) is not None:
                            g65_call = True
                        if expr == b"20":
                            scale = 25.4
                        elif expr == b"21":
                            scale = 1.0
                        if expr in (b"81", b"82", b"83"):
                            operation = "drill"
                        elif expr == b"84":
                            operation = "tap"
                        elif turning and expr in (b"32", b"33", b"76", b"92"):
                            operation = "thread"
                    elif letter == 88 or letter == 89 or letter == 90:
                        has_xyz = True
            if pos == size:
                break
            start = pos
        if pos < size:
            ch = clean[pos]
            if ch == 91:
                depth += 1
            elif ch == 93 and depth > 0:
                depth -= 1
        pos += 1
    if g65_call:
        return [], None, has_words, False, False, initial_scale
    return selected, operation, has_words, has_t, has_xyz, scale


def scan_source(str source, bint turning, double default_unit_scale=1.0, cancelled=None):
    """Return the same minimal discovery structures as the Python scanner."""
    cdef bytes encoded = source.encode("utf-8")
    cdef const unsigned char* data = <const unsigned char*>PyBytes_AS_STRING(encoded)
    cdef Py_ssize_t size = PyBytes_GET_SIZE(encoded)
    cdef Py_ssize_t capacity = 256
    cdef unsigned char* clean = <unsigned char*>malloc(capacity)
    cdef Py_ssize_t line_start = 0
    cdef Py_ssize_t line_end
    cdef Py_ssize_t comment_end
    cdef Py_ssize_t pos
    cdef Py_ssize_t clean_size
    cdef Py_ssize_t comment_start = -1
    cdef Py_ssize_t semicolon = -1
    cdef Py_ssize_t index = 0
    cdef unsigned char ch
    cdef bint in_paren
    cdef list comments
    cdef list selected
    cdef object operation
    cdef bint has_words
    cdef bint has_t
    cdef bint has_xyz
    cdef object inline
    cdef object nearby
    cdef object key
    cdef double scale = default_unit_scale
    cdef dict headers = {}
    cdef list occurrences = []
    cdef dict operations = {}
    cdef object active_tool = None
    cdef object previous = ""
    cdef Py_ssize_t previous_line = -100

    if clean == NULL:
        raise MemoryError()
    try:
        while line_start < size:
            if index % 256 == 0 and cancelled is not None and cancelled():
                raise InterruptedError("Tool discovery cancelled")
            line_end = line_start
            while line_end < size and data[line_end] != 10:
                line_end += 1
            if line_end - line_start > capacity:
                capacity = line_end - line_start
                clean = <unsigned char*>realloc(clean, capacity)
                if clean == NULL:
                    raise MemoryError()

            comments = []
            clean_size = 0
            in_paren = False
            comment_start = -1
            semicolon = -1
            pos = line_start
            while pos < line_end:
                ch = data[pos]
                if ch == 40:
                    in_paren = True
                    comment_start = pos + 1
                    pos += 1
                    continue
                if ch == 41:
                    if in_paren and comment_start >= 0:
                        comments.append(_normalized_comment(encoded, comment_start, pos))
                    in_paren = False
                    comment_start = -1
                    pos += 1
                    continue
                if ch == 59:
                    semicolon = pos
                    if not in_paren:
                        comment_end = line_end
                        if comment_end > pos and data[comment_end - 1] == 13:
                            comment_end -= 1
                        comments.append(_normalized_comment(encoded, pos + 1, comment_end))
                        break
                if not in_paren:
                    clean[clean_size] = ch
                    clean_size += 1
                pos += 1
            if in_paren and semicolon >= comment_start:
                comment_end = line_end
                if comment_end > semicolon and data[comment_end - 1] == 13:
                    comment_end -= 1
                comments.append(_normalized_comment(encoded, semicolon + 1, comment_end))

            if comments:
                _remember_headers(headers, comments, turning)
            selected, operation, has_words, has_t, has_xyz, scale = _scan_words(
                clean, clean_size, turning, scale
            )
            if selected:
                active_tool = selected[len(selected) - 1]
            if active_tool is not None and operation is not None:
                operations.setdefault(active_tool, operation)

            inline = " ".join(comments)
            nearby = previous if index - previous_line <= 8 else ""
            for key in selected:
                occurrences.append((key, inline, nearby, scale))

            if has_t:
                previous = ""
            elif comments and _COMMENT_TOOL.search(inline) is None and (not has_words or _TOOL_HINT.search(inline)):
                previous = inline
                previous_line = index
            elif has_xyz:
                previous = ""

            index += 1
            line_start = line_end + 1
        return headers, occurrences, operations
    finally:
        free(clean)
