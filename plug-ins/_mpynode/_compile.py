from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext
ext_modules = [
    Extension("_openmaya",  ["_openmaya.py"]),
    Extension("mpynode_obj_c",  ["mpynode_obj_c.py"]),
    Extension("mpynode_obj", ["mpynode_obj.py"]),
#   ... all your modules that need be compiled ...
]
setup(
    name = 'MPyNode Plugin',
    cmdclass = {'build_ext': build_ext},
    ext_modules = ext_modules
)
