"""MPyNode test suite, grouped by area.

Importing this package keeps the run out of the user's MPyNode home
(``~/.mpynode``: preferences, port cache, trust store, ...). Every test module
imports it first, before anything from the project
(``authoring/test_suite_home_isolation.py`` checks), so this runs before any
test imports mpynode, however the module is started: discovered, named on the
command line, discovered from its own folder, or run on its own
(``mayapy tests/ui/test_x.py``). ``MPYNODE_HOME`` then names a fresh temp
folder for this run, and what reads the home at import time
(``mpynode.ui.preferences.PREFS_PATH``) resolves under it. Subprocesses inherit
it. ``tools/_unittest_exit.py`` imports this package before it loads a test,
so a module outside the package that imports mpynode first is covered too.
"""

import os
import tempfile

HOME_ENV = "MPYNODE_HOME"
# The run's home, set beside MPYNODE_HOME: a child process of the run that
# imports this package again keeps the run's home instead of making another.
RUN_HOME_ENV = "MPYNODE_TEST_RUN_HOME"
# Each of these moves one location out of the home on its own
# (mpynode._common.home); a test run drops them.
LOCATION_ENVS = ("MPYNODE_PREFS", "MPYNODE_PORT_CACHE", "MPYNODE_TRUST_STORE",
                 "MPYNODE_TYPEID_REGISTRY", "MPYNODE_COMPILED")

# The user's folder and the outer MPYNODE_HOME as the run found them, so the
# guard test (authoring/test_suite_home_isolation.py) can check that the run's
# home is not the one MPyNode would have used.
USER_DIR   = os.path.expanduser("~")
OUTER_HOME = None

_PREFIX    = "mpynode-test-home-"
_run_home  = None


def isolate_home() -> str:
    """Point MPyNode's home at this run's temp folder and return it.

    The first call decides; later calls only return the folder. An outer
    MPYNODE_HOME is replaced, unless it is a test home this package made for
    a parent process of this run."""
    global _run_home, OUTER_HOME
    if _run_home is not None:
        return _run_home
    outer = os.environ.get(HOME_ENV)
    if (outer and outer == os.environ.get(RUN_HOME_ENV)
            and os.path.basename(outer).startswith(_PREFIX)
            and os.path.isdir(outer)):
        _run_home = outer
    else:
        OUTER_HOME = outer
        _run_home  = tempfile.mkdtemp(prefix=_PREFIX)
    os.environ[HOME_ENV]     = _run_home
    os.environ[RUN_HOME_ENV] = _run_home
    for name in LOCATION_ENVS:
        os.environ.pop(name, None)
    return _run_home


isolate_home()
