"""QScintilla adaptation of CNCEditor's HeidenhainLexer motion highlighting."""

import re

from PyQt6.QtGui import QColor

from app.ui.support.lexer import GcodeLexer

_TOKENS = re.compile(r'"(?:[^"\n]|"")*"|\([^)]*\)|;[^\r\n]*')
_NUMBER = re.compile(r"^\s*(?:N)?\d+\s+", re.IGNORECASE)
_MOTION = re.compile(r"^\s*(L|LP|CC|CR|CP|CT|C)\b", re.IGNORECASE)
_AXIS = re.compile(r"\b(?:I?[XYZABCUVW]|I?P[AR])\s*[+-]?(?:\d|\.\d|Q[LR]?\d)", re.IGNORECASE)


class HeidenhainLexer(GcodeLexer):
    """Highlight native Klartext without interpreting or executing the program."""

    Comment = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stylesLexer[self.Comment] = "Comment"
        self.apply_theme({})

    def language(self):
        return "Heidenhain iTNC"

    def description(self, style):
        return self.stylesLexer.get(style, "")

    def apply_theme(self, colors):
        super().apply_theme(colors)
        self.setColor(QColor(colors.get("comment", "#b0b0b0")), self.Comment)
        self.setPaper(self.defaultPaper(), self.Comment)

    def _line_styles(self, line, previous):
        """Return character spans and the motion state after one physical line."""
        if line.lstrip().startswith("/"):
            return [(line, self.Comment)], previous
        tokens = list(_TOKENS.finditer(line))
        comments = [match for match in tokens if not match[0].startswith('"')]
        code = list(line)
        for match in tokens:
            code[match.start() : match.end()] = " " * len(match[0])
        command = _NUMBER.sub("", "".join(code))
        motion = _MOTION.match(command)
        style = self.Default
        if motion:
            if motion[1].upper() in {"L", "LP"}:
                style = self.Rapid if re.search(r"\bFMAX\b", command, re.IGNORECASE) else self.Linear
            else:
                style = self.Circular
            previous = style
        elif _AXIS.search(command):
            style = previous
        spans = []
        offset = 0
        for match in comments:
            spans.append((line[offset : match.start()], style))
            spans.append((match[0], self.Comment))
            offset = match.end()
        spans.append((line[offset:], style))
        return spans, previous

    def styleText(self, start, end):
        """Style complete lines using Scintilla's UTF-8 byte positions."""
        editor = self.editor()
        if editor is None:
            return
        source = editor.text().encode("utf-8")
        end = min(end, len(source))
        if end <= start:
            return
        previous = self.Rapid
        offset = 0
        for line in source.decode("utf-8").splitlines(True):
            spans, previous = self._line_styles(line, previous)
            length = len(line.encode("utf-8"))
            if offset + length > start:
                self.startStyling(offset)
                for text, style in spans:
                    self.setStyling(len(text.encode("utf-8")), style)
            offset += length
            if offset >= end:
                break
