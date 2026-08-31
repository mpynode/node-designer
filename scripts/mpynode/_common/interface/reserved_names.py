"""Reserved-name resolver -- the ONE authoritative answer to "may a user take
this name on this node?".

Three authoring-time guard sites (add-attr, rename, stored/temporary vars) and
the scene-open warning all resolve through here, so the answer cannot drift
between them.

What counts as reserved, and where each part comes from:

* **SelfProxy bridge methods** -- ``get_compute_locals`` / ``diff_storage`` /
  ... are real attributes on the class, so ``self.X`` finds them by normal
  lookup and ``__getattr__`` (the plug / storage tiers) never runs. Derived
  LIVE from ``dir(SelfProxy)``; that module imports only ``typing``.
* **Blessed methods + properties** -- SelfProxy Tier 0 / 0.5, above the plug
  tree. Derived LIVE from the Maya-free ``method_registry``.
* **Framework compute_locals slots** -- SelfProxy Tier 1. These are seeded
  inside ``compute()`` from a live datablock, so they cannot be read back
  without Maya AND a real evaluation. They are declared on the wrapper class
  instead, across two tuples: ``INTERNAL_API_SLOTS`` (already shipping; also
  drives the Framework / Variables tabs) and ``RESERVED_COMPUTE_LOCALS`` (the
  seeded names that are deliberately NOT UI rows). ``tests/authoring/test_reserved_names``
  AST-parses the real seed dicts out of ``_api1`` / ``_api2`` and fails if the
  union stops matching.

The rule that decides the edge cases: a name that SHADOWS is reserved, a name
that COEXISTS is not. A seeded compute_locals slot the bridge also passes in
``output_scratch_keys`` COEXISTS -- a real plug WINS on read there, so a user
input/output of that name is readable via ``self.<name>`` while writes still
land in the scratch slot. Those are declared per wrapper in a third tuple,
``COEXISTING_SCRATCH_SLOTS``, and subtracted below. The same rule is why
mPyBlendShape's ``aliases`` / ``target_count`` / ``alias_fingerprint`` are not
reserved (see ``_AUTHORING_ONLY_SLOTS``).

Everything is lazy and fails OPEN. ``wrappers/_mpy_node.py`` imports this
during plug-in registration, before ``_common`` is guaranteed importable, so an
unavailable dependency must yield "nothing is reserved" -- never an exception.
"""

from __future__ import annotations


# Bookkeeping prefix owned by SelfProxy's ``__dict__`` (see self_proxy.py).
RESERVED_PREFIXES = ("_psp_",)


# Node type -> (module path, wrapper class name). A LOCAL copy of the map in
# ui/widgets/plug_tree_walker.py, which can't be imported here: it lives in
# ``ui`` and does ``import maya.cmds`` at module scope, which the
# registration-time caller cannot reach.
_TYPE_TO_WRAPPER = {
    "mPyNode": ("mpynode.wrappers._mpy_node", "MPyNode"),
    "mPyBlendShape": ("mpynode.wrappers.mpy_blend_shape", "MPyBlendShape"),
    "mPyConstraint": ("mpynode.wrappers.mpy_constraint", "MPyConstraint"),
    "mPyDeformer": ("mpynode.wrappers.mpy_deformer", "MPyDeformer"),
    "mPyFile": ("mpynode.wrappers.mpy_file", "MPyFile"),
    "mPyIkSolver": ("mpynode.wrappers.mpy_iksolver", "MPyIkSolver"),
    "mPyLocator": ("mpynode.wrappers.mpy_locator", "MPyLocator"),
    "mPyMesh": ("mpynode.wrappers.mpy_mesh", "MPyMesh"),
    "mPyNurbsCurve": ("mpynode.wrappers.mpy_nurbs_curve", "MPyNurbsCurve"),
    "mPyNurbsSurface": ("mpynode.wrappers.mpy_nurbs_surface",
                        "MPyNurbsSurface"),
    "mPySkinCluster": ("mpynode.wrappers.mpy_skin_cluster", "MPySkinCluster"),
    "mPyTransform": ("mpynode.wrappers.mpy_transform", "MPyTransform"),
}


# INTERNAL_API_SLOTS rows that are NOT actually reserved: ``@property`` names on
# the MPyBlendShape WRAPPER, never bound into SelfProxy, so a user input called
# ``aliases`` resolves to the plug and works today. Blocking them would regress
# that, so they are dropped here rather than removed from INTERNAL_API_SLOTS,
# which drives UI rows. ``morphs`` is deliberately absent -- it is a real
# blessed PropertySpec, resolving at SelfProxy Tier 0.5 above the plug tree.
_AUTHORING_ONLY_SLOTS = {
    "mPyBlendShape": frozenset({"aliases", "target_count",
                                "alias_fingerprint"}),
}


def known_types():
    """Every mpy node type this resolver can answer for."""
    return tuple(sorted(_TYPE_TO_WRAPPER))


def _wrapper_class_for_type(node_type):
    """Wrapper class for ``node_type``, or None. Never raises."""
    try:
        entry = _TYPE_TO_WRAPPER.get(str(node_type or ""))
        if entry is None:
            return None
        module_name, class_name = entry
        mod = __import__(module_name, fromlist=[class_name])
        return getattr(mod, class_name, None)
    except Exception:
        return None


def _slot_reason(name, node_type, direction, hint):
    tier = str(direction or "").strip().lower()
    if tier in ("read", "write", "readwrite"):
        label = "framework {} slot".format(tier.upper())
    else:
        label = "framework slot"
    text = "{!r} is a {} on {}".format(name, label, node_type)
    if hint:
        text += " -- {}".format(hint)
    return text


def _coexisting_scratch_slots(cls):
    """Slot names the node's compute bridge passes as ``output_scratch_keys``.

    For those a real plug WINS on read (see ``compute/self_proxy.py``), so a
    user input/output of that name COEXISTS with the write buffer -- it stays
    readable as ``self.<name>`` -- instead of being shadowed by it. Not
    reserved.

    Declared on the wrapper for the same reason ``RESERVED_COMPUTE_LOCALS``
    is: the set is only passed from inside the api2 compute body, so it cannot
    be read back without Maya AND a real evaluation. ``_tests/
    test_reserved_names`` AST-parses the real ``output_scratch_keys=`` call
    and fails if the declaration drifts either way. Never raises."""
    try:
        raw = getattr(cls, "COEXISTING_SCRATCH_SLOTS", ()) or ()
        return frozenset(str(name) for name in raw)
    except Exception:
        return frozenset()


def _add_wrapper_slots(node_type, out):
    """Fold both wrapper name tuples into ``out``. Never raises."""
    cls = _wrapper_class_for_type(node_type)
    if cls is None:
        return
    skip = set(_AUTHORING_ONLY_SLOTS.get(str(node_type or ""), frozenset()))
    skip |= _coexisting_scratch_slots(cls)
    for attr_name in ("INTERNAL_API_SLOTS", "RESERVED_COMPUTE_LOCALS"):
        try:
            raw = getattr(cls, attr_name, ()) or ()
        except Exception:
            continue
        for entry in raw:
            try:
                # Both the legacy flat-string form and the extended
                # (name, direction, hint) triple are accepted.
                if isinstance(entry, str):
                    name, direction, hint = entry, "", ""
                else:
                    name = str(entry[0])
                    direction = str(entry[1]) if len(entry) > 1 else ""
                    hint = str(entry[2]) if len(entry) > 2 else ""
            except Exception:
                continue
            if not name or name in skip:
                continue
            out.setdefault(
                name, _slot_reason(name, node_type, direction, hint)
            )


def _add_blessed(node_type, out):
    """Fold SelfProxy Tier 0 / 0.5 names into ``out``. Never raises."""
    try:
        from mpynode._common.interface.method_registry import (
            methods_for_type,
            properties_for_type,
        )
    except Exception:
        return
    try:
        for spec in methods_for_type(node_type) or ():
            out.setdefault(
                spec.name,
                "{!r} is a built-in method on {} -- call it as "
                "self.{}(...)".format(spec.name, node_type, spec.name),
            )
    except Exception:
        pass
    try:
        for spec in properties_for_type(node_type) or ():
            out.setdefault(
                spec.name,
                "{!r} is a built-in property on {} -- read it as "
                "self.{}".format(spec.name, node_type, spec.name),
            )
    except Exception:
        pass


def _add_self_bridge(out):
    """Fold the SelfProxy public method surface into ``out``. Never raises."""
    try:
        from mpynode._common.compute.self_proxy import SelfProxy
    except Exception:
        return
    try:
        names = dir(SelfProxy)
    except Exception:
        return
    for name in names:
        if name.startswith("_"):
            continue
        out.setdefault(
            name,
            "{!r} is a built-in method of 'self' (the framework compute "
            "bridge) and would hide any attribute or variable of that "
            "name".format(name),
        )


def reserved_names_for_type(node_type):
    """``{name: reason}`` for every name a user may not take on ``node_type``.

    ``reason`` is a full sentence fit for a dialog. Returns ``{}`` for an
    unknown type and on ANY failure (fail open).
    """
    out = {}
    try:
        # Nothing to say about a node that is not one of ours -- the whole
        # reserved surface (bridge, blessed, slots) only exists on an mpy node.
        if str(node_type or "") not in _TYPE_TO_WRAPPER:
            return {}
        _add_wrapper_slots(node_type, out)
        _add_blessed(node_type, out)
        _add_self_bridge(out)
    except Exception:
        return {}
    return out


def reserved_names_for_node(node_name):
    """``reserved_names_for_type`` for a live node. Returns ``{}`` on any
    failure -- node gone, Maya unavailable, unregistered type."""
    try:
        import maya.cmds as mc

        node_type = mc.nodeType(node_name)
    except Exception:
        return {}
    return reserved_names_for_type(node_type)


def check_reserved_name(name, node_type=None, node_name=None):
    """Return the REASON ``name`` is reserved, or None if it is free.

    Pass ``node_type`` when known; ``node_name`` is resolved to a type lazily.
    With neither, only the type-independent surface (prefixes + the SelfProxy
    bridge) is checked. Never raises.
    """
    try:
        text = str(name or "")
        if not text:
            return None
        for prefix in RESERVED_PREFIXES:
            if text.startswith(prefix):
                return (
                    "names starting with {!r} are reserved by the "
                    "framework's 'self' bookkeeping".format(prefix)
                )
        if node_type is None and node_name is not None:
            reserved = reserved_names_for_node(node_name)
        elif node_type is not None:
            reserved = reserved_names_for_type(node_type)
        else:
            reserved = {}
            _add_self_bridge(reserved)
        return reserved.get(text)
    except Exception:
        return None
