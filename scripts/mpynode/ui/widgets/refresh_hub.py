"""RefreshHub -- central MNodeMessage subscriber for the Node Designer's
per-node views (Attributes / Storage / Autocomplete).

Each Node Designer view that depends on the live plug tree (and
needs to re-render when the artist adds an attribute, makes a
connection, renames a node, etc.) subscribes to a single
``RefreshHub`` bound to the currently-selected node. The hub
proxies a small set of MNodeMessage / MEventMessage events through
a debounced Qt timer so:

* All views share ONE set of MNodeMessage subscriptions per node
 (no proliferation).
* A burst of Maya events (e.g. `addAttr` of a Double3 emits 4 events
 for parent + 3 children) collapses into a single refresh call
 per view.
* MNodeMessage callbacks fire on the main thread; the debounce
 hands control back to the Qt event loop so refresh work doesn't
 block the callback chain.
* On node-about-to-delete (or explicit ``detach()``) the
 MNodeMessage handles are torn down via the existing
 ``_common.callbacks.CALLBACK_MANAGER`` so plugin unload stays
 clean.

API
---

``RefreshHub(node_name)`` -- bind to a node. The hub auto-attaches
its MNodeMessage callbacks via API 1.0 (the wrappers + PlugProxy
are all api1).

``hub.subscribe(view_id, callback, events="all")`` -- register a
callback. ``events`` is "all" or a tuple of event names::

 "attribute_added_or_removed", "attribute_set",
 "name_changed", "node_about_to_delete"

``hub.unsubscribe(view_id)`` -- remove one subscriber by id. Tear
down callbacks if no subscribers remain.

``hub.detach()`` -- remove ALL Maya callbacks. Safe to call twice.

``hub.fire(event_name)`` -- manually fire an event (for tests + the
explicit `add_input_attr` notification path the wrappers already
emit).

Headless usage
--------------

The hub is testable headless: if Qt isn't available, the debounce
falls back to a synchronous call (the test harness can flush the
queue by calling ``hub._dispatch_pending()`` directly).

Plug-in unload contract
-----------------------

All MNodeMessage handles go through ``CALLBACK_MANAGER.register``;
``CALLBACK_MANAGER.remove_all()`` (called from each plugin's
``uninitializePlugin``) tears them down even if the artist forgot
to close the Node Designer.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Optional, Tuple

import maya.OpenMaya as om

from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER, OWNER_SHARED


_DEBOUNCE_MS = 50

EVENT_ATTR_ADDED_OR_REMOVED = "attribute_added_or_removed"
EVENT_ATTR_SET = "attribute_set"
EVENT_NAME_CHANGED = "name_changed"
EVENT_NODE_ABOUT_TO_DELETE = "node_about_to_delete"

_ALL_EVENTS = (
    EVENT_ATTR_ADDED_OR_REMOVED,
    EVENT_ATTR_SET,
    EVENT_NAME_CHANGED,
    EVENT_NODE_ABOUT_TO_DELETE,
)


def _resolve_mobject_for_name(node_name: str) -> Optional[Any]:
    """Resolve ``node_name`` -> api1 MObject. Returns None on any
    failure (deleted node, bad name)."""
    try:
        sel = om.MSelectionList()
        sel.add(node_name)
        mob = om.MObject()
        sel.getDependNode(0, mob)
        return mob
    except Exception:
        return None


class RefreshHub:
    """Central per-node MNodeMessage subscriber. Multiple
    Node Designer views share a single hub instance bound to the
    same node.

    Construction registers four MNodeMessage callbacks via API 1.0.
    Each event sets a pending flag; a debounced timer flushes the
    pending events through every subscriber's callback.

    Subscribers register via ``subscribe(view_id, callback,
    events="all")``. ``callback`` is invoked with the event name as
    its single argument.
    """

    def __init__(self, node_name: str):
        self._node_name = node_name
        self._mobject = _resolve_mobject_for_name(node_name)
        # {view_id: (callback, events_tuple, plug_filter)}
        self._subscribers: dict = {}
        # Event names waiting on the next debounce flush.
        self._pending_events: set = set()
        # Changed plug short names for this debounce window, from
        # ``fire_plug_set``. A subscriber with a plug_filter only sees
        # ATTR_SET when its filter intersects this set.
        self._pending_plug_names: set = set()
        # CALLBACK_MANAGER tokens for the 4 MNodeMessage handles.
        self._tokens: list = []
        # Debounce timer; lazy-built so headless paths work without Qt.
        self._timer = None
        self._attached = False
        if self._mobject is not None and not self._mobject.isNull():
            self._attach_maya_callbacks()
            self._attached = True

    # ------------------------------------------------------------------
    # Subscriber API
    # ------------------------------------------------------------------

    def subscribe(
        self,
        view_id: str,
        callback: Callable[[str], None],
        events: Any = "all",
        plug_filter=None,
    ) -> None:
        """Register a callback for one or more event types.

        ``events`` is the string ``"all"`` or a tuple/list of event
        name constants (e.g. ``(EVENT_ATTR_ADDED_OR_REMOVED,)``).
        Re-subscribing under the same ``view_id`` replaces the
        existing entry.

        optional ``plug_filter`` tuple/list of short plug
        names. When set, ``EVENT_ATTR_SET`` only fires for this
        subscriber if the changed plug's short name is in the
        filter. Other event types (added/removed, name changed,
        about-to-delete) ignore the filter -- they fire whenever
        they would have fired without it. ``None`` (default) means
        "all plugs" (backward compatible with N.0 subscribers).
        """
        if events == "all":
            ev_tuple: Tuple[str,...] = _ALL_EVENTS
        else:
            ev_tuple = tuple(events)
        pf_tuple = tuple(plug_filter) if plug_filter else None
        self._subscribers[view_id] = (callback, ev_tuple, pf_tuple)

    def unsubscribe(self, view_id: str) -> bool:
        """Remove a subscriber. Returns True if found + removed."""
        if view_id in self._subscribers:
            del self._subscribers[view_id]
            return True
        return False

    def has_subscriber(self, view_id: str) -> bool:
        return view_id in self._subscribers

    def subscriber_count(self) -> int:
        return len(self._subscribers)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def is_attached(self) -> bool:
        return self._attached

    def node_name(self) -> str:
        return self._node_name

    def detach(self) -> None:
        """Tear down all Maya callbacks. Safe to call twice. Does
        NOT clear subscribers (so a re-attached hub can re-fire)."""
        for tok in self._tokens:
            try:
                CALLBACK_MANAGER.unregister(tok)
            except Exception:
                pass
        self._tokens = []
        self._attached = False
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Event firing (Maya callbacks + manual + test API)
    # ------------------------------------------------------------------

    def fire(self, event_name: str) -> None:
        """Mark ``event_name`` pending + arm the debounce timer.
        Idempotent within a debounce window (a burst of identical
        events fires the subscriber callback exactly once)."""
        self._pending_events.add(event_name)
        self._arm_timer()

    def fire_plug_set(self, plug_short_name: str) -> None:
        """Variant of ``fire(EVENT_ATTR_SET)`` that
        records the changed plug's short name. Subscribers with a
        ``plug_filter`` only see this event if the plug name
        intersects their filter.

        Multiple distinct plug names within the same debounce
        window are all collected; the dispatch sends ATTR_SET to
        any subscriber whose filter matches ANY pending plug name
        (collapses bursts, preserves correctness)."""
        self._pending_events.add(EVENT_ATTR_SET)
        self._pending_plug_names.add(plug_short_name)
        self._arm_timer()

    def _arm_timer(self) -> None:
        """Schedule a debounced flush.

        * If a ``QApplication`` is running, use ``QTimer.singleShot``
          on the main thread (the production path; the actual
          debounce comes from Qt's event loop merging multiple
          arm-timer calls into one fire-at-50ms-later).
        * If no QApplication is running (headless mayapy / tests),
          dispatch synchronously. Bursts still collapse because
          ``_pending_events`` is a set + ``_dispatch_pending``
          drains it.

        Either way, callers can also call ``_dispatch_pending``
        explicitly to flush the queue immediately (used by the
        test harness)."""
        # QTimer construction without a live QApplication is unsafe and can
        # hang interpreter shutdown, so check first.
        try:
            from PySide6.QtWidgets import QApplication
        except Exception:
            try:
                from PySide2.QtWidgets import QApplication
            except Exception:
                QApplication = None
        if QApplication is None or QApplication.instance() is None:
            # Headless: dispatch synchronously.
            self._dispatch_pending()
            return

        if self._timer is not None and self._timer.isActive():
            return
        try:
            from mpynode.ui.qt_wrapper import QTimer

            if self._timer is None:
                self._timer = QTimer()
                self._timer.setSingleShot(True)
                self._timer.timeout.connect(self._dispatch_pending)
            self._timer.start(_DEBOUNCE_MS)
        except Exception:
            # Timer creation failed: fall back to sync dispatch.
            self._dispatch_pending()

    def _dispatch_pending(self) -> None:
        """Drain ``_pending_events`` and call every subscriber whose
        event mask intersects. Called from the Qt timer (main
        thread) or directly from the test harness.

        subscribers with a ``plug_filter`` only receive
        ``EVENT_ATTR_SET`` if the filter intersects the pending
        plug-name set."""
        if not self._pending_events:
            return
        events_snapshot = set(self._pending_events)
        plug_names_snapshot = set(self._pending_plug_names)
        self._pending_events.clear()
        self._pending_plug_names.clear()
        # A snapshot, in case a callback unsubscribes mid-dispatch.
        for view_id, entry in list(self._subscribers.items()):
            # Older entries were 2-tuples, newer ones 3. Normalize.
            if len(entry) == 3:
                callback, ev_tuple, plug_filter = entry
            else:
                callback, ev_tuple = entry
                plug_filter = None
            for ev in events_snapshot:
                if ev not in ev_tuple:
                    continue
                if ev == EVENT_ATTR_SET and plug_filter is not None:
                    # Skip unless a changed plug intersects the filter.
                    if not (plug_names_snapshot & set(plug_filter)):
                        continue
                try:
                    callback(ev)
                except Exception:
                    # Swallowed, so one bad callback can't break the rest.
                    pass
                break  # one fire per (subscriber, dispatch)

    # ------------------------------------------------------------------
    # Maya callback wiring (api1 MNodeMessage)
    # ------------------------------------------------------------------

    def _attach_maya_callbacks(self) -> None:
        """Subscribe the 4 MNodeMessage events. All handles go
        through CALLBACK_MANAGER so plugin uninit can sweep them."""
        try:
            from maya import OpenMaya as om

            # 1. Attribute add / remove
            cb_id = om.MNodeMessage.addAttributeAddedOrRemovedCallback(
                self._mobject, self._on_attribute_added_or_removed
            )
            tok = CALLBACK_MANAGER.register(
                cb_id, om.MMessage.removeCallback, OWNER_SHARED
            )
            self._tokens.append(tok)

            # 2. Attribute value set / dirty
            cb_id = om.MNodeMessage.addAttributeChangedCallback(
                self._mobject, self._on_attribute_changed
            )
            tok = CALLBACK_MANAGER.register(
                cb_id, om.MMessage.removeCallback, OWNER_SHARED
            )
            self._tokens.append(tok)

            # 3. Name changed
            cb_id = om.MNodeMessage.addNameChangedCallback(
                self._mobject, self._on_name_changed
            )
            tok = CALLBACK_MANAGER.register(
                cb_id, om.MMessage.removeCallback, OWNER_SHARED
            )
            self._tokens.append(tok)

            # 4. About to delete
            cb_id = om.MNodeMessage.addNodeAboutToDeleteCallback(
                self._mobject, self._on_about_to_delete
            )
            tok = CALLBACK_MANAGER.register(
                cb_id, om.MMessage.removeCallback, OWNER_SHARED
            )
            self._tokens.append(tok)
        except Exception:
            # Maya unavailable / older API: degrade to manual fire().
            pass

    # Maya callback handlers -- kept tiny; they just fire the event.

    def _on_attribute_added_or_removed(self, *_args):
        self.fire(EVENT_ATTR_ADDED_OR_REMOVED)

    def _on_attribute_changed(self, msg, plug=None, *_args):
        # Filter on kAttributeSet so we fire on value-set, not every dirty
        # tick, and route the plug's short name through ``fire_plug_set`` so
        # filtered subscribers can opt out of unrelated changes.
        try:
            from maya import OpenMaya as om

            if not (msg & om.MNodeMessage.kAttributeSet):
                return
        except Exception:
            pass
        plug_short_name = ""
        if plug is not None:
            try:
                from maya import OpenMaya as om

                attr_mob = plug.attribute()
                plug_short_name = om.MFnAttribute(attr_mob).name() or ""
            except Exception:
                plug_short_name = ""
        if plug_short_name:
            self.fire_plug_set(plug_short_name)
        else:
            # No plug name: fire ATTR_SET unconditionally. Unfiltered
            # subscribers see it, filtered ones don't.
            self.fire(EVENT_ATTR_SET)

    def _on_name_changed(self, _node, _old_name, *_args):
        # The wrappers ask hub.node_name(), so keep the cache current.
        try:
            from maya import OpenMaya as om

            fn = om.MFnDependencyNode(self._mobject)
            self._node_name = fn.name()
        except Exception:
            pass
        self.fire(EVENT_NAME_CHANGED)

    def _on_about_to_delete(self, *_args):
        self.fire(EVENT_NODE_ABOUT_TO_DELETE)
        # Mark for teardown, but do NOT detach() from inside the callback
        # chain: removeCallback against an in-flight callback can re-enter
        # Maya's MMessage system and hang. The next subscribe() / detach(),
        # or the test harness's _dispatch_pending() flush, cleans up.
        self._attached = False


def make_hub(node_name: str) -> Optional["RefreshHub"]:
    """Convenience factory: build a RefreshHub bound to ``node_name``.
    Returns None if the node doesn't exist."""
    hub = RefreshHub(node_name)
    if not hub.is_attached():
        return None
    return hub
