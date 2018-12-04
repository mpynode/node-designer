import os

import maya.cmds as mc
import maya.api.OpenMaya as om

if mc.about(apiVersion=True) < 201700:
    from PySide.QtGui import QMainWindow

else:
    from PySide2.QtWidgets import QMainWindow

from mqt_main import QMayaMain


class QMayaWindow(QMainWindow):
    """
    Base class for creating a QMainWindow with Maya as it's parent
    """
    
    TITLE = "QMayaWindow"
    
    USES_SCENE_OPENED = False
    SCENE_OPENED = None
    
    USES_PRE_SCENE_OPENED = False
    PRE_SCENE_OPENED = None
    
    USES_DAG_OBJECT_CREATED = False
    DAG_OBJECT_CREATED = None
    
    USES_NAME_CHANGED = False
    
    
    def __init__(self):
        """
        Initialize a new QMayaWindow instance
        
        **RETURNS**		*None*
        """
        
        self._maya_win = QMayaMain.getMainWindow()
        self._maya_signals = None
        
        QMainWindow.__init__(self, self._maya_win)
        
        self._setMayaSignals()
        
        self.setWindowTitle(self.TITLE)
        
    
    def _setMayaSignals(self):
        
        if self.USES_SCENE_OPENED:
            self.SCENE_OPENED = QMayaMain.createSceneOpenSignal()
            
        if self.USES_PRE_SCENE_OPENED:
            self.PRE_SCENE_OPENED = QMayaMain.createPreSceneOpenSignal()
            
        if self.USES_DAG_OBJECT_CREATED:
            self.DAG_OBJECT_CREATED = QMayaMain.createDagObjCreatedSignal()
        
        
    def closeEvent(self, event):
        """
        OVERRIDE... Insures proper garbage collection of UI
        """
        
        self.deleteLater()
        QMainWindow.closeEvent(self, event)