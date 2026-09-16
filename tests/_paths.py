"""Repo-anchored paths for the test suite.

Any test needing the repo root or a fixture imports it from here rather than
counting ``os.path.dirname`` levels up from its own ``__file__``. A category
package sits two levels below the root (``tests/nodes/``) and a sub-category
three (``tests/compile/transpiler/``), so a hand-counted chain is wrong the
moment a module moves between buckets -- and a wrong root does not fail loudly:
the artifact-freshness gates resolve nothing and quietly skip.
"""
import os

_HERE   = os.path.dirname(os.path.abspath(__file__))

TESTS   = _HERE
ROOT    = os.path.dirname(_HERE)
SCRIPTS = os.path.join(ROOT,  "scripts")
DATA    = os.path.join(_HERE, "data")
ASSETS  = os.path.join(_HERE, "test_assets")
