import os
import sys
from distutils.core import setup
from Cython.Build import cythonize

ext_name = "mpynode_obj_cy"
input_name = ext_name + ".pyx"
maya_dir = None
exe_path = sys.executable.replace("\\", "/")
py_version = tuple([str(item) for item in tuple(sys.version_info)])
build_dir = os.path.dirname(__file__).replace("\\", "/")
output_name = build_dir + "/" + ext_name + ".pyd"
output_version_name = build_dir + "/" + ext_name + py_version[0] + py_version[1] + py_version[2] + ".pyd"

if not "MAYA_LOCATION" in os.environ:
    maya_dir = os.environ["MAYA_LOCATION"].replace("\\", "/")
else:
    maya_dir = os.path.normpath(exe_path + "/../../").replace("\\", "/")
    
include_dir = maya_dir + "/include/python2.7"
lib_dir = maya_dir + "/lib"

if "INCLUDE" in os.environ:
    os.environ["INCLUDE"] += ";" + include_dir
else:
    os.environ["INCLUDE"] = include_dir
    
if "LIB" in os.environ:
    os.environ["LIB"] += ";" + lib_dir
else:
    os.environ["LIB"] = lib_dir

ext_modules = cythonize(input_name)
setup(name=output_version_name, ext_modules=ext_modules)