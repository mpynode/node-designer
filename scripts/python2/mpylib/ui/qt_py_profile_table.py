import types
import os

try:
    import PySide
    
except ImportError as err:
    import PySide2
    from PySide2.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QWidget, QHBoxLayout
    from PySide2.QtCore import Qt
    PySide = PySide2

else:
    from PySide.QtGui import QTableWidget, QTableWidgetItem, QHeaderView, QWidget, QHBoxLayout
    from PySide.QtCore import Qt
    
    
class QtPyProfileTable(QTableWidget):
    
    HEADER_TITLES = ("Name", "Call Count", "Rec-call Count", "Cumulative Time", "Total Time", "Module")
    
    
    def __init__(self, parent=None):
        
        try:
            super().__init__(0, 6, parent=parent) # python3
        except:
            super(QtPyProfileTable, self).__init__(0, 6, parent=parent) # python2
            
        
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
        
        
    def refresh(self, profiler_stats=None):
        
        self.clearContents()
        
        if profiler_stats:
            
            stats = [item for item in profiler_stats if type(item.code) == types.CodeType]
            
            self.setRowCount(len(stats))
            
            for row, profile_entry in enumerate(stats):
                code_obj = profile_entry.code
                func_name = code_obj.co_name + " (" + os.path.basename(code_obj.co_filename) + " : " + str(code_obj.co_firstlineno) + ")"
                
                self.setItem(row, 0, QTableWidgetItem(func_name))
                self.setItem(row, 1, QTableWidgetItem(str(profile_entry.callcount)))
                self.setItem(row, 2, QTableWidgetItem(str(round(profile_entry.reccallcount, 4))))
                self.setItem(row, 3, QTableWidgetItem(str(round(profile_entry.totaltime, 4))))
                self.setItem(row, 4, QTableWidgetItem(str(round(profile_entry.inlinetime, 4))))
                self.setItem(row, 5, QTableWidgetItem(code_obj.co_filename))
        else:
            self.setRowCount(0)
        
        
if __name__ == "__main__":
    
    import sys
    import cProfile
    
    try:
        import PySide
        
    except ImportError as err:
        from PySide2.QtWidgets import QApplication
    
    else:
        from PySide.QtGui import QApplication
        
        
    def testA(a, b):
        
        return a + b
 
    class TestClass(object):
        
        def testB(self):
            return testA(1, 2)
    
    app = QApplication(sys.argv)
    
    table_widget = QtPyProfileTable()
    table_widget.show()
    
    test_obj = TestClass()
    
    profiler = cProfile.Profile()
    profiler.runcall(test_obj.testB)
    
    table_widget.refresh(profiler_stats=profiler.getstats())
    
    sys.exit(app.exec_())