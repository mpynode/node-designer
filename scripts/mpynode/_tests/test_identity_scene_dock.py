"""Identity panel docked into the Scene tab's bottom split (UI relocation).

The Identity panel used to be its own left-hand tab, so naming a Class meant
switching away from the scene tree and losing sight of the node (and its
siblings) being edited. It is now docked into the BOTTOM of the Scene tab under
a draggable vertical splitter: scene tree on top, Identity panel below, both
visible at once -- mirroring the editor <-> tools divider on the right.

These are inspect-based structural checks on ``NDMainWindow._build_ui`` (the
established pattern for this file -- constructing the full window under mayapy's
QApplication is unreliable, so the other _build_ui tests inspect source too).
They lock the load-bearing facts of the layout: a vertical scene splitter holds
the tree AND the identity widget, that splitter (not the bare tree) is the
"Scene" tab, and the old dedicated Identity tab is gone.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import inspect
import unittest


def _build_ui_src():
    from mpynode.ui.mpynode_designer import NDMainWindow

    return inspect.getsource(NDMainWindow._build_ui)


class TestIdentityDockedInSceneTab(unittest.TestCase):
    def test_scene_pane_is_a_vertical_splitter(self):
        src = _build_ui_src()
        # A dedicated vertical splitter holds the scene pane's two halves.
        self.assertIn("self._scene_split", src)
        self.assertIn("QSplitter(Qt.Vertical, self._panel_tab_widget)", src)

    def test_tree_and_identity_share_the_scene_split(self):
        src = _build_ui_src()
        self.assertIn("self._scene_split.addWidget(self._scene_tree)", src)
        self.assertIn("self._scene_split.addWidget(self._identity_widget)", src)

    def test_scene_split_is_the_scene_tab(self):
        src = _build_ui_src()
        # The SPLITTER (tree + identity), not the bare tree, is the Scene tab.
        self.assertIn(
            'self._panel_tab_widget.addTab(self._scene_split, "Scene")', src)
        self.assertNotIn(
            'self._panel_tab_widget.addTab(self._scene_tree, "Scene")', src)

    def test_no_standalone_identity_tab(self):
        src = _build_ui_src()
        # The dedicated Identity tab is gone -- identity lives in the scene pane.
        self.assertNotIn("insertTab(1, self._identity_widget", src)

    def test_tree_never_collapses(self):
        src = _build_ui_src()
        # The tree is the primary surface and must always stay visible; the
        # identity panel may be dragged shut, but the tree may not.
        self.assertIn("self._scene_split.setCollapsible(0, False)", src)

    def test_the_whole_left_panel_can_be_dragged_shut(self):
        # Different splitter, different claim: the tree cannot collapse WITHIN
        # the Scene tab, but the panel that holds Scene / Attributes /
        # Variables / Framework can be closed against the editor. Only the
        # editor itself is pinned open.
        src = _build_ui_src()
        self.assertIn("splitter.setCollapsible(0, True)", src)
        self.assertIn("splitter.setCollapsible(1, False)", src)

    def test_other_panel_tabs_survive(self):
        src = _build_ui_src()
        for label in ("Attributes", "Variables", "Framework"):
            self.assertIn(
                'self._panel_tab_widget.addTab(self._%s_widget, "%s")'
                % (label.lower(), label),
                src,
            )


if __name__ == "__main__":
    unittest.main()
