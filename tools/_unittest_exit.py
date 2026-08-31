"""``python -m unittest`` stand-in that survives Maya's teardown.

Once ``maya.standalone.initialize()`` has run, mayapy's shutdown replaces the
interpreter's status with 0, so a failing ``mayapy -m unittest`` run still exits
0. Running the same TestProgram here and leaving through ``os._exit`` reports
the real result before Maya's teardown can overwrite it.
"""

import os
import sys
import unittest

sys.path.insert(0, os.getcwd())

try:
    prog = unittest.main(module=None,
                         argv=["python -m unittest"] + sys.argv[1:],
                         exit=False)
    code = 0 if prog.result.wasSuccessful() else 1
except SystemExit as exc:
    if exc.code is None:
        code = 0
    elif isinstance(exc.code, int):
        code = exc.code
    else:
        sys.stderr.write("%s\n" % (exc.code,))
        code = 1

sys.stdout.flush()
sys.stderr.flush()
os._exit(code)
