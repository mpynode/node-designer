"""Per-node MNodeMessage callback helpers.

Wraps Maya's ``MNodeMessage.addAttributeChangedCallback`` so the rest of
the codebase can install + remove plug-changed listeners without touching
``maya.api.OpenMaya`` directly.

Design:
  * Caller passes a ``dispatcher`` callable (anything taking the changed
    plug). We wrap it so we ONLY fire on ``kAttributeSet`` messages \u2014
    the others (``kAttributeAdded``, ``kAttributeRemoved``, etc.) fire
    on different conditions and we don't want them by default.
  * Errors inside the dispatcher are swallowed: callbacks that raise from
    inside a Maya callback can crash Maya. Always silent on user code.
  * Callback IDs are returned as opaque ints; pass them back to
    ``remove_callback`` on tear-down.
"""

from __future__ import annotations

import maya.api.OpenMaya as om


def _on_attribute_changed(msg, plug, other_plug, client_data):
    """Internal Maya callback. Forwards to the user's dispatcher on
    kAttributeSet only."""
    # Bit-flag check; ignore non-Set events.
    if not (msg & om.MNodeMessage.kAttributeSet):
        return
    try:
        client_data(plug)
    except Exception:
        # NEVER raise out of a Maya callback -- it can crash the app.
        pass


def _on_connection_changed(msg, plug, other_plug, client_data):
    """Internal Maya callback. Forwards to the user's dispatcher ONLY on
    connection-state changes (kConnectionMade / kConnectionBroken), so the
    Attributes panel can refresh its connected-dot when wiring changes
    outside the Designer. Kept separate from ``_on_attribute_changed`` (which
    fires on kAttributeSet) so neither path regresses the other."""
    if not (
        msg
        & (om.MNodeMessage.kConnectionMade | om.MNodeMessage.kConnectionBroken)
    ):
        return
    try:
        client_data(plug)
    except Exception:
        # NEVER raise out of a Maya callback — it can crash the app.
        pass


def install_node_connection_callback(node_name: str, dispatcher) -> int:
    """Install an MNodeMessage.addAttributeChangedCallback that fires the
    given ``dispatcher`` (called with the changed ``MPlug``) ONLY on
    connection made/broken events. Returns the callback id (opaque int).

    Use ``remove_callback`` to tear down. Raises if the node is missing.
    """
    sel = om.MSelectionList()
    sel.add(node_name)
    mobj = sel.getDependNode(0)
    cb_id = om.MNodeMessage.addAttributeChangedCallback(
        mobj, _on_connection_changed, dispatcher
    )
    return cb_id


def install_node_attr_callback(node_name: str, dispatcher) -> int:
    """Install an MNodeMessage.addAttributeChangedCallback on the given
    node. Returns the callback id (opaque int).

    ``dispatcher`` is called with the changed ``MPlug`` instance.

    Raises if the node doesn't exist.
    """
    sel = om.MSelectionList()
    sel.add(node_name)
    mobj = sel.getDependNode(0)
    cb_id = om.MNodeMessage.addAttributeChangedCallback(
        mobj, _on_attribute_changed, dispatcher
    )
    return cb_id


def remove_callback(cb_id) -> None:
    """Remove a Maya callback by id. Safe to call on invalid ids."""
    if cb_id is None:
        return
    try:
        om.MMessage.removeCallback(cb_id)
    except Exception:
        pass


def remove_callbacks(cb_ids) -> None:
    """Remove a batch of callback ids. Safe to call on empty / mixed."""
    for cb_id in cb_ids or ():
        remove_callback(cb_id)
