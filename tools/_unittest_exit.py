"""``python -m unittest`` stand-in that survives Maya's teardown.

Once ``maya.standalone.initialize()`` has run, mayapy's shutdown replaces the
interpreter's status with 0, so a failing ``mayapy -m unittest`` run still exits
0. Running the same TestProgram here and leaving through ``os._exit`` reports
the real result before Maya's teardown can overwrite it.

``os._exit`` skips Python finalization, but Windows still runs every loaded
DLL's detach code -- so Maya tore itself down over a live interpreter, its
crash handler fired ("Fatal Error. Attempting to save in ...") and wrote an
``untitled[Recovered-...].ma`` into %TEMP% after EVERY green run (68 of them
by 2026-09-08). ``maya.standalone.uninitialize()`` first lets Maya shut down
in order; measured: no Fatal Error, and the exit status still comes through
``os._exit`` unchanged. Only called when a test actually initialized Maya --
pure file tests never import it.
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

standalone = sys.modules.get("maya.standalone")
if standalone is not None:
    try:
        standalone.uninitialize()
    except Exception:
        pass  # worst case is today's behaviour; the status below still wins

os._exit(code)
