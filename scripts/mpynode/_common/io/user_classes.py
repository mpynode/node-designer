"""In-memory home for UI-authored node Classes.

A UI-authored logical Class (e.g. ``Procrustes``) has no real module on disk.
Instead of writing a stub ``.py``, we synthesize a thin, code-free subclass of
the node's root wrapper in memory and expose it under a single synthetic module
``mpynode_user`` registered in ``sys.modules``.

Why this is safe: a live node ALWAYS executes its authored code from its plugs
(``_computeSource``/``_initSource``/``_methodsSource``), never from the imported
class -- the class is consumed only at ``MPyNode.__new__`` dispatch as an
identity token. So the class body can be empty; it exists only so
``_import_py_class("mpynode_user.Procrustes")`` resolves and ``isinstance`` /
``MyClass.ls()`` work without a bake.

No files are written. ``mpynode_user`` is rebuilt from the scene on file-open
(see ``scene_callbacks``). The one and only on-disk ``.py`` is the explicit,
user-driven Bake output.
"""
from __future__ import annotations

import importlib
import sys
import types

PACKAGE = "mpynode_user"


def ensure_module():
    """Return the in-memory ``mpynode_user`` module, creating + registering it in
    ``sys.modules`` on first call. Idempotent; no disk, no ``sys.path`` change."""
    mod = sys.modules.get(PACKAGE)
    if mod is None:
        mod = types.ModuleType(PACKAGE)
        mod.__doc__ = "In-memory home for UI-authored MPyNode classes."
        sys.modules[PACKAGE] = mod
    return mod


def _root_wrapper(native_type):
    """The registry root wrapper class for a Maya native type (mPyNode ->
    MPyNode, mPyFile -> MPyFile, ...). Raises ValueError if the type is unknown."""
    from mpynode._node_registry import get_spec

    spec = get_spec(native_type)
    if spec is None:
        raise ValueError("unknown native_type %r" % (native_type,))
    root = spec.get_wrapper_class()
    if not isinstance(root, type):
        raise ValueError("no wrapper class for native_type %r" % (native_type,))
    return root


def synthesize(class_name, native_type):
    """Return an importable class ``mpynode_user.<class_name>`` subclassing the
    root wrapper for ``native_type``, creating it in memory on first request.

    Idempotent: a repeat call with the SAME base returns the existing class; the
    SAME name with a DIFFERENT base raises ValueError (a real identity clash)."""
    if not class_name or not isinstance(class_name, str):
        raise ValueError("class_name must be a non-empty str")
    mod = ensure_module()
    root = _root_wrapper(native_type)
    existing = getattr(mod, class_name, None)
    if existing is not None:
        if isinstance(existing, type) and issubclass(existing, root):
            return existing
        raise ValueError(
            "class %r already synthesized with a different base "
            "(have %r, requested subclass of %r)"
            % (class_name, existing, root))
    cls = type(class_name, (root,), {"__module__": PACKAGE})
    setattr(mod, class_name, cls)
    importlib.invalidate_caches()
    return cls


def dotted_path(class_name):
    """The canonical importable dotted path for a UI-authored class name."""
    return "%s.%s" % (PACKAGE, class_name)


def stamp_class(node_name, native_type, class_name):
    """Synthesize ``mpynode_user.<class_name>`` and stamp it as ONE node's
    ``class_path`` -- the reusable, UI-free name/fork primitive shared by the
    scene-tree menu, the Identity panel, and the compile dialog's fork step.

    Returns the canonical dotted path on success, or ``None`` if the node can't
    be wrapped. Mutates the scene (writes the ``class_path`` plug); the CALLER
    owns any undo chunk (so a multi-node fork is one undoable step). Propagates
    ``ValueError`` from ``synthesize`` on an invalid name or an identity clash
    (same name, different base)."""
    from mpynode._node_registry import wrap_node

    synthesize(class_name, native_type)  # validates + registers the class
    wn = wrap_node(node_name, native_type)
    if wn is None:
        return None
    path = dotted_path(class_name)
    wn.set_py_class(path)
    return path


def synthesize_from_scene():
    """Rebuild the in-memory classes for every distinct ``class_path`` under
    ``mpynode_user.`` present in the current scene. Returns the count
    synthesized. Best-effort; never raises."""
    ensure_module()  # a scene sweep always leaves mpynode_user present (maybe empty)
    try:
        from maya import cmds
    except Exception:
        return 0
    from mpynode._node_registry import all_native_types
    from mpynode.wrappers._mpy_node import _read_py_class

    try:
        known = set(cmds.allNodeTypes() or [])
    except Exception:
        known = None
    seen = set()
    count = 0
    prefix = PACKAGE + "."
    for nt in all_native_types():
        if known is not None and nt not in known:
            continue
        try:
            nodes = cmds.ls(type=nt) or []
        except Exception:
            continue
        for node in nodes:
            pc = _read_py_class(node)
            if not pc or not pc.startswith(prefix):
                continue
            short = pc.rpartition(".")[2]
            key = (short, nt)
            if not short or key in seen:
                continue
            seen.add(key)
            try:
                synthesize(short, nt)
                count += 1
            except Exception:
                pass
    return count
