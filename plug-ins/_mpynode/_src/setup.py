import os
import sys
from distutils.core import setup
from Cython.Build import cythonize
from distutils.extension import Extension

# Check if MAYA_VERSION is set in the environment variables
if "MAYA_VERSION" not in os.environ:
    raise ValueError("MAYA_VERSION environment variable is not set.")

maya_version = os.environ["MAYA_VERSION"]
ext_base_name = "mpynode_obj_cy"
include_paths = {"2025":"/include/Python311/Python", "2024":"/include/Python310/Python", "2023":"/include/Python39/Python"}
os_version_lookup = {"win32":"win", "linux":"linux", "darwin":"osx"}
os_version = os_version_lookup.get(sys.platform, None)

if not os_version:
    raise ValueError(f"Unsupported operating system: {sys.platform}")

exe_path = sys.executable.replace("\\", "/")
maya_dir = os.path.normpath(exe_path + "/../../").replace("\\", "/")

src_dir = os.path.dirname(__file__).replace("\\", "/")
base_dir = os.path.normpath(f"{src_dir}/..").replace("\\", "/")
os_dir = f"{src_dir}/{os_version}"
output_dir = base_dir
input_name = f"{src_dir}/{ext_base_name}.pyx"
ext_name = f"{ext_base_name}_{os_version}_{maya_version}"

# Use a specific version of Python based on the Maya version
include_dir = f"{maya_dir}{include_paths[maya_version]}"
lib_dir = maya_dir + "/lib"

if "INCLUDE" in os.environ:
    os.environ["INCLUDE"] += ";" + include_dir
else:
    os.environ["INCLUDE"] = include_dir
    
if "LIB" in os.environ:
    os.environ["LIB"] += ";" + lib_dir
else:
    os.environ["LIB"] = lib_dir
    
# Make the output directory if it doesn't exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    
print(f"input name: {input_name}")
print(f"os dir: {os_dir}")
print(f"current working directory: {os.getcwd()}")
print(f"build directory: {src_dir}")
print(f"output directory: {output_dir}")

# Define the extension module with the correct name
ext_modules = [
    Extension(
        name=ext_name,
        sources=[input_name],
        include_dirs=[include_dir],
        library_dirs=[lib_dir],
    )
]

setup(
    name=ext_name,
    ext_modules=cythonize(ext_modules),
)