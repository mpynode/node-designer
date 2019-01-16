from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext
ext_modules = [
    Extension("mpynode_designer",     ["mpynode_designer.py"]),
    Extension("mqt_dock_widget",      ["mqt_dock_widget.py"]),
    Extension("mqt_main_window",      ["mqt_main_window.py"]),
    Extension("mqt_main",             ["mqt_main.py"]),
    Extension("qt_log",               ["qt_log.py"]),
    Extension("qt_py_editor",         ["qt_py_editor.py"]),
    Extension("qt_py_highlighter",    ["qt_py_highlighter.py"]),
    Extension("qt_py_profile_table",  ["qt_py_profile_table.py"]),

]
setup(
    name = 'MPyNode',
    cmdclass = {'build_ext': build_ext},
    ext_modules = ext_modules
)
