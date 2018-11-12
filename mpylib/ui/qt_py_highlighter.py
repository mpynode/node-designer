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


class QtPythonHighlighter (QSyntaxHighlighter):
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
    
    
    def __init__(self, document):
        
        QSyntaxHighlighter.__init__(self, document)
        
        self._styles = {"keyword": self._formatText("khaki"),
                        "operator": self._formatText("white"),
                        "brace": self._formatText("darkGray"),
                        "defclass": self._formatText("deepskyblue", "bold"),
                        "string": self._formatText("violet"),
                        "string2": self._formatText("salmon"),
                        "comment": self._formatText("springgreen", "italic"),
                        "self": self._formatText("azure", "italic"),
                        "numbers": self._formatText("skyblue")}        

        # Multi-line strings (expression, flag, style)
        # FIXME: The triple-quotes in these two lines will mess up the
        # syntax highlighting from this point onward
        self._tri_single = (QRegExp("'''"), 1, self._styles["string2"])
        self._tri_double = (QRegExp('"""'), 2, self._styles["string2"])

        rules = []

        # Keyword, operator, and brace rules
        rules += [(r'\b%s\b' % w, 0, self._styles['keyword'])
            for w in self.KEYWORDS]
        rules += [(r'%s' % o, 0, self._styles['operator'])
            for o in self.OPERATORS]
        rules += [(r'%s' % b, 0, self._styles['brace'])
            for b in self.BRACES]

        # All other rules
        rules += [
            # 'self'
            (r'\bself\b', 0, self._styles['self']),

            # Double-quoted string, possibly containing escape sequences
            (r'"[^"\\]*(\\.[^"\\]*)*"', 0, self._styles['string']),
            # Single-quoted string, possibly containing escape sequences
            (r"'[^'\\]*(\\.[^'\\]*)*'", 0, self._styles['string']),

            # 'def' followed by an identifier
            (r'\bdef\b\s*(\w+)', 1, self._styles['defclass']),
            # 'class' followed by an identifier
            (r'\bclass\b\s*(\w+)', 1, self._styles['defclass']),

            # From '#' until a newline
            (r'#[^\n]*', 0, self._styles['comment']),

            # Numeric literals
            (r'\b[+-]?[0-9]+[lL]?\b', 0, self._styles['numbers']),
            (r'\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b', 0, self._styles['numbers']),
            (r'\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b', 0, self._styles['numbers']),
        ]

        # Build a QRegExp for each pattern
        self.rules = [(QRegExp(pat), index, fmt)
            for (pat, index, fmt) in rules]
        
    
    def _formatText(self, color, style=""):
        """
        Return a QTextCharFormat with the given attributes.
        """
        
        clr = QColor()
        clr.setNamedColor(color)
    
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
        for expression, nth, format in self.rules:
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
        
        
        
#if __name__ == "__main__":
    
    #from PySide.QtGui import QApplication, QPlainTextEdit
    
    #app = QApplication([])
    
    #editor = QPlainTextEdit()
    #highlight = QtPythonHighlighter(editor.document())
    #editor.show()
    
    #app.exec_()