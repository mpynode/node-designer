"""Tiny selection helper shared by the wrapper create methods.

Used to honor ``skip_selection=True`` on creators that go through commands with
NO ``skipSelect`` flag (``cmds.deformer`` / ``cmds.shadingNode``): snapshot the
active selection before the create, then restore it afterward.
"""

from maya import cmds as _mc


def restore_selection(prior):
    """Restore a selection snapshot taken before an unavoidable select.

    ``prior`` is the list from ``cmds.ls(selection=True, long=True)`` captured
    before the create. None/empty restores an empty selection (matching "the new
    node is not selected" when nothing was selected to begin with).
    """
    if prior:
        _mc.select(prior, replace=True)
    else:
        _mc.select(clear=True)
