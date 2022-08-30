import os

import maya.cmds as mc
import maya.OpenMayaUI as omui
import maya.OpenMaya as om


if mc.about(apiVersion=True) < 201700:
    import shiboken

    from PySide.QtCore import SIGNAL, Signal, Slot, QObject
    from PySide.QtGui import QWidget

else:
    import shiboken2 as shiboken
    
    from PySide2.QtCore import SIGNAL, Signal, Slot, QObject
    from PySide2.QtWidgets import QWidget


class QMayaMain(object):
    """
    Class for interacting with the Maya UI on the Qt level
    """
    
    MAIN_WIN = None
    
    SCENE_SIGNAL_OBJ = None
    
    SCENE_OPENED_CALLBACK = None
    PRE_SCENE_OPENED_CALLBACK = None
    DAG_OBJ_CREATED_CALLBACK = None
    
    
    @classmethod
    def getMainWindow(cls):
        """
        Returns the main Maya ui as a QWidget
        
        **RETURNS**		QWidget or None
        """
        
        if cls.MAIN_WIN is not None:
            return cls.MAIN_WIN
    
        ptr = omui.MQtUtil.mainWindow()
    
        ##---if ptr is None, that means Maya is in some sort of batch mode (no ui)---##
        if ptr is not None:
            cls.MAIN_WIN = shiboken.wrapInstance(long(ptr), QWidget)
            return cls.MAIN_WIN
        
        else:
            cls.MAIN_WIN = None
    
        return None
    
    
    @classmethod
    def getSignalObject(cls):
        """
        Get the QMayaSignals object being used by this class. If one does not exist,
        a new one will be created and returned.
        
        :RETURNS:	QMayaSignals
        """

        if cls.SCENE_SIGNAL_OBJ is None:
            cls.SCENE_SIGNAL_OBJ = QMayaSignals()

        return cls.SCENE_SIGNAL_OBJ



    @staticmethod
    def sceneOpenEvent(event):
        """
        :purpose:	Emits a sceneOpened Qt signal from the current OpenSceneEvent object for the
        			scene. If no OpenSceneEvent object exists, one will be created.
        :returns:	None
        """

        sig = QMayaMain.getSignalObject()
        sig.SCENE_OPENED.emit()
        
        
    @classmethod
    def createSceneOpenSignal(cls):
        """
        :purpose:	This function sets a SceneOpened MEventMessage callback that can be used
                    to keep any listening Qt widgets up to date. The the callback event
                    tells the main maya window QObject to emit the signal SCENE_OPENED. 
                    A new callback is only created if none yet exist 
        :returns:	Qt Signal object
        """
    
        if cls.SCENE_OPENED_CALLBACK is None:
            
            cls.SCENE_OPENED_CALLBACK = om.MSceneMessage.addCallback(om.MSceneMessage.kAfterOpen, cls.sceneOpenEvent)
    
        sig_obj = cls.getSignalObject()
        
        return sig_obj.SCENE_OPENED
    
    
    @staticmethod
    def preSceneOpenEvent(event):
        """
        """

        sig = QMayaMain.getSignalObject()
        sig.PRE_SCENE_OPENED.emit()
        
        
    @classmethod
    def createPreSceneOpenSignal(cls):
        """
        """
    
        if cls.PRE_SCENE_OPENED_CALLBACK is None:
            
            cls.PRE_SCENE_OPENED_CALLBACK = om.MSceneMessage.addCallback(om.MSceneMessage.kBeforeOpen, cls.preSceneOpenEvent)
    
        sig_obj = cls.getSignalObject()
        
        return sig_obj.PRE_SCENE_OPENED    
    
    
    @staticmethod
    def dagObjCreatedEvent(event):
        """
        """
        
        sig = QMayaMain.getSignalObject()
        sig.DAG_OBJECT_CREATED.emit()
        
        
    @classmethod
    def createDagObjCreatedSignal(cls):
        """
        """
    
        if cls.DAG_OBJ_CREATED_CALLBACK is None:
            
            cls.DAG_OBJ_CREATED_CALLBACK = om.MEventMessage.addEventCallback("DagObjectCreated", cls.dagObjCreatedEvent)
    
        return cls.getSignalObject().DAG_OBJECT_CREATED
    
    
class QMayaSignals(QObject):
    """
    :purpose:	Signal object to be called when a new Maya scene is opened
    """
    
    SCENE_OPENED = Signal()
    PRE_SCENE_OPENED = Signal()
    SCENE_IMPORTED = Signal()
    
    DAG_OBJECT_CREATED = Signal()
    NAME_CHANGED = Signal()
    