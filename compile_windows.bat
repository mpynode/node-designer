@setlocal enableextensions & "python.exe" -x "%~f0" %* & goto :EOF


import os, shutil, glob

from distutils.dir_util import copy_tree
from subprocess import check_output


# Create release directory if missing
ROOT = os.path.split(os.path.realpath(__file__))[0]
RELEASE_DIR = os.path.join(ROOT,'release_windows')

if not os.path.isdir(RELEASE_DIR):
    os.makedirs(RELEASE_DIR)
    
 
def copyfile(src,dst,move=False):
    folder = os.path.split(dst)[0]
    if not os.path.isdir(folder):
        os.makedirs(folder)
    
    if move:
        if os.path.isfile(dst):
            os.remove(dst)
        os.rename(src, dst)
    else:
        shutil.copy2(src, dst)
    
    

# Walk down the directory, c
def compile_folder(path):
    
    # Look for _compile.py scripts under scripts and plug-ins
    for root, dirs, files in os.walk(path):
        
        # skip _tests
        if not os.path.split(root)[1] == '_tests':
            for f in files:
                if f == '_compile.py':
                    comp_file = os.path.join(root,f)
                    
                    # Cythonize
                    print 'compiling: %s'%comp_file
                    os.chdir(root)
                    check_output('python _compile.py build_ext --inplace', shell=True).decode()
        
                    # Cleanup build folders
                    if os.path.isdir(os.path.join(root,'build')):
                        shutil.rmtree(os.path.join(root,'build'))
                    
                    # Cleanup .c files
                    for c in glob.glob(os.path.join(root,'*.c')):
                        os.remove(c)
                        
                # Copy over __init__.py's and plugin entry point
                elif f in ['__init__.py','mpynode_plugin.py']:
                    dst = root.replace(ROOT,RELEASE_DIR)
                    copyfile(os.path.join(root,f),os.path.join(dst,f))
            
            
                        
            # Copy over resources if present
            if 'resources' in dirs:
                src = os.path.join(root,'resources')
                dst = root.replace(ROOT,RELEASE_DIR)
                dst = os.path.join(dst,'resources')
                
                copy_tree(src, dst)
                
                
            # Move generated pyd's, except for mpynode_obj_cy which we copy over instead
            for src in glob.glob(os.path.join(root,'*.pyd')) + glob.glob(os.path.join(root,'*.so')):
                dst = src.replace(ROOT,RELEASE_DIR)
                
                if os.path.split(os.path.splitext(src)[0])[1] == 'mpynode_obj_cy':
                    copyfile(src, dst)
                else:
                    copyfile(src, dst, move=True)
            
        
        
        
        
            
                    
                                     
compile_folder(os.path.join(ROOT,'plug-ins'))
compile_folder(os.path.join(ROOT,'scripts'))
print ''
raw_input('all done, press any key to exit')