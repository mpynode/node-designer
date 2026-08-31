"""Variables tab slimmed to USER vars only (Persistent + Temporary).

The Properties (``INTERNAL_API_SLOTS``) section moved to the new Framework
tab, so the Variables widget must no longer render a "Properties" top-level
section -- only "Persistent" and "Temporary".

The data collectors (``collect_internal_api_rows`` / ``_dir_label`` /
``NDPlugRowItem``) stay importable: the Framework tab reuses them. The
old rendering-only dead code (``NDInternalVarItem`` / ``_direction_glyph``
and friends) is deleted.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-varsslim-test"])

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _qapp_available():
    return _QAPP is not None


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestVariablesSlim(unittest.TestCase):
    def _make_locator(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        mc.file(new=True, force=True)
        return MPyLocator.create(name="varsSlim")

    def test_no_properties_section(self):
        from mpynode.ui.widgets.variables import NDVariablesWidget

        loc = self._make_locator()
        w = NDVariablesWidget()
        try:
            w.setPyNode(loc)
            tree = w._tree
            top_texts = [
                tree.topLevelItem(i).text(0)
                for i in range(tree.topLevelItemCount())
            ]
            self.assertNotIn(
                "Properties", top_texts,
                "Variables tab must no longer render the Properties section "
                "(it moved to the Framework tab); saw %r" % (top_texts,),
            )
            self.assertIn("Persistent", top_texts)
            self.assertIn("Temporary", top_texts)
        finally:
            w.deleteLater()

    def test_collectors_still_importable(self):
        # Framework tab + tests reuse these -- they must remain importable.
        from mpynode.ui.widgets.variables import (  # noqa: F401
            NDPlugRowItem,
            _dir_label,
            collect_internal_api_rows,
        )

    def test_dead_code_removed(self):
        import mpynode.ui.widgets.variables as v

        self.assertFalse(hasattr(v, "NDInternalVarItem"))
        self.assertFalse(hasattr(v, "_direction_glyph"))


if __name__ == "__main__":
    unittest.main()
