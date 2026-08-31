"""methods_registry -- per-node Methods source (companion commands + helper API).

The Methods tab is a third code tier alongside Compute and Init, but explicitly
ISOLATED from both: its source execs into its OWN namespace and is NEVER injected
into the compute namespace (unlike Init). Plain ``def``s are a callable helper
API; a ``def`` flagged with ``@maya_command`` is a companion command (callable in
the interpreted node here, and compiled into a real ``MPxCommand`` by the native
pipeline -- see native/codegen + bundler).

Storage mirrors ``InitSourceMixin``: a hidden ``_methodsSource`` string plug so
the source round-trips with the .ma. Unlike Init, there is no per-frame consumer,
so the namespace is built lazily on demand (no scene-callback registration).

Static command DETECTION (used by the spec extractor / codegen) lives in
``maya_command.detect_commands`` and never exec's user code. The lazy runtime
``build_methods_namespace`` / ``call_command`` here DO exec the source -- the same
trust model as Init/Compute (the user's own tab code).
"""
from __future__ import annotations

import inspect
import sys
from typing import List

from mpynode._common.methods.maya_command import (
    detect_commands,
    detect_demos,  # re-exported for callers
    detect_tests,  # re-exported for callers
    duplicate_command_names,  # re-exported for callers
    resolve_create_command_names,  # re-exported for callers
    maya_command,
    maya_demo,
    maya_test,
)
from mpynode._common.methods import test_helpers

__all__ = [
    "MethodsSourceMixin",
    "build_methods_namespace",
    "invoke_command",
    "invoke_factory",
    "run_node_setup",
    "run_node_demo",
    "run_type_demo",
    "run_node_test",
    "run_node_tests",
    "run_test_on_node_name",
    "resolve_demo",
    "resolve_test",
    "make_methods_header",
    "detect_commands",
    "detect_demos",
    "detect_tests",
    "duplicate_command_names",
    "resolve_create_command_names",
]

_PLUG = "_methodsSource"


def make_methods_header(node_type: str) -> str:
    """Friendly commented header to prefill a fresh Methods tab.

    Comment-only, so ``split_methods_source`` routes the whole header to the
    primary Methods view (the class body); the collapsible "Module" strip stays
    empty. The ``@maya_command`` / ``@maya_demo`` decorators are ALWAYS available
    here -- no import is needed (the runtime pre-injects them, and the .py / native
    bake re-synthesizes the import automatically), so the header does not show one.
    """
    bar = "# " + "-" * 68
    return "\n".join([
        bar,
        f"# {node_type} -- Methods: the class body (companion commands + methods).",
        "#",
        "# This tab is ISOLATED from Init and Compute (its own namespace).",
        "# Define class methods here (self-first). Flag any you want exposed as a",
        "# Maya command with @maya_command, or as a demo with @maya_demo -- both",
        "# are always available, no import needed. When the node is compiled or",
        "# baked, each flagged method becomes a companion MPxCommand callable from",
        "# maya.cmds / MEL.",
        "#",
        "# Imports, helper functions, and constants (the code OUTSIDE the class)",
        "# go in the collapsible 'Module' strip at the top of this tab.",
        "#",
        "# @maya_command(name='setMeshRegion', undoable=True)",
        "# def set_region_ids(self, indices=None):",
        "#     self.set_variable('region_ids', indices, persistent=True)",
        bar,
        "",
    ])


def invoke_command(fn, wrapper, args=(), kwargs=None):
    """Call a Methods command ``fn`` with the correct first argument.

    The first parameter classifies the command (the Phase 2 convention):

      * a ``classmethod`` object, OR a plain function whose first parameter is
        named ``cls`` -> a **factory** command: bind the wrapper CLASS
        (``type(wrapper)``). Such a command typically creates + returns a NEW
        node, so it must NOT receive a pre-existing instance.
      * a ``staticmethod`` object -> call with no binding.
      * otherwise -> a **runtime** command: bind the wrapper INSTANCE.

    Pure dispatch (no Maya/Qt) so it is unit-testable.
    """
    kwargs = kwargs or {}
    if isinstance(fn, classmethod):
        return fn.__func__(type(wrapper), *args, **kwargs)
    if isinstance(fn, staticmethod):
        return fn.__func__(*args, **kwargs)
    try:
        first = next(iter(inspect.signature(fn).parameters), None)
    except (TypeError, ValueError):
        first = None
    if first == "cls":
        return fn(type(wrapper), *args, **kwargs)
    return fn(wrapper, *args, **kwargs)


def invoke_factory(fn, wrapper_cls, args=(), kwargs=None):
    """Call a cls-first / @classmethod factory `fn`, binding wrapper_cls
    directly (no instance). Mirrors invoke_command's factory branch."""
    kwargs = kwargs or {}
    if isinstance(fn, classmethod):
        return fn.__func__(wrapper_cls, *args, **kwargs)
    if isinstance(fn, staticmethod):
        return fn.__func__(*args, **kwargs)
    return fn(wrapper_cls, *args, **kwargs)


def _resolved_is_factory(fn):
    """True if the RESOLVED runtime object `fn` is a cls-first / @classmethod
    factory (NOT a staticmethod, self-first function, or None). Mirrors the
    inline cls-first check used elsewhere in this module."""
    if isinstance(fn, classmethod):
        return True
    if isinstance(fn, staticmethod) or fn is None:
        return False
    try:
        params = list(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        return False
    return bool(params) and params[0] == "cls"


def _resolved_is_instance_setup(fn):
    """True if the RESOLVED runtime object `fn` is an instance method (self-first
    plain function, NOT a classmethod/staticmethod object or None). The runtime
    backstop for the self-first setup gate -- mirror of _resolved_is_factory."""
    if isinstance(fn, (classmethod, staticmethod)) or fn is None:
        return False
    try:
        params = list(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        return False
    return bool(params) and params[0] == "self"


def build_methods_namespace(source: str) -> dict:
    """Exec ``source`` into a fresh namespace with ``maya_command`` + ``maya_demo``
    available.

    Raises ``SyntaxError`` on a malformed source (callers that must not fail
    should guard). This DOES exec user code -- same trust model as Init/Compute.

    The marker decorators (``maya_command`` / ``maya_demo`` / ``maya_test``) and
    the ``@maya_test`` assertion helpers (``assert_close`` / ``assert_equal`` /
    ``assert_true`` / ...) are pre-injected, so authored code uses them with NO
    import (the .py / native bake re-synthesizes the imports automatically).
    """
    ns = {
        "maya_command": maya_command,
        "maya_demo": maya_demo,
        "maya_test": maya_test,
    }
    ns.update(test_helpers.HELPERS)
    exec(compile(source or "", "<methods>", "exec"), ns)
    return ns


def run_node_setup(node, selection):
    """Build the node's setup fn from its methods_source, verify it is a
    self-first ``def setup(self, ...)``, and invoke it with ``selection=``.

    Single source of truth for self-first setup invocation (shared by
    _RunSetupCommand and _TemplateCreateCommand so they cannot drift).
    Raises ``node_setup.SetupError`` if there is no self-first setup.
    """
    from mpynode._common.methods import setup_helpers as node_setup

    fn = build_methods_namespace(node.get_methods_source() or "").get("setup")
    if not _resolved_is_instance_setup(fn):
        raise node_setup.SetupError(
            "node %r has no self-first setup" % node.get_name())
    return invoke_command(fn, node, kwargs={"selection": selection})


def resolve_demo(source, demo_name=None):
    """Resolve the chosen demo in ``source`` to ``(fn, is_factory)``.

    Picks by ``demo_name`` (matching ``func_name`` or label) or the sole/first
    demo. Exec's the source once to bind the function object, then classifies it
    with the runtime gates. Raises ``node_setup.SetupError`` when there is no
    demo, ``demo_name`` matches none, or the chosen def is neither a factory nor
    an instance def."""
    from mpynode._common.methods import setup_helpers as node_setup
    from mpynode._common import node_setups

    specs = node_setups.find_demos(source)
    spec = node_setups.select_demo(specs, demo_name)
    if spec is None:
        if demo_name:
            raise node_setup.SetupError("no demo named %r" % demo_name)
        raise node_setup.SetupError("no demo defined")
    ns = build_methods_namespace(source or "")
    fn = ns.get(spec.func_name)
    is_factory = _resolved_is_factory(fn)
    is_instance = _resolved_is_instance_setup(fn)
    if not (is_factory or is_instance):
        raise node_setup.SetupError(
            "demo %r is neither a factory nor an instance def" % spec.func_name)
    return fn, is_factory


def run_node_demo(node, demo_name=None):
    """Run an EXISTING node's INSTANCE demo bound to ``node``. ``demo_name``
    selects among multiple demos (else the first). A demo fabricates its own
    showcase scene (NO selection kwarg). Twin of :func:`run_node_setup`.

    Raises ``node_setup.SetupError`` when there is no matching instance demo. A
    FACTORY demo is rejected here -- it is created via :func:`run_type_demo`
    (bound to the wrapper CLASS, not an instance)."""
    from mpynode._common.methods import setup_helpers as node_setup

    fn, is_factory = resolve_demo(node.get_methods_source() or "", demo_name)
    if is_factory:
        raise node_setup.SetupError(
            "demo %r is a factory; run it via run_type_demo"
            % (demo_name or "demo"))
    return invoke_command(fn, node)


def run_type_demo(native_type, source, demo_name=None):
    """Run a FACTORY demo bound to the wrapper CLASS for ``native_type`` (resolved
    via :func:`mpynode._node_registry.get_spec`). No host node is created or
    wrapped -- the factory owns creation. ``demo_name`` selects among multiple
    demos (else the first).

    Raises ``node_setup.SetupError`` when there is no matching factory demo or the
    type has no registered wrapper class."""
    from mpynode._node_registry import get_spec
    from mpynode._common.methods import setup_helpers as node_setup

    fn, is_factory = resolve_demo(source or "", demo_name)
    if not is_factory:
        raise node_setup.SetupError(
            "demo %r is not a factory" % (demo_name or "demo"))
    spec = get_spec(native_type)
    if spec is None:
        raise node_setup.SetupError(
            "no registered spec for %r" % native_type)
    wrapper_cls = spec.get_wrapper_class()
    return invoke_factory(fn, wrapper_cls)


def resolve_test(source, test_name=None):
    """Resolve the chosen ``@maya_test`` in ``source`` to ``(spec, fn)``.

    Picks by ``test_name`` (matching ``func_name`` or label) or the first test
    in source order. Exec's the source once to bind the function object. Raises
    ``node_setup.SetupError`` when there is no test, ``test_name`` matches none,
    or the chosen def is not a self-first instance def (a test operates on an
    existing node instance)."""
    from mpynode._common.methods import setup_helpers as node_setup
    from mpynode._common import node_setups

    specs = node_setups.find_tests(source)
    spec = node_setups.select_test(specs, test_name)
    if spec is None:
        if test_name:
            raise node_setup.SetupError("no test named %r" % test_name)
        raise node_setup.SetupError("no test defined")
    ns = build_methods_namespace(source or "")
    fn = ns.get(spec.func_name)
    if not _resolved_is_instance_setup(fn):
        raise node_setup.SetupError(
            "test %r is not a self-first instance def" % spec.func_name)
    return spec, fn


def run_node_test(node, test_name=None):
    """Run ONE of a node's ``@maya_test`` methods bound to ``node`` and return a
    result dict ``{name, label, passed, error}``.

    ``test_name`` selects among multiple tests (else the first). The test is
    invoked with the ``@maya_test(digits=N)`` tolerance scoped as the default for
    any ``assert_close`` calls inside it. PASS = the body returns normally
    (``passed=True``, ``error=None``); FAIL = the body raises (``passed=False``,
    ``error`` = the exception text). A missing/invalid test raises
    ``node_setup.SetupError`` (an authoring error, distinct from a test FAIL)."""
    spec, fn = resolve_test(node.get_methods_source() or "", test_name)
    prev = test_helpers.set_default_digits(spec.digits)
    try:
        invoke_command(fn, node)
        return {"name": spec.func_name, "label": spec.label,
                "passed": True, "error": None}
    except test_helpers.TestFailure as exc:
        return {"name": spec.func_name, "label": spec.label,
                "passed": False, "error": str(exc)}
    except Exception as exc:  # any other exception is also a FAIL
        return {"name": spec.func_name, "label": spec.label,
                "passed": False, "error": "%s: %s" % (type(exc).__name__, exc)}
    finally:
        test_helpers.set_default_digits(prev)


class _NodeNameProxy:
    """Minimal stand-in ``self`` for running a ``@maya_test`` against a node that
    is NOT wrapped -- notably a COMPILED node in the parity harness, which has no
    ``_methodsSource`` plug and no registered wrapper. A well-formed test drives
    the node through its PUBLIC plugs (``self.get_name()`` + ``cmds``), so a proxy
    exposing the node name is all it needs."""

    __slots__ = ("_name",)

    def __init__(self, node_name):
        self._name = node_name

    def get_name(self):
        return self._name

    @property
    def name(self):
        return self._name

    def __str__(self):
        return self._name


def run_test_on_node_name(node_name, source, test_name=None):
    """Run a ``@maya_test`` from EXPLICIT ``source`` against a bare node NAME.

    For the parity harness / compiled nodes that carry no ``_methodsSource`` plug:
    the authored source (the spec's ``methods``) is supplied directly and bound to
    a :class:`_NodeNameProxy`. Same result contract as :func:`run_node_test`
    (``{name, label, passed, error}``); a missing/invalid test raises
    ``node_setup.SetupError``."""
    spec, fn = resolve_test(source, test_name)
    prev = test_helpers.set_default_digits(spec.digits)
    try:
        invoke_command(fn, _NodeNameProxy(node_name))
        return {"name": spec.func_name, "label": spec.label,
                "passed": True, "error": None}
    except test_helpers.TestFailure as exc:
        return {"name": spec.func_name, "label": spec.label,
                "passed": False, "error": str(exc)}
    except Exception as exc:
        return {"name": spec.func_name, "label": spec.label,
                "passed": False, "error": "%s: %s" % (type(exc).__name__, exc)}
    finally:
        test_helpers.set_default_digits(prev)


def run_node_tests(node):
    """Run ALL of a node's ``@maya_test`` methods (source order) and return the
    list of per-test result dicts (see :func:`run_node_test`). An empty list
    means the node defines no tests."""
    from mpynode._common import node_setups

    specs = node_setups.find_tests(node.get_methods_source() or "")
    return [run_node_test(node, s.func_name) for s in specs]


class MethodsSourceMixin:
    """Adds ``set_methods_source`` / ``get_methods_source`` /
    ``clear_methods_source`` / ``has_methods_source`` / ``list_commands`` /
    ``call_command`` to any wrapper with a ``self._name``. Persists the Methods
    source on a hidden ``_methodsSource`` string plug (parity with
    ``_initSource``) so it round-trips with the .ma."""

    def set_methods_source(self, source: str) -> bool:
        """Persist the Methods source. Returns True iff it also PARSES (a syntax
        error still stores the text -- so the user never loses edits -- but
        returns False so the UI can flag it)."""
        from maya import cmds

        if not cmds.attributeQuery(_PLUG, node=self._name, exists=True):
            cmds.addAttr(self._name, longName=_PLUG, dataType="string",
                         hidden=True)
        try:
            cmds.setAttr(f"{self._name}.{_PLUG}", source or "", type="string")
        except Exception as exc:
            sys.stderr.write(
                f"[methods_registry] set_methods_source failed on "
                f"{self._name!r}: {exc}\n")
            return False
        try:
            compile(source or "", "<methods>", "exec")
        except SyntaxError as exc:
            sys.stderr.write(
                f"[methods_registry] methods source has a syntax error: {exc}\n")
            return False
        return True

    def get_methods_source(self) -> str:
        from maya import cmds

        if not cmds.attributeQuery(_PLUG, node=self._name, exists=True):
            return ""
        try:
            return cmds.getAttr(f"{self._name}.{_PLUG}") or ""
        except Exception:
            return ""

    def clear_methods_source(self) -> None:
        from maya import cmds

        if cmds.attributeQuery(_PLUG, node=self._name, exists=True):
            try:
                cmds.setAttr(f"{self._name}.{_PLUG}", "", type="string")
            except Exception:
                pass

    def has_methods_source(self) -> bool:
        return bool(self.get_methods_source().strip())

    def run_setup(self, selection=None):
        """Run THIS node's own self-first ``def setup(self, ...)`` bound to this
        instance. Convenience so a ``demo`` body can wire a freshly-fabricated
        peer via ``wrap_node(shape).run_setup([shape])`` -- the wrapper does NOT expose
        methods_source funcs as attributes, so ``self.setup(...)`` would
        AttributeError; this routes through the validated dispatcher instead."""
        return run_node_setup(self, selection)

    def run_demo(self, demo_name=None):
        """Run THIS node's own instance demo (fabricates its showcase scene),
        selecting by ``demo_name`` among multiple. See :meth:`run_setup`."""
        return run_node_demo(self, demo_name)

    def run_test(self, test_name=None):
        """Run ONE of THIS node's ``@maya_test`` validation methods bound to this
        instance; returns ``{name, label, passed, error}``. Selecting by
        ``test_name`` among multiple (else the first). See :meth:`run_setup`."""
        return run_node_test(self, test_name)

    def run_tests(self) -> List[dict]:
        """Run ALL of THIS node's ``@maya_test`` methods (source order); returns
        the list of per-test result dicts. Empty when the node defines none."""
        return run_node_tests(self)

    def list_tests(self) -> List[dict]:
        """Statically-detected ``@maya_test`` defs in this node's Methods source
        (never exec'd)."""
        return detect_tests(self.get_methods_source())

    def list_commands(self) -> List[dict]:
        """Statically-detected ``@maya_command`` defs in this node's Methods
        source (never exec'd)."""
        return detect_commands(self.get_methods_source())

    def build_methods_namespace(self) -> dict:
        """Exec this node's Methods source into a fresh isolated namespace."""
        return build_methods_namespace(self.get_methods_source())

    def call_command(self, command_name: str, *args, **kwargs):
        """Invoke a Methods command in the interpreted node. ``command_name``
        may be the @maya_command name OR the python def name. Raises KeyError if
        not found.

        A RUNTIME command (first param ``self``) is bound to this wrapper
        instance; a FACTORY command (first param ``cls``, or authored as a
        ``@classmethod``) is bound to the wrapper CLASS and typically returns a
        NEW node. See :func:`invoke_command`."""
        source = self.get_methods_source()
        func_name = None
        for c in detect_commands(source):
            if command_name in (c["name"], c["func_name"]):
                func_name = c["func_name"]
                break
        if func_name is None:
            raise KeyError(
                f"no @maya_command named {command_name!r} on {self._name!r}")
        ns = build_methods_namespace(source)
        fn = ns.get(func_name)
        if fn is None:
            raise KeyError(
                f"command {command_name!r} did not define {func_name!r}")
        return invoke_command(fn, self, args, kwargs)


def methods_source_of(node_name: str) -> str:
    """Read a node's persisted Methods source (the ``_methodsSource`` plug) by
    NAME, or "" when the plug is absent / unreadable. The module-level twin of
    :meth:`MethodsSourceMixin.get_methods_source` for callers (e.g. the Scene-tab
    right-click menu) that only have a node name, not a wrapped instance."""
    from maya import cmds

    # Exception-safe: this feeds a right-click menu gate, so a missing / invalid
    # node (attributeQuery raises "No object matches name" rather than returning
    # False) must degrade to "" -- never break menu building.
    try:
        if not cmds.attributeQuery(_PLUG, node=node_name, exists=True):
            return ""
        return cmds.getAttr(f"{node_name}.{_PLUG}") or ""
    except Exception:
        return ""


def node_has_runnable_setup(node_name: str, native_type: str) -> bool:
    """True when "Run setup" applies to ``node_name``: either its TYPE ships a
    built-in setup (:func:`node_setups.type_has_setup`) OR the node's OWN Methods
    source defines a self-first ``def setup(self)``
    (:func:`node_setups.has_setup_source`).

    This is the Scene-tab right-click gate. The earlier type-only check missed
    template nodes -- a plain ``mPyNode`` carrying an instance ``def setup(self)``
    in its Methods tab (e.g. the bubble_sort gallery template) --
    which the Methods-tab right-click already surfaces; this aligns the two
    gates. ``node_setups`` stays Maya-free; the plug read lives here."""
    from mpynode._common import node_setups

    if node_setups.type_has_setup(native_type):
        return True
    return node_setups.has_setup_source(methods_source_of(node_name))


def node_has_runnable_demo(node_name, native_type):
    """True when "Run demo" applies to ``node_name``: its Methods source carries
    at least one demo -- a ``@maya_demo`` decorated def OR the reserved ``def
    demo`` (instance or factory). ``native_type`` is unused (demo has no type
    default; kept for call-site symmetry with :func:`node_has_runnable_setup`)."""
    from mpynode._common import node_setups

    return node_setups.has_demo_source(methods_source_of(node_name))
