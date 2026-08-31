"""``@maya_command`` marker + static command detection (Methods-tab feature).

The Methods tab holds plain Python ``def``s, explicitly isolated from Init and
Compute. A ``def`` flagged with ``@maya_command`` is a *companion command*: in
the interpreted mPyNode it is callable through the command framework, and the
native compile step emits a companion ``MPxCommand`` registered alongside the
node (so ``maya.cmds.<name>`` / MEL can drive the compiled node).

This module is deliberately dependency-light (``ast``/``warnings`` only -- NO
maya, NO Qt) so it can be imported into the user's Methods namespace AND used
by the spec extractor / codegen alike.

``maya_command`` is a SIDE-EFFECT-FREE no-op marker (the decorated function still
works as a normal function); it only records ``__maya_command__`` metadata.
``detect_commands(source)`` finds the flagged top-level defs by STATIC AST --
never importing or exec'ing user code, consistent with the codebase's
RCE-safety posture (cf. import_follower).

Static-detection caveats (the detector ONLY honors literals):

  * ``@maya_command(name=...)`` -- ``name`` must be a string LITERAL. Any
    expression (e.g. ``name=PREFIX + 'X'``) cannot be resolved without exec'ing
    user code, so detection warns and falls back to the def's own name.
  * ``@maya_command(undoable=...)`` -- ``undoable`` must be a bool LITERAL.
    Non-literal values warn and default to ``True``.
  * ``@maya_command(creates=...)`` -- ``creates`` must be a bool LITERAL.
    Non-literal values warn and default to ``False``. ``creates=True`` on a
    factory / staticmethod def warns and is ignored (see ``maya_command``).
  * The decorator must be written as the literal name ``@maya_command`` (or as
    an attribute ``@m.maya_command`` of an imported module). Aliasing it with
    ``from ... import maya_command as mc`` and writing ``@mc`` defeats the
    static walker -- detection warns so the silent-drop is visible.
"""
from __future__ import annotations

import ast
import warnings
from typing import List


# ---- The marker decorator (importable into the Methods namespace) ----

def maya_command(name=None, undoable=True, creates=False):
    """Flag a Methods ``def`` as a companion Maya command.

    Usable bare (``@maya_command``) or parameterized
    (``@maya_command(name="createMeshRegion", undoable=False)``). Records
    ``func.__maya_command__ = {"name", "undoable", "creates"}`` and returns the
    function UNCHANGED -- it is a no-op at runtime.

    ``creates=True`` marks a **create command**: the ``blendShape``/``skinCluster``
    shape, where one call both CREATES the node and wires it into the scene. It is
    written on the self-first ``setup`` def::

        @maya_command("patchRelax", creates=True)
        def setup(self, selection=None, *args, **kwargs):
            ...

    The body stays an ordinary instance method -- ``self`` is just its first
    parameter, and who produced that node is the caller's business. Interpreted,
    the caller is the gallery / Scene-tab "Run setup" and the node already exists.
    Compiled, the generated ``MPxCommand`` snapshots the selection, creates the
    node itself, and passes it in as ``self``. Same body, same order
    (create -> configure), different caller.

    Keeping ``setup`` the primitive is deliberate and directional: create+configure
    is mechanically derivable from configure, but configure can NEVER be recovered
    from a function that begins ``node = cls.create()``. "Re-run setup on an
    existing node" is a real feature (Scene tab, ``build(setup=True)``), so the
    re-runnable half has to be the one the author writes.

    ``creates=True`` is meaningless on a ``cls``-first / ``@classmethod`` factory
    (which already creates its own node) or a ``@staticmethod`` (no binding at
    all); detection warns and ignores it there.

    Static detection caveat: ``name=`` must be a string LITERAL and ``undoable=``
    / ``creates=`` must be bool LITERALS to be honored by the static walker
    (``detect_commands``). Any non-literal value cannot be resolved without
    exec'ing user code, so detection warns and falls back to the def's name /
    ``undoable=True`` / ``creates=False``. The runtime decorator itself accepts
    any value -- this constraint is purely about what the offline native-compile
    pass can see.
    """
    if callable(name):  # used bare: @maya_command
        fn = name
        fn.__maya_command__ = {
            "name": fn.__name__, "undoable": True, "creates": False}
        return fn

    def _decorate(fn):
        fn.__maya_command__ = {
            "name": name or fn.__name__,
            "undoable": bool(undoable),
            "creates": bool(creates),
        }
        return fn

    return _decorate


def maya_test(label=None, digits=None):
    """Flag a Methods ``def`` as a node VALIDATION / PARITY test.

    Usable bare (``@maya_test``) or parameterized
    (``@maya_test(label='UV move updates 3D', digits=3)``). Records
    ``func.__maya_test__ = {"label": ..., "digits": ...}`` and returns the
    function UNCHANGED -- a no-op at runtime.

    A test is an instance method (``self``-first) authored like a demo: it may
    build its own scene, set inputs and read outputs through the node's PUBLIC
    plug interface (identical for the interpreted and compiled node), then
    ``assert``. PASS = returns normally; FAIL = raises. Because it drives only
    public plugs, the SAME test validates the interpreted node and its compile
    -- both passing is parity confidence.

    ``digits`` is the default decimal-place tolerance for ``assert_close`` calls
    made inside this test (the runner scopes it); omitted -> the helper default.
    Static detection caveat: ``label=`` must be a string LITERAL and ``digits=``
    an int LITERAL to be honored by ``detect_tests``; non-literals warn and fall
    back (humanized def name / helper default)."""
    if callable(label):  # used bare: @maya_test
        fn = label
        fn.__maya_test__ = {"label": None, "digits": None}
        return fn

    def _decorate(fn):
        fn.__maya_test__ = {"label": label, "digits": digits}
        return fn

    return _decorate


def maya_demo(label=None):
    """Flag a Methods ``def`` as a runnable demo (Methods-tab feature).

    Usable bare (``@maya_demo``) or parameterized (``@maya_demo(label='Igloo
    (SDF)')``). Records ``func.__maya_demo__ = {"label": ...}`` and returns the
    function UNCHANGED -- a no-op at runtime. Static detection caveat: ``label=``
    must be a string LITERAL to be honored by ``detect_demos``; a non-literal
    warns and falls back to the humanized def name."""
    if callable(label):  # used bare: @maya_demo
        fn = label
        fn.__maya_demo__ = {"label": None}
        return fn

    def _decorate(fn):
        fn.__maya_demo__ = {"label": label}
        return fn

    return _decorate


# ---- Static detection (AST only) ----

_MARKER = "maya_command"
_MARKER_DEMO = "maya_demo"
_MARKER_TEST = "maya_test"


def _decorator_is_marker(dec: ast.AST, marker: str = _MARKER):
    """If ``dec`` is a ``marker`` decorator, return its ``ast.Call`` (for a
    parameterized form) or ``True`` (bare); else ``None``."""
    target = dec.func if isinstance(dec, ast.Call) else dec
    is_marker = (
        (isinstance(target, ast.Name) and target.id == marker)
        or (isinstance(target, ast.Attribute) and target.attr == marker)
    )
    if not is_marker:
        return None
    return dec if isinstance(dec, ast.Call) else True


def _const_str(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(
        node.value, str) else None


def _const_bool(node, default):
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    return default


def _const_int(node):
    """Int literal value (rejecting bool, which is an int subclass), else None."""
    if (isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)):
        return node.value
    return None


def _node_source(text: str, node: ast.AST) -> str:
    """Source of a def INCLUDING its decorators (decorator-aware slice; mirrors
    import_follower._node_source)."""
    decos = getattr(node, "decorator_list", None) or []
    if not decos:
        try:
            seg = ast.get_source_segment(text, node)
            if seg:
                return seg
        except Exception:
            pass
    try:
        lines = text.splitlines()
        start = node.lineno - 1
        for d in decos:
            start = min(start, d.lineno - 1)
        end = getattr(node, "end_lineno", None)
        if end:
            return "\n".join(lines[start:end])
    except Exception:
        pass
    try:
        seg = ast.get_source_segment(text, node)
        if seg:
            return seg
    except Exception:
        pass
    return ""


def _param_names(fn: ast.AST) -> List[str]:
    """Positional + keyword param names of a def, with the binding parameter
    (``self`` for an instance command, ``cls`` for a factory command) removed --
    neither is a command argument."""
    a = fn.args
    names = []
    for grp in (getattr(a, "posonlyargs", None) or [], a.args, a.kwonlyargs):
        names.extend(arg.arg for arg in grp)
    return [n for n in names if n not in ("self", "cls")]


def _is_factory_def(fn: ast.AST) -> bool:
    """True if the def is a FACTORY command (creates a node rather than operating
    on one). Detected statically by either signal the runtime/export honor:

      * a ``@classmethod`` decorator, or
      * a first positional parameter literally named ``cls``.

    This is the single static flag the native codegen, ``py_export``, and the
    runtime dispatcher all consult to tell a factory command from an instance
    (``self``) command. Mirrors ``methods_registry.invoke_command``'s runtime
    binding rule."""
    has_classmethod = any(
        isinstance(d, ast.Name) and d.id == "classmethod"
        for d in (getattr(fn, "decorator_list", None) or [])
    )
    if has_classmethod:
        return True
    pos = (getattr(fn.args, "posonlyargs", None) or []) + (fn.args.args or [])
    return bool(pos) and pos[0].arg == "cls"


def _is_static_def(fn: ast.AST) -> bool:
    """True if the def is a STATIC command -- a ``@staticmethod`` (and NOT also a
    ``@classmethod``). ``invoke_command`` calls a static command with NO binding,
    so the companion must NOT demand a target node for it. Mirrors
    ``methods_registry.invoke_command``'s three-way classification."""
    decos = getattr(fn, "decorator_list", None) or []
    has_static = any(
        isinstance(d, ast.Name) and d.id == "staticmethod" for d in decos)
    has_classmethod = any(
        isinstance(d, ast.Name) and d.id == "classmethod" for d in decos)
    return has_static and not has_classmethod


def _is_instance_def(fn: ast.AST) -> bool:
    """True iff `fn` is an INSTANCE-method def: an ast.FunctionDef whose first
    positional param is literally 'self' AND which carries NO @classmethod /
    @staticmethod decorator. The decorator rejection is load-bearing: a
    ``@classmethod def setup(self)`` also has a 'self' first param and must NOT
    be accepted as an instance setup (it binds the class). FunctionDef only (no
    AsyncFunctionDef), matching _is_factory_def's constraint."""
    if not isinstance(fn, ast.FunctionDef):
        return False
    for dec in (getattr(fn, "decorator_list", None) or []):
        nm = dec.id if isinstance(dec, ast.Name) else getattr(dec, "attr", None)
        if nm in ("classmethod", "staticmethod"):
            return False
    pos = (getattr(fn.args, "posonlyargs", None) or []) + (fn.args.args or [])
    return bool(pos) and pos[0].arg == "self"


def _collect_alias_targets(tree: ast.Module, symbol: str = _MARKER):
    """Return (name_aliases, module_aliases) introduced by top-level imports.

    ``name_aliases`` are names bound by ``from ...maya_command import <symbol>
    as <X>`` (where ``X != symbol``) -- writing ``@X`` on a def would defeat the
    static walker. ``module_aliases`` are names bound by ``import
    ...maya_command as <M>`` (any asname); the attribute-form detector already
    handles ``@M.<symbol>`` correctly, so these are returned for explicit
    do-NOT-warn filtering rather than as silent-drop suspects.
    """
    name_aliases = set()
    module_aliases = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.ImportFrom):
            mod = stmt.module or ""
            if not (mod.endswith("maya_command")
                    or mod.endswith("mpynode._common.methods.maya_command")):
                continue
            for alias in stmt.names:
                if alias.name == symbol:
                    asname = alias.asname or alias.name
                    if asname != symbol:
                        name_aliases.add(asname)
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                if (alias.name == "mpynode._common.methods.maya_command"
                        or alias.name.endswith(".maya_command")):
                    if alias.asname:
                        module_aliases.add(alias.asname)
    return name_aliases, module_aliases


def _decorator_uses_alias(dec: ast.AST, name_aliases) -> str:
    """If ``dec`` is a bare ast.Name whose id is in ``name_aliases``, return
    that id (the suspect alias). Else ``''``.

    Attribute-form decorators (``@m.maya_command``) are NOT treated as suspects
    here because ``_decorator_is_marker`` already detects them via
    ``attr == 'maya_command'`` -- they're not silent-drops.
    """
    target = dec.func if isinstance(dec, ast.Call) else dec
    if isinstance(target, ast.Name) and target.id in name_aliases:
        return target.id
    return ""


def detect_commands(source: str, tree=None) -> List[dict]:
    """Statically find ``@maya_command``-flagged top-level defs in ``source``.

    Returns a list (source order) of ``{name, func_name, undoable, creates,
    is_factory, is_static, params, body_src, lineno}``. ``is_factory`` is True
    for a ``cls``-first / ``@classmethod`` command (creates a node);
    ``is_static`` is True for a ``@staticmethod`` command (no binding); otherwise
    it is an instance (``self``) command. ``creates`` is True for an instance
    command whose compiled form must CREATE the node before binding it as
    ``self`` (the ``blendShape``/``skinCluster`` shape) -- it is forced False on a
    factory / staticmethod, which cannot honor it. Never raises: a syntax error /
    empty source yields ``[]``.

    Warns (``UserWarning``) when:

      * an ``async def`` carries ``@maya_command`` (cannot be a sync MPxCommand
        and is dropped);
      * the decorator references an aliased import of ``maya_command`` -- the
        static walker only matches the literal name / attribute form, so the
        def is dropped silently otherwise;
      * ``name=`` / ``undoable=`` is given a non-literal expression -- the
        static walker can't read it, so it falls back (def name / ``True``).
    """
    if not source or not source.strip():
        return []
    if tree is None:
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            return []

    name_aliases, _module_aliases = _collect_alias_targets(tree)

    out = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # An async def is never registered, but a marked one is flagged so the
        # silent drop is visible.
        is_async = isinstance(node, ast.AsyncFunctionDef)

        call = None
        for dec in (node.decorator_list or []):
            m = _decorator_is_marker(dec)
            if m is not None:
                call = m
                break

        if is_async:
            if call is not None:
                warnings.warn(
                    "@maya_command on async def %r is not supported and was "
                    "ignored." % node.name
                )
            continue

        if call is None:
            # No marker matched. If the def carries a bare-Name decorator whose
            # id is an aliased import of maya_command, warn the silent-drop.
            for dec in (node.decorator_list or []):
                alias = _decorator_uses_alias(dec, name_aliases)
                if alias:
                    warnings.warn(
                        "maya_command appears to be aliased as %r on def %r; "
                        "aliased decorators are not statically detected and "
                        "the command will NOT be registered. Use the literal "
                        "@maya_command." % (alias, node.name)
                    )
                    break
            continue

        name = node.name
        name_explicit = False
        undoable = True
        creates = False
        if isinstance(call, ast.Call):
            # name= keyword, else first positional, else def name.
            kw = {k.arg: k.value for k in call.keywords if k.arg}
            if "name" in kw:
                lit = _const_str(kw["name"])
                if lit is None:
                    warnings.warn(
                        "@maya_command(name=...) on def %r is not a string "
                        "literal; it cannot be statically read and the def "
                        "name %r is used instead." % (node.name, node.name)
                    )
                else:
                    name = lit
                    name_explicit = True
            elif call.args:
                lit = _const_str(call.args[0])
                if lit is None:
                    warnings.warn(
                        "@maya_command(<positional name>) on def %r is not a "
                        "string literal; it cannot be statically read and the "
                        "def name %r is used instead." % (node.name, node.name)
                    )
                else:
                    name = lit
                    name_explicit = True
            if "undoable" in kw:
                val = kw["undoable"]
                if isinstance(val, ast.Constant) and isinstance(val.value, bool):
                    undoable = val.value
                else:
                    warnings.warn(
                        "@maya_command(undoable=...) on def %r is not a bool "
                        "literal; it cannot be statically read and defaults "
                        "to True." % node.name
                    )
            if "creates" in kw:
                val = kw["creates"]
                if isinstance(val, ast.Constant) and isinstance(val.value, bool):
                    creates = val.value
                else:
                    warnings.warn(
                        "@maya_command(creates=...) on def %r is not a bool "
                        "literal; it cannot be statically read and defaults "
                        "to False." % node.name
                    )

        is_factory = _is_factory_def(node)
        is_static = _is_static_def(node)
        # ``creates`` only means anything for an INSTANCE command: it tells the
        # compiled dispatcher to make the node and pass it as ``self``. A
        # factory already makes its own and a staticmethod gets no binding, so
        # honoring it there would be a silent no-op.
        if creates and (is_factory or is_static):
            warnings.warn(
                "@maya_command(creates=True) on def %r is ignored: creates= "
                "applies to a self-first instance command (the dispatcher "
                "creates the node and binds it as 'self'); this def is a %s."
                % (node.name, "factory" if is_factory else "staticmethod")
            )
            creates = False

        out.append({
            "name": name,
            "name_explicit": name_explicit,
            "func_name": node.name,
            "undoable": undoable,
            "creates": creates,
            "is_factory": is_factory,
            "is_static": is_static,
            "params": _param_names(node),
            "body_src": _node_source(source, node),
            "lineno": node.lineno,
        })
    return out


def resolve_create_command_names(commands, node_type_name):
    """Give every un-named ``creates=True`` command the NODE TYPE's name.

    Mutates and returns ``commands`` (``detect_commands`` output).

    WHY THIS EXISTS. A create command wants to be named after the node, the way
    ``cmds.blendShape`` makes a ``blendShape`` -- Maya has no objection to a
    command and a node type sharing a name (measured on 2026: 214 built-ins do,
    including ``blendShape``, ``skinCluster``, ``cluster`` and ``deltaMush``).
    But the node's own name is NOT knowable where the setup is authored: the
    eight per-type default setups in ``_common/node_setups/<type>.py`` are ONE
    text file merge-seeded into every node of that type, so any literal written
    there is shared by all of them. With four mPyDeformer templates that is four
    templates registering the same command -- the second ``registerCommand``
    fails and aborts the whole merged plug-in, which is precisely what
    ``tools/audit_name_clashes.py`` exists to catch.

    So a shared setup writes the decorator with no name::

        @maya_command(creates=True)
        def setup(self, selection=None, *args, **kwargs):

    and the two spec entry points -- which DO know the node type, because they
    computed it -- call this to bind the name per node. A template that wants
    something other than its type name still writes the literal, and
    ``name_explicit`` keeps this from overwriting it.
    """
    if not node_type_name:
        return commands
    for c in commands:
        if c.get("creates") and not c.get("name_explicit"):
            c["name"] = node_type_name
    return commands


def duplicate_command_names(commands) -> List[str]:
    """Command NAMES that occur more than once in ``commands`` (sorted unique).

    Maya commands live in a single global string namespace, so two defs that
    resolve to the same command name collide -- the bundler must reject this at
    assemble time across all nodes in a plugin (this helper is the per-node
    half)."""
    seen = {}
    for c in commands:
        seen[c["name"]] = seen.get(c["name"], 0) + 1
    return sorted(n for n, k in seen.items() if k > 1)


# ---- @maya_demo static detection ----

def _humanize_label(func_name: str) -> str:
    """Fallback demo label from a def name. The reserved ``demo`` def gets the
    canonical 'Run demo'; everything else is title-cased words."""
    if func_name == "demo":
        return "Run demo"
    pretty = func_name.replace("_", " ").strip().title()
    return pretty or "Run demo"


def detect_demos(source: str, tree=None) -> List[dict]:
    """Statically find ``@maya_demo``-flagged top-level defs in ``source``.

    Returns a list (source order) of ``{label, func_name, is_factory, is_static,
    is_instance, lineno}``. Never raises: a syntax error / empty source yields
    ``[]``. Warns (``UserWarning``) on an ``async def`` marker, an aliased
    marker, or a non-literal ``label=`` -- mirroring ``detect_commands``."""
    if not source or not source.strip():
        return []
    if tree is None:
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            return []

    name_aliases, _module_aliases = _collect_alias_targets(tree, _MARKER_DEMO)

    out = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        is_async = isinstance(node, ast.AsyncFunctionDef)

        call = None
        for dec in (node.decorator_list or []):
            m = _decorator_is_marker(dec, _MARKER_DEMO)
            if m is not None:
                call = m
                break

        if is_async:
            if call is not None:
                warnings.warn(
                    "@maya_demo on async def %r is not supported and was "
                    "ignored." % node.name
                )
            continue

        if call is None:
            for dec in (node.decorator_list or []):
                alias = _decorator_uses_alias(dec, name_aliases)
                if alias:
                    warnings.warn(
                        "maya_demo appears to be aliased as %r on def %r; "
                        "aliased decorators are not statically detected and the "
                        "demo will NOT be registered. Use the literal "
                        "@maya_demo." % (alias, node.name)
                    )
                    break
            continue

        label = None
        if isinstance(call, ast.Call):
            kw = {k.arg: k.value for k in call.keywords if k.arg}
            if "label" in kw:
                lit = _const_str(kw["label"])
                if lit is None:
                    warnings.warn(
                        "@maya_demo(label=...) on def %r is not a string "
                        "literal; it cannot be statically read and the def "
                        "name is used instead." % node.name
                    )
                else:
                    label = lit
            elif call.args:
                lit = _const_str(call.args[0])
                if lit is None:
                    warnings.warn(
                        "@maya_demo(<positional label>) on def %r is not a "
                        "string literal; the def name is used instead."
                        % node.name
                    )
                else:
                    label = lit

        out.append({
            "label": label or _humanize_label(node.name),
            "func_name": node.name,
            "is_factory": _is_factory_def(node),
            "is_static": _is_static_def(node),
            "is_instance": _is_instance_def(node),
            "lineno": node.lineno,
        })
    return out


# ---- @maya_test static detection ----

def detect_tests(source: str, tree=None) -> List[dict]:
    """Statically find ``@maya_test``-flagged top-level defs in ``source``.

    Returns a list (source order) of ``{label, func_name, digits, is_factory,
    is_static, is_instance, lineno}``. ``digits`` is the int-literal tolerance
    from ``@maya_test(digits=N)`` or ``None``. Never raises: a syntax error /
    empty source yields ``[]``. Warns (``UserWarning``) on an ``async def``
    marker, an aliased marker, or a non-literal ``label=`` / ``digits=`` --
    mirroring ``detect_demos``."""
    if not source or not source.strip():
        return []
    if tree is None:
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            return []

    name_aliases, _module_aliases = _collect_alias_targets(tree, _MARKER_TEST)

    out = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        is_async = isinstance(node, ast.AsyncFunctionDef)

        call = None
        for dec in (node.decorator_list or []):
            m = _decorator_is_marker(dec, _MARKER_TEST)
            if m is not None:
                call = m
                break

        if is_async:
            if call is not None:
                warnings.warn(
                    "@maya_test on async def %r is not supported and was "
                    "ignored." % node.name
                )
            continue

        if call is None:
            for dec in (node.decorator_list or []):
                alias = _decorator_uses_alias(dec, name_aliases)
                if alias:
                    warnings.warn(
                        "maya_test appears to be aliased as %r on def %r; "
                        "aliased decorators are not statically detected and the "
                        "test will NOT be registered. Use the literal "
                        "@maya_test." % (alias, node.name)
                    )
                    break
            continue

        label = None
        digits = None
        if isinstance(call, ast.Call):
            kw = {k.arg: k.value for k in call.keywords if k.arg}
            if "label" in kw:
                lit = _const_str(kw["label"])
                if lit is None:
                    warnings.warn(
                        "@maya_test(label=...) on def %r is not a string "
                        "literal; it cannot be statically read and the def "
                        "name is used instead." % node.name
                    )
                else:
                    label = lit
            elif call.args:
                lit = _const_str(call.args[0])
                if lit is None:
                    warnings.warn(
                        "@maya_test(<positional label>) on def %r is not a "
                        "string literal; the def name is used instead."
                        % node.name
                    )
                else:
                    label = lit
            if "digits" in kw:
                d = _const_int(kw["digits"])
                if d is None:
                    warnings.warn(
                        "@maya_test(digits=...) on def %r is not an int "
                        "literal; the helper default tolerance is used."
                        % node.name
                    )
                else:
                    digits = d

        out.append({
            "label": label or _humanize_label(node.name),
            "func_name": node.name,
            "digits": digits,
            "is_factory": _is_factory_def(node),
            "is_static": _is_static_def(node),
            "is_instance": _is_instance_def(node),
            "lineno": node.lineno,
        })
    return out
