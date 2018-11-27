import __builtin__
import copy
import sys
import traceback
import keyword
import logging
from collections import OrderedDict

import maya.cmds as mc
import maya.api.OpenMaya as om

if mc.about(apiVersion=True) < 201700:
    import PySide
    from PySide.QtCore import Qt, Signal, Slot, QSize, QObject
    from PySide.QtGui import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QColor, QStatusBar, QMessageBox, QTreeWidget, QTreeWidgetItem, QDialog, QComboBox, QCheckBox
    from PySide.QtGui import QFont, QFontMetrics, QPlainTextEdit, QTabWidget, QTabBar, QAction, QKeySequence, QLineEdit, QFrame, QLabel, QMenu, QIcon, QPixmap, QPushButton, QStackedLayout
    from PySide.QtGui import QRadioButton, QButtonGroup, QCompleter, QTextCursor, QAbstractItemView, QToolBar, QListWidget, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QGridLayout
    from PySide.QtGui import QDoubleValidator, QIntValidator, QListWidgetItem

else:
    import PySide2
    PySide = PySide2
    from PySide2.QtCore import Qt, Signal, Slot, QSize, QObject
    from PySide2.QtGui import QColor, QFont, QFontMetrics, QKeySequence, QIcon, QPixmap, QTextCursor, QDoubleValidator, QIntValidator
    from PySide2.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QStatusBar, QMessageBox, QTreeWidget, QTreeWidgetItem, QDialog, QComboBox, QCheckBox
    from PySide2.QtWidgets import QPlainTextEdit, QTabWidget, QTabBar, QLineEdit, QFrame, QLabel, QMenu, QPushButton, QStackedLayout, QGridLayout, QListWidgetItem
    from PySide2.QtWidgets import QRadioButton, QButtonGroup, QCompleter, QAbstractItemView, QToolBar, QAction, QListWidget, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog

from qt_log import QtLog
from qt_py_editor import QtPythonEditor
from qt_py_highlighter import QtPythonHighlighter
from qt_py_profile_table import QtPyProfileTable

from mqt_main_window import QMayaWindow

from ..nodes import MPyNode
from .._base import MNode


ATTR_COLOR_DEFAULT = (80, 230, 80)
ATTR_COLOR_DARK_GREEN = (0, 128, 1)
ATTR_COLOR_GREEN = (80, 230, 80)
ATTR_COLOR_BLUE = (128, 230, 230)
ATTR_COLOR_DARK_BLUE = (10, 40, 195)
ATTR_COLOR_GREY_BLUE = (128, 170, 170)
ATTR_COLOR_ORANGE = (221, 135, 36)
ATTR_COLOR_PINK = (230, 1, 230)
ATTR_COLOR_BLACK = (0, 0, 0)
ATTR_COLOR_PY_YELLOW = (255, 218, 76)

ATTR_COLOR_MAP = {MPyNode.ATTR_TYPE_INT:ATTR_COLOR_DARK_GREEN, MPyNode.ATTR_TYPE_FLOAT:ATTR_COLOR_GREEN,
                  MPyNode.ATTR_TYPE_ANGLE:ATTR_COLOR_BLUE, MPyNode.ATTR_TYPE_BOOL:ATTR_COLOR_ORANGE,
                  MPyNode.ATTR_TYPE_COLOR:ATTR_COLOR_GREEN, MPyNode.ATTR_TYPE_EULER:ATTR_COLOR_GREEN,
                  MPyNode.ATTR_TYPE_MATRIX:ATTR_COLOR_GREY_BLUE, MPyNode.ATTR_TYPE_MESH:ATTR_COLOR_PINK,
                  MPyNode.ATTR_TYPE_NURBS_CURVE:ATTR_COLOR_BLUE, MPyNode.ATTR_TYPE_NURBS_SURFACE:ATTR_COLOR_BLACK,
                  MPyNode.ATTR_TYPE_STRING:ATTR_COLOR_DARK_BLUE,
                  MPyNode.ATTR_TYPE_PY:ATTR_COLOR_PY_YELLOW,
                  MPyNode.ATTR_TYPE_TIME:ATTR_COLOR_GREEN,
                  MPyNode.ATTR_TYPE_ENUM:ATTR_COLOR_BLACK}

MEL_ATTR_TYPE_MAP = {"bool":MPyNode.ATTR_TYPE_BOOL,
                     "long":MPyNode.ATTR_TYPE_INT, "short":MPyNode.ATTR_TYPE_INT, "byte":MPyNode.ATTR_TYPE_INT,
                     "float":MPyNode.ATTR_TYPE_FLOAT, "double":MPyNode.ATTR_TYPE_FLOAT,
                     "char":MPyNode.ATTR_TYPE_STRING, "string":MPyNode.ATTR_TYPE_STRING,
                     "enum":MPyNode.ATTR_TYPE_ENUM,
                     "doubleAngle":MPyNode.ATTR_TYPE_ANGLE,
                     "doubleLinear":MPyNode.ATTR_TYPE_FLOAT,
                     "time":MPyNode.ATTR_TYPE_TIME,
                     "matrix":MPyNode.ATTR_TYPE_MATRIX, "fltMatrix":MPyNode.ATTR_TYPE_MATRIX,
                     "reflectance":MPyNode.ATTR_TYPE_COLOR, "spectrum":MPyNode.ATTR_TYPE_COLOR,
                     "float2":MPyNode.ATTR_TYPE_FLOAT, "float3":MPyNode.ATTR_TYPE_FLOAT,
                     "double2":MPyNode.ATTR_TYPE_FLOAT, "double3":MPyNode.ATTR_TYPE_FLOAT,
                     "doubleArray":MPyNode.ATTR_TYPE_FLOAT, "floatArray":MPyNode.ATTR_TYPE_FLOAT,
                     "Int32Array":MPyNode.ATTR_TYPE_INT,
                     "vectorArray":MPyNode.ATTR_TYPE_VECTOR,
                     "nurbsCurve":MPyNode.ATTR_TYPE_NURBS_CURVE, "nurbsSurface":MPyNode.ATTR_TYPE_NURBS_CURVE,
                     "mesh":MPyNode.ATTR_TYPE_MESH}


class NDMainWindow(QMayaWindow):

    VERSION = "1.0.1b1"
    TITLE = "Node Designer " + VERSION

    USES_SCENE_OPENED = True
    USES_DAG_OBJECT_CREATED = True

    DEFAULT_X_POS = 200
    DEFAULT_Y_POS = 200
    DEFUALT_WIDTH = 900
    DEFAULT_HEIGHT = 600

    NODE_PARENT_CLASSES = (MPyNode,)
    
    PROFILE_CALLBACK_NAME = "emitMPyNodeProfileCallback"
    INPUT_VALUES_CALLABCK_NAME = "emitMPyNodeInputValuesCallback"
    OUTPUT_VALUES_CALLABCK_NAME = "emitMPyNodeOutputValuesCallback"
    LOG_ERROR_CALLBACK_NAME = "emitMPyNodeErrorCallback"
    LOG_TXT_CALLBACK_NAME = "emitMPyNodeTextCallback"
    
    FILE_BINARY_FILTER = "Binary (*." + MPyNode._BINARY_FILE_EXT + ")"
    FILE_ASCII_FILTER = "Ascii (*." + MPyNode._ASCII_FILE_EXT + ")"
    EXPORT_FILE_FILTERS = FILE_BINARY_FILTER + ";;" + FILE_ASCII_FILTER
    

    def __init__(self):

        super(NDMainWindow, self).__init__()
        
        self._cur_py_node = None

        self._v_layout = None
        self._h_splitter = None
        self._v_splitter = None

        self._save_to_file_action = None
        self._export_to_file_action = None
        self._import_from_file_action = None
        self._new_node_action = None
        self._save_node_action = None
        self._save_all_nodes_action = None

        self._file_menu = None
        self._node_menu = None

        self._main_tool_bar = None
        self._script_tab_widget = None
        self._panel_tab_widget = None
        self._attributes_widget = None
        self._variables_widget = None
        self._scene_tree = None
        self._tools_tab_widget = None
        self._log_widget = None
        self._profile_widget = None
        self._watch_var_values_widget = None
        
        self._callback_array = om.MCallbackIdArray()

        self.setDocumentMode(True) ##---does this help keep focus?...probably not

        ##---create a blank master widget to be parent of all ui widgets----##
        self._main_widget = QWidget(self)
        self.setCentralWidget(self._main_widget)

        self._buildActions()

        self._buildToolBar()

        self._buildLayouts()
        self._buildScriptWidget()
        self._buildPanelTabWidget()
        self._buildToolsTabWidget()

        self._buildSplitter()

        self._buildMenus()

        self._setSignals()
        self._setCallbacks()

        self.setGeometry(self.DEFAULT_X_POS, self.DEFAULT_Y_POS,
                         self.DEFUALT_WIDTH, self.DEFAULT_HEIGHT)


    def _buildToolBar(self):

        self._main_tool_bar = QToolBar(self)
        self.addToolBar(Qt.TopToolBarArea, self._main_tool_bar)

        self._main_tool_bar.addAction(self._new_node_action)
        self._main_tool_bar.addAction(self._save_node_action)
        self._main_tool_bar.addAction(self._save_all_nodes_action)


    def _setSignals(self):

        self._script_tab_widget.LOG_SIGNAL.connect(self._log_widget.write)

        self._script_tab_widget.currentChanged.connect(self._scriptTabChanged)

        self._attributes_widget.LOG_SIGNAL.connect(self._log_widget.write)
        self._attributes_widget.SCRIPT_SIGNAL.connect(self.writeScriptToLog)
        self._attributes_widget.NODE_RENAME_SIGNAL.connect(self.nodeRenamedEvent)

        self._scene_tree.itemClicked.connect(self.sceneSelectChangeEvent)
        self._scene_tree.itemDoubleClicked.connect(self.sceneDoubleClickEvent)

        self.SCENE_OPENED.connect(self.sceneOpenRefresh)
        #self.DAG_OBJECT_CREATED.connect(self.testCreateNode)
        
        self._variables_widget.LOG_SIGNAL.connect(self._log_widget.write)
        
        
    def _setCallbacks(self):
        
        self._callback_array.append(om.MUserEventMessage.addUserEventCallback(self.PROFILE_CALLBACK_NAME, self._onLogProfile, None))
        self._callback_array.append(om.MUserEventMessage.addUserEventCallback(self.INPUT_VALUES_CALLABCK_NAME, self._onWatchInputs, None))
        self._callback_array.append(om.MUserEventMessage.addUserEventCallback(self.LOG_ERROR_CALLBACK_NAME, self._onLogError, None))
        self._callback_array.append(om.MUserEventMessage.addUserEventCallback(self.LOG_TXT_CALLBACK_NAME, self._onLogText, None))
        
        
    def _onLogProfile(self, data):
        
        if self._cur_py_node and self._cur_py_node == MNode(data[0]):
            self._profile_widget._onLogProfile(self._cur_py_node, data[1])
            
        else:
            self._profile_widget._onLogProfile()
            
            
    def _onWatchInputs(self, data):
        
        if self._cur_py_node and self._cur_py_node == MNode(data[0]):
            self._watch_var_values_widget._onWatchVariables(self._cur_py_node, data[1])
            
        else:
            self._watch_var_values_widget._onWatchVariables()
            
            
    def _onLogError(self, data):
        
        if self._cur_py_node and self._cur_py_node == MNode(data[0]):
            self._log_widget.write(data[1], QtLog.ERROR_TYPE)
            
            
    def _onLogText(self, data):
        
        if self._cur_py_node and self._cur_py_node == MNode(data[0]):
            self._log_widget.write(data[1])


    def sceneOpenRefresh(self):

        self._script_tab_widget.closeAllTabs()
        self._scene_tree.refresh()
        self._attributes_widget.refresh(None)
        self._variables_widget.setPyNode(None)

        self._log_widget.write("Opened scene: " + str(mc.file(q=True, sceneName=True)))


    def testCreateNode(self):

        self._log_widget.write("Node Created")
        

    def nodeRenamedEvent(self, py_node):

        self._script_tab_widget._updateTabNodeName(py_node)
        self._scene_tree.refresh()


    def _scriptTabChanged(self, tab_index):
        
        def _clearWidgets():
            self._cur_py_node = None
            self._attributes_widget.refresh(None)
            self._variables_widget.setPyNode(None)
            self._profile_widget._onNodeChanged(None)
            self._watch_var_values_widget._onNodeChanged(None)            

        if tab_index != -1:
            tab_widget = self._script_tab_widget.widget(tab_index)
            py_node = tab_widget.getMPyNode()

            if py_node:
                self._cur_py_node = py_node
                self._attributes_widget.refresh(py_node)
                self._variables_widget.setPyNode(py_node)
                self._profile_widget._onNodeChanged(py_node)
                self._watch_var_values_widget._onNodeChanged(py_node)

            else:
                _clearWidgets()
                
        else:
            _clearWidgets()


    def _buildLayouts(self):
        """
        Builds the windows main layout
        """

        self._v_layout = QVBoxLayout(self._main_widget)
        self._main_widget.setLayout(self._v_layout)


    def _buildScriptWidget(self):

        self._script_tab_widget = NDScriptTabWidget(self._main_widget)


    def _buildPanelTabWidget(self):

        self._panel_tab_widget = QTabWidget(self._main_widget)
        self._panel_tab_widget.setMovable(False)
        self._panel_tab_widget.setTabsClosable(False)

        self._buildAttributesWidget()
        self._buildStorageWidget()
        self._buildSceneTree()

        self._panel_tab_widget.setCurrentIndex(2)


    def _buildAttributesWidget(self):

        self._attributes_widget = NDAttributesWidget(self._main_widget)

        self._panel_tab_widget.addTab(self._attributes_widget, "Attributes")
        
        
    def _buildStorageWidget(self):
        
        self._variables_widget = NDVariablesWidget(self._main_widget)
        
        self._panel_tab_widget.addTab(self._variables_widget, "Storage")


    def _buildSceneTree(self):

        self._scene_tree = NDSceneTree(self._main_widget)

        self._panel_tab_widget.addTab(self._scene_tree, "Scene")

        self._scene_tree.refresh()
        
        
    def _buildToolsTabWidget(self):
        
        self._tools_tab_widget = QTabWidget(self._main_widget)
        self._tools_tab_widget.setMovable(True)
        self._tools_tab_widget.setTabsClosable(False)      
        
        self._log_widget = NDLogWidget(self._main_widget)
        self._tools_tab_widget.addTab(self._log_widget, "Log")
        
        self._profile_widget = NDProfileWidget(self._main_widget)
        self._tools_tab_widget.addTab(self._profile_widget, "Profile")
        
        self._watch_var_values_widget = NDWatchVarsWidget(self._main_widget)
        self._tools_tab_widget.addTab(self._watch_var_values_widget, "Watch")


    def _buildSplitter(self):
        """
        Builds and configures the main splitter widget
        """        

        self._v_splitter = QSplitter(Qt.Vertical, self._main_widget)
        self._h_splitter = QSplitter(Qt.Horizontal, self._main_widget)

        self._v_splitter.addWidget(self._script_tab_widget)
        self._v_splitter.addWidget(self._tools_tab_widget)

        self._h_splitter.addWidget(self._panel_tab_widget)
        self._h_splitter.addWidget(self._v_splitter)

        self._v_layout.addWidget(self._h_splitter)

        self._h_splitter.setSizes([int(self.DEFUALT_WIDTH * 0.27), int(self.DEFUALT_WIDTH * 0.72)])
        self._v_splitter.setSizes([int(self.DEFAULT_HEIGHT * 0.83), int(self.DEFAULT_HEIGHT * 0.16)])

        #self._v_splitter.setSizes((800, 1))


    def _buildActions(self):

        self._save_to_file_action = QAction("Save to File", self,
                                            statusTip="Save current node as python class", triggered=self.saveToFile)
        
        self._export_to_file_action = QAction("Export to File", self,
                                              statusTip="Export current node to a file", triggered=self.exportToFile)
        
        self._import_from_file_action = QAction("Import from File", self,
                                                statusTip="Import a node from a file", triggered=self.importFromFile)

        self._new_node_action = QAction("&New Node", self, shortcut=QKeySequence.New,
                                        statusTip="Create a new node", triggered=self.addNewNode)

        self._save_node_action = QAction("&Save Node", self, shortcut=QKeySequence(Qt.Key_F5), statusTip="Save edits to the current node",
                                         triggered=self.saveCurrentNode)

        self._save_all_nodes_action = QAction("&Save All", self,
                                              statusTip="Save edits to the all open nodes", triggered=self.saveAllNodes)


    def saveToFile(self):

        pass
    
    
    def exportToFile(self):
        
        if self._cur_py_node:
            file_path, selected_filter = QFileDialog.getSaveFileName(self, "Exporting " + self._cur_py_node.getName(),
                                                                     "", self.EXPORT_FILE_FILTERS)
            
            if file_path:
                use_binary, file_ext  = (True, MPyNode._BINARY_FILE_EXT) if selected_filter == self.FILE_BINARY_FILTER else (False, MPyNode._ASCII_FILE_EXT)
                
                if not file_path.endswith("." + file_ext):
                    file_path += "." + file_ext
                
                try:
                    self._cur_py_node.exportToFile(file_path, use_binary=use_binary)
                    
                except Exception, err:
                    err_txt = "Error exporting to file -> " + str(file_path)
                    self._log_widget.write(err_txt, QtLog.ERROR_TYPE)
                    self._onLogError((self._cur_py_node, sys.exc_info()))
                
                else:
                    self._log_widget.write("Exported to file -> " + str(file_path))
        
        else:
            self._log_widget.write("No active nodes", QtLog.ERROR_TYPE)
    
    
    def importFromFile(self):
        
        node_list = []
        
        file_paths, selected_filter = QFileDialog.getOpenFileNames(self, "Import Node ",
                                                                  "", self.EXPORT_FILE_FILTERS)
        
        if file_paths:
            for file_path in file_paths:
                try:
                    node_list.append(MPyNode.importFromFile(file_path))
                    
                except Exception, err:
                    err_txt = "Error importing file -> " + str(file_path)
                    self._log_widget.write(err_txt, QtLog.ERROR_TYPE)
                    self._onLogError((self._cur_py_node, sys.exc_info()))                 
                
        if node_list:
            self._scene_tree.refresh()  
            return node_list
        
        return None
    

    def _buildMenus(self):

        self._file_menu = self.menuBar().addMenu("&File")
        #self._file_menu.addAction(self._save_to_file_action)
        self._file_menu.addAction(self._import_from_file_action)
        self._file_menu.addAction(self._export_to_file_action)

        self._node_menu = self.menuBar().addMenu("&Node")
        self._node_menu.addAction(self._new_node_action)
        self._node_menu.addAction(self._save_node_action)
        self._node_menu.addAction(self._save_all_nodes_action)


    def addNewNode(self):

        if len(self.NODE_PARENT_CLASSES) != 1:
            self._log_widget.write("TODO: More than one parent class available")
            return None

        else:
            py_node = self.NODE_PARENT_CLASSES[0]()

            tab_widget, tab_index = self._script_tab_widget.addNewTab(py_node)
            self._script_tab_widget.setCurrentIndex(tab_index)

            self._log_widget.write("New node added: " + py_node.getName())

            self._scene_tree.refresh()

            return py_node


    def sceneDoubleClickEvent(self, item, column):

        if item:

            py_node = item.getMPyNode()

            if py_node and py_node.isValid():

                py_node.select(replace=True)

            else:
                self._log_widget.write("Cannot locate node in scene", QtLog.ERROR_TYPE)


    def sceneSelectChangeEvent(self, item, col):

        if item:

            py_node = item.getMPyNode()

            if py_node:

                tab_index = self._script_tab_widget.getIndexOfNode(py_node)

                if tab_index is not None:

                    self._script_tab_widget.setCurrentIndex(tab_index)

                else:
                    tab_widget, tab_index = self._script_tab_widget.addNewTab(py_node)

                    self._script_tab_widget.setTabText(tab_index, tab_widget._py_node.getName())
                    self._script_tab_widget.setCurrentIndex(tab_index)

                    self._log_widget.write("Editing node: " + tab_widget._py_node.getName())


    def saveCurrentNode(self):

        self._script_tab_widget.saveCurrentNode()


    def saveAllNodes(self):

        self._script_tab_widget.saveAllNodes()
        
    
    def removeCallbacks(self):
        
        om.MMessage.removeCallbacks(self._callback_array)
        
        
    def writeScriptToLog(self, func, args, kargs):
        
        log_txt = func.__name__ + "("
        
        if args:
            log_txt += ", ".join([str(arg) for arg in args]) + ", "
        
        if kargs:
            log_txt += ", ".join([str(key) + "=" + str(val) for key, val in kargs.items()])
        
        log_txt += ")"
        
        self._log_widget.write(log_txt)


    def closeEvent(self, event):
        """
        OVERRIDE... check for unsaved scripts
        """

        close_ok = self._script_tab_widget._tabCloseCheckAll()

        if close_ok:
            
            self.removeCallbacks()
            
            super(NDMainWindow, self).closeEvent(event)
            event.accept()

        else:
            event.ignore()


class NDScriptTabWidget(QTabWidget):

    NEW_TAB_NAME = "untitled"
    UNSVAED_CHAR = "*"

    LOG_SIGNAL = Signal(str, int)


    def __init__(self, parent=None):

        super(NDScriptTabWidget, self).__init__(parent)

        self.setMovable(True)
        self.setTabsClosable(True)
        self.setDocumentMode(True) ##---does this help keep focus?...probably not

        self._setSignals()


    def _updateTabNodeName(self, py_node):

        tab_count = self.count()

        if tab_count:

            for i in xrange(tab_count):

                widget = self.widget(i)

                if widget._py_node == py_node:
                    self.setTabText(i, py_node.getName())


    def _setSignals(self):

        self.tabCloseRequested.connect(self.closeTabEvent)


    def closeAllTabs(self):

        num_tabs = self.count()

        if num_tabs:
            for i in reversed(range(num_tabs)):
                self.removeTab(i)


    def addNewTab(self, py_node):

        tab_widget = NDScriptEditor(self, py_node)
        tab_index = self.addTab(tab_widget, self.NEW_TAB_NAME + self.UNSVAED_CHAR)

        self.setTabText(tab_index, py_node.getName())

        tab_widget.LOG_SIGNAL.connect(self.LOG_SIGNAL.emit)

        return tab_widget, tab_index


    def hasExpressionChanged(self, tab_index):

        tab_widget = self.widget(tab_index)

        return tab_widget.hasUnsavedChanges()


    def _tabCloseCheckAll(self):

        tab_count = self.count()

        if tab_count:
            for tab_index in xrange(tab_count):

                if self.hasExpressionChanged(tab_index):
                    tab_widget = self.widget(tab_index)

                    py_node = tab_widget.getMPyNode()

                    do_save = self.showNodeSaveDlg(py_node.getName()) if py_node else self.showNewNodeSaveDlg()

                    if do_save == QMessageBox.Save:
                        self._saveTabNode(tab_widget)

                    if do_save == QMessageBox.Cancel:
                        return False

        return True


    def _tabCloseCheck(self, tab_index):
        """
        When the user attempts to close a script tab this returns bool whether the given tab should close
        """

        ##---if the script in the tab matches the expression in the node, just return True----##
        if not self.hasExpressionChanged(tab_index):
            return True

        tab_widget = self.widget(tab_index)

        py_node = tab_widget.getMPyNode()

        if py_node and not py_node.isValid():
            py_node = None

        do_save = self.showNodeSaveDlg(py_node.getName()) if py_node else self.showNewNodeSaveDlg()

        if do_save == QMessageBox.Save:
            self._saveTabNode(tab_widget)
            return True

        if do_save == QMessageBox.Cancel:
            return False

        elif do_save == QMessageBox.Discard:
            return True

        return False


    def _saveTabNode(self, tab_widget):

        py_node = tab_widget.getMPyNode()

        if not py_node or not py_node.isValid():
            tab_widget._py_node = MPyNode()

        txt = tab_widget.getText()

        if txt:
            txt = txt.replace('\t', MPyNode._CODE_TAB)
        else:
            txt = ""

        tab_widget._py_node.setExpression(txt)

        self.LOG_SIGNAL.emit("Node saved: " + tab_widget._py_node.getName(), 2)


    def getIndexOfNode(self, py_node):

        tab_count = self.count()

        if tab_count:
            for i in xrange(tab_count):

                tab_node = self.widget(i).getMPyNode()

                if tab_node == py_node:
                    return i

        return None


    def showNodeSaveDlg(self, node_name):

        dlg = QMessageBox()
        dlg.setText(str(node_name) + " has been modified")
        dlg.setInformativeText("Save to changes to node?")
        dlg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        dlg.setDefaultButton(QMessageBox.Save)

        return dlg.exec_()        


    def showNewNodeSaveDlg(self):

        dlg = QMessageBox()
        dlg.setText("There is no scene node associated with this script.")
        dlg.setInformativeText("Save to new node?")
        dlg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        dlg.setDefaultButton(QMessageBox.Save)

        return dlg.exec_()


    def closeTabEvent(self, tab_index):

        close = self._tabCloseCheck(tab_index)

        if close:
            self.removeTab(tab_index)


    def saveCurrentNode(self):

        tab_widget = self.currentWidget()

        if tab_widget:
            self._saveTabNode(tab_widget)

        else:
            self.LOG_SIGNAL.emit("Nothing to save.", 1)


    def saveAllNodes(self):

        tab_count = self.count()

        if tab_count:

            for tab_index in xrange(tab_count):
                tab_widget = self.widget(tab_index)

                self._saveTabNode(tab_widget)


class NDScriptEditor(QtPythonEditor):

    TAB_STOP = 4

    LOG_SIGNAL = Signal(str, int)


    def __init__(self, parent=None, py_node=None):

        super(NDScriptEditor, self).__init__(parent)

        self._py_node = py_node

        if self._py_node:
            exp_str = self._py_node.getExpression()

            self.setText(exp_str)


    def getMPyNode(self):
        
        try:
            if not self._py_node.isValid():
                self._py_node = None
                
        except:
            self._py_node = None

        return self._py_node


    def setText(self, txt):

        if txt:
            self.document().setPlainText(txt)

        else:
            self.document().setPlainText("")

    def getText(self):

        txt = self.document().toPlainText()

        if txt:
            return txt

        return None


    def hasUnsavedChanges(self):

        if self._py_node:

            if self._py_node.isValid():

                node_expr = self._py_node.getExpression()
                expr_txt = self.getText()

                if expr_txt != node_expr:
                    return True

            else:
                self.LOG_SIGNAL.emit("Error: node is no longer valid")
                return True

        return False
    
    
class NDToolsTabWidget(QTabWidget):
    
    def __init__(self, parent=None):
    
        super(NDToolsTabWidget, self).__init__(parent)
    

class NDVariablesWidget(QWidget):
    
    LOG_SIGNAL = Signal(str, int)
    
    
    def __init__(self, parent=None):
        
        super(NDVariablesWidget, self).__init__(parent)
        
        self._py_node = None
        
        self._button_panel = None
        self._variable_tree = None
        
        self._v_layout = QVBoxLayout(self)
        
        self.setLayout(self._v_layout)
        self._v_layout.setSpacing(0)
        self._v_layout.setContentsMargins(0, 0, 0, 0)
        
        
    def _buildButtonPanel(self):
        
        self._button_panel = QFrame(self)
        button_layout = QHBoxLayout(self._button_panel)
        
        plus_var_button = QPushButton("+", self._button_panel)
        plus_var_button.setMinimumSize(QSize(20, 20))
        plus_var_button.setMaximumSize(QSize(20, 20))
        plus_var_button.clicked.connect(self._onAddVariable)
        
        minus_var_button = QPushButton("-", self._button_panel)
        minus_var_button.setMinimumSize(QSize(20, 20))
        minus_var_button.setMaximumSize(QSize(20, 20))
        minus_var_button.clicked.connect(self._onRemoveVariable)
        
        refresh_button = QPushButton("Refresh", self._button_panel)
        refresh_button.setMaximumHeight(20)
        refresh_button.clicked.connect(self._onRefresh)
        
        button_layout.addWidget(plus_var_button)
        button_layout.addWidget(minus_var_button)
        button_layout.addWidget(refresh_button)
        button_layout.addStretch(1)
        button_layout.setSpacing(3)
        button_layout.addWidget(refresh_button)
        
        self._button_panel.setLayout(button_layout)
        self._v_layout.addWidget(self._button_panel)
        
        
    def _onRefresh(self):
        
        self.refresh()
        
        
    def _onAddVariable(self):
        
        self._variable_tree.addNewItem()
        
        
    def _onRemoveVariable(self):
        
        sel_item = self._variable_tree.currentItem()
        
        if sel_item:
            root = self._variable_tree.invisibleRootItem()
            
            for item in self._variable_tree.selectedItems():
                item.delete()
                root.removeChild(item)
        
        
    def setPyNode(self, py_node=None):
        
        self._py_node = py_node
        
        self.refresh()
        
    
    def refresh(self):
        
        self.clear()
        
        if self._py_node:
            
            self._buildButtonPanel()
            
            self._variable_tree = NDVariablesTree(self, py_node=self._py_node)
            self._v_layout.addWidget(self._variable_tree)
            
            self._variable_tree.refresh()
            self._variable_tree.LOG_SIGNAL.connect(self.LOG_SIGNAL.emit)
        
        
    def clear(self):

        if self._variable_tree:
            self._variable_tree.deleteLater()
            self._variable_tree = None
            
        if self._button_panel:
            self._button_panel.deleteLater()
            self._button_panel = None            
        
        
class NDVariablesTree(QTreeWidget):
    
    COLUMN_NAMES = ("Name", "Value")
    LOG_SIGNAL = Signal(str, int)
    VAR_IGNORE_LIST = ("",)
    
    
    def __init__(self, parent=None, py_node=None):

        super(NDVariablesTree, self).__init__(parent)
        
        self._py_node = py_node
    
        self.setColumnCount(len(self.COLUMN_NAMES))
        self.setHeaderItem(QTreeWidgetItem(self.COLUMN_NAMES))
        self.setSelectionMode(QAbstractItemView.ContiguousSelection)
        
        
    def addNewItem(self):
        
        tree_item = NDVariablesTreeItem(self, self._py_node, None, None, self.LOG_SIGNAL)
        
        tree_item.setSelected(True)
        
        
    def refresh(self, str_exp="*"):

        self.clear()

        if self._py_node:
            
            var_map = self._py_node.getStoredVariables()
            
            if var_map:
                for var_name in sorted(var_map.keys()):
                    
                    NDVariablesTreeItem(self, self._py_node, var_name, var_map[var_name], self.LOG_SIGNAL)
        
        
class NDVariablesTreeItem(QTreeWidgetItem):
    
    DEFAULT_FLAGS = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
    

    def __init__(self, parent, py_node, var_name, var_val, log_sig=None):

        super(NDVariablesTreeItem, self).__init__(parent)

        self._py_node = py_node
        self._log_signal = log_sig
        
        self._var_name = None
        self._var_name_str = ""
        self._var_val = None
        self._var_val_str = "None"
        
        self.setFlags(self.DEFAULT_FLAGS)
        
        self.refresh(var_name, var_val)
        
        
    def _setVarName(self, var_name):
        
        if (var_name is not None) and (var_name != self._var_name):
            
            ##---make sure that there isn't a variable already set with that name---##
            if (self._var_name is None) or (not self._py_node.hasStoredVariable(var_name)):
                cur_val = None
                
                ##----if this item represents a variable that is already named....replace it with this one---##
                if (self._var_name is not None) and (self._py_node.hasStoredVariable(self._var_name)):
                    cur_val = self._py_node.getStoredVariables()[self._var_name]
                    self._py_node.removeStoredVariable(self._var_name)
                
                self._var_name = str(var_name) if var_name else None
                self._var_name_str = str(var_name) if var_name else ""
                
                if self._var_name_str:
                    self._py_node.setStoredVariable(self._var_name, cur_val)
                    
                    if self._log_signal:
                        self._log_signal.emit("Variable named: " + str(var_name), 2)
                    
            else:
                self._log_signal.emit("Variable name is invalid or conflicts with existing variable: " + str(var_name), 1)
        
        return self._var_name_str    
        
        
    def _setVarValue(self, var_val):
        
        self._var_val = var_val
        self._var_val_str = ""
        
        if type(var_val) in (str, unicode, chr, unichr):
            self._var_val_str = "\"" + str(var_val) + "\""
            
        else:
            self._var_val_str = str(var_val)
            
        if self._var_name is not None:
            self._py_node.setStoredVariable(self._var_name, var_val)
            
            if self._log_signal:
                self._log_signal.emit("Variable set: " + str(self._var_name) + " = " + str(var_val), 2)            
            
        return self._var_val_str
    
    
    def setName(self, var_name):
        
        name_str = self._setVarName(var_name)
        self.setText(0, name_str)
        
        
    def setValue(self, var_val):
        
        val_str = self._setVarValue(var_val)
        
        self.setText(1, val_str)
    
    
    def refresh(self, var_name=None, var_val=None):
        
        self.setName(var_name)
        self.setValue(var_val)
        
        
    def delete(self):
        
        if self._var_name and self._py_node.hasStoredVariable(self._var_name):
            self._py_node.removeStoredVariable(self._var_name)
        
        
    def setData(self, col, role, data):
        
        if col == 0:
            
            var_name_str = self._setVarName(data)
            
            super(NDVariablesTreeItem, self).setData(col, role, var_name_str)
            
        else:
            try:
                py_data = eval(data)
                
            except Exception, err:
                
                err_txt = "Error: invalid python value given -> " + str(data) + "\n" + str(err)
                
                if self._log_signal:
                    self._log_signal.emit(err_txt, 1)
                    
                else:
                    print err_txt
                    
            else:
                var_val_str = self._setVarValue(py_data)
                
                super(NDVariablesTreeItem, self).setData(col, role, var_val_str)
                
                
class NDProfileWidget(QWidget):

    
    def __init__(self, parent=None):

        super(NDProfileWidget, self).__init__(parent)
        
        self._py_node = None
        self._profile_cb = None
        self._profile_table = None
        
        self._v_layout = QVBoxLayout(self)
        self.setLayout(self._v_layout)
        
        self._buildCheckbox()
        self._buildTable()
        
    
    def _buildCheckbox(self):
        
        self._profile_cb = QCheckBox(self)
        self._profile_cb.setText("Run Profiler")
        self._profile_cb.setChecked(False)
        self._profile_cb.setEnabled(False)
        self._v_layout.addWidget(self._profile_cb)
        
        self._profile_cb.stateChanged.connect(self._onToggleProfiler)
        
    
    def _buildTable(self):
        
        self._profile_table = QtPyProfileTable(self)
        self._v_layout.addWidget(self._profile_table)
        
    
    def _onToggleProfiler(self, state):
        
        self._profile_table.refresh()
        
        if self._py_node:
            run_profiler = state == Qt.Checked
            self._py_node.setStoredVariable(MPyNode._RUN_PROFILER_VAR_NAME, run_profiler)
        
        
    def _onNodeChanged(self, py_node):
        """
        Designed to be called when the UI changes its current node. This resets the profiler widget to relfect the
        node change.
        """
        
        if py_node:
            self._py_node = py_node
            self._profile_cb.setEnabled(True)
            node_vars = self._py_node.getStoredVariables()
            
            if node_vars and MPyNode._RUN_PROFILER_VAR_NAME in node_vars:
                self._profile_cb.setChecked(node_vars[MPyNode._RUN_PROFILER_VAR_NAME])
            
            else:
                self._profile_cb.setChecked(False)
                
        else:
            self._py_node = None
            self._profile_cb.setChecked(False)
            self._profile_cb.setEnabled(False)
                
        self._profile_table.refresh()
        
        
    def _onLogProfile(self, py_node=None, data=None):
        
        if py_node:
            if data:
                data = sorted(data,key=lambda x: x.totaltime)[::-1] # [evignola] Sort data by total time, highest to lowest
                self._profile_table.refresh(data)
        else:  
            self._profile_table.refresh()
    

class NDAttributesWidget(QWidget):

    LOG_SIGNAL = Signal(str, int)
    SCRIPT_SIGNAL = Signal(object, tuple, dict)
    NODE_RENAME_SIGNAL = Signal(object)


    def __init__(self, parent=None):

        super(NDAttributesWidget, self).__init__(parent)

        self._py_node = None
        self._name_field = None
        self._input_frame = None
        self._output_frame = None

        self._v_layout = QVBoxLayout(self)
        self.setLayout(self._v_layout)


    def _setSignals(self):

        if self._input_frame:
            self._input_frame.LOG_SIGNAL.connect(self.LOG_SIGNAL.emit)
            self._input_frame.SCRIPT_SIGNAL.connect(self.SCRIPT_SIGNAL.emit)

        if self._output_frame:
            self._output_frame.LOG_SIGNAL.connect(self.LOG_SIGNAL.emit)
            self._output_frame.SCRIPT_SIGNAL.connect(self.SCRIPT_SIGNAL.emit)


    def _nodeNameChanged(self):

        if self._py_node:

            txt = self._name_field.text()
            orig_node_name = self._py_node.getName()

            if txt != orig_node_name:

                try:
                    self._py_node.rename(txt)

                except Exception, err:
                    self.LOG_SIGNAL.emit(err.message, 1)

                node_name = self._py_node.getName()
                self._name_field.setText(node_name)

                self.NODE_RENAME_SIGNAL.emit(self._py_node)

                self.LOG_SIGNAL.emit("Rename \"" + orig_node_name + "\" to \"" + self._py_node.getName() + "\"", 0)


    def refresh(self, py_node=None):

        self.clear()

        if py_node:
            self._py_node = py_node

            self._buildTextField(py_node)
            self._buildInputFrame(py_node)
            self._buildOutputFrame(py_node)

            self._input_frame.refresh()
            self._output_frame.refresh()

        else:
            self._py_node = None

        self._setSignals()


    def _buildInputFrame(self, py_node):

        self._input_frame = NDInputAttrTree(self, py_node)

        self._v_layout.addWidget(self._input_frame)


    def _buildOutputFrame(self, py_node):

        self._output_frame = NDOutputAttrTree(self, py_node)

        self._v_layout.addWidget(self._output_frame)


    def _buildTextField(self, py_node):

        self._name_field = QLineEdit(self)

        self._v_layout.addWidget(self._name_field)

        self._name_field.returnPressed.connect(self._nodeNameChanged)
        self._name_field.editingFinished.connect(self._nodeNameChanged)
        self._name_field.setText(py_node.getName())


    def clear(self):

        if self._name_field:
            self._name_field.deleteLater()
            self._name_field = None

        if self._input_frame:
            self._input_frame.deleteLater()
            self._input_frame = None

        if self._output_frame:
            self._output_frame.deleteLater()
            self._output_frame = None


class NDInputAttrTree(QTreeWidget):

    ATTR_CATEGORY = "input"
    
    REMOVE_CONNECTIONS_FUNC = "removeInputConnections"
    
    NEW_ATTR_TYPES = MPyNode.listValidInputTypes()
    ATTR_DEFAULT_TYPE = MPyNode.ATTR_TYPE_FLOAT
    ADD_ATTR_FUNC_NAME = "addInputAttr"
    LIST_ATTR_FUNC_NAME = "getInputAttrMap"
    REMOVE_ATTR_FUNC_NAME = "deleteInputAttr"

    ATTR_ADDED_SIGNAL = Signal(str)
    LOG_SIGNAL = Signal(str, int)
    SCRIPT_SIGNAL = Signal(object, tuple, dict)


    def __init__(self, parent, py_node):

        super(NDInputAttrTree, self).__init__(parent)

        self._py_node = py_node
        self._add_attr_action = None
        self._delete_attr_action = None
        self._connect_attr_action = None
        self._remove_inputs_action = None

        self.setColumnCount(1)
        self.setHeaderItem(QTreeWidgetItem([self.ATTR_CATEGORY.upper()]))

        self.setFrameStyle(QFrame.Panel | QFrame.Plain)
        self.setLineWidth(1)

        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.itemDoubleClicked.connect(self.attrDoubleClickEvent)

        self._buildActions()


    def _buildActions(self):

        self._add_attr_action = QAction("Add New " + self.ATTR_CATEGORY.capitalize(), self,
                                        statusTip="Create a new " + self.ATTR_CATEGORY, triggered=self.showAddAttrDlg)

        self._delete_attr_action = QAction("Delete " + self.ATTR_CATEGORY.capitalize(), self,
                                           statusTip="Delete " + self.ATTR_CATEGORY + " from selected node", triggered=self.deleteSelectedAttrs)            

        self._connect_attr_action = QAction("Connect Attrs to " + self.ATTR_CATEGORY.capitalize(), self,
                                            statusTip="Connect attributes from selected node(s)", triggered=self.showConnectAttrDlg)

        self._remove_inputs_action = QAction("Diconnect All " + self.ATTR_CATEGORY.capitalize() + "s", self,
                                             statusTip="Diconnect all connections to this attribute", triggered=self.removeAllConnections)


    def attrDoubleClickEvent(self, item, column):

        if item:

            if self._py_node and self._py_node.isValid():

                self._py_node.select(replace=True)

            else:
                self.LOG_SIGNAL.emit("Cannot locate node in scene", QtLog.ERROR_TYPE)


    def contextMenuEvent(self, event):

        menu = QMenu(self)
        menu.addAction(self._add_attr_action)

        sel_items = self.selectedItems()

        if sel_items:
            menu.addAction(self._delete_attr_action)
            menu.addSeparator()
            menu.addAction(self._connect_attr_action)
            menu.addAction(self._remove_inputs_action)

        action = menu.exec_(self.mapToGlobal(event.pos()))


    def removeAllConnections(self):

        sel_items = self.selectedItems()

        if sel_items:

            for item in sel_items:
                attr_name = item.text(0).split()[0]

                try:
                    func = getattr(self._py_node, self.REMOVE_CONNECTIONS_FUNC)
                    func(attr_name)

                except Exception, err:
                    self.LOG_SIGNAL.emit(err.message, 1)

                else:
                    self.LOG_SIGNAL.emit(self.ATTR_CATEGORY + "s disconnected from: " + attr_name, 2)

        else:
            self.LOG_SIGNAL.emit("No attributes selected", 1)        


    def showConnectAttrDlg(self):

        sel_items = self.selectedItems()

        if sel_items:
            nodes = MNode.ls(sl=True)

            if nodes:

                attr_name = sel_items[0].text(0).split()[0]

                dlg = NDConnectInputAttrDialog(self, self._py_node, attr_name, nodes)
                result = dlg.exec_()

                if result:
                    other_attr = dlg.getAttrName()
                    append = dlg.getAppendConnect()
                    self.connectAttrEvent(attr_name, nodes, other_attr, append=append)

            else:
                self.LOG_SIGNAL.emit("Nothing selected", 1)

        else:
            self.LOG_SIGNAL.emit("No attributes selected", 1)


    def showAddAttrDlg(self):

        dlg = NDAddAttrDialog(self, self.NEW_ATTR_TYPES, self._py_node.getName(), self.ATTR_DEFAULT_TYPE)
        dlg.ADD_ATTR_SIGNAL.connect(self.addNewAttrEvent)

        result = dlg.exec_()

        if result:
            attr_name = dlg.getAttrName()
            attr_type = dlg.getAttrType()
            is_array = dlg.getIsArray()
            display_option = dlg.getAttrDisplayOptions(attr_type, is_array)

            self.addNewAttrEvent(attr_name, attr_type, display_option, is_array)


    def addNewAttrEvent(self, attr_name, attr_type, display_option, is_array):

        if attr_name:
            if not self._py_node.hasAttr(attr_name):
                
                ##-----make sure the attribute name is not a Python keyword or builtin---##
                if (not attr_name in keyword.kwlist) and (not attr_name in dir(__builtin__)):
                
                    add_func = getattr(self._py_node, self.ADD_ATTR_FUNC_NAME)
    
                    add_func(attr_name, attr_type, is_array=is_array, **display_option)
    
                    self.refresh()
    
                    self.ATTR_ADDED_SIGNAL.emit(attr_name)
                    self.LOG_SIGNAL.emit("Attribute '" + attr_name + "' added to node " + self._py_node.getName() , 2)
                    self.SCRIPT_SIGNAL.emit(add_func, (attr_type, is_array), display_option)
                    
                    ##---automatically hoook up default time nodes as input if a time input is created---##
                    if attr_type == MPyNode.ATTR_TYPE_TIME:
                        time_nodes = MNode.ls(type="time")
                        
                        if time_nodes:
                            time_nodes[0].connectAttr("outTime", self._py_node, attr_name)
                    
                else:
                    self.LOG_SIGNAL.emit("Cannot add attribute. The name \"" + attr_name + "\" is Python keyword or builtin", 1)

            else:
                self.LOG_SIGNAL.emit("Node already has an attribute named: " + attr_name, 1)

        else:
            self.LOG_SIGNAL.emit("Cannot add an " + self.ATTR_CATEGORY + " attr with no name.", 1)


    def connectAttrEvent(self, py_node_attr, other_nodes, other_attr, append=True):

        def doConnectAttr(py_node, py_node_attr, other_node, other_attr, force_connect=True):
            """
            Internal function for wrapping the call to connectAttr in a try block
            """

            try:
                other_node.connectAttr(other_attr, py_node, py_node_attr, force=force_connect)

            except Exception, err:
                self.LOG_SIGNAL.emit(None, QtLog.LAST_EXCEPTION_TYPE)

            else:
                self.LOG_SIGNAL.emit(other_node.getName() + "." + other_attr + " -------> " + py_node.getName() + "." + py_node_attr, QtLog.SUCCESS_TYPE)

        if other_nodes:
            if other_attr:

                is_array = False if not self._py_node.getInputAttrMap()[py_node_attr].has_key(MPyNode.ATTR_MAP_ARRAY_KEY) else True

                if not is_array:
                    doConnectAttr(self._py_node, py_node_attr, other_nodes[0], other_attr)

                else:

                    if not append:
                        for i, other_node in enumerate(other_nodes):
                            doConnectAttr(self._py_node, py_node_attr + "[" + str(i) + "]", other_node, other_attr, force_connect=True)

                    else:
                        array_size = self._py_node.getAttr(py_node_attr, size=True)

                        for i, other_node in enumerate(other_nodes, array_size):
                            doConnectAttr(self._py_node, py_node_attr + "[" + str(i) + "]", other_node, other_attr, force_connect=True)

            else:
                self.LOG_SIGNAL.emit("No source attribute given.", 1)

        else:
            self.LOG_SIGNAL.emit("No source nodes given.", 1)


    def deleteSelectedAttrs(self):

        sel_items = self.selectedItems()

        if sel_items:

            for item in sel_items:

                attr_name = item.text(0)

                if attr_name:
                    if self._py_node and self._py_node.isValid():

                        attr_name = attr_name.split("[")[0].strip()

                        list_func = getattr(self._py_node, self.LIST_ATTR_FUNC_NAME)
                        attrs = list_func()

                        if attrs and attr_name in attrs:

                            delete_func = getattr(self._py_node, self.REMOVE_ATTR_FUNC_NAME)

                            delete_func(attr_name)

        self.refresh()


    def refresh(self):

        self.clear()
        list_func = getattr(self._py_node, self.LIST_ATTR_FUNC_NAME)
        attr_map = list_func()

        if attr_map:
            ##---default alpha order on attribute names---##
            attr_names = attr_map.keys()
            attr_names.sort()

            for attr_name in attr_names:
                attr_data = attr_map[attr_name]

                attr_type = attr_data[MPyNode._ATTR_MAP_TYPE_KEY]
                is_array = False if not attr_data.has_key(MPyNode.ATTR_MAP_ARRAY_KEY) else True
                icon_clr = ATTR_COLOR_MAP[attr_type] if ATTR_COLOR_MAP.has_key(attr_type) else ATTR_COLOR_DEFAULT

                self.addTopLevelItem(NDAttrTreeItem(self, attr_name, attr_type, is_array=is_array, icon_clr=icon_clr))


class NDOutputAttrTree(NDInputAttrTree):

    ATTR_CATEGORY = "output"
    
    REMOVE_CONNECTIONS_FUNC = "removeOutputConnections"

    NEW_ATTR_TYPES = MPyNode.listValidOutputTypes()
    ADD_ATTR_FUNC_NAME = "addOutputAttr"
    LIST_ATTR_FUNC_NAME = "getOutputAttrMap"
    REMOVE_ATTR_FUNC_NAME = "deleteOutputAttr"


    def showConnectAttrDlg(self):
        """
        Overrides base class method.
        """

        ##---what attributes does the use have selected?---##
        sel_items = self.selectedItems()

        if sel_items:
            ##---what maya nodes does the user have selected---##
            nodes = MNode.ls(sl=True)

            if nodes:

                attr_name = sel_items[0].text(0).split()[0]

                dlg = NDConnectOutputAttrDialog(self, self._py_node, attr_name, nodes)
                result = dlg.exec_()

                if result:
                    other_attr = dlg.getAttrName()
                    append = dlg.getAppendConnect()
                    replace = dlg.getReplaceConnect()
                    self.connectAttrEvent(attr_name, nodes, other_attr, append=append, replace=replace)

            else:
                self.LOG_SIGNAL.emit("Nothing selected", 1)

        else:
            self.LOG_SIGNAL.emit("No attributes selected", 1)


    def connectAttrEvent(self, py_node_attr, other_nodes, other_attr, append=False, replace=True):
        
        if other_nodes:
            if other_attr:
                is_array = False if not self._py_node.getOutputAttrMap()[py_node_attr].has_key(MPyNode.ATTR_MAP_ARRAY_KEY) else True
                
                ##---figure out what output attrs to use----##
                out_attrs = [py_node_attr]
                if is_array:
                    if not append:
                        out_attrs = [py_node_attr + "[" + str(i) + "]" for i in range(len(other_nodes))] 
                        
                    else:
                        start_i = self._py_node.getAttr(py_node_attr, size=True)
                        end_i = start_i + len(other_nodes)
                        out_attrs = [py_node_attr + "[" + str(i) + "]" for i in range(start_i, end_i)]
                
                ##---remove any existing output connections if "replace" is on-----##
                if replace:
                    for out_attr in out_attrs:
                        self._py_node.removeOutputConnections(out_attr)
                
                for i, other_node in enumerate(other_nodes):
                    
                    dst_is_array = other_node.attributeQuery(other_attr, multi=True)
                    if not is_array:
                        src_attrs = [out_attrs[0]] if not dst_is_array else out_attrs
                    else:
                        src_attrs = [out_attrs[i]] if not dst_is_array else out_attrs
                        
                    dst_attrs =  [other_attr] if not dst_is_array else [other_attr + "[" + str(in_i) + "]" for in_i in range(len(out_attrs))]
                    
                    for src_attr, dst_attr in map(None, src_attrs, dst_attrs):
                        
                        if (not src_attr is None) and (not dst_attr is None):
                            try:
                                self._py_node.connectAttr(src_attr, other_node, dst_attr, force=True)
                            
                            except Exception, err:
                                self.LOG_SIGNAL.emit(None, QtLog.LAST_EXCEPTION_TYPE)

                            else:
                                self.LOG_SIGNAL.emit(self._py_node.getName() + "." + src_attr + " -------> "\
                                                     + other_node.getName() + "." + dst_attr, QtLog.SUCCESS_TYPE)
                            
            else:
                self.LOG_SIGNAL.emit("No source attribute given.", 1)

        else:
            self.LOG_SIGNAL.emit("No source nodes given.", 1)    


class NDAttrTreeItem(QTreeWidgetItem):

    def __init__(self, parent, attr_name, attr_type, is_array=False, icon_clr=(80, 230, 80)):

        super(NDAttrTreeItem, self).__init__(parent)

        item_txt = attr_name if not is_array else attr_name + " [ ]"

        self.setIcon(0, NDAttrIcon(icon_clr))
        self.setText(0, item_txt)
        self.setToolTip(0, attr_type)


class NDAttrIcon(QIcon):

    def __init__(self, clr):

        pixmap = QPixmap(10, 10)
        pixmap.fill(QColor(*clr))

        super(NDAttrIcon, self).__init__(pixmap)


class NDConnectInputAttrDialog(QDialog):

    LIST_ATTR_OPTIONS = [{"connectable":True, "read":True, "hasData":True},
                         {"connectable":True, "read":True, "hasData":True, "multi":True}]

    VALID_ATTR_TYPES = MEL_ATTR_TYPE_MAP.keys()

    VALID_ATTR_TYPES_MAP = MPyNode._INPUT_TYPES_MAP


    def __init__(self, parent, py_node, py_node_attr, other_nodes):

        super(NDConnectInputAttrDialog, self).__init__()

        self._py_node = py_node
        self._py_node_attr = py_node_attr
        self._attr_type = None
        self._other_nodes = other_nodes

        self._attr_list_frame = None
        self._button_frame = None        

        self._filter_field = None
        self._list_widget = None

        self._force_cb = None

        self._main_layout = QVBoxLayout(self)
        self.setLayout(self._main_layout)

        self._queryNodeAttrType()

        self._buildAttrList()
        self._refreshAttrList()
        self._buildButtonFrame()

        self.setWindowTitle("Connect Attributes: " + py_node.getName())


    def _queryNodeAttrType(self):

        attr_map = self._py_node.getInputAttrMap()

        self._attr_type = attr_map[self._py_node_attr][MPyNode._ATTR_MAP_TYPE_KEY]


    def _getFilteredAttrs(self, node, search_str=None):
        """
        Main attribute filtering method used by the connect attr dialog windows

        **node**		*string* name or *MNode* of the node to filter attributes for

        **search_str**	optional *string* to filter attributes by name. Does not currently support regex style searches

        **RETURNS**		Tuple of *string* attributes or *None*
        """

        def _validateAttr(cur_node, attr_name, valid_types, search):

            if not "." in attr_name:

                if cur_node.getAttr(attr_name, type=True) != "TdataCompound":
                    return (cur_node.getAttr(attr_name, type=True) in valid_types) and (search.lower() in attr_name.lower())

                elif cur_node.getAttr(attr_name, size=True):
                    try:
                        attr_data_type = cur_node.getAttr(attr_name + "[0]", type=True)
                    except:
                        return False

                    return (attr_data_type in valid_types) and (search.lower() in attr_name.lower())

            return False

        if not search_str:
            search_str = ""

        attrs = set()
        for LIST_ATTR_OPTIONS in self.LIST_ATTR_OPTIONS:
            for att in node.listAttr(**LIST_ATTR_OPTIONS):
                attrs.add(att)

        valid_attr_types = self.VALID_ATTR_TYPES_MAP[self._attr_type] if self._attr_type in self.VALID_ATTR_TYPES_MAP else self.VALID_ATTR_TYPES

        ##----filter the list. Always filter child attrbutes. eaxmple "attr.childAttr.grandchildAttr", etc----##
        attrs = [attr for attr in attrs if _validateAttr(node, attr, valid_attr_types, search_str)]


        # If attributes are present, filter potential multi attribute duplicates and return
        if attrs:
            attrs = sorted(attrs)
            multi = [x for x in sorted(attrs) if '[' in x]

            for m in multi:
                try:
                    i = attrs.index(m.split('[')[0])
                    attrs.pop(i)
                except:
                    pass

            return tuple(attrs)

        return None


    def _refreshAttrList(self, search_str=None):

        self._list_widget.clear()

        if self._other_nodes:
            attr_list = self._getFilteredAttrs(self._other_nodes[-1], search_str=search_str)

            if attr_list:
                for attr in sorted(attr_list):
                    attr_type = self._other_nodes[-1].getAttr(attr, type=True)

                    attr_item = QTreeWidgetItem(self._list_widget)
                    attr_item.setIcon(0, NDAttrIcon(self._getAttrColor(attr_type)))
                    attr_item.setText(0, attr)
                    attr_item.setText(1, attr_type)
                    self._list_widget.addTopLevelItem(attr_item)
                    
        self._list_widget.setColumnWidth(0, 160)


    def _buildAttrList(self):

        self._attr_list_frame = QFrame(self)
        self._attr_list_frame.setFrameStyle(QFrame.Panel | QFrame.Plain)

        v_layout = QVBoxLayout(self._attr_list_frame)

        self._filter_field = QLineEdit(self)
        self._filter_field.textChanged.connect(self._refreshAttrList)
        v_layout.addWidget(self._filter_field)

        self._list_widget = QTreeWidget(self)
        v_layout.addWidget(self._list_widget)

        self._main_layout.addWidget(self._attr_list_frame)

        self._list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list_widget.setHeaderItem(QTreeWidgetItem(["Attr Names", "Data Types"]))

        h_layout = QHBoxLayout(self._button_frame)

        self._force_cb = QCheckBox(self._button_frame)
        self._force_cb.setText("Append")
        self._force_cb.setChecked(False)
        h_layout.addWidget(self._force_cb)

        v_layout.addLayout(h_layout)
        
        return h_layout


    def _getAttrColor(self, attr_type):

        if attr_type in MEL_ATTR_TYPE_MAP:
            pynode_attr_type = MEL_ATTR_TYPE_MAP[attr_type]

            if pynode_attr_type in ATTR_COLOR_MAP:
                return ATTR_COLOR_MAP[pynode_attr_type]

        return ATTR_COLOR_DEFAULT


    def _buildButtonFrame(self):

        self._button_frame = QFrame(self)
        self._button_frame.setFrameStyle(QFrame.Panel | QFrame.Plain)

        h_layout = QHBoxLayout(self._button_frame)

        ok_button = QPushButton("Connect", self._button_frame)
        ok_button.clicked.connect(self.accept)
        h_layout.addWidget(ok_button)

        cancel_button = QPushButton("Cancel", self._button_frame)
        cancel_button.clicked.connect(self.reject)
        h_layout.addWidget(cancel_button)

        self._main_layout.addWidget(self._button_frame)


    def getAttrName(self):

        sel_items = self._list_widget.selectedItems()

        if sel_items:

            return sel_items[0].text(0)

        return None

    def getAppendConnect(self):

        return bool(self._force_cb.checkState()) 


class NDConnectOutputAttrDialog(NDConnectInputAttrDialog):

    LIST_ATTR_OPTIONS = [{"connectable":True, "write":True, "hasData":True},
                         {"connectable":True, "write":True, "hasData":True, "multi":True}]

    VALID_ATTR_TYPES = MEL_ATTR_TYPE_MAP.keys()
    

    def _queryNodeAttrType(self):
        
        self._replace_cb = None

        attr_map = self._py_node.getOutputAttrMap()
        self._attr_type = attr_map[self._py_node_attr][MPyNode._ATTR_MAP_TYPE_KEY]
        
        
    def _buildAttrList(self):
        
        h_layout = super(NDConnectOutputAttrDialog, self)._buildAttrList()
        
        self._replace_cb = QCheckBox(self._button_frame)
        self._replace_cb.setText("Replace")
        self._replace_cb.setChecked(True)
        h_layout.addWidget(self._replace_cb)
        
        return h_layout
        
        
    def getReplaceConnect(self):

        return bool(self._replace_cb.checkState())


class NDAddAttrDialog(QDialog):

    DISPLAY_TYPES = ("Keyable", "Displayable", "Hidden")
    KEYABLE_ATTR_OPTS = {"keyable":True}
    DISPLAYABLE_ATTR_OPTS = {"channelBox":True}
    HIDDEN_ATTR_OPTS = {}

    ATTR_TYPE_MAP = OrderedDict((map(None, DISPLAY_TYPES, (KEYABLE_ATTR_OPTS, DISPLAYABLE_ATTR_OPTS, HIDDEN_ATTR_OPTS))))

    ADD_ATTR_SIGNAL = Signal(str, str, dict, bool)
    
    FLOAT_DEFAULT_VAL = 0.0
    INT_DEFAULT_VAL = 0
    
    STACK_LAYOUT_MAP = {MPyNode.ATTR_TYPE_FLOAT:0, MPyNode.ATTR_TYPE_ANGLE:0, MPyNode.ATTR_TYPE_TIME:0,
                        MPyNode.ATTR_TYPE_INT:1,
                        MPyNode.ATTR_TYPE_BOOL:2,
                        MPyNode.ATTR_TYPE_ENUM:3}
    BLANK_FRAME_INDEX = 4


    def __init__(self, parent, attr_types, node_name, default_type=None):

        super(NDAddAttrDialog, self).__init__()

        self._attr_types = attr_types

        self._name_field = None
        self._type_combo = None
        self._array_check = None
        self._radio_grp = None
        self._enum_name_list = None

        self._attr_frame = None
        self._properties_frame = None
        self._property_layout = None
        self._button_frame = None
        
        self._float_frame = None
        self._float_min_field = None
        self._float_max_field = None
        self._float_default_field = None
        
        self._int_frame = None
        self._int_min_field = None
        self._int_max_field = None
        self._int_default_field = None
        
        self._bool_frame = None
        self._bool_radio_grp = None
        
        self._enum_frame = None
        self._enum_name_list = None
        
        self._blank_frame = None
        
        self._property_func_map = {MPyNode.ATTR_TYPE_FLOAT:self._getFloatProperties,
                                   MPyNode.ATTR_TYPE_ANGLE:self._getFloatProperties,
                                   MPyNode.ATTR_TYPE_TIME:self._getFloatProperties,
                                   MPyNode.ATTR_TYPE_INT:self._getIntProperties,
                                   MPyNode.ATTR_TYPE_BOOL:self._getBoolProperties,
                                   MPyNode.ATTR_TYPE_ENUM:self._getEnumProperties}
        
        self._main_layout = QVBoxLayout(self)
        self.setLayout(self._main_layout)

        self._buildAttrFrame()
        self._buildPropertiesFrame()
        self._buildButtonFrame()

        self.setWindowTitle("Add Attribute: " + node_name)
        
        self._setSignals()
        self._setDefaultType(default_type)


    def _buildAttrFrame(self):

        self._attr_frame = QFrame(self)
        #self._attr_frame.setFrameStyle(QFrame.Panel | QFrame.Plain)

        h_layout = QHBoxLayout(self._attr_frame)

        v_layout_1 = QVBoxLayout()
        v_layout_1.addWidget(QLabel("Long name:", self._attr_frame))
        v_layout_1.addWidget(QLabel("Attribute type:", self._attr_frame))
        v_layout_1.addWidget(QLabel("Array:", self._attr_frame))
        v_layout_1.addWidget(QLabel("Make attribute:", self._attr_frame))

        h_layout.addLayout(v_layout_1)
        
        v_layout_2 = QVBoxLayout()

        self._name_field = QLineEdit(self._attr_frame)
        v_layout_2.addWidget(self._name_field)

        self._type_combo = QComboBox(self._attr_frame)
        self._type_combo.addItems(self._attr_types)
        v_layout_2.addWidget(self._type_combo)

        self._array_check = QCheckBox(self._attr_frame)
        v_layout_2.addWidget(self._array_check)

        self._radio_grp = QButtonGroup(self._attr_frame)
        radio_layout = QHBoxLayout(self._attr_frame)

        for i, key in enumerate(self.ATTR_TYPE_MAP.keys()):

            button = QRadioButton(key, self._attr_frame)
            self._radio_grp.addButton(button, i)
            radio_layout.addWidget(button)

            if i == 0:
                button.setChecked(True)

        v_layout_2.addLayout(radio_layout)

        h_layout.addLayout(v_layout_2)

        self._main_layout.addWidget(self._attr_frame)
        
        
    def _setSignals(self):
        
        self._type_combo.currentIndexChanged.connect(self._typeChangedEvent)
        self._array_check.stateChanged.connect(self._enablePropertiesWidget)
        
        
    def _enablePropertiesWidget(self, state):
        
        self._properties_frame.setEnabled(not bool(state))
    
        
    def _typeChangedEvent(self, index):
        
        attr_type = self._attr_types[index]
        
        if self.STACK_LAYOUT_MAP.has_key(attr_type):
            self._property_layout.setCurrentIndex(self.STACK_LAYOUT_MAP[attr_type])
            
        else:
            self._property_layout.setCurrentIndex(self.BLANK_FRAME_INDEX)
        
        
    def _setDefaultType(self, default_type):
        
        if default_type:
            if default_type in self._attr_types:
                self._type_combo.setCurrentIndex(list(self._attr_types).index(default_type))
                
                
    def _getFloatProperties(self):
        
        properties = {}
        min_val = self._float_min_field.text()
        max_val = self._float_max_field.text()
        default_val = self._float_default_field.text()
        
        if min_val != "":
            properties["min"] = float(min_val)
            
        if max_val != "":
            properties["max"] = float(max_val)
            
        if default_val != "":
            properties["defaultValue"] = float(default_val)
            
        return properties if properties else None
    
    
    def _getIntProperties(self):
        
        properties = {}
        min_val = self._int_min_field.text()
        max_val = self._int_max_field.text()
        default_val = self._int_default_field.text()
        
        if min_val != "":
            properties["min"] = int(min_val)
            
        if max_val != "":
            properties["max"] = int(max_val)
            
        if default_val != "":
            properties["defaultValue"] = int(default_val)
            
        return properties if properties else None
    
    
    def _getBoolProperties(self):
        
        properties = {}
        
        default_val = self._bool_radio_grp.checkedId()
        
        if default_val > 0:
            properties["defaultValue"] = bool(default_val)
            
        return properties if properties else None
    
    
    def _getEnumProperties(self):
        
        properties = {}
        
        item_count = self._enum_name_list.count()
        
        if item_count > 0:
            enum_items = []
            for i in range(item_count):
                item = self._enum_name_list.item(i)
                item_text = item.text()
                
                if item_text:
                    enum_items.append(str(item_text))
                    
            if enum_items:
                properties["enumName"] = ":".join(enum_items)
        
        return properties if properties else None      
        
        
    def _buildPropertiesFrame(self):
        
        self._properties_frame = QFrame(self)
        #self._properties_frame.setFrameStyle(QFrame.Panel | QFrame.Plain)
        
        v_layout_1 = QVBoxLayout(self._properties_frame)
        
        label = QLabel("Attribute Properties", self._properties_frame)
        label.setStyleSheet("QLabel { background-color : gray; color : silver; font: bold large;}")
        v_layout_1.addWidget(label)
        
        self._property_layout = QStackedLayout(self._properties_frame)
        
        ##-----0 - float ----##
        self._buildFloatPropertiesFrame()
        self._property_layout.addWidget(self._float_frame)
        
        ##-----1 - int ----##
        self._buildIntPropertiesFrame()
        self._property_layout.addWidget(self._int_frame)
        
        ##-----2 - bool ----##
        self._buildBoolPropertiesFrame()
        self._property_layout.addWidget(self._bool_frame)
        
        ##-----3 - blank ----##
        self._buildEnumPropertiesFrame()
        self._property_layout.addWidget(self._enum_frame)        
        
        ##-----4 - blank ----##
        self._buildBlankPropertiesFrame()
        self._property_layout.addWidget(self._blank_frame)
        
        v_layout_1.addLayout(self._property_layout)
        self._main_layout.addWidget(self._properties_frame, stretch=1)
        
        
    def _buildIntPropertiesFrame(self):
        
        self._int_frame = QFrame(self)
        v_layout = QVBoxLayout(self._int_frame)
        v_layout.setContentsMargins(2, 2, 2, 2)
    
        h_layout_1 = QHBoxLayout(self._int_frame)
        min_label = QLabel("Minimum:", self._int_frame)
        min_label.setMinimumWidth(60)
        h_layout_1.addWidget(min_label)
        self._int_min_field = QLineEdit(self._int_frame)
        self._int_min_field.setValidator(QIntValidator())
        h_layout_1.addWidget(self._int_min_field)
        v_layout.addLayout(h_layout_1)
    
        h_layout_2 = QHBoxLayout(self._int_frame)
        max_label = QLabel("Maximum:", self._int_frame)
        max_label.setMinimumWidth(60)
        h_layout_2.addWidget(max_label)
        self._int_max_field = QLineEdit(self._int_frame)
        self._int_max_field.setValidator(QIntValidator())
        h_layout_2.addWidget(self._int_max_field)
        v_layout.addLayout(h_layout_2)
    
        h_layout_3 = QHBoxLayout(self._int_frame)
        default_label = QLabel("Default:", self._int_frame)
        default_label.setMinimumWidth(60)
        h_layout_3.addWidget(default_label)
        self._int_default_field = QLineEdit(self._int_frame)
        self._int_default_field.setValidator(QIntValidator())
        self._int_default_field.setText(str(self.INT_DEFAULT_VAL))
        h_layout_3.addWidget(self._int_default_field)
        v_layout.addLayout(h_layout_3)
    
        v_layout.addStretch(1)
    
    
    def _buildFloatPropertiesFrame(self):
        
        self._float_frame = QFrame(self)
        v_layout = QVBoxLayout(self._float_frame)
        v_layout.setContentsMargins(2, 2, 2, 2)
        
        h_layout_1 = QHBoxLayout(self._float_frame)
        min_label = QLabel("Minimum:", self._float_frame)
        min_label.setMinimumWidth(60)
        h_layout_1.addWidget(min_label)
        self._float_min_field = QLineEdit(self._float_frame)
        self._float_min_field.setValidator(QDoubleValidator())
        h_layout_1.addWidget(self._float_min_field)
        v_layout.addLayout(h_layout_1)
        
        h_layout_2 = QHBoxLayout(self._float_frame)
        max_label = QLabel("Maximum:", self._float_frame)
        max_label.setMinimumWidth(60)
        h_layout_2.addWidget(max_label)
        self._float_max_field = QLineEdit(self._float_frame)
        self._float_max_field.setValidator(QDoubleValidator())
        h_layout_2.addWidget(self._float_max_field)
        v_layout.addLayout(h_layout_2)
        
        h_layout_3 = QHBoxLayout(self._float_frame)
        default_label = QLabel("Default:", self._float_frame)
        default_label.setMinimumWidth(60)
        h_layout_3.addWidget(default_label)
        self._float_default_field = QLineEdit(self._float_frame)
        self._float_default_field.setValidator(QDoubleValidator())
        self._float_default_field.setText(str(self.FLOAT_DEFAULT_VAL))
        h_layout_3.addWidget(self._float_default_field)
        v_layout.addLayout(h_layout_3)
        
        v_layout.addStretch(1)
        
        
    def _buildBoolPropertiesFrame(self):
        
        self._bool_frame = QFrame(self)
        v_layout = QVBoxLayout(self._bool_frame)
        h_layout = QHBoxLayout(self._bool_frame)
        
        h_layout.addWidget(QLabel("Default:", self._bool_frame))
        self._bool_radio_grp = QButtonGroup(self._bool_frame)
        
        true_button = QRadioButton("True", self._bool_frame)
        true_button.setChecked(True)
        self._bool_radio_grp.addButton(true_button, 1)
        h_layout.addWidget(true_button)
        
        false_button = QRadioButton("False", self._bool_frame)
        self._bool_radio_grp.addButton(false_button, 0)
        h_layout.addWidget(false_button)
        
        v_layout.addLayout(h_layout)
        v_layout.addStretch(1)
        
        
    def _buildEnumPropertiesFrame(self):
        
        self._enum_frame = QFrame(self)
        v_layout = QVBoxLayout(self._enum_frame)
        h_layout_1 = QHBoxLayout(self._enum_frame)
        
        plus_button = QPushButton("+", self._enum_frame)
        plus_button.setMaximumWidth(25)
        h_layout_1.addWidget(plus_button)
        minus_button = QPushButton("-", self._enum_frame)
        minus_button.setMaximumWidth(25)
        h_layout_1.addWidget(minus_button)
        h_layout_1.addStretch(1)
        v_layout.addLayout(h_layout_1)
        
        self._enum_name_list = QListWidget(self._enum_frame)
        
        v_layout.addWidget(self._enum_name_list)
        
        plus_button.clicked.connect(self._addEnumItem)
        minus_button.clicked.connect(self._removeEnumItem)
        
        
    def _buildBlankPropertiesFrame(self):
        
        self._blank_frame = QFrame(self)
        
    
    def _addEnumItem(self):
        
        new_item = QListWidgetItem("")
        new_item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self._enum_name_list.addItem(new_item)
        self._enum_name_list.setCurrentItem(new_item)
        
        
    def _removeEnumItem(self):
        
        cur_item = self._enum_name_list.currentItem()
        
        if cur_item:
            self._enum_name_list.takeItem(self._enum_name_list.row(cur_item))


    def _buildButtonFrame(self):

        self._button_frame = QFrame(self)
        #	self._button_frame.setFrameStyle(QFrame.Panel | QFrame.Plain)

        layout = QHBoxLayout(self._button_frame)

        ok_button = QPushButton("OK", self._button_frame)
        ok_button.clicked.connect(self.accept)
        layout.addWidget(ok_button)

        add_button = QPushButton("Add", self._button_frame)
        add_button.clicked.connect(self.emitAddAttrEvent)
        layout.addWidget(add_button)

        cancel_button = QPushButton("Cancel", self._button_frame)
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(cancel_button)        

        self._main_layout.addWidget(self._button_frame)


    def emitAddAttrEvent(self):

        attr_name = self.getAttrName()
        attr_type = self.getAttrType()
        is_array = self.getIsArray()
        display_opts = self.getAttrDisplayOptions(attr_type, is_array)

        self.ADD_ATTR_SIGNAL.emit(attr_name, attr_type, display_opts, is_array)


    def getAttrName(self):

        return str(self._name_field.text())


    def getAttrType(self):

        return str(self._type_combo.currentText())


    def getIsArray(self):

        return bool(self._array_check.checkState())


    def getAttrDisplayOptions(self, attr_type, is_array):

        button_id = self._radio_grp.checkedId()
        
        display_opts = copy.deepcopy(self.ATTR_TYPE_MAP[self.DISPLAY_TYPES[button_id]])
        
        if (attr_type in self._property_func_map) and (not is_array):
            properties = self._property_func_map[attr_type]()
            
            if not properties is None:
                display_opts.update(properties)        

        return display_opts


class NDSceneTree(QTreeWidget):


    def __init__(self, parent=None):

        super(NDSceneTree, self).__init__(parent)

        self.setColumnCount(1)
        self.setHeaderItem(QTreeWidgetItem(["Name"]))

        #self.setSelectionMode(QAbstractItemView.ExtendedSelection)


    def refresh(self, node_class=MPyNode, str_exp=None):

        self.clear()

        py_nodes = node_class.ls(*([] if str_exp is None else [str_exp]))

        if py_nodes:

            for py_node in py_nodes:
                NDSceneTreeItem(self, py_node)


class NDSceneTreeItem(QTreeWidgetItem):

    def __init__(self, parent, py_node):

        super(NDSceneTreeItem, self).__init__(parent)

        self._py_node = py_node

        self.setText(0, py_node.getName())


    def getMPyNode(self):

        return self._py_node


class NDLogWidget(QtLog):

    DEFAULT_TEXT_COLOR = (110, 255, 255)


    def __init__(self, parent=None):

        super(NDLogWidget, self).__init__(parent)
        
        
class NDWatchTable(QTableWidget):
    
    HEADER_TITLES = ("Variable Name", "Value", "Type")
    
    
    def __init__(self, parent=None):
        
        super(NDWatchTable, self).__init__(0, len(NDWatchTable.HEADER_TITLES), parent=parent)
        
        self._buildHeaders()
        

    def _buildHeaders(self):
        
        v_header = QHeaderView(Qt.Orientation.Vertical)
        h_header = QHeaderView(Qt.Orientation.Horizontal)
        
        if PySide.__version_info__[0] == 1:
            v_header.setResizeMode(QHeaderView.ResizeToContents)
            h_header.setResizeMode(QHeaderView.ResizeToContents)
        
        else:
            v_header.setSectionResizeMode(QHeaderView.ResizeToContents)
            h_header.setSectionResizeMode(QHeaderView.ResizeToContents)
        
        self.setVerticalHeader(v_header)
        self.setHorizontalHeader(h_header)
        self.setHorizontalHeaderLabels(self.HEADER_TITLES)
        
        
    def refresh(self, var_dict=None):
        
        self.clearContents()
        
        if var_dict:
            self.setRowCount(len(var_dict))
            
            for row, var_name in enumerate(var_dict.keys()):
                for col, txt in enumerate((var_name, str(var_dict[var_name]), str(type(var_dict[var_name])))):
                    
                    item = QTableWidgetItem(txt)
                    item.setFlags(Qt.ItemIsEnabled) #disables editing
                    self.setItem(row, col, item)
                        
        else:
            self.setRowCount(0)
            
            
class NDWatchVarsWidget(QWidget):
    
    CHECKBOX_TEXT = "Watch Values"
    MPYNODE_VAR_NAME = MPyNode._WATCH_VALUES_VAR_NAME
    

    def __init__(self, parent=None):

        super(NDWatchVarsWidget, self).__init__(parent)
        
        self._py_node = None
        self._watch_cb = None
        self._watch_table = None
        
        self._v_layout = QVBoxLayout(self)
        self.setLayout(self._v_layout)
        
        self._buildCheckbox()
        self._buildTable()
        
    
    def _buildCheckbox(self):
        
        self._watch_cb = QCheckBox(self)
        self._watch_cb.setText(self.CHECKBOX_TEXT)
        self._watch_cb.setChecked(False)
        self._watch_cb.setEnabled(False)
        self._v_layout.addWidget(self._watch_cb)
        
        self._watch_cb.stateChanged.connect(self._onToggleWatch)
        
    
    def _buildTable(self):
        
        self._watch_table = NDWatchTable(self)
        self._v_layout.addWidget(self._watch_table)
        
    
    def _onToggleWatch(self, state):
        
        self._watch_table.refresh()
        
        if self._py_node:
            watch_vars = state == Qt.Checked
            self._py_node.setVariable(self.MPYNODE_VAR_NAME, watch_vars)
        
        
    def _onNodeChanged(self, py_node):
        """
        Designed to be called when the UI changes its current node. This resets the profiler widget to relfect the
        node change.
        """
        
        if py_node:
            self._py_node = py_node
            self._watch_cb.setEnabled(True)
            node_vars = self._py_node.getStoredVariables()
            
            if node_vars and self.MPYNODE_VAR_NAME in node_vars:
                self._watch_cb.setChecked(node_vars[self.MPYNODE_VAR_NAME])
            
            else:
                self._watch_cb.setChecked(False)
                
        else:
            self._py_node = None
            self._watch_cb.setChecked(False)
            self._watch_cb.setEnabled(False)
                
        self._watch_table.refresh()
        
        
    def _onWatchVariables(self, py_node=None, data=None):
        
        if py_node:
            if data:
                self._watch_table.refresh(data)
        else:  
            self._watch_table.refresh()
