"""Upgrade a v1 node that arrived through a file open, in place.

Companion to ``v1_import``, which reads a ``.ma`` as text. This one never
touches the file: it reads the node that Maya already built.

That is possible because v2 registers the same node TYPE name as v1. Opening a
v1 scene therefore does not produce an ``unknown`` node -- Maya builds a v2
``mPyNode`` and replays v1's ``setAttr`` calls at it. Measured on a real v1
scene, with v2 loaded:

  * the node arrives as a v2 ``mPyNode``, not ``unknown``;
  * all 26 user attributes survive, because ``addAttr`` is type-agnostic;
  * ``_inputAttrs`` and ``_outputAttrs`` arrive VERBATIM but UNREADABLE. The
    two versions share the plug name and nothing else: v1 wrote base64+pickle
    of ``{name: [type]}`` where v2 writes plain JSON of
    ``{name: {attr_type, is_array, order}}``. The blob therefore survives the
    open looking undamaged and is read by v2 as an empty node -- attributes
    present in the Channel Box, absent from the Attributes tab, and
    ``self.<attr>`` unresolved. ``_storedVarNames`` has the same disease:
    a pickled list where v2 keeps a comma-joined string. Only
    ``_storedVarsData`` is genuinely compatible;
  * the expression was **lost**, because v1 wrote it to a plug named
    ``expression`` that v2 did not declare.

A shared name with an unshared format is the failure mode to watch for here.
It is far more dangerous than a plug that fails to load, because every
surface-level check -- the plug exists, it is non-empty, it still decodes --
passes while the feature is completely broken.

``_api2.helpers.make_legacy_expression_attr`` now declares that plug, so the
value lands. This module is what then turns it into a real v2 node.

Reading from the DG rather than the file is what makes this work for ``.mb``
scenes, references, imports and paste -- none of which the text importer can
help with, because by the time they are in the scene there is no file to
re-read.
"""
from __future__ import annotations

LEGACY_PLUG = "expression"
_COMPUTE_PLUG = "_computeSource"
_V1_PLUGS = {"inputs": "_inputAttrs", "outputs": "_outputAttrs",
             "stored": "_storedVarsData"}


def _get(node, plug, default=""):
    import maya.cmds as mc

    full = "%s.%s" % (node, plug)
    if not mc.objExists(full):
        return default
    try:
        val = mc.getAttr(full)
    except Exception:
        return default
    return default if val is None else val


def _has_plug(node, plug) -> bool:
    """Whether the plug EXISTS, as distinct from being empty.

    The distinction is the whole safety gate below, so it gets its own
    function rather than riding on ``_get``, which cannot tell "absent" from
    "empty" and returns the same default for both.
    """
    import maya.cmds as mc

    try:
        return bool(mc.objExists("%s.%s" % (node, plug)))
    except Exception:
        return False


def is_pending(node) -> bool:
    """True if ``node`` carries a v1 payload that v2 owns and has not upgraded.

    Three conditions, and the third is a hard safety gate:

    1. a non-empty legacy ``expression`` -- the v1 payload;
    2. ``_computeSource`` EXISTS -- so v2, not v1, is serving this node type;
    3. ``_computeSource`` is empty -- so the upgrade has not already run.

    (2) is not a formality. v1 and v2 register the same node TYPE name, and
    whichever plug-in gets there first wins: a v1 install in the Maya user
    directory (plus ``requires -nodeType "mPyNode" "mpynode_plugin.py"`` in
    every v1 scene, which loads it by name) means v2's registration fails and
    the nodes in the scene are v1 nodes served by v1's code. Upgrading one of
    those is actively destructive -- rewriting ``_inputAttrs`` into v2's JSON
    leaves v1 unable to build its expression locals, and its compute dies with
    ``NameError: name '<input>' is not defined``. Requiring ``_computeSource``
    to exist is an exact test because v1 does not declare it anywhere in its
    source tree, so a v1-owned node can never satisfy it.

    (1) and (3) together make the sweep idempotent with no marker attribute:
    no node authored in v2 can look like that, since v2 never writes
    ``expression`` at all, and an already-upgraded node fails (3).
    """
    if not str(_get(node, LEGACY_PLUG)).strip():
        return False
    if not _has_plug(node, _COMPUTE_PLUG):
        return False          # v1 owns this node -- hands off. See above.
    return not str(_get(node, _COMPUTE_PLUG)).strip()


def find_pending(nodes=None):
    """Every v1-payload node in the scene (or within ``nodes``)."""
    import maya.cmds as mc

    if nodes is None:
        nodes = mc.ls(type="mPyNode") or []
    return [n for n in nodes if is_pending(n)]


def find_foreign(nodes=None):
    """v1-payload nodes that v2 does NOT own, and so must not be touched.

    Exists to be reported rather than acted on: this is the state where the
    Designer looks inert for no visible reason -- v2's plug-in loaded, its
    node type did not register, and every panel reads an empty node -- so the
    one thing worth doing is naming it.
    """
    import maya.cmds as mc

    if nodes is None:
        nodes = mc.ls(type="mPyNode") or []
    return [n for n in nodes
            if str(_get(n, LEGACY_PLUG)).strip()
            and not _has_plug(n, _COMPUTE_PLUG)]


def _v1_node_from_plugs(node):
    """Build a :class:`v1_import.V1Node` from the live plugs."""
    from mpynode._common.io import v1_import as V

    v1 = V.V1Node(node)
    v1.expression = str(_get(node, LEGACY_PLUG))
    for field, plug in _V1_PLUGS.items():
        payload = str(_get(node, plug))
        if not payload.strip():
            continue
        try:
            obj = V._unpickle_b64(payload)
        except V.V1ImportError:
            continue
        if not isinstance(obj, dict):
            continue
        if field == "stored":
            v1.stored_vars = dict(obj)
        else:
            table = {k: (v[0] if isinstance(v, (list, tuple)) and v else v)
                     for k, v in obj.items()}
            setattr(v1, field, table)
    return v1


def _rewrite_attr_registry(node, v1_table, enums, plug):
    """Re-express a v1 attribute table in v2's registry schema.

    The two share a plug NAME and nothing else. v1 wrote base64+pickle of
    ``{name: [type]}``; v2 writes plain JSON of
    ``{name: {attr_type, is_array, order, enum_names?}}``. So the v1 payload
    survives a scene open looking intact and is read by v2 as nothing at all --
    which is why the attributes were on the Maya node but absent from the
    Attributes tab, and why ``self.<attr>`` did not bind.

    ``is_array`` comes from the live plug rather than the table, because v1's
    schema simply does not record it -- ``controlMatrices`` is stored as
    ``['matrix']`` whether or not the addAttr said ``-multi``.

    ``order`` follows the v1 dict, which preserves authoring order, and that is
    what drives Channel Box / Attribute Editor ordering.
    """
    import json

    import maya.cmds as mc

    table, missing = {}, []
    for i, (name, typ) in enumerate(v1_table.items()):
        if not mc.objExists("%s.%s" % (node, name)):
            missing.append(name)
            continue
        try:
            is_array = bool(mc.attributeQuery(name, node=node, multi=True))
        except Exception:
            is_array = False
        meta = {"attr_type": typ, "is_array": is_array, "order": i}
        if typ == "enum":
            meta["enum_names"] = list(enums.get(name) or ["0", "1"])
        table[name] = meta

    try:
        mc.setAttr("%s.%s" % (node, plug), json.dumps(table), type="string")
    except Exception:
        pass
    return table, missing


def upgrade_node(node, clear_legacy=False):
    """Convert one pending node in place. Returns the conversion report.

    ``clear_legacy`` is off by default. Leaving the original payload in place
    costs a hidden string and buys an audit trail -- you can still see what the
    node was before the rewrite -- and the sweep stays idempotent regardless,
    because the gate is ``_computeSource`` being empty rather than the legacy
    plug being absent. It is cleared ONLY on success when asked; clearing after
    a failure would turn a recoverable problem into a permanent one.
    """
    import maya.cmds as mc

    from mpynode._common.io import v1_import as V
    from mpynode.wrappers._mpy_node import MPyNode

    v1 = _v1_node_from_plugs(node)
    spec = V.convert(v1)

    wrapper = MPyNode(node)

    # FIRST: re-express v1's attribute tables in v2's schema. Until this runs
    # the plugs exist on the Maya node but v2 does not know they are its own,
    # so the Attributes tab is empty and self.<attr> does not resolve.
    _in, miss_in = _rewrite_attr_registry(
        node, v1.inputs, spec["synthesized_enums"], "_inputAttrs")
    _out, miss_out = _rewrite_attr_registry(
        node, v1.outputs, spec["synthesized_enums"], "_outputAttrs")
    spec["registered_inputs"] = sorted(_in)
    spec["registered_outputs"] = sorted(_out)
    spec["missing_plugs"] = sorted(miss_in + miss_out)

    for attr, names in spec["synthesized_enums"].items():
        # v1 stored no enum labels and v2 rejects an enum without them. The
        # attribute already exists on the node (addAttr carried it over), so
        # this is a relabel, not an add.
        full = "%s.%s" % (node, attr)
        if mc.objExists(full):
            try:
                mc.addAttr(full, edit=True, enumName=":".join(names))
            except Exception:
                pass

    # `_storedVarsData` is base64+pickle on both sides, so the values survive
    # the open untouched -- but `_storedVarNames` does NOT: v2 comma-joins a
    # plain string where v1 pickled a list. v2 gates persistence on names
    # membership, so a v1 node's variables read back as none at all, and the
    # undecodable blob shows up as one garbage variable name. set_variables
    # replaces the dict AND the names list together, which is exactly the
    # repair; the per-variable call cannot fix the names plug.
    if spec["stored_vars"]:
        try:
            wrapper.set_variables(dict(spec["stored_vars"]))
        except Exception as exc:
            spec["stored_var_error"] = "%s: %s" % (type(exc).__name__, exc)

    if spec["init"].strip():
        wrapper.set_init_expression(spec["init"])
    wrapper.set_compute_expression(spec["compute"])

    if clear_legacy:
        try:
            mc.setAttr("%s.%s" % (node, LEGACY_PLUG), "", type="string")
        except Exception:
            pass

    spec["upgraded"] = node
    return spec


def upgrade_scene(nodes=None, clear_legacy=False):
    """Upgrade every pending node. Returns ``(reports, failures)``.

    Never raises: this runs from a scene-open callback, where an exception
    would abort the rest of the open and take unrelated panels with it.
    """
    reports, failures = [], []
    for node in find_pending(nodes):
        try:
            reports.append(upgrade_node(node, clear_legacy=clear_legacy))
        except Exception as exc:
            failures.append((node, "%s: %s" % (type(exc).__name__, exc)))
    return reports, failures


def summarize(reports, failures):
    """One human line per node, for the log. The report is the deliverable as
    much as the node is -- a silent 90% conversion is worse than a noisy one."""
    out = []
    for r in reports:
        bits = ["upgraded v1 node %r" % r["upgraded"],
                "%d in / %d out registered" % (len(r.get("registered_inputs") or []),
                                               len(r.get("registered_outputs") or [])),
                "%d rewrites" % r["rewrites"]]
        if r.get("stored_vars"):
            bits.append("%d stored var(s)" % len(r["stored_vars"]))
        if r.get("stored_var_error"):
            bits.append("stored vars FAILED: %s" % r["stored_var_error"])
        if r.get("missing_plugs"):
            bits.append("declared but ABSENT on the node: %s"
                        % ", ".join(r["missing_plugs"]))
        if r["synthesized_enums"]:
            bits.append("enum labels invented for %s (rename them)"
                        % ", ".join(sorted(r["synthesized_enums"])))
        if r["shadowed"]:
            bits.append("shadowed input(s) aliased: %s" % ", ".join(r["shadowed"]))
        if r["globals_in_defs"]:
            bits.append("helper def reads %s as a global -- needs finishing"
                        % ", ".join(r["globals_in_defs"]))
        if r.get("dead_imports"):
            bits.append("DROPPED dead v1-library import(s) [%s] -- v2 does not "
                        "ship mpylib and does not make api objects ambient, so "
                        "those names are now undefined at their use sites; "
                        "replace them with numpy or mpynode.api"
                        % "; ".join(r["dead_imports"]))
        if r.get("vec_ctor_fixes"):
            bits.append("rewrote bare %s to numpy (_v1_vec shim added to "
                        "Init; v2 does not seed api objects)"
                        % "/".join(r["vec_ctor_fixes"]))
        if r.get("matrix_view_fixes"):
            bits.append("auto-fixed %d MatrixView call(s): %s"
                        % (len(r["matrix_view_fixes"]),
                           "; ".join(r["matrix_view_fixes"])))
        if r.get("vec3_fixes"):
            bits.append("auto-fixed 4-component writes to %s "
                        "(_v1_vec3 shim added to Init; delete it once the "
                        "maths is tidied)" % ", ".join(r["vec3_fixes"]))
        if r["needs_hand_finish"]:
            # Deliberately NOT phrased as "the maths is broken" any more. The
            # two mismatches that actually broke a converted node are fixed
            # above; what is left is that constructing api objects per
            # evaluation is slow and will not lower to C++.
            bits.append("still constructs v1 API objects (%s) -- runs, but "
                        "numpy/MatrixView would be faster and only that "
                        "lowers to C++" % ", ".join(r["api_objects"]))
        out.append(" -- ".join(bits))
    for node, err in failures:
        out.append("could NOT upgrade v1 node %r: %s" % (node, err))
    return out
