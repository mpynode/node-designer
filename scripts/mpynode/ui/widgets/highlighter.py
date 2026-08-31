"""QtPythonHighlighter \u2014 syntax highlighter for Python source.

Adapted from the original qt_py_highlighter.py. Trimmed:
  * Removed the legacy ``print`` / ``exec`` keyword entries (Python 2 era \u2014
    these are no longer keywords in Python 3, so highlighting them as
    keywords is misleading).
  * Removed the ``__main__`` test block at the bottom (mayapy doesn't
    have a usable QApplication anyway).

Kept the var-color override API (``setVarColorMap`` / ``appendVarColor``
/ ``removeVarColor`` / ``clearVarColors``) for the per-attr color picker.
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import (
    QColor,
    QFont,
    QRegularExpression,
    QSyntaxHighlighter,
    QTextCharFormat,
)

# Single source of truth for "what looks like a clickable URL", shared with
# the click handler in editor_core so the STYLING here and the DETECTION there
# can never drift. Stops at whitespace, quotes and trailing brackets.
URL_PATTERN = r"https?://[^\s\"'`<>)\]]+"


class QtPythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for the Python language (Python 3)."""

    KEYWORDS = (
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
        # Built-in singletons
        "None",
        "True",
        "False",
    )

    OPERATORS = (
        "=",
        "==",
        "!=",
        "<",
        "<=",
        ">",
        ">=",
        "\\+",
        "-",
        "\\*",
        "/",
        "//",
        "\\%",
        "\\*\\*",
        "\\+=",
        "-=",
        "\\*=",
        "/=",
        "\\%=",
        "\\^",
        "\\|",
        "\\&",
        "\\~",
        ">>",
        "<<",
    )

    BRACES = ("\\{", "\\}", "\\(", "\\)", "\\[", "\\]")

    VAR_PATTERN_PREFIX = "\\b"
    VAR_PATTERN_SUFFIX = "\\b"

    def __init__(self, document):
        super().__init__(document)

        # Monokai-ish palette.
        self._styles = {
            "keyword": self.formatText((249, 38, 102)),
            "operator": self.formatText((255, 255, 255)),
            "brace": self.formatText((255, 255, 255)),
            "defclass": self.formatText((146, 226, 46), "bold"),
            "string": self.formatText((230, 219, 91)),
            "string2": self.formatText((230, 219, 91)),
            "comment": self.formatText((127, 192, 88), "italic"),
            "self": self.formatText((0, 166, 210), "italic"),
            "numbers": self.formatText((174, 129, 222)),
            # Link-blue + underlined. Overrides the comment colour on the URL
            # span, since rebuildRules() appends this AFTER the comment rule.
            "url": self.formatText((102, 175, 255), "underline"),
        }

        # Multi-line strings: (regex, state-int, style)
        self._tri_single = (QRegularExpression("'''"), 1, self._styles["string2"])
        self._tri_double = (QRegularExpression('"""'), 2, self._styles["string2"])

        self._rules = []
        self._default_rules = [
            (r"\b%s\b" % keyword, 0, self._styles["keyword"])
            for keyword in self.KEYWORDS
        ]
        self._default_rules += [
            (r"%s" % operator, 0, self._styles["operator"])
            for operator in self.OPERATORS
        ]
        self._default_rules += [
            (r"%s" % brace, 0, self._styles["brace"]) for brace in self.BRACES
        ]
        self._default_rules += [
            (r"\bself\b", 0, self._styles["self"]),
            # double-quoted string
            (r'"[^"\\]*(\\.[^"\\]*)*"', 0, self._styles["string"]),
            # single-quoted string
            (r"'[^'\\]*(\\.[^'\\]*)*'", 0, self._styles["string"]),
            # def name + class name
            (r"\bdef\b\s*(\w+)", 1, self._styles["defclass"]),
            (r"\bclass\b\s*(\w+)", 1, self._styles["defclass"]),
            # numeric literals
            (r"\b[+-]?[0-9]+[lL]?\b", 0, self._styles["numbers"]),
            (r"\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b", 0, self._styles["numbers"]),
            (
                r"\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b",
                0,
                self._styles["numbers"],
            ),
        ]
        # LAST, so comments win over keywords on the same line.
        self._comment_rules = [(r"#[^\n]*", 0, self._styles["comment"])]
        # After comments, so a link inside a comment renders blue +
        # underlined rather than comment-green.
        self._url_rules = [(URL_PATTERN, 0, self._styles["url"])]
        self._var_rules_map = {}

        self.rebuildRules()

    def rebuildRules(self):
        self._rules = [
            (QRegularExpression(pat), index, fmt)
            for (pat, index, fmt) in self._default_rules
        ]
        if self._var_rules_map:
            self._rules += [
                (QRegularExpression(pat), index, fmt)
                for (pat, index, fmt) in self._var_rules_map.values()
            ]
        self._rules += [
            (QRegularExpression(pat), index, fmt)
            for (pat, index, fmt) in self._comment_rules
        ]
        self._rules += [
            (QRegularExpression(pat), index, fmt)
            for (pat, index, fmt) in self._url_rules
        ]
        self.rehighlight()

    @classmethod
    def formatText(cls, color, style=""):
        """Return a QTextCharFormat with the given color + style flags."""
        clr = QColor(*color)
        fmt = QTextCharFormat()
        fmt.setForeground(clr)
        if "bold" in style:
            fmt.setFontWeight(QFont.Bold)
        if "italic" in style:
            fmt.setFontItalic(True)
        if "underline" in style:
            fmt.setFontUnderline(True)
        return fmt

    def highlightBlock(self, text):
        """Apply syntax highlighting to a single block of text."""
        for expression, nth, fmt in self._rules:
            match_iter = expression.globalMatch(text)
            while match_iter.hasNext():
                match = match_iter.next()
                index = match.capturedStart(nth)
                length = len(match.captured(nth))
                self.setFormat(index, length, fmt)

        self.setCurrentBlockState(0)

        # Multi-line strings.
        in_multiline = self.matchMultiline(text, *self._tri_single)
        if not in_multiline:
            in_multiline = self.matchMultiline(text, *self._tri_double)

    def matchMultiline(self, text, delimiter, in_state, style):
        """Highlight multi-line triple-quoted strings."""
        if self.previousBlockState() == in_state:
            start = 0
            add = 0
        else:
            match = delimiter.match(text)
            if match.hasMatch():
                start = match.capturedStart()
                add = match.capturedLength()
            else:
                start = -1
                add = 0

        while start >= 0:
            match_end = delimiter.match(text, start + add)
            if match_end.hasMatch():
                end = match_end.capturedStart()
            else:
                end = -1
            if end >= 0:
                length = end - start + match_end.capturedLength()
                self.setCurrentBlockState(0)
            else:
                self.setCurrentBlockState(in_state)
                length = len(text) - start
            self.setFormat(start, length, style)
            match = delimiter.match(text, start + length)
            if match.hasMatch():
                start = match.capturedStart()
                add = match.capturedLength()
            else:
                start = -1
                add = 0

        return self.currentBlockState() == in_state

    # ------------------------------------------------------------------
    # Variable-color overrides
    # ------------------------------------------------------------------

    def clearVarColors(self):
        self._var_rules_map = {}

    def setVarColorMap(self, var_map: dict):
        self._var_rules_map = {}
        for var_name, color in var_map.items():
            reg_ex = self.VAR_PATTERN_PREFIX + var_name + self.VAR_PATTERN_SUFFIX
            style = self.formatText(color, style="italic")
            self._var_rules_map[var_name] = (QRegularExpression(reg_ex), 0, style)
        self.rebuildRules()

    def appendVarColor(self, var_name: str, color):
        reg_ex = self.VAR_PATTERN_PREFIX + var_name + self.VAR_PATTERN_SUFFIX
        style = self.formatText(color, style="italic")
        self._var_rules_map[var_name] = (QRegularExpression(reg_ex), 0, style)
        self.rebuildRules()

    def removeVarColor(self, var_name: str):
        if var_name in self._var_rules_map:
            del self._var_rules_map[var_name]
        self.rebuildRules()
