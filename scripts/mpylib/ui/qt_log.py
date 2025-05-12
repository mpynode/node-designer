import sys
import traceback

from Qt.QtCore import Qt
from Qt.QtGui import QColor, QTextCursor
from Qt.QtWidgets import QTextEdit, QMenu, QAction


class QtLog(QTextEdit):
    """
    Custom QTextEdit widget for displaying data as log output.
    """

    DEFAULT_TYPE = 0
    ERROR_TYPE = 1
    SUCCESS_TYPE = 2
    LAST_EXCEPTION_TYPE = 3

    DEFAULT_TEXT_COLOR = (0, 0, 255)
    ERROR_TEXT_COLOR = (255, 0, 0)
    SUCCESS_TEXT_COLOR = (0, 255, 0)


    def __init__(self, parent=None):
        
        self.TEXT_COLOR_MAP = {self.DEFAULT_TYPE:self.DEFAULT_TEXT_COLOR,
                               self.ERROR_TYPE:self.ERROR_TEXT_COLOR,
                               self.SUCCESS_TYPE:self.SUCCESS_TEXT_COLOR,
                               self.LAST_EXCEPTION_TYPE:self.ERROR_TEXT_COLOR}
        
        QTextEdit.__init__(self, parent)
        
        self.setReadOnly(True)
        
        ##----needed to add custom actions to the default context menu----##
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        self._clear_log_action = QAction("Clear Log", self, statusTip="Clear the log", triggered=self.clear)
        
        
    def showContextMenu(self, pnt):
        """
        Used to append custom actions to the default context menu 
        """
        
        menu = self.createStandardContextMenu(pnt)
        menu.addSeparator()
        menu.addAction(self._clear_log_action)
        menu.exec_(self.mapToGlobal(pnt))


    def write(self, text, txt_format=0):
        """
        Writes the given text to log in the given format
        """
        
        if txt_format == self.LAST_EXCEPTION_TYPE:
            text = "".join(traceback.format_exception(*sys.exc_info()))

        #if self.TEXT_COLOR_MAP.has_key(txt_format):
        if txt_format in self.TEXT_COLOR_MAP:

            cur_clr = self.textColor()

            self.setTextColor(QColor(*self.TEXT_COLOR_MAP[txt_format]))

            self.append(text)

            self.setTextColor(QColor(*self.DEFAULT_TEXT_COLOR))
            self.moveCursor(QTextCursor.End, QTextCursor.MoveAnchor)
            self.ensureCursorVisible()

        else:
            raise RuntimeError("Invalid text format: " + str(txt_format))