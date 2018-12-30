import sys

try:
    import PySide
    
except ImportError, err:
    from PySide2.QtCore import QRegExp
    from PySide2.QtGui import QColor, QTextCharFormat, QFont, QSyntaxHighlighter
    from PySide2.QtWidgets import QTextEdit

else:
    from PySide.QtCore import QRegExp
    from PySide.QtGui import QColor, QTextCharFormat, QFont, QSyntaxHighlighter


class QtPythonHighlighter(QSyntaxHighlighter):
    """
    Syntax highlighter for the Python language.
    """
    
    KEYWORDS = ("and", "as", "assert", "break", "class", "continue", "def",
                "del", "elif", "else", "except", "exec", "finally",
                "for", "from", "global", "if", "import", "in",
                "is", "lambda", "not", "or", "pass", "print",
                "raise", "return", "try", "while", "yield",
                "None", "True", "False")

    OPERATORS = ("=", "==", "!=", "<", "<=", ">", ">=",
                 "\+", "-", "\*", "/", "//", "\%", "\*\*",
                 "\+=", "-=", "\*=", "/=", "\%=",
                 "\^", "\|", "\&", "\~", ">>", "<<")

    BRACES = ("\{", "\}", "\(", "\)", "\[", "\]")
    
    VAR_PATTERN_PREFIX = "\\b"
    VAR_PATTERN_SUFFIX = "\\b"
    
    
    def __init__(self, document):
        
        super(QtPythonHighlighter, self).__init__(document)
        
        self._styles = {"keyword": QtPythonHighlighter.formatText((249, 38, 102)),
                        "operator": QtPythonHighlighter.formatText((255, 255, 255)),
                        "brace": QtPythonHighlighter.formatText((255, 255, 255)),
                        "defclass": QtPythonHighlighter.formatText((146, 226, 46), "bold"),
                        "string": QtPythonHighlighter.formatText((230, 219, 91)),
                        "string2": QtPythonHighlighter.formatText((230, 219, 91)),
                        "comment": QtPythonHighlighter.formatText((127, 192, 88), "italic"),
                        "self": QtPythonHighlighter.formatText((0, 166, 210), "italic"),
                        "numbers": QtPythonHighlighter.formatText((174, 129, 222))}        

        # Multi-line strings (expression, flag, style)
        # FIXME: The triple-quotes in these two lines will mess up the
        # syntax highlighting from this point onward
        self._tri_single = (QRegExp("'''"), 1, self._styles["string2"])
        self._tri_double = (QRegExp('"""'), 2, self._styles["string2"])
        
        self._rules = {}
        self._default_rules = [(r"\b%s\b" % keyword, 0, self._styles["keyword"]) for keyword in self.KEYWORDS]
        self._default_rules += [(r"%s" % operator, 0, self._styles["operator"]) for operator in self.OPERATORS]
        self._default_rules += [(r"%s" % brace, 0, self._styles["brace"]) for brace in self.BRACES]
        self._default_rules += [(r'\bself\b', 0, self._styles['self']),
                               (r'"[^"\\]*(\\.[^"\\]*)*"', 0, self._styles['string']),
                               (r"'[^'\\]*(\\.[^'\\]*)*'", 0, self._styles['string']),
                               (r'\bdef\b\s*(\w+)', 1, self._styles['defclass']),
                               (r'\bclass\b\s*(\w+)', 1, self._styles['defclass']),
                               (r'\b[+-]?[0-9]+[lL]?\b', 0, self._styles['numbers']),
                               (r'\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b', 0, self._styles['numbers']),
                               (r'\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b', 0, self._styles['numbers'])]
        self._comment_rules = [(r'#[^\n]*', 0, self._styles['comment'])]
        self._var_rules_map = {}

        self.rebuildRules()
        

    def rebuildRules(self):
        
        self._rules = [(QRegExp(pat), index, fmt) for (pat, index, fmt) in self._default_rules]
        
        if self._var_rules_map:
            self._rules += [(QRegExp(pat), index, fmt) for (pat, index, fmt) in self._var_rules_map.values()]
            
        self._rules += [(QRegExp(pat), index, fmt) for (pat, index, fmt) in self._comment_rules]
            
        self.rehighlight()
        
    
    @classmethod
    def formatText(cls, color, style=""):
        """
        Return a QTextCharFormat with the given attributes.
        """
        
        clr = QColor(*color)
    
        txt_format = QTextCharFormat()
        txt_format.setForeground(clr)
        
        if "bold" in style:
            txt_format.setFontWeight(QFont.Bold)
            
        if "italic" in style:
            txt_format.setFontItalic(True)
    
        return txt_format    


    def highlightBlock(self, text):
        """
        Apply syntax highlighting to the given block of text.
        """
        
        # Do other syntax formatting
        for expression, nth, format in self._rules:
            index = expression.indexIn(text, 0)

            while index >= 0:
                # We actually want the index of the nth match
                index = expression.pos(nth)
                length = len(expression.cap(nth))
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)

        # Do multi-line strings
        in_multiline = self.matchMultiline(text, *self._tri_single)
        if not in_multiline:
            in_multiline = self.matchMultiline(text, *self._tri_double)


    def matchMultiline(self, text, delimiter, in_state, style):
        """
        Do highlighting of multi-line strings. ``delimiter`` should be a
        ``QRegExp`` for triple-single-quotes or triple-double-quotes, and
        ``in_state`` should be a unique integer to represent the corresponding
        state changes when inside those strings. Returns True if we're still
        inside a multi-line string when this function is finished.
        """
        # If inside triple-single quotes, start at 0
        if self.previousBlockState() == in_state:
            start = 0
            add = 0
        # Otherwise, look for the delimiter on this line
        else:
            start = delimiter.indexIn(text)
            # Move past this match
            add = delimiter.matchedLength()

        # As long as there's a delimiter match on this line...
        while start >= 0:
            # Look for the ending delimiter
            end = delimiter.indexIn(text, start + add)
            # Ending delimiter on this line?
            if end >= add:
                length = end - start + add + delimiter.matchedLength()
                self.setCurrentBlockState(0)
            # No; multi-line string
            else:
                self.setCurrentBlockState(in_state)
                length = len(text) - start + add
            # Apply formatting
            self.setFormat(start, length, style)
            # Look for the next match
            start = delimiter.indexIn(text, start + length)

        # Return True if still inside a multi-line string, False otherwise
        if self.currentBlockState() == in_state:
            return True
        else:
            return False
        
        
    def clearVarColors(self):
        self._var_rules_map = {}
        
        
    def setVarColorMap(self, var_map):
        
        self._var_rules_map = {}
        
        for var_name, color in var_map.items():
            reg_ex = self.VAR_PATTERN_PREFIX + var_name + self.VAR_PATTERN_SUFFIX
            style = self.formatText(color, style="italic")
            
            self._var_rules_map[var_name] = (QRegExp(reg_ex), 0, style)
            
        self.rebuildRules()
    
    
    def appendVarColor(self, var_name, color):
        
        reg_ex = self.VAR_PATTERN_PREFIX + var_name + self.VAR_PATTERN_SUFFIX
        style = self.formatText(color, style="italic")
        
        self._var_rules_map[var_name] = (QRegExp(reg_ex), 0, style)
        self.rebuildRules()
        
        
    def removeVarColor(self, var_name):
        
        if var_name in self._var_rules_map:
            del(self._var_rules_map[var_name])
            
        self.rebuildRules()
        
        
if __name__ == "__main__":
    
    from PySide2.QtWidgets import QApplication, QPlainTextEdit
    
    app = QApplication([])
    
    editor = QPlainTextEdit()
    highlight = QtPythonHighlighter(editor.document())
    editor.show()
    
    app.exec_()