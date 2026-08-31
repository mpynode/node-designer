"""Master compiler-audit orchestrator.

For every template (or a filtered subset), in an ISOLATED fresh mayapy per step:
  1. compile the template .mpn to a native plugin (opus-4.8[1m], effort high --
     the reliable tier; see compile_one.py's EFFORT note. 'max' times out on hard
     ports. Override with MPYNODE_PORT_EFFORT.)
  2. build EACH @maya_demo of the template against the COMPILED node + save one
     .ma per demo (multi-demo templates -- e.g. DNET: Grid Net / Layout Net /
     Two Knots -- get one .ma each; single-demo templates keep <folder>.ma)
  3. clean-reopen each .ma to prove the compiled plugin loads

Writes per-template artifacts under compiled_templates/<folder>/ and a running
master_results.json + master.log at the audit root. Continues past any failure
and records it. Safe to re-run on a subset: pass folder names as argv.

Usage (plain python3):
    python3 run_all.py [folder1 folder2 ...]
"""
import os
import sys
import ast
import json
import time
import subprocess

HARNESS = os.path.dirname(os.path.abspath(__file__))


def _mpn_methods_source(mpn_path):
    """The template's methods_source string (under data/, with fallbacks)."""
    try:
        d = json.load(open(mpn_path))
    except Exception:
        return ""
    if isinstance(d.get("data"), dict) and isinstance(
            d["data"].get("methods_source"), str):
        return d["data"]["methods_source"]
    for k in ("methods_source", "methodsSource", "_methodsSource"):
        if isinstance(d.get(k), str):
            return d[k]
    return ""


def demo_specs_for(mpn_path):
    """Every demo in the template's methods_source as (func_name, label), in
    source order. Standalone AST mirror of node_setups.find_demos (this runs
    under plain python3, so it cannot import mpynode/maya): every top-level def
    decorated with @maya_demo (bare or called, honoring a `label=`/positional
    label) UNIONED with the reserved `def demo` when not already decorated.

    Returns [] on a parse error or when there is no demo (caller falls back to
    the default/first demo with the templates.json label)."""
    src = _mpn_methods_source(mpn_path)
    if not src.strip():
        return []
    try:
        tree = ast.parse(src)
    except Exception:
        return []
    out, seen = [], set()

    def _label(fn):
        for dec in fn.decorator_list:
            name = label = None
            if isinstance(dec, ast.Name):
                name = dec.id
            elif isinstance(dec, ast.Attribute):
                name = dec.attr
            elif isinstance(dec, ast.Call):
                f = dec.func
                name = f.id if isinstance(f, ast.Name) else getattr(
                    f, "attr", None)
                for kw in (dec.keywords or []):
                    if kw.arg == "label" and isinstance(kw.value, ast.Constant):
                        label = kw.value.value
                for a in dec.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        label = a.value
            if name == "maya_demo":
                return True, label
        return False, None

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            is_demo, label = _label(node)
            if is_demo and node.name not in seen:
                seen.add(node.name)
                out.append((node.name, label or node.name, node.lineno))
    if "demo" not in seen:
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "demo":
                out.append(("demo", "Run demo", node.lineno))
    out.sort(key=lambda t: t[2])
    return [(fn, lbl) for fn, lbl, _ in out]


ROOT = os.path.dirname(os.path.dirname(HARNESS))            # project root
AUDIT_ROOT = os.path.join(ROOT, "compiled_templates")       # audit output root
MAYAPY = os.environ.get(
    "MPYNODE_MAYAPY",
    "/Applications/Autodesk/maya2026/Maya.app/Contents/bin/mayapy")

from demo_specs import load_templates  # noqa: E402

# node_name comes from each .mpn, not the manifest copy -- see load_templates.
TEMPLATES = load_templates(HARNESS, ROOT)

FILTER = set(sys.argv[1:])
if FILTER:
    TEMPLATES = [t for t in TEMPLATES if t["folder"] in FILTER]

MASTER_LOG = os.path.join(AUDIT_ROOT, "master.log")
MASTER_JSON = os.path.join(AUDIT_ROOT, "master_results.json")

# preserve prior results for folders we are NOT re-running this pass
_prior = {}
if os.path.isfile(MASTER_JSON):
    try:
        for r in json.load(open(MASTER_JSON)):
            _prior[r["folder"]] = r
    except Exception:
        _prior = {}

_ml = open(MASTER_LOG, "a")


def ML(msg=""):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    _ml.write(line + "\n")
    _ml.flush()
    print(line, flush=True)


def base_env(out_dir):
    e = dict(os.environ)
    e["MPYNODE_ROOT"] = ROOT
    e["MPYNODE_USE_STUDIO"] = "1"
    # T38: headless can't show the trust prompt, so an untrusted scene stops
    # exec'ing Init AND Compute. reopen_check.py opens a saved demo .ma, which
    # would otherwise mark the whole session untrusted and silently flatten the
    # INTERPRETED reference it compares against.
    e["MPYNODE_TRUST_PICKLE"] = "1"
    e["PYTHONPATH"] = os.path.join(ROOT, "scripts") + ":" + e.get("PYTHONPATH", "")
    e["MAYA_PLUG_IN_PATH"] = ":".join(
        [os.path.join(ROOT, "plug-ins"), out_dir, e.get("MAYA_PLUG_IN_PATH", "")])
    e["QT_QPA_PLATFORM"] = "offscreen"
    cb = e.get("CLAUDE_BIN")
    if not cb:
        for c in ("/usr/local/bin/claude", "/opt/homebrew/bin/claude"):
            if os.path.isfile(c):
                cb = c
                break
    if cb:
        e["CLAUDE_BIN"] = cb
    return e


def run_step(script, args, out_dir, prefix, timeout):
    """Run a mayapy step; return (json_dict_or_None, ok, tail)."""
    cmd = [MAYAPY, os.path.join(HARNESS, script)] + args
    try:
        p = subprocess.run(cmd, cwd=ROOT, env=base_env(out_dir),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
        out = p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as exc:
        return None, False, "TIMEOUT after %ss" % timeout
    except Exception as exc:
        return None, False, "subprocess error: %r" % exc
    data = None
    for line in out.splitlines():
        if line.startswith(prefix):
            try:
                data = json.loads(line[len(prefix):])
            except Exception:
                data = None
    tail = "\n".join(out.splitlines()[-25:])
    return data, (p.returncode == 0), tail


results = []
t_start = time.time()
ML("=" * 70)
ML("AUDIT START: %d template(s)" % len(TEMPLATES))

for idx, t in enumerate(TEMPLATES, 1):
    folder = t["folder"]
    out_dir = os.path.join(AUDIT_ROOT, folder)
    os.makedirs(out_dir, exist_ok=True)
    mpn = os.path.join(ROOT, t["mpn"])
    plugin = t["plugin"]
    label = t["demo_label"]
    # Dual-read the node name: templates.json now carries ``node_name`` (the old
    # key was ``source_name``); tolerate either so a partly-migrated manifest works.
    src = t.get("node_name") or t.get("source_name")
    rec = {
        "folder": folder, "mpn": t["mpn"], "native_type": t["native_type"],
        "source_name": src, "demo_label": label,
        "compile": None, "build": None, "reopen": None,
        "status": "pending", "issues": [],
    }
    ML("-" * 70)
    ML("[%d/%d] %s  (%s / %s)  demo=%r"
       % (idx, len(TEMPLATES), folder, t["native_type"], src, label))

    # 1. COMPILE  (step cap overridable via MPYNODE_STEP_TIMEOUT; keep it >=
    # MPYNODE_PORT_TIMEOUT so a slow port isn't killed by the orchestrator first).
    _step_tmo = int(os.environ.get("MPYNODE_STEP_TIMEOUT", "1800"))
    cj, cok, ctail = run_step(
        "compile_one.py", [mpn, out_dir, plugin, label], out_dir,
        "RESULT_JSON:", timeout=_step_tmo)
    rec["compile"] = cj
    if cj is None:
        rec["issues"].append("compile: no result (%s)" % ctail.replace("\n", " | ")[-300:])
        rec["status"] = "compile_failed"
        ML("   COMPILE: NO RESULT -- %s" % ctail.splitlines()[-1:])
        results.append(rec)
        _all = {r["folder"]: r for r in results}
        merged = list(_prior.values())
        merged = [r for r in merged if r["folder"] not in _all] + results
        json.dump(merged, open(MASTER_JSON, "w"), indent=1)
        continue
    node0 = (cj.get("nodes") or [{}])[0]
    ML("   COMPILE: ok=%s  %ss  det=%s ai=%s  build_status=%s  verify pass=%s maxerr=%s"
       % (cj.get("ok"), cj.get("seconds"), cj.get("deterministic"),
          cj.get("ai_ported"), node0.get("build_status"),
          node0.get("verify_pass"), node0.get("verify_maxerr")))
    if not cj.get("ok"):
        rec["issues"].append("compile failed: %s" % (cj.get("errors")))
        rec["status"] = "compile_failed"
        results.append(rec)
        _all = {r["folder"]: r for r in results}
        merged = [r for r in _prior.values() if r["folder"] not in _all] + results
        json.dump(merged, open(MASTER_JSON, "w"), indent=1)
        continue

    # 1b. ONE ARTIFACT. Every @maya_command now compiles into the node's own
    # bundle as an MPxCommand, so a compile must leave exactly one loadable
    # plug-in in out_dir and NO sibling <type>_commands.py. Checked here rather
    # than trusted, because a stray companion still LOADS -- the failure would
    # only show up as a duplicate plug-in in Maya's plug-in manager.
    _arts = sorted(f for f in os.listdir(out_dir)
                   if f.endswith((".bundle", ".mll", ".so"))
                   or f.endswith("_commands.py"))
    rec["artifacts"] = _arts
    if _arts != [plugin + ".bundle"]:
        rec["issues"].append("artifacts: expected exactly [%s.bundle], got %s"
                             % (plugin, _arts))
        ML("   ARTIFACTS: WRONG -- %s" % _arts)
    else:
        ML("   ARTIFACTS: ok -- %s" % _arts)

    # 2+3. BUILD each demo against the compiled node, then REOPEN-check each .ma.
    # A template may declare several @maya_demo methods (e.g. DNET: Grid Net /
    # Layout Net / Two Knots). Build EVERY one -- the earlier audit built only
    # the first, silently missing the rest.
    demos = demo_specs_for(mpn) or [(None, label)]
    multi = len(demos) > 1
    _btmo = int(os.environ.get("MPYNODE_BUILD_TIMEOUT", "900"))
    rec["multi_demo"] = multi
    rec["demos"] = []
    ML("   demos (%d): %s" % (len(demos), [d[1] for d in demos]))
    for func_name, dlabel in demos:
        ma_base = folder if not multi else "%s__%s" % (folder, func_name or "demo")
        demo_sel = func_name or "-"
        drec = {"func_name": func_name, "label": dlabel, "ma_basename": ma_base,
                "build": None, "reopen": None, "status": "pending"}

        bj, bok, btail = run_step(
            "build_demo_compiled.py", [mpn, out_dir, plugin, demo_sel, ma_base],
            out_dir, "BUILD_JSON:", timeout=_btmo)
        drec["build"] = bj
        if bj is None:
            drec["status"] = "build_failed"
            rec["issues"].append("[%s] build: no result (%s)"
                                 % (dlabel, btail.replace("\n", " | ")[-260:]))
            ML("   BUILD[%s]: NO RESULT -- %s" % (dlabel, btail.splitlines()[-1:]))
        else:
            ML("   BUILD[%s]: built=%s swapped=%s ma=%s aux=%d errors=%s"
               % (dlabel, bj.get("built"), bj.get("swapped"),
                  os.path.basename(bj.get("ma") or ""),
                  len(bj.get("aux_interpreted") or []), bj.get("errors")))
            for n in (bj.get("notes") or []):
                rec["issues"].append("[%s] note: %s" % (dlabel, n))
            if not bj.get("built"):
                drec["status"] = "build_failed"
                rec["issues"].append("[%s] build failed: %s" % (dlabel, bj.get("errors")))
            elif bj.get("ma"):
                rj, rok, rtail = run_step(
                    "reopen_check.py", [out_dir, bj["ma"]], out_dir,
                    "REOPEN_JSON:", timeout=600)
                drec["reopen"] = rj
                if rj is None:
                    drec["status"] = "reopen_failed"
                    rec["issues"].append("[%s] reopen: no result (%s)"
                                         % (dlabel, rtail.replace("\n", " | ")[-200:]))
                    ML("   REOPEN[%s]: NO RESULT" % dlabel)
                else:
                    ML("   REOPEN[%s]: reopened=%s compiled_nodes=%s verts=%s unknown=%s"
                       % (dlabel, rj.get("reopened"), rj.get("compiled_nodes"),
                          rj.get("mesh_verts"), rj.get("unknown_nodes")))
                    if not (rj.get("reopened") and rj.get("unknown_nodes") == 0
                            and rj.get("compiled_nodes", 0) > 0):
                        rec["issues"].append("[%s] reopen weak: %s" % (dlabel, rj))
                        drec["status"] = "reopen_weak"
        if drec["status"] == "pending":
            drec["status"] = "ok"
        rec["demos"].append(drec)

    # Back-compat: mirror the FIRST demo into rec["build"]/rec["reopen"].
    if rec["demos"]:
        rec["build"] = rec["demos"][0]["build"]
        rec["reopen"] = rec["demos"][0]["reopen"]
    # Overall status = worst across demos (compile already ok at this point).
    dstat = [d["status"] for d in rec["demos"]]
    for sev in ("build_failed", "reopen_failed", "reopen_weak"):
        if sev in dstat:
            rec["status"] = sev
            break
    else:
        # A one-artifact violation is its own failure: the demos can all pass
        # while the compile still shipped a second plug-in beside the bundle.
        rec["status"] = "ok" if rec.get("artifacts") == [plugin + ".bundle"] \
            else "artifacts_bad"
    ML("   STATUS: %s  (demos: %s)"
       % (rec["status"], {d["label"]: d["status"] for d in rec["demos"]}))
    results.append(rec)

    # persist after every template
    _all = {r["folder"]: r for r in results}
    merged = [r for r in _prior.values() if r["folder"] not in _all] + results
    json.dump(merged, open(MASTER_JSON, "w"), indent=1)

dt = time.time() - t_start
ML("=" * 70)
by_status = {}
for r in results:
    by_status[r["status"]] = by_status.get(r["status"], 0) + 1
ML("AUDIT DONE in %d:%02d.  %s" % (dt // 60, dt % 60, by_status))
_ml.close()
print("AUDIT_SUMMARY:" + json.dumps({"seconds": round(dt, 1),
      "by_status": by_status, "n": len(results)}))
