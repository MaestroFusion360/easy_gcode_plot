"""G-code syntax highlighting lexer used by the editor."""

import re

from PyQt6.Qsci import QsciLexerCustom
from PyQt6.QtGui import QColor


class GcodeLexer(QsciLexerCustom):
    """Custom QScintilla lexer for highlighting G-code."""

    def __init__(self, parent=None):
        """Initialize lexer styles and colors."""
        super().__init__(parent)

        self.stylesLexer = {
            0: "Default",
            1: "Rapid",
            2: "Linear",
            3: "Circular",
        }

        for key, value in self.stylesLexer.items():
            setattr(self, value, key)

        self.initColors()

    def initColors(self):
        """Assign colors for each move type style."""
        self.setColor(QColor("#000000"), self.Default)
        self.setColor(QColor("#ff0000"), self.Rapid)
        self.setColor(QColor("#2ecc71"), self.Linear)
        self.setColor(QColor("#0000ff"), self.Circular)

    def language(self):
        """Declare lexer language name."""
        return "G-Code"

    def description(self, style):
        """Provide a brief description for the given style id."""
        if style < len(self.stylesLexer):
            description = "Custom lexer for the G-Code"
        else:
            description = ""
        return description

    def styleText(self, start, end):
        """Apply syntax highlighting between given character positions."""
        editor = self.editor()
        if editor is None:
            return

        source = ""
        if end > editor.length():
            end = editor.length()
        if end > start:
            source = str(editor.text())[start:end]
        if not source:
            return

        # rapid = 0, linear = 1, circular = 2
        prev_move = 0
        lst = source.splitlines(True)

        self.startStyling(start)

        if start != 0:
            previous_style = editor.SendScintilla(editor.SCI_GETSTYLEAT, start - 1)
            if previous_style == self.Rapid:
                prev_move = 0
            elif previous_style == self.Linear:
                prev_move = 1
            elif previous_style == self.Circular:
                prev_move = 2
            else:
                source1 = str(editor.text())[0 : start - 1]
                lst1 = source1.splitlines(True)
                i = 0
                while i < len(lst1):
                    line = lst1[i]
                    blockskip = "".join(re.findall(r"^\/.*", line))
                    if blockskip:
                        line = line.replace(blockskip, "")
                    comment = "".join(re.findall(r"\(.*?\)", line))
                    if comment:
                        line = line.replace(comment, "")
                    circular = re.findall(r"[G]0?[2-3][\D]", line)
                    linear = re.findall(r"[G]0?[1][\D]", line)
                    rapid = re.findall(r"[G]0?[0][\D]", line)
                    if rapid:
                        prev_move = 0
                    elif linear:
                        prev_move = 1
                    elif circular:
                        prev_move = 2

                    i += 1

        i = 0
        while i < len(lst):
            line = lst[i]
            blockskip = "".join(re.findall(r"^\/.*", line))
            if blockskip:
                line = line.replace(blockskip, "")
            comment = "".join(re.findall(r"\(.*?\)", line))
            if comment:
                line = line.replace(comment, "")
            lineNum = "".join(re.findall(r"^[N]\d+[\s]+", line))
            if comment:
                line = line.replace(lineNum, "")

            axis = re.findall(r"[XYZIJKR]{1}(?:[+-]?[\d\.]+|\#\<.*\>|\[.*\]|\#\d+)", line)
            circular = re.findall(r"[G]0?[2-3][\D]", line)
            linear = re.findall(r"[G]0?[1][\D]", line)
            rapid = re.findall(r"[G]0?[0][\D]", line)

            if rapid:
                prev_move = 0
                self.setStyling(len(lst[i]), self.Rapid)
            elif linear:
                prev_move = 1
                self.setStyling(len(lst[i]), self.Linear)
            elif circular:
                prev_move = 2
                self.setStyling(len(lst[i]), self.Circular)
            elif axis:
                if prev_move == 0:
                    self.setStyling(len(lst[i]), self.Rapid)
                elif prev_move == 1:
                    self.setStyling(len(lst[i]), self.Linear)
                elif prev_move == 2:
                    self.setStyling(len(lst[i]), self.Circular)
                # else:
                #     self.setStyling(len(lst[i]), self.Default)
            else:
                self.setStyling(len(lst[i]), self.Default)

            i += 1
