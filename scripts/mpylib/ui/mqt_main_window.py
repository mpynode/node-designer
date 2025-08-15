import maya.cmds as mc

from mpylib.ui.mqt_main import QMayaMain

from Qt.QtWidgets import QMainWindow


class QMayaWindow(QMainWindow):
    """
    Base class for creating a QMainWindow with Maya as it's parent
    """

    TITLE = "QMayaWindow"

    REPLACE_EXISTING = True

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

        if self.REPLACE_EXISTING:
            self._replaceExisting(self._maya_win)

        self._maya_signals = None

        QMainWindow.__init__(self, self._maya_win)

        self._setMayaSignals()

        self.setWindowTitle(self.TITLE)

    def _replaceExisting(self, parent):
        children = parent.children()

        for child in children:
            if str(type(self)) == str(type(child)):
                child.close()

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
