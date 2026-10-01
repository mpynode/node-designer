"""Plan and build ONE plug-in from nodes that are already compiled to C++.

The Compile dialog compiles nodes from their Python; this module starts from
the C++ it produced. Any node source MPyNode has written is an input:

  * ``<plugin>/build/source/<node>.cpp`` from a single-node compile
    (a complete plug-in with its own ``initializePlugin``);
  * ``<plugin>/build/source/<node>.cpp`` from a multi-node compile
    (a bundler fragment: namespaced, with ``register_*`` hooks);
  * the scratch ``<plugin>/build/<node>/<node>.cpp`` the pipeline promotes
    from (a standalone source whose ids are still placeholders).

It is not concatenation. Each source is turned into an isolated unit by
:mod:`mpynode.native.compiler.bundler` -- wrapped in its own namespace, entry
points renamed, registered through one generated ``plugin_main.cpp`` -- so the
combiner is Python, run by the mayapy that ships with Maya. The folder it
writes rebuilds with the plain ``build.bat`` / ``build.sh`` inside it.

This module owns what the bundler does not: finding the inputs, telling what
each one is, deciding each node's MTypeId, refusing every combination that
cannot load before anything is compiled, writing a manifest of exactly what
went in, and test-loading the result in the target Maya. It never imports
Qt, so the CLI and the Designer share it.
"""
from __future__ import annotations

import dataclasses
import glob
import hashlib
import json
import os
import re
import subprocess
import time
from typing import Dict, List, Optional, Tuple

from mpynode.native.compiler import bundler
from mpynode.native.toolchain import toolchain, typeid_registry

NOT_NODES = ("plugin_main.cpp", "shared_helpers.cpp")
_STAMP_RE = re.compile(r"^// build: ([0-9a-f]+)", re.M)
_QT_MARK  = "QtGui/QCursor"


class InputError(ValueError):
    """An input that cannot be resolved (missing path, bad selector)."""


class BundleRefused(RuntimeError):
    """Pre-flight refused the set. ``codes`` are the E-codes that fired."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join("%s %s" % e for e in self.errors))

    @property
    def codes(self):
        return sorted({c for c, _m in self.errors})


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _norm_hex(value) -> str:
    return bundler._hex_id(value)


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Member:
    """One input source and everything the plan knows about it."""
    path:             str
    kind:             str = ""                                                  # standalone | fragment | scratch | refused
    node:             str = ""                                                  # the REGISTERED node type name
    cls:              str = ""
    hook:             str = ""                                                  # a fragment's register_* hook
    ids:              Dict[str, str] = dataclasses.field(default_factory=dict)  # literal
    commands:         List[str] = dataclasses.field(default_factory=list)
    needs_qt:         bool = False
    sha256:           str = ""
    build_stamp:      str = ""
    recipe:           str = ""
    source_plugin:    str = ""
    manifest_id:      Optional[str] = None
    source_literal:   Optional[str] = None
    fragment_version: int = 0
    reason:           str = ""
    resolved:         Dict[str, str] = dataclasses.field(default_factory=dict)
    id_source:        Dict[str, str] = dataclasses.field(default_factory=dict)

    @property
    def sanitized(self) -> str:
        return re.sub(r"\W", "_", self.node)

    def row(self) -> dict:
        """The ``bundled_from`` manifest row: enough to refresh the bundle."""
        return {
            "path":          self.path,
            "kind":          self.kind,
            "sha256":        self.sha256,
            "node":          self.node,
            "class":         self.cls,
            "ids":           dict(self.resolved),
            "id_source":     dict(self.id_source),
            "build_stamp":   self.build_stamp,
            "recipe":        self.recipe,
            "source_plugin": self.source_plugin,
            "commands":      list(self.commands),
            "needs_qt":      self.needs_qt,
        }


# ---------------------------------------------------------------------------
# 1. Inputs
# ---------------------------------------------------------------------------

def _node_sources_in(folder: str) -> List[str]:
    """The node ``.cpp`` files a folder holds, at whichever of the three
    layouts it is (a plug-in folder, its ``build/``, or ``build/source``)."""
    for cand in (os.path.join(folder, "build", "source"),
                 os.path.join(folder, "source"), folder):
        cpps = sorted(p for p in glob.glob(os.path.join(cand, "*.cpp"))
                      if os.path.basename(p) not in NOT_NODES)
        if cpps:
            return cpps
    return []


def resolve_inputs(specs) -> List[str]:
    """Expand the CLI's INPUT forms into absolute ``.cpp`` paths, in order,
    without duplicates.

      ``X.cpp``         one source
      ``FOLDER``        every node in its ``build/source`` (or ``source``, or
                        the folder itself); ``plugin_main`` / shared unit skipped
      ``FOLDER::a,b``   only the nodes whose file stem is ``a`` or ``b``
      ``@list.txt``     one INPUT per line, ``#`` comments
      globs             expanded here, so they work from cmd.exe too
    """
    out: List[str] = []
    for spec in specs:
        spec = str(spec).strip()
        if not spec:
            continue
        if spec.startswith("@"):
            try:
                with open(spec[1:], encoding="utf-8") as fh:
                    lines = [ln.split("#", 1)[0].strip() for ln in fh]
            except OSError as exc:
                raise InputError("cannot read %s: %s" % (spec, exc))
            out += resolve_inputs([ln for ln in lines if ln])
            continue
        only = None
        if "::" in spec:
            spec, sel = spec.rsplit("::", 1)
            only = {s.strip() for s in sel.split(",") if s.strip()}
        paths = sorted(glob.glob(spec)) if any(c in spec for c in "*?[") else [spec]
        if not paths:
            raise InputError("no such input: %s" % spec)
        for p in paths:
            p = os.path.abspath(p)
            if os.path.isdir(p):
                cpps = _node_sources_in(p)
                if not cpps:
                    raise InputError("no node sources under %s" % p)
                if only is not None:
                    stems   = {os.path.splitext(os.path.basename(c))[0]: c for c in cpps}
                    missing = sorted(only - set(stems))
                    if missing:
                        raise InputError("%s has no node(s) %s; it has %s"
                                         % (p, ", ".join(missing), ", ".join(sorted(stems))))
                    cpps = [stems[s] for s in sorted(only)]
                out += cpps
            elif os.path.isfile(p):
                if only is not None:
                    raise InputError("'::' selects nodes from a FOLDER, not a file: %s" % p)
                out.append(p)
            else:
                raise InputError("no such input: %s" % p)
    seen: Dict[str, None] = {}
    for p in out:
        seen.setdefault(os.path.normcase(p), None)
        seen[os.path.normcase(p)] = p
    return list(dict.fromkeys(seen.values()))


# ---------------------------------------------------------------------------
# 2. Scan
# ---------------------------------------------------------------------------

def _sibling_manifest(m: Member) -> None:
    """Fill ``manifest_id`` / ``recipe`` / ``source_plugin`` from the
    ``build/manifest.json`` beside the source, and for a scratch input the
    promoted ``build/source/<node>.cpp`` literal it would ship with."""
    d     = os.path.dirname(m.path)
    build = os.path.dirname(d)  # build/source/x.cpp, build/<t>/x.cpp
    mf    = os.path.join(build, "manifest.json")
    try:
        with open(mf, encoding="utf-8") as fh:
            man = json.load(fh)
    except (OSError, ValueError):
        man = None
    if man:
        for row in man.get("nodes") or []:
            if row.get("type_name") == m.node:
                if row.get("type_id"):
                    m.manifest_id = _norm_hex(row["type_id"])
                break
        m.recipe        = str(man.get("porter_recipe_version") or "")
        m.source_plugin = str(man.get("plugin_name") or "")
    if m.kind == "scratch":
        sib = os.path.join(build, "source", m.sanitized + ".cpp")
        try:
            with open(sib, encoding="utf-8") as fh:
                for cls, hx in bundler._TYPEID_CLS_RE.findall(fh.read()):
                    if cls == m.cls:
                        m.source_literal = _norm_hex(hx)
                        break
        except OSError:
            pass


def _trailing_code(text: str) -> bool:
    """True when code follows ``uninitializePlugin`` that the transform would
    drop on the floor (it keeps nothing after that function)."""
    flat = bundler._flatten_probe_guards(text)
    fn   = bundler._extract_fn(flat, "uninitializePlugin")
    if not fn:
        return False
    tail = flat[fn[1]:]
    return any(bundler._is_code(ln) and not ln.lstrip().startswith("#")
               for ln in tail.splitlines())


def scan(path: str) -> Member:
    """Read one source and say what it is. Never raises for a bad input --
    it comes back ``kind == "refused"`` with the reason, so pre-flight can
    report every problem at once."""
    m    = Member(path=os.path.abspath(path))
    base = os.path.basename(m.path)
    if base in NOT_NODES:
        m.kind, m.reason = "refused", "not a node: %s is a bundle's own file" % base
        return m
    try:
        with open(m.path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        m.kind, m.reason = "refused", "cannot read: %s" % exc
        return m
    text          = raw.decode("utf-8", errors="replace")
    m.sha256      = _sha256(raw)
    m.needs_qt    = _QT_MARK in text
    st            = _STAMP_RE.search(text)
    m.build_stamp = st.group(1) if st else ""

    if bundler.is_fragment_text(text):
        try:
            info = bundler.fragment_info(text)
        except ValueError as exc:
            m.kind, m.reason = "refused", str(exc)
            return m
        m.kind = "fragment"
        m.node, m.cls = info["node_name"], info["class"]
        m.hook             = info["register"]
        m.ids              = {k: _norm_hex(v) for k, v in info["type_id_map"].items()}
        m.commands         = list(info["commands"])
        m.fragment_version = int(info["version"])
        if "defined in shared_helpers.cpp" in text:
            m.kind, m.reason = "refused", (
                "fragment %s depends on a shared_helpers.cpp that is not an "
                "input; re-bundle it from its standalone source" % m.node)
    elif bundler._INIT_RE.search(text):
        init = bundler._extract_fn(text, "initializePlugin")
        reg  = bundler._REGNAME_RE.search(text, init[0] if init else 0)
        if not reg:
            m.kind, m.reason = "refused", (
                "registers no node type: no registerNode / registerTransform "
                "in initializePlugin (a shape, data or command-only plug-in "
                "cannot be bundled)")
            return m
        m.node, m.cls = reg.group(1), reg.group(2)
        m.ids = {(m.node if c == m.cls else "%s#%s" % (m.node, c)): _norm_hex(hx)
                 for c, hx in bundler._TYPEID_CLS_RE.findall(text)}
        m.commands = bundler.command_names_in(text)
        parent     = os.path.basename(os.path.dirname(m.path))
        gparent    = os.path.basename(os.path.dirname(os.path.dirname(m.path)))
        m.kind = ("scratch" if parent == os.path.splitext(base)[0] and gparent == "build"
                  else "standalone")
        if not bundler._extract_fn(text, "uninitializePlugin"):
            m.kind, m.reason = "refused", "no uninitializePlugin"
            return m
        if _trailing_code(text):
            m.kind, m.reason = "refused", (
                "code after uninitializePlugin, which the transform drops; "
                "move it above the plug-in entry points")
            return m
    else:
        m.kind, m.reason = "refused", (
            "not a node source: neither initializePlugin nor a bundler "
            "register_* hook")
        return m
    _sibling_manifest(m)
    return m


# ---------------------------------------------------------------------------
# 3. Ids
# ---------------------------------------------------------------------------

def resolve_ids(members: List[Member], pins: Optional[Dict[str, str]] = None
                ) -> List[Tuple[str, str]]:
    """Decide every MTypeId. Each node keeps what it shipped with. First
    match wins, per key (``<node>`` or ``<node>#<Class>``):

      1. an explicit pin;
      2. the literal in the input, unless it is the spec's PLACEHOLDER
         (``suggest_type_id(node)`` for the main class, that + 1 for a
         companion) -- a scratch source still carries those;
      3. for the main class, the sibling manifest's ``type_id``;
      4. the literal in the sibling ``build/source/<node>.cpp``;
      5. derived, the registry's own scheme.

    The literal beats the manifest because manifests go stale (the mega's
    said patchRelax was 0x00078000 while its source had 0x0004cf56).
    Duplicates are never probed forward: a moved id would depend on what else
    is in the bundle, and ``.mb`` scenes store ids. A fragment's ids are baked
    into its text and stay as they are. Returns pre-flight errors (a pin on a
    fragment).
    """
    from mpynode.native.spec.spec_extractor import suggest_type_id

    pins = {k: _norm_hex(v) for k, v in (pins or {}).items()}
    errors: List[Tuple[str, str]] = []
    for m in members:
        if m.kind == "refused":
            continue
        ph = int(suggest_type_id(m.node), 16)
        for key, literal in m.ids.items():
            companion = key != m.node
            if key in pins:
                if m.kind == "fragment" and pins[key] != literal:
                    errors.append(("E4", "%s: cannot pin %s to %s -- a fragment's id "
                                   "is baked into its text (%s); re-bundle it from "
                                   "its standalone source" % (m.node, key, pins[key], literal)))
                    m.resolved[key], m.id_source[key] = literal, "literal"
                    continue
                m.resolved[key], m.id_source[key] = pins[key], "pinned"
                continue
            if m.kind == "fragment":
                m.resolved[key], m.id_source[key] = literal, "literal"
                continue
            lit   = int(literal, 16)
            is_ph = (lit == ph + 1) if companion else (lit == ph)
            if not is_ph:
                m.resolved[key], m.id_source[key] = literal, "literal"
            elif not companion and m.manifest_id:
                m.resolved[key], m.id_source[key] = m.manifest_id, "manifest"
            elif not companion and m.source_literal:
                m.resolved[key], m.id_source[key] = m.source_literal, "source"
            else:
                m.resolved[key]  = _norm_hex(typeid_registry.deterministic_id(key))
                m.id_source[key] = "derived"
    return errors


# ---------------------------------------------------------------------------
# 4. Pre-flight
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Plan:
    members:  List[Member]
    errors:   List[Tuple[str, str]]
    warnings: List[str]
    needs_qt: bool = False

    @property
    def ok(self) -> bool:
        return not self.errors


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _unwrapped_runs(m: Member, text: str) -> Dict[str, str]:
    """The global-only runs isolation must leave at file scope, keyed by their
    first code line, so two members can be compared on them."""
    if m.kind == "fragment":
        mm   = re.search(r"^namespace nd_\w+\s*\{", text, re.M)
        head = text[: mm.start()] if mm else text
    else:
        fn   = bundler._extract_fn(bundler._flatten_probe_guards(text), "initializePlugin")
        head = text[: fn[0]] if fn else text
    _pre, left = bundler.isolate_global_runs(head.splitlines(), "nd_probe")
    out = {}
    for run in left:
        first = next((ln.strip() for ln in run.splitlines() if bundler._is_code(ln)), run[:60])
        # The key is the run's SIGNATURE -- its first line up to the body --
        # so `extern "C" int hook() { return 1; }` and the same with `return 2`
        # compare instead of passing as two unrelated runs.
        key      = re.split(r"[{=;]", first, 1)[0].strip()
        out[key] = run
    return out


def preflight(members: List[Member], *, maya: str, exclude=(),
              pins: Optional[Dict[str, str]] = None) -> Plan:
    """Every reason the set cannot become one plug-in, all at once.

    | code | refused when |
    |------|--------------|
    | E1   | the same registered name twice with different content (byte-identical duplicates are merged) |
    | E2   | two names that collide once sanitized to a file / namespace name |
    | E3   | a command registered by two members (Maya's command space is global) |
    | E4   | two members resolve to one MTypeId, or a pin on a fragment |
    | E5   | two legacy fragments with the same ``register_*`` hook (LNK2005) |
    | E6   | an input that is not a node |
    | E7   | a fragment that expects a ``shared_helpers.cpp`` |
    | E8   | members disagree on a global-only run isolation cannot wrap |
    | E9   | a Qt member when the target Maya's Qt headers cannot be found |
    | E10  | building on Linux (no link recipe) |
    """
    errors:   List[Tuple[str, str]] = []
    warnings: List[str] = []
    excl = {str(e) for e in exclude}
    kept: List[Member] = []
    for m in members:
        if m.node in excl or m.sanitized in excl or os.path.splitext(
                os.path.basename(m.path))[0] in excl:
            warnings.append("excluded %s (%s)" % (m.node or os.path.basename(m.path), m.path))
            continue
        kept.append(m)
    members = kept

    for m in members:
        if m.kind == "refused":
            code = "E7" if "shared_helpers" in m.reason else "E6"
            errors.append((code, "%s: %s" % (m.path, m.reason)))
    live = [m for m in members if m.kind != "refused"]

    errors += resolve_ids(live, pins)

    # E1 -- one registered name, one member.
    by_name: Dict[str, List[Member]] = {}
    for m in live:
        by_name.setdefault(m.node, []).append(m)
    deduped: List[Member] = []
    for m in live:
        group = by_name[m.node]
        if group[0] is not m:
            continue  # handled with the first
        if len(group) > 1:
            if all(g.sha256 == m.sha256 for g in group):
                warnings.append("%s given %d times with identical content; using %s"
                                % (m.node, len(group), m.path))
            else:
                errors.append(("E1", "node '%s' comes from %d different sources: %s"
                               % (m.node, len(group), ", ".join(g.path for g in group))))
        deduped.append(m)
    live = deduped

    # E2 -- sanitized names are file and namespace names.
    by_san: Dict[str, List[str]] = {}
    for m in live:
        by_san.setdefault(m.sanitized, []).append(m.node)
    for san, names in by_san.items():
        if len(names) > 1:
            errors.append(("E2", "node names %s all become '%s' as a file and "
                           "namespace name" % (", ".join("'%s'" % n for n in names), san)))

    texts = {m.path: _read(m.path) for m in live}

    # E3 -- commands.
    clashes = bundler.find_command_clashes([(m.node, texts[m.path]) for m in live])
    for cmd, owners in sorted(clashes.items()):
        errors.append(("E3", "command '%s' is registered by %s"
                       % (cmd, ", ".join(sorted(set(owners))))))

    # E4 -- ids.
    by_id: Dict[str, List[str]] = {}
    for m in live:
        for key, hx in m.resolved.items():
            by_id.setdefault(hx, []).append(key)
    for hx, keys in by_id.items():
        if len(keys) > 1:
            errors.append(("E4", "MTypeId %s is claimed by %s" % (hx, ", ".join(keys))))

    # E5 -- legacy fragments' hooks are named after the CLASS.
    by_hook: Dict[str, List[str]] = {}
    for m in live:
        if m.kind == "fragment" and m.fragment_version < 2:
            by_hook.setdefault(m.hook, []).append(m.node)
    for hook, names in by_hook.items():
        if len(names) > 1:
            errors.append(("E5", "legacy fragments %s share the hook %s (their classes "
                           "have the same name); re-bundle one from its standalone "
                           "source" % (", ".join(names), hook)))

    # E8 -- global-only runs.
    runs: Dict[str, Tuple[str, str]] = {}
    for m in live:
        for first, run in _unwrapped_runs(m, texts[m.path]).items():
            if first in runs and runs[first][1] != run:
                errors.append(("E8", "%s and %s carry different versions of global "
                               "code isolation cannot wrap (%r)"
                               % (runs[first][0], m.node, first[:60])))
            runs.setdefault(first, (m.node, run))

    needs_qt = any(m.needs_qt for m in live)
    if needs_qt:
        problem = toolchain.qt_include_problem(maya)
        if problem:
            errors.append(("E9", problem))
    if toolchain.is_linux():
        errors.append(("E10", "no Linux link recipe; build on Windows or macOS"))

    for m in live:
        main = m.resolved.get(m.node)
        if (m.kind != "fragment" and m.manifest_id and main
                and m.id_source.get(m.node) == "literal" and m.manifest_id != main):
            warnings.append("%s: its manifest says %s but the source carries %s; "
                            "keeping the source" % (m.node, m.manifest_id, main))
        if m.commands and m.source_plugin:
            warnings.append("%s registers command(s) %s: it cannot be loaded beside "
                            "its own plug-in '%s'" % (m.node, ", ".join(m.commands),
                                                      m.source_plugin))
        if m.kind == "fragment" and m.fragment_version < 2:
            warnings.append("%s is a legacy fragment; its runtime is isolated on the way in"
                            % m.node)
    return Plan(members=live, errors=errors, warnings=warnings, needs_qt=needs_qt)


def out_dir_problem(out_dir: str) -> Optional[str]:
    """E11: an output folder is acceptable when it does not exist, is empty,
    or was written by the bundler (its ``build/README.txt`` says so)."""
    if not os.path.exists(out_dir):
        return None
    if not os.path.isdir(out_dir):
        return "%s is not a directory" % out_dir
    if not os.listdir(out_dir):
        return None
    readme = os.path.join(out_dir, bundler.BUILD_DIRNAME, "README.txt")
    if bundler._is_bundler_output(readme):
        return None
    return ("%s is not empty and was not written by the bundler; choose a new "
            "--out or empty it" % out_dir)


# ---------------------------------------------------------------------------
# 5. Build + manifest
# ---------------------------------------------------------------------------

def _manifest_version() -> int:
    try:
        from mpynode.native.toolchain.compile_controller import MANIFEST_VERSION
        return int(MANIFEST_VERSION)
    except Exception:
        return 1


def default_version(members: List[Member]) -> str:
    """``1.0+<sha12>`` over the member sources, so two bundles of the same
    inputs carry the same version and a changed input changes it."""
    h = hashlib.sha256("\n".join(sorted(m.sha256 for m in members)).encode()).hexdigest()
    return "1.0+" + h[:12]


def build(plan: Plan, name: str, out_dir: str, *, maya: str,
          compile_now: bool = True, best_effort: bool = False,
          strict_load: bool = False, vendor: str = "mpynode-native",
          version: Optional[str] = None, log_cb=None) -> dict:
    """Assemble the plan into ``<out_dir>/<name>.<ext>`` (+ its re-buildable
    ``build/`` tree) and write ``build/manifest.json``.

    Raises :class:`BundleRefused` on pre-flight errors or an unsafe
    ``out_dir``; every other failure comes back in the report's ``reason``.
    """
    if plan.errors:
        raise BundleRefused(plan.errors)
    problem = out_dir_problem(out_dir)
    if problem:
        raise BundleRefused([("E11", problem)])
    version = version or default_version(plan.members)
    # A registry that reads no pin file: every id was decided by resolve_ids.
    reg = typeid_registry.TypeIdRegistry(path=os.path.join(out_dir, ".no-pins.json"))
    for m in plan.members:
        for key, hx in m.resolved.items():
            reg.claim_literal(key, hx)
    nodes = [(m.node, m.path) for m in plan.members]
    report = bundler.assemble(nodes, name, out_dir, strict=not best_effort,
                              registry=reg, maya=maya, compile_now=compile_now,
                              log_cb=log_cb, vendor=vendor, version=version,
                              strict_load=strict_load)
    report["manifest"] = write_manifest(out_dir, name, plan, report, maya=maya,
                                        vendor=vendor, version=version,
                                        strict_load=strict_load)
    return report


def write_manifest(out_dir: str, name: str, plan: Plan, report: dict, *,
                   maya: str, vendor: str, version: str, strict_load: bool) -> str:
    """The build receipt, in the controller's shape (``nodes[].type_name`` /
    ``build_status`` are what ``validate_registered_types`` and the Designer's
    load offer read) plus ``bundled_from``: the exact inputs, so ``--refresh``
    can rebuild the same set and a picker can reload the selection."""
    by_name = {r["name"]: r for r in report.get("nodes", [])}
    rows    = []
    for m in plan.members:
        rec = by_name.get(m.node, {})
        rows.append({
            "source_node":    m.node,
            "type_name":      m.node,
            "type_id":        rec.get("id") or m.resolved.get(m.node),
            "type_id_source": m.id_source.get(m.node, ""),
            "base":           "",
            "build_status":   rec.get("status", "unknown"),
            "build_reason":   rec.get("reason", ""),
            "commands":       list(m.commands),
            "spec":           None,
        })
    man = {
        "manifest_version": _manifest_version(),
        "plugin_name":      name,
        "bundle":           report.get("bundle"),
        "created":          time.time(),
        "maya":             maya,
        "vendor":           vendor,
        "version":          version,
        "strict_load":      bool(strict_load),
        "bundled_by":       "mpynode.native.bundle",
        "nodes":            rows,
        "bundled_from":     [m.row() for m in plan.members],
    }
    path = os.path.join(bundler.build_dir_for(out_dir), "manifest.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1)
    return path


def read_manifest(out_dir: str) -> dict:
    with open(os.path.join(bundler.build_dir_for(out_dir), "manifest.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def refresh_inputs(out_dir: str, *, from_self: bool = False) -> Tuple[List[str], dict]:
    """The inputs a previous bundle was made from (its manifest's
    ``bundled_from``), or with ``from_self`` its own ``build/source``
    fragments, plus the settings it was built with."""
    man = read_manifest(out_dir)
    if from_self:
        paths = _node_sources_in(out_dir)
    else:
        paths   = [r["path"] for r in man.get("bundled_from") or []]
        missing = [p for p in paths if not os.path.isfile(p)]
        if missing:
            raise InputError("inputs recorded by %s no longer exist: %s (use "
                             "--from-self to rebuild from its own build/source)"
                             % (out_dir, ", ".join(missing)))
    if not paths:
        raise InputError("%s records no inputs" % out_dir)
    return paths, man


# ---------------------------------------------------------------------------
# 6. Load check
# ---------------------------------------------------------------------------

_LOAD_SCRIPT = r'''
import json, os, sys
import maya.standalone
maya.standalone.initialize(name="python")
from maya import cmds
p, want = %(bundle)r, %(want)r
out = {"loaded": False, "registered": [], "commands": [], "missing": [],
       "create_failed": [], "error": ""}
try:
    try:
        cmds.loadPlugin(p)
    except Exception as exc:          # loadPlugin may or may not raise
        out["error"] = str(exc).strip()
    name = os.path.splitext(os.path.basename(p))[0]
    out["loaded"] = bool(cmds.pluginInfo(name, q=True, loaded=True))
    if out["loaded"]:
        out["registered"] = sorted(cmds.pluginInfo(name, q=True, dependNode=True) or [])
        out["commands"]   = sorted(cmds.pluginInfo(name, q=True, command=True) or [])
        out["missing"]    = [t for t in want if t not in out["registered"]]
        for t in out["registered"]:
            try:
                cmds.createNode(t)
            except Exception as exc:
                out["create_failed"].append("%%s: %%s" %% (t, exc))
        cmds.file(new=True, force=True)
        try:
            cmds.unloadPlugin(name)
        except Exception as exc:
            out["error"] += " unload: %%s" %% exc
except Exception as exc:
    out["error"] += " %%s" %% exc
print("ND_LOAD_CHECK " + json.dumps(out))
sys.stdout.flush()
maya.standalone.uninitialize()
os._exit(0)
'''


def load_check(bundle_path: str, expected_types: List[str], maya: str,
               timeout: float = 600.0) -> dict:
    """Load the bundle in the TARGET Maya's own mayapy (a fresh process, with
    Autodesk's crash reporter off), confirm it registers every expected type,
    create one of each, and unload. ``ok`` is True only when all of that held.
    ``loadPlugin`` does not reliably raise on a failed initializePlugin, so
    the verdict comes from ``pluginInfo``, never from the call."""
    mayapy = toolchain.mayapy_path(maya)
    result = {"ok": False, "mayapy": mayapy, "loaded": False, "registered": [],
              "commands": [], "missing": list(expected_types), "create_failed": [],
              "error": "", "stderr": ""}
    if not os.path.isfile(mayapy):
        result["error"] = "mayapy not found at %s" % mayapy
        return result
    env                     = dict(os.environ)
    env["MAYA_DISABLE_CER"] = "1"
    script                  = _LOAD_SCRIPT % {"bundle": bundle_path, "want": list(expected_types)}
    try:
        proc = subprocess.run([mayapy, "-c", script], env=env, capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        result["error"] = "load check timed out after %.0fs" % timeout
        return result
    result["stderr"] = (proc.stderr or "")[-4000:]
    for line in (proc.stdout or "").splitlines():
        if line.startswith("ND_LOAD_CHECK "):
            try:
                result.update(json.loads(line[len("ND_LOAD_CHECK "):]))
            except ValueError:
                result["error"] = "unreadable load-check report"
            break
    else:
        result["error"] = result["error"] or ("mayapy exited %d without a report"
                                              % proc.returncode)
    result["ok"] = bool(result["loaded"] and not result["missing"]
                        and not result["create_failed"])
    return result


# ---------------------------------------------------------------------------
# 7. What the Designer needs on top: where compiled nodes live, and a result
#    in the compile controller's shape
# ---------------------------------------------------------------------------

def compiled_artifact_for(folder: str) -> Optional[str]:
    """The compiled node source a template or plug-in folder ships, or
    ``None``: the promoted ``build/source/<type>.cpp`` for the type its
    manifest records, else the scratch ``build/<type>/<type>.cpp``. The type
    comes from the manifest, never from a directory listing -- a stale scratch
    dir left by a rename is invisible to the manifest but not to listdir."""
    build = os.path.join(folder, bundler.BUILD_DIRNAME)
    try:
        with open(os.path.join(build, "manifest.json"), encoding="utf-8") as fh:
            man = json.load(fh)
    except (OSError, ValueError):
        return None
    for row in man.get("nodes") or []:
        ty = row.get("type_name")
        if not ty:
            continue
        san = re.sub(r"\W", "_", ty)
        for cand in (os.path.join(build, bundler.SOURCE_DIRNAME, san + ".cpp"),
                     os.path.join(build, san, san + ".cpp")):
            if os.path.isfile(cand):
                return cand
    return None


_SKIP_DIRS = {"stages", "__pycache__", "_optscratch", "scenes", "reports",
              ".git", "port_cache"}


def list_candidates(roots) -> List[Member]:
    """Every compiled node under ``roots`` (template trees, the user's
    compiled folder, anything the picker was pointed at), one :class:`Member`
    per manifest row that has a source on disk. A multi-node build's members
    are listed one by one, so a picker can take part of it."""
    out: List[Member] = []
    seen = set()
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            if os.path.basename(dirpath) != bundler.BUILD_DIRNAME or "manifest.json" not in filenames:
                continue
            dirnames[:] = []  # a build tree: nothing to find below it
            try:
                with open(os.path.join(dirpath, "manifest.json"), encoding="utf-8") as fh:
                    man = json.load(fh)
            except (OSError, ValueError):
                continue
            for row in man.get("nodes") or []:
                ty = row.get("type_name")
                if not ty or row.get("build_status") in ("dropped", "compile-failed"):
                    continue
                san = re.sub(r"\W", "_", ty)
                for cand in (os.path.join(dirpath, bundler.SOURCE_DIRNAME, san + ".cpp"),
                             os.path.join(dirpath, san, san + ".cpp")):
                    key = os.path.normcase(cand)
                    if os.path.isfile(cand) and key not in seen:
                        seen.add(key)
                        out.append(scan(cand))
                        break
    return out


def controller_row(m: Member, rec: Optional[dict] = None) -> dict:
    """A manifest / result row for a prebuilt member, in the compile
    controller's row shape (what the Designer's summary, the load offer and
    ``validate_registered_types`` read). No spec, no verify: the node was
    compiled and verified when it was built."""
    rec = rec or {}
    return {
        "source_node":      m.node,
        "type_name":        m.node,
        "type_id":          rec.get("id") or m.resolved.get(m.node),
        "type_id_source":   m.id_source.get(m.node, ""),
        "base":             "",
        "spec_hash":        "",
        "port_cache_key":   "",
        "cache":            "prebuilt",
        "build_status":     rec.get("status", "unknown"),
        "build_reason":     rec.get("reason", ""),
        "ported":           True,
        "incomplete":       [],
        "invented_io":      [],
        "missing_includes": [],
        "vp2_skip":         "",
        "verify": {"ran": False, "pass": None, "maxerr": None, "tol": None,
                   "reason": "already compiled; not re-verified"},
        "spec":     None,
        "prebuilt": m.row(),
    }


def as_controller_result(report: dict, plan: Plan, plugin_name: str,
                         strict: bool = True) -> dict:
    """The bundler report as the dict ``compile_plugin`` returns, so the
    Compile dialog's finish path (summary, warnings, the offer to load) serves
    a bundle of compiled nodes without a second code path."""
    by_name = {r["name"]: r for r in report.get("nodes", [])}
    rows    = [controller_row(m, by_name.get(m.node)) for m in plan.members]
    errors: List[str] = []
    if not report.get("ok"):
        reason = report.get("reason") or "assemble failed"
        tail   = (report.get("stderr") or "").strip().splitlines()[-12:]
        errors.append(reason + ("\n" + "\n".join(tail) if tail else ""))
    for d in report.get("dropped") or []:
        errors.append("dropped %s: %s" % (d, by_name.get(d, {}).get("reason", "")))
    return {
        "ok":            bool(report.get("ok")),
        "bundle_path":   report.get("bundle"),
        "manifest_path": report.get("manifest"),
        "report_path":   None,
        "plugin_name":   plugin_name,
        "nodes":         rows,
        "errors":        errors,
        "strict":        strict,
        "companions":    [],
        "prebuilt":      True,
    }
