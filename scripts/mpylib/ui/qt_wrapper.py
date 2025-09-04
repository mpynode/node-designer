# import Qt from either qtpy or Qt.py

try:
    
    # try qtpy (preferred)
    from qtpy.QtCore import QObject, QSize, Qt, Signal, Slot, QEvent, QRect
    try:
        # Try to import QRegExp (available in Qt6)
        from qtpy.QtCore import QRegularExpression
    except ImportError:
        # Fallback to QRegularExpression (Qt5)
        from qtpy.QtCore import QRegExp as QRegularExpression

    from qtpy.QtGui import (
        QPainter,
        QTextFormat, 
        QTextCharFormat, 
        QSyntaxHighlighter, 
        QColor,
        QDoubleValidator,
        QFont,
        QFontMetrics,
        QIcon,
        QIntValidator,
        QKeySequence,
        QPixmap,
        QTextCursor,
    )
    from qtpy.QtWidgets import (
        QApplication,
        QTextEdit, 
        QAbstractItemView,
        QAction,
        QButtonGroup,
        QCheckBox,
        QColorDialog,
        QComboBox,
        QCompleter,
        QDialog,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QRadioButton,
        QSplitter,
        QStackedLayout,
        QStatusBar,
        QTabBar,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QToolBar,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QDockWidget, 
        QWidget,
    )    
    
except ImportError:
    # Fallback to Qt.py
    from Qt.QtCore import QObject, QSize, Qt, Signal, Slot, QEvent, QRect
    
    try:
        # Try to import QRegExp (available in Qt6)
        from Qt.QtCore import QRegularExpression
    except ImportError:
        # Fallback to QRegularExpression (Qt5)
        from Qt.QtCore import QRegExp as QRegularExpression
        
    from Qt.QtGui import (
        QPainter,
        QTextFormat, 
        QSyntaxHighlighter,
        QTextCharFormat, 
        QColor,
        QDoubleValidator,
        QFont,
        QFontMetrics,
        QIcon,
        QIntValidator,
        QKeySequence,
        QPixmap,
        QTextCursor,
    )
    from Qt.QtWidgets import (
        QApplication,
        QTextEdit, 
        QAbstractItemView,
        QAction,
        QButtonGroup,
        QCheckBox,
        QColorDialog,
        QComboBox,
        QCompleter,
        QDialog,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QRadioButton,
        QSplitter,
        QStackedLayout,
        QStatusBar,
        QTabBar,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QToolBar,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QDockWidget, 
        QWidget,
    )    
    