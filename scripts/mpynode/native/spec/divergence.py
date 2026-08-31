"""Per-class divergence detection + fork planning for compile-time integrity.

The redesign compiles ONE native type per Class, but a node's authored code and
attributes live per-INSTANCE on its plugs. So two instances of one Class can
diverge (Duplicate-then-edit), and naively compiling a single representative
would silently mis-compile the edited siblings -- the must-fix #1 integrity gap.

This module has two layers:

* **Node level** (`diverged_classes`) -- groups live wrappers by their canonical
  Class and flags any Class whose instances are not structurally identical, using
  the normalized-source ``content_hash`` (expression/init/methods + attr/var
  NAMES, values/comments/whitespace excluded). The compile DIALOG consumes this
  (it holds live nodes) to **warn + offer to fork** the edited instance.
* **Spec level** (`diverged_spec_groups`, `specs_are_identical`) -- the same
  detection over porter spec dicts, so the compile CONTROLLER (which only sees
  specs) can collapse genuinely-identical instances of one Class to a single
  compiled type and surface a clear error for divergent ones -- a backstop for
  callers that bypass the dialog.

`plan_forks` turns a divergence map into a deterministic fork plan (which
instances keep the original Class, which get new auto-named Classes).

Everything here is detection/planning only -- it never mutates a node. The
content hash is NOT an identity (editing code changes it); identity remains the
explicit ``class_path``.
"""
from __future__ import annotations

from mpynode._common.io.content_hash import node_content_hash, source_hash


# ---------------------------------------------------------------------------
# Node level (live wrappers) -- consumed by the compile dialog
# ---------------------------------------------------------------------------


def _class_of(py_node):
    """The node's canonical ``class_path`` (``""`` for a class-less node)."""
    try:
        return py_node.get_py_class() or ""
    except Exception:
        return ""


def _node_name(py_node):
    """Best-effort scene name of a wrapper (falls back to ``str``)."""
    try:
        return py_node.get_name()
    except Exception:
        return str(py_node)


def group_nodes_by_class(py_nodes):
    """``{class_path: [py_node, ...]}`` for the CLASSED nodes among ``py_nodes``.

    Class-less nodes (no ``class_path``) are omitted: each compiles as its own
    per-instance type, so there is no shared Class for them to diverge within.
    ``None`` entries are skipped (a name that failed to wrap is not a node).
    Insertion order within each group follows ``py_nodes``."""
    groups = {}
    for n in py_nodes:
        if n is None:
            continue
        cp = _class_of(n)
        if cp:
            groups.setdefault(cp, []).append(n)
    return groups


def hash_partition(py_nodes):
    """``{content_hash: [py_node, ...]}`` -- partition a group of instances by
    their normalized-source content hash. ``None`` entries are skipped. A node
    whose hash can't be computed lands under ``None`` (its own partition, i.e.
    treated as a divergence)."""
    parts = {}
    for n in py_nodes:
        if n is None:
            continue
        try:
            h = node_content_hash(n)
        except Exception:
            h = None
        parts.setdefault(h, []).append(n)
    return parts


def class_is_diverged(py_nodes):
    """True if the given instances of ONE Class are not all structurally
    identical (more than one distinct content hash)."""
    return len(hash_partition(py_nodes)) > 1


def diverged_classes(py_nodes):
    """``{class_path: {content_hash: [py_node, ...]}}`` for every Class whose
    instances are NOT all structurally identical.

    Empty dict ⇒ every Class in ``py_nodes`` is internally consistent (safe to
    compile one representative per Class). A non-empty entry is a divergence the
    caller must surface (warn + offer fork) before compiling that Class."""
    out = {}
    for cp, group in group_nodes_by_class(py_nodes).items():
        parts = hash_partition(group)
        if len(parts) > 1:
            out[cp] = parts
    return out


# ---------------------------------------------------------------------------
# Fork planning -- turn a divergence map into concrete class assignments
# ---------------------------------------------------------------------------


def _short(class_path):
    """The bare class name from a dotted ``class_path`` (``mpynode_user.Foo`` ->
    ``Foo``)."""
    return class_path.rpartition(".")[2] or class_path


def plan_forks(diverged, taken_names=None):
    """Deterministic fork plan for a ``diverged_classes`` map.

    For each diverged Class, the FIRST content variant (in first-seen order)
    KEEPS the original Class; every other variant is assigned a fresh Class name
    ``<Base>2``, ``<Base>3``, ... skipping any name in ``taken_names`` or already
    assigned in this plan. Returns::

        [{"class_path": "mpynode_user.Widget",
          "class_name": "Widget",
          "keep":  ["nodeA", ...],                    # stay on the original Class
          "forks": [{"class_name": "Widget2",
                     "nodes": ["nodeB", ...]}, ...]}]  # each variant -> new Class

    Node ordering follows the input; naming is fully deterministic (no clock /
    randomness), so a resumed / replayed run yields the same plan. Only diverged
    Classes (>= 2 variants) appear."""
    taken = set(taken_names or [])
    plans = []
    for class_path, parts in diverged.items():
        groups = list(parts.values())  # dict preserves first-seen order
        if len(groups) < 2:
            continue
        base = _short(class_path)
        taken.add(base)
        forks = []
        suffix = 2
        for grp in groups[1:]:
            while (base + str(suffix)) in taken:
                suffix += 1
            new_name = base + str(suffix)
            taken.add(new_name)
            suffix += 1
            forks.append({"class_name": new_name,
                          "nodes": [_node_name(n) for n in grp]})
        plans.append({
            "class_path": class_path,
            "class_name": base,
            "keep": [_node_name(n) for n in groups[0]],
            "forks": forks,
        })
    return plans


# ---------------------------------------------------------------------------
# Spec level (porter dicts) -- consumed by the compile controller
# ---------------------------------------------------------------------------


def _attr_tokens(attrs):
    """``["name:type:is_array", ...]`` for a spec's normalized attr map. Includes
    type + is_array (not just the name) so two instances of one Class that share
    attr NAMES but differ in an attr's TYPE or array-ness -- a real structural
    divergence that changes the generated C++ -- hash differently instead of
    collapsing to one silently-mis-compiled type."""
    out = []
    for name, meta in (attrs or {}).items():
        meta = meta or {}
        out.append("%s:%s:%d" % (name, meta.get("type") or "",
                                 1 if meta.get("is_array") else 0))
    return out


def spec_content_hash(spec):
    """Content hash for a porter SPEC dict -- the compile-path (authoritative)
    analog of ``node_content_hash``. Hashes the normalized compute/init/methods
    plus each attr's name+type+is_array and the persistent-var names. Unlike the
    names-only node-level hash it is structurally aware (type/is_array), so the
    dedup + controller catch a Duplicate-then-retype divergence the node-level
    pre-flight cannot see; the two layers may therefore differ in absolute value
    but the spec layer is the one the compile decision is made on."""
    spec = spec or {}
    return source_hash(
        spec.get("compute") or "",
        _attr_tokens(spec.get("inputs")),
        _attr_tokens(spec.get("outputs")),
        init=spec.get("init") or "",
        methods=spec.get("methods") or "",
        persistent_names=list((spec.get("variables") or {}).keys()),
    )


def specs_are_identical(a, b):
    """True if two specs have the same normalized authoring (safe to compile as
    a single representative of one Class)."""
    return spec_content_hash(a) == spec_content_hash(b)


def _spec_type_name(spec):
    return ((spec or {}).get("suggested") or {}).get("node_type_name") or ""


def diverged_spec_groups(specs):
    """``{node_type_name: {content_hash: [spec, ...]}}`` for every compiled TYPE
    whose specs are not all structurally identical.

    Groups by ``suggested.node_type_name`` -- the exact key the controller dedups
    on -- so a type with >1 distinct content hash is precisely a divergence the
    controller must surface instead of silently compiling one representative.
    Specs with no type name are skipped."""
    groups = {}
    for s in specs:
        tn = _spec_type_name(s)
        if not tn:
            continue
        groups.setdefault(tn, []).append(s)
    out = {}
    for tn, group in groups.items():
        parts = {}
        for s in group:
            parts.setdefault(spec_content_hash(s), []).append(s)
        if len(parts) > 1:
            out[tn] = parts
    return out
