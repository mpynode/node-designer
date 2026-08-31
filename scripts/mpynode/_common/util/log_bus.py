"""Log broadcast bus.

Qt-free producer/consumer bus for routing log messages from non-UI
code (compute bridges, helpers, demos) into one or more UI panels
(currently ``mpynode.ui.widgets.logger.NDLoggerWidget``).

**Why this lives in `_common/` and not in `ui/widgets/`:** non-UI
code (the bridge `_run_expression` paths) need to call ``log()`` on
expression error, but they MUST NOT transitively import Qt. Qt isn't
available in mayapy batch and isn't appropriate for headless test
contexts. The bus has zero Qt deps; the widget side imports the bus
and calls ``subscribe(self)``.

Usage:

 # From any non-UI module (bridge, helper, etc.):
 from mpynode._common.util.log_bus import log
 log("compute() ran in 3.2ms")
 log(f"expression error: {exc}", level="error")

 # From a UI widget on construction:
 from mpynode._common.util.log_bus import subscribe, unsubscribe
 subscribe(self)
 #... and on closeEvent:
 unsubscribe(self)

Subscribers must implement ``append_message(message: str, level: str)``.
Failures inside a subscriber are silently swallowed so a buggy panel
doesn't break the broadcast loop.
"""

from __future__ import annotations

from typing import Any


# Live subscribers. Each must expose ``append_message(message, level)``.
# Using a bare list (vs. a Python ``logging`` Handler) keeps coupling
# minimal and avoids interfering with global logging configuration.
_SUBSCRIBERS: list[Any] = []


# Valid level strings. Subscribers can map to colors / styling as
# they see fit. Producers should stick to these three for consistency.
VALID_LEVELS: frozenset[str] = frozenset({"info", "warning", "error"})


def log(message: str, level: str = "info") -> None:
    """Broadcast a message to every live subscriber.

    Safe to call from any thread / context. Returns silently if no
    subscribers are alive. ``level`` should be one of
    ``info`` / ``warning`` / ``error`` (defaults to ``info``); other
    strings are passed through unchanged so subscribers can interpret
    them however they want.
    """
    text = str(message)
    for subscriber in list(_SUBSCRIBERS):
        try:
            subscriber.append_message(text, level)
        except Exception:
            # Swallow failures from individual subscribers so the
            # broadcast loop keeps going. List cleanup is the
            # subscriber's responsibility (call ``unsubscribe``
            # in your destructor / closeEvent).
            pass


def subscribe(subscriber: Any) -> None:
    """Register a subscriber. Idempotent: re-subscribing is a no-op."""
    if subscriber not in _SUBSCRIBERS:
        _SUBSCRIBERS.append(subscriber)


def unsubscribe(subscriber: Any) -> None:
    """Remove a subscriber. Safe if not present."""
    try:
        _SUBSCRIBERS.remove(subscriber)
    except ValueError:
        pass
