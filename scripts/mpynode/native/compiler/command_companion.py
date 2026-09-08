"""command_companion -- HISTORICAL companion emitter, now the cross-node
command-name clash gate only.

**No sibling plug-in is written any more.** Every ``@maya_command`` compiles
INTO the node's own ``.bundle`` as a real ``MPxCommand`` -- the locator's
mesh-region pair through ``kernels.command_codegen``'s hand-written C++, and
everything else through ``kernels.command_dispatch``, whose generated ``doIt``
parses ``MSyntax`` flags and dispatches into Python. A compile therefore
produces ONE artifact. See ``command_dispatch``'s module docstring for the four
measured constraints that shape the generated code.

What this module still does: :func:`emit_companions` walks every node BEFORE
anything is written and rejects a command name defined on two of them. Maya
command names are a single global namespace, so a duplicate fails the second
``registerCommand`` at load -- and in a MERGED bundle a failing register hook
aborts ``initializePlugin`` for the WHOLE plug-in, taking every other node with
it. The bundler has its own gate reading ``registerCommand("...")`` out of the
generated C++; this one works from the specs, so the two cover each other.

Retained below (unused by the compile path, still exercised by tests): the
Python plug-in generator that shipped the previous ``<type>_commands.py``.

Why the old design chose a sibling Python plug-in: a Python ``MPxCommand``
registering through its own ``MFnPlugin`` avoided the C++<->Python
plugin-``MObject`` handoff. That handoff turned out to be unnecessary -- the
generated C++ never touches an ``MObject``, it hands base64 text to
``MGlobal::executePythonCommand`` -- and the sibling cost a second plug-in to
load, took no command arguments at all, and was not undoable.

Command kinds (the Phase-2 convention; see ``maya_command.detect_commands``'s
``is_factory``):

  * **factory** (``cls``-first / ``@classmethod``): creates a node. The companion
    binds a compiled-type proxy CLASS whose ``.create()`` / ``.build()`` is
    ``createNode(<compiled_type>)`` -- so ``def setup(cls): n = cls.create()``
    makes the COMPILED node, not an interpreted ``mPyNode``.
  * **instance** (``self``-first): operates on an existing node. The companion
    resolves the target from the command's object argument / active selection
    (the shipped ``setMeshRegion`` contract) and binds a proxy to that node.

GENERATED-CODE TRUST: the companion embeds the node's Methods source verbatim and
exec's it at command time -- the identical trust model to the live node's Methods
tab (the user's own code) and Init/Compute.

v1 scope (honest staging): factory commands and instance commands are dispatched
with their target resolved; extra command PARAMETERS are not yet threaded through
``maya.cmds`` flags (they take their defaults) and commands are not yet undoable.
Both are documented follow-ups -- never a silent mis-compile.

This module is import-light (``ast`` via ``maya_command`` only -- NO maya, NO Qt)
so the compiler can call it offline.
"""
from __future__ import annotations

import os
import re
from typing import List

from mpynode._common.methods.maya_command import (
    detect_commands,
    duplicate_command_names,
)

# A Maya command name must be a plain identifier (registerCommand and MEL both
# require it). Anything else (empty, spaces, hyphens) registers a command that
# cannot be called and aborts the registration loop, taking later commands
# with it.
_VALID_COMMAND_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _command_kind(cmd: dict) -> str:
    """The command's binding kind -- one of ``"factory"`` (``cls``-first /
    ``@classmethod``, creates a node), ``"static"`` (``@staticmethod``, no
    binding / no target), ``"creates"`` (``self``-first + ``creates=True``: the
    dispatcher creates the node and binds it as ``self``), or ``"instance"``
    (``self``-first, operates on a resolved target). Mirrors
    ``methods_registry.invoke_command``'s classification so a static/utility
    command is not forced to demand a node, and kept in step with
    ``command_dispatch.python_module_source`` -- the two disagreeing would make
    the compile dialog label a create command "instance"."""
    if cmd.get("is_factory"):
        return "factory"
    if cmd.get("is_static"):
        return "static"
    if cmd.get("creates"):
        return "creates"
    return "instance"


def _needs_target(cmd: dict) -> bool:
    """Only an INSTANCE (``self``) command resolves a target node; factory and
    static commands do not (``invoke_command`` ignores the binding for them),
    and a ``creates`` command makes its own node rather than resolving one."""
    return _command_kind(cmd) == "instance"


def companion_command_summary(source: str, commands=None) -> List[dict]:
    """``[{name, func_name, kind}, ...]`` for every ``@maya_command`` in
    ``source`` -- the per-command native-vs-companion report the compile dialog
    surfaces (here every command is a companion; ``kind`` is factory/instance)."""
    cmds = commands if commands is not None else detect_commands(source)
    return [
        {"name": c["name"], "func_name": c["func_name"], "kind": _command_kind(c)}
        for c in cmds
    ]


# ---- Generated-module fragments -------------------------------------------

# Compiled-type proxy + target resolution + result marshalling, shared by every
# generated companion. A literal so the generated module is self-contained.
_RUNTIME_SUPPORT = '''
class _CompiledProxy(object):
    """Lightweight handle to a COMPILED node, standing in for the live wrapper
    inside a companion command. A FACTORY command uses the CLASS
    (``.create()`` / ``.build()`` -> ``createNode(<type>)``); an INSTANCE command
    uses an instance bound to a node name (attribute access proxies to plugs)."""

    _compiled_type = _NODE_TYPE

    def __init__(self, name=None):
        object.__setattr__(self, "_name", name)

    @classmethod
    def create(cls, name=None):
        kw = {"name": name} if name else {}
        return cls(cmds.createNode(cls._compiled_type, **kw))

    # Factory bodies may call cls.build(); alias it to create().
    build = create

    def get_name(self):
        return object.__getattribute__(self, "_name")

    def __getattr__(self, attr):
        # Unknown attribute -> read it as a plug on the bound node.
        name = object.__getattribute__(self, "_name")
        if name is None:
            raise AttributeError(attr)
        try:
            return cmds.getAttr("%s.%s" % (name, attr))
        except Exception:
            raise AttributeError(attr)

    def __setattr__(self, attr, value):
        if attr == "_name":
            object.__setattr__(self, attr, value)
            return
        name = object.__getattribute__(self, "_name")
        cmds.setAttr("%s.%s" % (name, attr), value)


def _resolve_target(args, cmd_name):
    """Resolve an INSTANCE command's target node: an explicit object argument
    first, else the active selection. Errors if neither names a node -- exactly
    the implicit-self-becomes-explicit-which-node contract.

    The API 2.0 ``MArgList`` exposes no ``length()``; ``asString(i)`` raises once
    the index runs past the end, so probe incrementally."""
    i = 0
    while i < 256:  # safety bound; real commands take a handful of args
        try:
            s = args.asString(i)
        except Exception:
            break
        if s and cmds.objExists(s):
            return s
        i += 1
    sel = cmds.ls(selection=True) or []
    if sel:
        return sel[0]
    raise RuntimeError(
        "%s: select (or name) the target node -- a compiled command has no "
        "implicit 'self'." % cmd_name)


def _set_result(command, result):
    if result is None:
        return
    getter = getattr(result, "get_name", None)
    if callable(getter):
        result = getter()
        if result is None:
            return
    # 0-d numpy array -> its scalar (so `return np.array(0.5)` marshals numeric).
    item = getattr(result, "item", None)
    if callable(item) and getattr(result, "ndim", None) == 0:
        try:
            result = result.item()
        except Exception:
            pass
    # Bool-like FIRST: numpy.bool_ is NOT a numbers.Integral, so without this it
    # would fall to str() -> "False", which is truthy and inverts downstream tests.
    if isinstance(result, bool) or type(result).__name__ in ("bool_", "bool8"):
        command.setResult(bool(result))
    elif isinstance(result, numbers.Integral):
        command.setResult(int(result))
    elif isinstance(result, numbers.Real):
        command.setResult(float(result))
    elif isinstance(result, (list, tuple)):
        command.setResult([str(x) for x in result])
    else:
        command.setResult(str(result))
'''


def _command_class(cmd: dict) -> str:
    """Source for one command's ``MPxCommand`` subclass."""
    func = cmd["func_name"]
    name = cmd["name"]
    cls = "_Cmd_%s" % func
    if _needs_target(cmd):
        dispatch = (
            "        _target = _resolve_target(args, %r)\n"
            "        _result = invoke_command(_fn, _CompiledProxy(_target))\n"
            % name
        )
    else:
        # factory / static: invoke_command ignores the binding -> no target.
        dispatch = (
            "        _result = invoke_command(_fn, _CompiledProxy())\n"
        )
    return (
        "class {cls}(om.MPxCommand):\n"
        "    kPluginCmdName = {name!r}\n"
        "\n"
        "    @staticmethod\n"
        "    def creator():\n"
        "        return {cls}()\n"
        "\n"
        "    def doIt(self, args):\n"
        "        _ns = build_methods_namespace(_METHODS_SRC)\n"
        "        _fn = _ns.get({func!r})\n"
        "        if _fn is None:\n"
        "            raise RuntimeError(\n"
        "                'companion: method {func} missing from methods source')\n"
        "{dispatch}"
        "        _set_result(self, _result)\n"
    ).format(cls=cls, name=name, func=func, dispatch=dispatch)


def generate_companion_plugin(
    plugin_name: str,
    node_type_name: str,
    methods_source: str,
    commands=None,
) -> str:
    """Return the source of a Python plugin exposing ``methods_source``'s
    ``@maya_command`` defs as ``maya.cmds`` commands bound to ``node_type_name``
    (the COMPILED node type). Returns ``""`` when there are no commands -- the
    caller emits nothing (no empty plugin)."""
    cmds = commands if commands is not None else detect_commands(methods_source)
    if not cmds:
        return ""

    # Fail loudly at COMPILE time rather than emit an un-loadable plugin (every
    # check below was an adversarially-confirmed defect):
    #  * an invalid command name aborts the registration loop;
    #  * duplicate command names collide in Maya's global command namespace ->
    #    the 2nd registerCommand fails at load;
    #  * duplicate python def names collide on the generated _Cmd_<func> class /
    #    _COMMANDS entry -> one command is lost, another double-registered.
    bad = [c["name"] for c in cmds
           if not _VALID_COMMAND_NAME.match(c["name"] or "")]
    if bad:
        raise ValueError(
            "companion: command name(s) are not valid Maya command identifiers: "
            + ", ".join(repr(b) for b in bad))
    dup_names = duplicate_command_names(cmds)
    if dup_names:
        raise ValueError(
            "companion: duplicate command name(s) would collide at "
            "registerCommand: " + ", ".join(dup_names))
    fn_counts = {}
    for c in cmds:
        fn_counts[c["func_name"]] = fn_counts.get(c["func_name"], 0) + 1
    dup_fns = sorted(n for n, k in fn_counts.items() if k > 1)
    if dup_fns:
        raise ValueError(
            "companion: duplicate method def name(s) (would collide on the "
            "generated command class): " + ", ".join(dup_fns))

    classes = [_command_class(c) for c in cmds]
    registry = "_COMMANDS = [%s]" % ", ".join("_Cmd_%s" % c["func_name"]
                                              for c in cmds)

    header = (
        "# -*- coding: utf-8 -*-\n"
        "# AUTO-GENERATED companion command plugin for %r.\n"
        "# Regenerated by the Node Designer native compiler -- do not edit.\n"
        "#\n"
        "# Ships beside the compiled .bundle; load BOTH (the .bundle registers\n"
        "# the node type %r, this plugin registers the commands that drive it).\n"
        % (node_type_name, node_type_name)
    )

    body = "\n".join([
        header,
        "import numbers",
        "",
        "import maya.api.OpenMaya as om",
        "import maya.cmds as cmds",
        "",
        "from mpynode._common.methods.methods_registry import (",
        "    build_methods_namespace,",
        "    invoke_command,",
        ")",
        "",
        "",
        "def maya_useNewAPI():",
        "    # Flags this plugin as Maya Python API 2.0.",
        "    pass",
        "",
        "",
        "_NODE_TYPE = %r" % node_type_name,
        "_METHODS_SRC = %r" % methods_source,
        _RUNTIME_SUPPORT,
        "",
        "\n\n".join(classes),
        "",
        registry,
        "",
        "",
        "def initializePlugin(mobject):",
        "    plugin = om.MFnPlugin(mobject)",
        "    _done = []",
        "    try:",
        "        for _cls in _COMMANDS:",
        "            plugin.registerCommand(_cls.kPluginCmdName, _cls.creator)",
        "            _done.append(_cls.kPluginCmdName)",
        "    except Exception:",
        "        # Roll back already-registered commands so a mid-loop failure",
        "        # cannot leak a half-registered, un-deregisterable plugin.",
        "        for _n in reversed(_done):",
        "            try:",
        "                plugin.deregisterCommand(_n)",
        "            except Exception:",
        "                pass",
        "        raise",
        "",
        "",
        "def uninitializePlugin(mobject):",
        "    plugin = om.MFnPlugin(mobject)",
        "    for _cls in _COMMANDS:",
        "        try:",
        "            plugin.deregisterCommand(_cls.kPluginCmdName)",
        "        except Exception:",
        "            pass",
        "",
    ])
    return body


def _native_command(spec: dict, cmd: dict) -> bool:
    """True if ``cmd`` is emitted as C++ INTO the ``.bundle`` -- now ALWAYS.

    Every ``@maya_command`` is emitted into the node's own bundle: the locator's
    mesh-region pair through ``command_codegen``'s hand-written templates, and
    everything else through ``command_dispatch`` (a real ``MPxCommand`` whose
    ``doIt`` dispatches into Python). A compile therefore produces ONE plug-in,
    and there is nothing left for a sibling companion to carry.

    Kept as a predicate rather than deleted because :func:`emit_companions` is
    still the CROSS-NODE command-name clash gate: its first pass walks
    ``native + companion`` and rejects a name defined on two nodes before
    anything is written. That gate is now the only thing it does.
    """
    return True


def emit_companions(nodes, plugin_name: str, out_dir: str) -> List[dict]:
    """Cross-node command-name clash gate. Writes NOTHING and returns ``[]``.

    Every command is now emitted into the node's own ``.bundle``
    (:func:`_native_command` is universally true), so the write pass below has
    no work: what survives is the validation pass, which is the point. Kept as
    the same call the compile controller already made rather than replaced, so
    the all-or-nothing ordering (validate every node before touching disk) is
    unchanged.

    ``nodes`` is an iterable of ``(type_name, spec)`` where ``type_name`` is the
    SANITIZED COMPILED type name (the companion's ``createNode`` target) and
    ``spec`` carries ``spec["methods"]`` (source) + ``spec["commands"]`` (the
    ``detect_commands`` list). Mesh-region commands that compile natively into the
    ``.bundle`` are excluded (see :func:`_native_command`). A node with no
    companion-eligible command writes nothing.

    Returns ``[{type_name, path, commands: [summary...]}, ...]`` (the per-command
    summary feeds the compile dialog's native-vs-companion report).

    Raises ``ValueError`` on a command-name clash ACROSS nodes (Maya command
    names are a single global namespace, so two plugins registering the same name
    would collide at load) -- including a COMPANION name that collides with one
    compiled NATIVELY into the ``.bundle`` (the bundler's native clash gate only
    sees C++ register lines; this one only sees companions, so the cross pair is
    invisible to either alone). Validation runs as a FIRST pass over ALL nodes
    BEFORE anything is written, so a clash leaves NO orphaned files on disk
    (all-or-nothing, mirroring the bundler's native gate).
    """
    # Pass 1 -- validate every node and PLAN the writes; touch no disk yet.
    # ``seen`` tracks EVERY command name (native + companion) so a companion can
    # never collide with a natively-compiled name, or vice versa.
    # ``generate_companion_plugin`` also raises here on intra-node clashes.
    seen = {}
    planned = []  # [(type_name, path, src, summary)]
    for type_name, spec in nodes:
        cmds = (spec or {}).get("commands") or []
        if not cmds:
            continue
        native = [c for c in cmds if _native_command(spec, c)]
        companion = [c for c in cmds if not _native_command(spec, c)]
        for c in native + companion:
            nm = c.get("name")
            if nm in seen:
                raise ValueError(
                    "command name %r is defined on both %r and %r "
                    "(Maya command names are global)" % (nm, seen[nm], type_name))
            seen[nm] = type_name
        if not companion:
            continue
        methods = (spec or {}).get("methods") or ""
        src = generate_companion_plugin(
            plugin_name, type_name, methods, commands=companion)
        if not src:
            continue
        path = os.path.join(out_dir, "%s_commands.py" % type_name)
        planned.append((
            type_name, path, src,
            companion_command_summary(methods, commands=companion)))

    # Pass 2 -- all nodes validated; now write (no orphans on a later clash).
    out = []
    for type_name, path, src, summary in planned:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(src)
        out.append({"type_name": type_name, "path": path, "commands": summary})
    return out
