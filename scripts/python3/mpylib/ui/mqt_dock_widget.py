
import maya.cmds as mc

if mc.about(apiVersion=True) < 201700:
    from PySide.QtGui import QDockWidget

else:
    from PySide2.QtWidgets import QDockWidget

from mqt_main import QMayaMain



class QMayaDockWidget(QDockWidget):
    """
    Base class for creating a QDockWidget in Maya
    """
    
    TITLE = "QMayaDockWidget"
    
    DEFAULT_FLOATING = True
    
    
    def __init__(self):
        """
        Initialize a new QMayaDockWidget instance
        
        **RETURNS**
         *None*
        
        >>> doc_widget = QMayaDockWidget()
        >>> doc_widget.show()
        
        """
        
        self._maya_win = QMayaMain.getMainWindow()
        
        QDockWidget.__init__(self, self._maya_win)
        
        self.setWindowTitle(self.TITLE)
        self.setFloating(self.DEFAULT_FLOATING)
        
        
    def closeEvent(self, event):
        """
        OVERRIDE... Insures proper garbage collection of UI
        """
        
        self.deleteLater()
        QDockWidget.closeEvent(self, event)