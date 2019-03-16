try:
    import PySide

except ImportError, err:
    from PySide2.QtWidgets import QWidget, QPlainTextEdit, QTextEdit
    from PySide2.QtGui import QColor, QFont, QFontMetrics, QTextFormat, QPainter
    from PySide2.QtCore import QSize, Qt, QRect, QEvent

else:
    from PySide.QtGui import QWidget, QPlainTextEdit, QTextEdit, QColor, QTextFormat, QPainter, QFontMetrics, QFont
    from PySide.QtCore import QSize, Qt, QRect, QEvent

from qt_py_highlighter import QtPythonHighlighter


class QtLineNumberArea(QWidget):

    def __init__(self, editor):
        super(QtLineNumberArea, self).__init__(editor)
        self._txt_editor = editor

    def sizeHint(self):
        return QSize(self._txt_editor.lineNumberAreaWidth(), 0)


    def paintEvent(self, event):
        self._txt_editor.lineNumberAreaPaintEvent(event)


class QtPythonEditor(QPlainTextEdit):

    HIGHLIGHT_COLOR = Qt.lightGray
    HIGHLIGHTER_CLASS = QtPythonHighlighter

    DEFAULT_FONT_FAMILY = "Courier"
    DEFAULT_FONT_SIZE = 10
    DEFAULT_LINE_WRAP_MODE = QPlainTextEdit.NoWrap

    TAB_STOP = 4

    _font = None
    _font_size = DEFAULT_FONT_SIZE
    
    
    def __init__(self, parent=None):

        QPlainTextEdit.__init__(self, parent)

        self._highlighter = self.HIGHLIGHTER_CLASS(self.document())
        self._line_number_widget = QtLineNumberArea(self)
        self.setLineWrapMode(self.DEFAULT_LINE_WRAP_MODE)

        self._initTextAttrs()
        self._initEvents()



    def _initEvents(self):

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        #self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.updateLineNumberAreaWidth()


    def _initTextAttrs(self):

        self.font = QFont()
        self.font.setFamily(self.DEFAULT_FONT_FAMILY)
        self.font.setStyleHint(QFont.Monospace)
        self.font.setFixedPitch(True)
        self.font.setPointSize(self._font_size)

        self.setFont(self.font)
        self.setTabStopWidth(self.TAB_STOP * QFontMetrics(self.font).width(" "))


    def resizeEvent(self, event):

        super(QtPythonEditor, self).resizeEvent(event)

        cr = self.contentsRect()
        self._line_number_widget.setGeometry(QRect(cr.left(), cr.top(),
                                                   self.lineNumberAreaWidth(), cr.height()))


    def eventFilter(self, obj, event):
        """
        Implemented here to enable standard text editor ctrl+scroll_wheel text zooming
        """

        if event.type() == QEvent.Wheel:
            if event.modifiers() == Qt.ControlModifier:
                if event.delta() > 0:
                    self._font_size = max(self._font_size-2,self.DEFAULT_FONT_SIZE)
                    #self.zoomIn(2)
                else:
                    self._font_size = max(self._font_size+2,self.DEFAULT_FONT_SIZE)
                    #self.zoomOut(2)
                    
                self.font.setPointSize(self._font_size)
                self.setFont(self.font)
                self.setTabStopWidth(self.TAB_STOP * QFontMetrics(self.font).width(" "))                    

                return True

        return False


    def lineNumberAreaWidth(self):

        digits = 1
        count = max(1, self.blockCount())
        while count >= 10:
            count /= 10
            digits += 1
        space = 3 + self.fontMetrics().width("9") * digits

        return space


    def updateLineNumberArea(self, rect, dy):

        if dy:
            self._line_number_widget.scroll(0, dy)
        else:
            self._line_number_widget.update(0, rect.y(), self._line_number_widget.width(),
                                       rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth()


    def updateLineNumberAreaWidth(self):

        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)


    def highlightCurrentLine(self):

        extraSelections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()

            lineColor = QColor(self.HIGHLIGHT_COLOR).lighter(160)

            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)

        self.setExtraSelections(extraSelections)


    def lineNumberAreaPaintEvent(self, event):

        mypainter = QPainter(self._line_number_widget)

        mypainter.fillRect(event.rect(), Qt.lightGray)

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        # Just to make sure I use the right font
        height = self.fontMetrics().height()
        while block.isValid() and (top <= event.rect().bottom()):
            if block.isVisible() and (bottom >= event.rect().top()):
                number = str(blockNumber + 1)
                mypainter.setPen(Qt.black)
                mypainter.drawText(0, top, self._line_number_widget.width(), height,
                                   Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1


    def getHighlighter(self):

        return self._highlighter


    def setFontSize(self, size):

        font = self.font()
        font.setPointSize(size)
        self.setFont(font)


if __name__ == "__main__":

    try:
        from PySide.QtGui import QApplication

    except ImportError, err:
        from PySide2.QtWidgets import QApplication

    app = QApplication([])

    editor = QtPythonEditor()
    editor.show()

    app.exec_()