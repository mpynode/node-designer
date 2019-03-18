@setlocal enableextensions & "python.exe" -x "%~f0" %* & goto :EOF

import os, shutil, glob, sys



# Files to fix
html_dir  = r'.\build\html\api'
fixes     = {'._base.mnode':'',
             '._base.mshape':''}

files = glob.glob(os.path.join(html_dir,'*.html'))
for f in files:
    
    data = []
    with open(f,'r') as io:
        
        for line in io.readlines():
            for fix in fixes:
                if fix in line:
                    line = line.replace(fix,fixes[fix])

            data.append(line)
    
    print 'writing: %s'%f
    with open(f,'w') as io:
        io.writelines(data)
        
raw_input('All Done!')