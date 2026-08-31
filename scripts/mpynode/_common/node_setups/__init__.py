"""Locate and validate per-type setup sources (``_common/node_setups/<Type>.py``).

A *setup source* is authored Python text containing a module-level instance method
``def setup(self, *args, **kwargs):`` that wires the node it is bound to into the
scene. Types with a setup source may be created with auto-setup (the right-click
"Create + run setup" menu option).

Qt-free + Maya-free on purpose (RCE-safe static detection). Mirrors
:mod:`mpynode._common.util.template_gallery`.

Layout::

    _common/node_setups/mPyMesh.py
    _common/node_setups/mPyDeformer.py
    _common/node_setups/mPyIkSolver.py

The file stem must match the registered native type name EXACTLY (case sensitive).
"""

from __future__ import annotations

import ast
import os
import warnings
from collections import namedtuple
from functools import lru_cache
from typing import List, Optional

from mpynode._common.methods.maya_command import (
    _is_instance_def,
    _is_factory_def,
    _is_static_def,
    detect_commands,
    detect_demos,
    detect_tests,
)

_SETUP_EXT = ".py"
_SETUP_DIRNAME = "node_setups"


def find_setups_root() -> Optional[str]:
    """Return the absolute path to the repo's ``_common/node_setups/`` directory,
    or ``None`` if it can't be located.

    Resolution order:
      1. ``$MPYNODE_ROOT/scripts/mpynode/_common/node_setups`` when
         ``MPYNODE_ROOT`` is set and the directory exists.
      2. Walk up from this file until a directory containing ``scripts/mpynode``
         is found (the repo root); return its
         ``scripts/mpynode/_common/node_setups`` subdir if that exists.
    """
    env_root = os.environ.get("MPYNODE_ROOT")
    if env_root:
        cand = os.path.join(
            env_root, "scripts", "mpynode", "_common", _SETUP_DIRNAME
        )
        if os.path.isdir(cand):
            return os.path.abspath(cand)

    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isdir(os.path.join(d, "scripts", "mpynode")):
            cand = os.path.join(d, "scripts", "mpynode", "_common", _SETUP_DIRNAME)
            return cand if os.path.isdir(cand) else None
        parent = os.path.dirname(d)
        if parent == d:  # reached the filesystem root
            return None
        d = parent


def setup_source_for_type(native_type: str, root: Optional[str] = None) -> Optional[str]:
    """Read the setup source for ``native_type`` as TEXT if one exists, else
    ``None``. Never imports / execs the file (RCE-safe at detection time).

    ``root`` overrides the setups directory (for tests); otherwise
    :func:`find_setups_root` is used.
    """
    if not native_type:
        return None
    if root is None:
        root = find_setups_root()
    if not root:
        return None
    fname = native_type + _SETUP_EXT
    # Case-sensitive stem match even on case-insensitive filesystems (macOS APFS):
    # os.path.isfile("mPyIksolver.py") returns True for "mPyIkSolver.py" there, so
    # require an EXACT entry in the directory listing (which preserves real case).
    try:
        if fname not in os.listdir(root):
            return None
    except (OSError, IOError):
        return None
    p = os.path.join(root, fname)
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, IOError):
        return None


def _find_hook(source: Optional[str], hook_name: str, accept=_is_instance_def) -> Optional[ast.FunctionDef]:
    """ast.FunctionDef for the module-level ``def <hook_name>`` whose LAST binding
    satisfies ``accept``, else None. Never execs; never raises. Shared engine for
    the reserved ``setup``/``demo`` hooks. ``accept`` defaults to the self-first
    instance gate; ``find_demos`` passes a widened predicate that also accepts a
    ``cls``-first / @classmethod factory (a demo-only relaxation).

    Returns the LAST matching def (not the first). This MUST match
    build_methods_namespace, which execs the source so that ns[hook_name] is the
    LAST definition (Python rebinding). A first-match gate would disagree with
    exec and let ``def <hook>(self)`` (first) shadow ``def <hook>(cls)`` (last),
    mis-binding an instance to a factory body. FunctionDef-only is intentional
    (async hooks are unsupported) -- this gate is deliberately NOT identical to
    detect_commands' AsyncFunctionDef-inclusive walk.
    """
    if not source or not source.strip():
        return None
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    last = None
    for node in tree.body:  # module level only
        if isinstance(node, ast.FunctionDef) and node.name == hook_name:
            last = node  # the LAST `def <hook>` of ANY kind (matches exec rebind)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == hook_name for t in node.targets
        ):
            last = None  # a later `<hook> = ...` rebind exec'd over the def
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == hook_name
        ):
            last = None  # `<hook>: T = ...` likewise rebinds the name
    if last is None:
        return None
    # The gate's verdict matches what exec will bind: only the LAST *binding* of
    # the name survives, and it is the auto-hook entry ONLY if it is a self-first
    # instance def (no @classmethod/@staticmethod). A self-first def shadowed by a
    # later factory def -- or by `<hook> = staticmethod(<hook>)` / `<hook> = None`
    # -- is correctly rejected here; runtime re-validate is the definitive backstop
    # for any exotic rebind the AST cannot resolve.
    if accept(last):
        return last
    return None


def find_setup(source: Optional[str]) -> Optional[ast.FunctionDef]:
    """ast.FunctionDef for the module-level self-first ``def setup``, else None.
    Never execs; never raises. See :func:`_find_hook`."""
    return _find_hook(source, "setup")


def find_demo(source: Optional[str]) -> Optional[ast.FunctionDef]:
    """ast.FunctionDef for the module-level self-first ``def demo``, else None.
    Never execs; never raises. The demo hook builds a self-contained showcase
    scene (create geometry, keyframe, viewFit, duplicate self) and delegates to
    ``self.setup(...)`` where a real setup exists. See :func:`_find_hook`."""
    return _find_hook(source, "demo")


def has_setup_source(source: Optional[str]) -> bool:
    """True when ``source`` contains a valid self-first ``def setup``."""
    return find_setup(source) is not None


CommandTemplate = namedtuple(
    "CommandTemplate", "name func_name params doc source"
)


def split_type_default(source: Optional[str]):
    """``(kept, templates)`` -- the seed minus its PLAIN commands, plus those.

    A seed carries two kinds of thing and they are surfaced differently:

      * the ``setup`` / ``demo`` hooks, any helper, and a ``creates=True``
        factory command -- these AUTO-MERGE onto the node, so a fresh node can
        be built and ``cmds.<nodeType>()`` works without the user writing
        anything. A create command needs no naming decision: it is already
        named per-Class by ``resolve_create_command_names``.
      * every PLAIN ``@maya_command`` -- these do NOT merge. They are offered as
        copy-out TEMPLATES in the Script tab instead, because the user has to
        make a naming decision the framework cannot make for them: two node
        types shipping the same plain command name is refused at mega-compile.

    Returns the kept text and a list of :class:`CommandTemplate`. Never execs,
    never raises: unparseable source yields ``(source, [])``.
    """
    src = source or ""
    if not src.strip():
        return src, []
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return src, []

    # Keyed by the def's own lineno, so two same-named defs cannot collide.
    by_line = {c["lineno"]: c for c in detect_commands(src, tree=tree)}
    lines = src.splitlines()
    drop = set()
    templates = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        cmd = by_line.get(node.lineno)
        if cmd is None or cmd.get("creates"):
            continue  # not a command, or the factory -- both stay
        start = node.lineno - 1
        for dec in (node.decorator_list or []):
            start = min(start, dec.lineno - 1)
        end = getattr(node, "end_lineno", None) or node.lineno
        drop.update(range(start, end))
        templates.append(CommandTemplate(
            name=cmd["name"],
            func_name=cmd["func_name"],
            params=tuple(cmd.get("params") or ()),
            doc=ast.get_docstring(node) or "",
            source="\n".join(lines[start:end]),
        ))

    if not drop:
        return src, []
    kept = [ln for i, ln in enumerate(lines) if i not in drop]
    # Collapse the runs of blank lines the excisions leave behind.
    out, blanks = [], 0
    for ln in kept:
        blanks = blanks + 1 if not ln.strip() else 0
        if blanks < 3:
            out.append(ln)
    return "\n".join(out).rstrip() + "\n", templates


def command_templates_for_type(native_type: str,
                               root: Optional[str] = None) -> List[CommandTemplate]:
    """The plain-command TEMPLATES a node type offers, for the Script tab.

    These are exactly the defs :func:`merge_type_default` declines to merge, so
    the palette and the node can never disagree about what is already there."""
    return split_type_default(
        setup_source_for_type(native_type, root=root))[1]


# The framework's own authoring surface, offered on EVERY node type. Distinct
# from command_templates_for_type, which yields the handful of PLAIN commands a
# particular seed declines to merge -- only mPyBlendShape has any, so a Script
# tab driven by that alone shows an empty palette on 11 of 12 types.
#
# These are skeletons, not commands: they are never "already used" (a node may
# carry any number of them), so they are always offered and carry no params.
_FRAMEWORK_TEMPLATES = (
    ("@maya_command", "my_command", "A companion MPxCommand on this node.", '''\
@maya_command(name="myCommand", undoable=True)
def my_command(self, value=1.0):
    """Runs as `cmds.myCommand(node, value=...)` once this node is built.

    `self` is the wrapped node. Rename BOTH the command and the def before
    committing: two node types shipping one plain command name is refused at
    mega-compile."""
    return value
'''),
    ("@maya_demo", "my_demo", "A demo the Scene tab can run.", '''\
@maya_demo(label="My Demo")
def my_demo(self):
    """Build a small scene that shows this node doing its job. Runs from the
    Scene tab and from the navigator's DEMOS row."""
    from maya import cmds as mc

    mc.polySphere()
'''),
    ("@maya_test", "test_my_node", "A test the harness reports pass/fail for.",
     '''\
@maya_test(digits=5)
def test_my_node(self):
    """Return True to pass. A @maya_test reports a VERDICT rather than raising,
    so an assertion that fails still returns cleanly."""
    return True
'''),
    ("def setup", "setup", "The reserved build hook, run once on create.", '''\
def setup(self):
    """Reserved hook: wire the node up when it is created. Runs from the Scene
    tab's Run setup and from the navigator's SETUP row."""
    return True
'''),
)


def framework_templates() -> List[CommandTemplate]:
    """The blessed decorators every node type can carry, as copy-out templates.

    Same :class:`CommandTemplate` shape the per-type offers use, so one palette
    renders both.
    """
    return [CommandTemplate(name, func_name, (), doc, source)
            for name, func_name, doc, source in _FRAMEWORK_TEMPLATES]


def merge_type_default(methods_source: Optional[str], native_type: str,
                       root: Optional[str] = None) -> str:
    """``methods_source`` with the type default appended if it has no setup yet.

    THE merge rule, in one place. ``MPyNode._populate_methods_source`` applies it
    to a live node at create time; ``spec_from_mpn_payload`` applies it to a
    template payload at compile time. They MUST agree: the node a user gets from
    a template carries the seeded setup, so the node compiled from that same
    template has to carry it too -- otherwise the compiled artifact silently
    lacks the create command (and the setup) that the interpreted one has.

    Rules: no type default -> return input; the source already has a self-first
    setup -> the author wins, return input; otherwise APPEND (never replace) so
    sibling methods/demos/commands survive.

    What gets appended is the seed MINUS its plain commands -- see
    :func:`split_type_default`. Those are offered as copy-out templates instead
    of being written into every node, so the user names them deliberately.
    """
    type_src = setup_source_for_type(native_type, root=root)
    if not type_src:
        return methods_source or ""
    type_src = split_type_default(type_src)[0]
    cur = methods_source or ""
    if find_setup(cur) is not None:
        return cur
    if not type_src.strip():
        return cur
    return (cur + "\n\n" + type_src) if cur.strip() else type_src


DemoSpec = namedtuple(
    "DemoSpec", "label func_name is_factory is_instance is_static lineno"
)


def _accept_demo_hook(fn) -> bool:
    """Reserved ``def demo`` acceptance: an instance def OR a factory (cls-first /
    @classmethod) def. Static twin of the runtime instance-or-factory gate."""
    return _is_instance_def(fn) or _is_factory_def(fn)


def find_demos(source):
    """All demos in ``source`` (source order): every ``@maya_demo``-decorated
    top-level def UNIONED with the reserved ``def demo`` (last binding) when it is
    not already decorated. Static AST only; never execs; never raises.

    A demo may be an instance def (``self``-first) or a factory (``cls``-first /
    @classmethod). Duplicate ``func_name``s (a Python redefinition) keep the first
    and warn. Returned in ascending ``lineno`` order."""
    if not source or not source.strip():
        return []
    specs = []
    seen = set()
    for d in detect_demos(source):
        fn = d["func_name"]
        if fn in seen:
            warnings.warn(
                "duplicate demo def %r; later definition ignored." % fn)
            continue
        seen.add(fn)
        specs.append(DemoSpec(
            d["label"], fn, d["is_factory"], d["is_instance"],
            d["is_static"], d["lineno"]))
    if "demo" not in seen:
        node = _find_hook(source, "demo", accept=_accept_demo_hook)
        if node is not None:
            specs.append(DemoSpec(
                "Run demo", "demo", _is_factory_def(node),
                _is_instance_def(node), _is_static_def(node), node.lineno))
    specs.sort(key=lambda s: s.lineno)
    return specs


def demo_labels(source):
    """UI convenience: the label of each demo in ``source`` (source order)."""
    return [s.label for s in find_demos(source)]


def select_demo(specs, demo_name=None):
    """Pick a DemoSpec from ``specs`` by ``func_name``/``label`` match, else the
    first (source order), else None when ``specs`` is empty or ``demo_name`` does
    not match. Shared selector for the runtime and the command layer."""
    if not specs:
        return None
    if demo_name:
        for s in specs:
            if demo_name in (s.func_name, s.label):
                return s
        return None
    return specs[0]


def has_demo_source(source: Optional[str]) -> bool:
    """True when ``source`` contains at least one demo -- a ``@maya_demo``
    decorated def OR the reserved ``def demo`` (instance or factory). Unlike
    setup, demo has NO type-default machinery: demos are authored only in a
    template/node's own methods_source."""
    return len(find_demos(source)) > 0


# ---- @maya_test discovery (decorator-only; NO reserved ``def test`` hook) ----

TestSpec = namedtuple(
    "TestSpec", "label func_name digits is_factory is_instance is_static lineno"
)


def find_tests(source):
    """All ``@maya_test``-decorated top-level defs in ``source`` (source order).

    Static AST only; never execs; never raises. Unlike demos there is NO
    reserved-name hook -- a test must be explicitly flagged with ``@maya_test``.
    Duplicate ``func_name``s (a Python redefinition) keep the first and warn.
    Returned in ascending ``lineno`` order."""
    if not source or not source.strip():
        return []
    specs = []
    seen = set()
    for d in detect_tests(source):
        fn = d["func_name"]
        if fn in seen:
            warnings.warn(
                "duplicate test def %r; later definition ignored." % fn)
            continue
        seen.add(fn)
        specs.append(TestSpec(
            d["label"], fn, d["digits"], d["is_factory"], d["is_instance"],
            d["is_static"], d["lineno"]))
    specs.sort(key=lambda s: s.lineno)
    return specs


def test_labels(source):
    """UI convenience: the label of each test in ``source`` (source order)."""
    return [s.label for s in find_tests(source)]


def select_test(specs, test_name=None):
    """Pick a TestSpec from ``specs`` by ``func_name``/``label`` match, else the
    first (source order), else None. Mirrors :func:`select_demo`."""
    if not specs:
        return None
    if test_name:
        for s in specs:
            if test_name in (s.func_name, s.label):
                return s
        return None
    return specs[0]


def has_test_source(source: Optional[str]) -> bool:
    """True when ``source`` contains at least one ``@maya_test`` def."""
    return len(find_tests(source)) > 0


@lru_cache(maxsize=None)
def _type_has_setup_cached(native_type: str) -> bool:
    """Cached implementation that may raise on IO errors.

    lru_cache does NOT memoize exceptions, so transient failures are retried
    on the next call. Only successful results are cached.
    """
    src = setup_source_for_type(native_type)
    return has_setup_source(src)


def type_has_setup(native_type: str) -> bool:
    """True when ``native_type`` has a setup source.

    This is the public gate used by the menu system and command builders.
    Transient IO failures return False (not cached).
    """
    try:
        return _type_has_setup_cached(native_type)
    except Exception:
        return False  # transient failure -> not cached
