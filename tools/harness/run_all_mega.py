"""Master orchestrator for the MEGA-plugin demo rebuild.

Unlike ``run_all.py`` (which compiles EACH template to its own plugin), this
assumes the ONE mega bundle has already been built by ``mega_plugin.py`` and,
for every template whose node type actually LINKED into that bundle:

  1. build EACH @maya_demo of the template against the mega-compiled node and
     save one .ma per demo (multi-demo templates get one .ma each)
  2. clean-reopen each .ma in a fresh mayapy to prove the mega plugin loads it

Templates whose type did NOT link (best-effort drops from the mega build) are
recorded with the drop reason and skipped -- not silently omitted.

Writes per-template artifacts under _audit/<folder>/ plus
mega_master_results.json + mega_master.log at the audit root.

Usage (plain python3):
    python3 run_all_mega.py [folder1 folder2 ...]
"""
import os
import sys
import ast
import json
import time
import subprocess

HARNESS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HARNESS))            # project root
# Audit scratch, NOT templates/ -- `out_dir` below is AUDIT_ROOT/<folder> with a
# FLAT folder name, which would litter the template tree with fake families.
AUDIT_ROOT = os.path.join(ROOT, "_audit")                   # audit output root
MAYAPY = os.environ.get(
    "MPYNODE_MAYAPY",
    "/Applications/Autodesk/maya2026/Maya.app/Contents/bin/mayapy")

# The mega tree is real committed source and lives with the templates; it is not
# audit output, so it does NOT hang off AUDIT_ROOT.
MEGA_DIR = os.environ.get("MPYNODE_MEGA_DIR",
                          os.path.join(ROOT, "templates",
                                       "All Templates Plugin"))

# Demo discovery. NOT imported from run_all.py: that module has no __main__
# guard, so importing it would run a whole per-template audit as a side effect.
sys.path.insert(0, HARNESS)
from demo_specs import demo_specs_for, load_templates  # noqa: E402


def _mega_info():
    """(bundle_path, {source_node: compiled_type}, {source_node: drop_reason}).

    Keyed by the TEMPLATE's node name (manifest ``source_node``), which is what
    templates.json carries -- NOT by the compiled ``type_name``. Those differ
    whenever a template stamps a Class: DNET's node is named ``dnet`` but its
    compiled type is ``mPyDnet``. Assuming they matched silently skipped DNET.
    """
    res_path = os.path.join(MEGA_DIR, "build", "mega_results.json")
    man_path = os.path.join(MEGA_DIR, "build", "manifest.json")
    if not os.path.isfile(res_path):
        raise SystemExit("no mega_results.json at %s -- run mega_plugin.py first"
                         % res_path)
    d = json.load(open(res_path))
    bundle = d.get("bundle_path")
    if bundle and not os.path.isabs(bundle):
        # mega_plugin writes bundle_path relative to the PROJECT ROOT
        # ("templates/All Templates Plugin/mPyMega.bundle"), not to MEGA_DIR --
        # joining it onto MEGA_DIR doubled the path and failed every build with
        # "mega bundle not found: .../All Templates Plugin/templates/All
        # Templates Plugin/...".
        bundle = os.path.join(ROOT, bundle)
    if bundle and not os.path.isfile(bundle):
        raise SystemExit("mega bundle not found: %s" % bundle)

    linked, dropped = {}, {}
    rows = []
    if os.path.isfile(man_path):
        rows = (json.load(open(man_path)).get("nodes") or [])
    for r in rows:
        src = r.get("source_node") or r.get("type_name")
        if r.get("build_status") == "compiled":
            linked[src] = r.get("type_name")
        else:
            dropped[src] = r.get("build_reason") or ""
    if not rows:      # manifest absent -- fall back to the results summary
        linked = {t: t for t in (d.get("linked") or [])}
        dropped = {x.get("type_name"): (x.get("reason") or "")
                   for x in (d.get("dropped") or [])}
    return bundle, linked, dropped


BUNDLE, LINKED, DROPPED = _mega_info()

TEMPLATES = load_templates(HARNESS, ROOT)

FILTER = set(sys.argv[1:])
if FILTER:
    TEMPLATES = [t for t in TEMPLATES if t["folder"] in FILTER]

MASTER_LOG = os.path.join(AUDIT_ROOT, "mega_master.log")
MASTER_JSON = os.path.join(AUDIT_ROOT, "mega_master_results.json")
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
    # T38: headless can't prompt, so an untrusted scene stops exec'ing Init AND
    # Compute. reopen_check_mega.py opens a saved .ma. Mirrors run_all.py.
    e["MPYNODE_TRUST_PICKLE"] = "1"
    # numpy/scipy/PIL may live outside Maya; point MPYNODE_EXTRA_PYTHONPATH at
    # that site-packages dir if so.
    ext = os.environ.get("MPYNODE_EXTRA_PYTHONPATH", "")
    e["PYTHONPATH"] = ":".join(
        p for p in [ext, os.path.join(ROOT, "scripts"),
                    e.get("PYTHONPATH", "")] if p)
    e["MAYA_PLUG_IN_PATH"] = ":".join(
        [os.path.join(ROOT, "plug-ins"), MEGA_DIR, out_dir,
         e.get("MAYA_PLUG_IN_PATH", "")])
    e["QT_QPA_PLATFORM"] = "offscreen"
    return e


def run_step(script, args, out_dir, prefix, timeout):
    cmd = [MAYAPY, os.path.join(HARNESS, script)] + args
    try:
        p = subprocess.run(cmd, cwd=ROOT, env=base_env(out_dir),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
        out = p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
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
    return data, (p.returncode == 0), "\n".join(out.splitlines()[-25:])


results = []
t_start = time.time()
ML("=" * 70)
ML("MEGA DEMO REBUILD: %d template(s)" % len(TEMPLATES))
ML("mega bundle : %s" % BUNDLE)
ML("linked types: %d   dropped: %d" % (len(LINKED), len(DROPPED)))

for idx, t in enumerate(TEMPLATES, 1):
    folder = t["folder"]
    out_dir = os.path.join(AUDIT_ROOT, folder)
    mpn = os.path.join(ROOT, t["mpn"])
    label = t["demo_label"]
    src = t.get("node_name") or t.get("source_name")
    ctype = LINKED.get(src)
    rec = {"folder": folder, "mpn": t["mpn"], "native_type": t["native_type"],
           "source_name": src, "demo_label": label, "compiled_type": ctype,
           "status": "pending", "demos": [], "issues": []}

    ML("-" * 70)
    ML("[%d/%d] %s  (%s / %s -> %s)" % (idx, len(TEMPLATES), folder,
                                        t["native_type"], src, ctype))

    if not ctype:
        reason = DROPPED.get(src, "type not present in the mega bundle")
        rec["status"] = "not_linked"
        rec["issues"].append("mega drop: %s" % reason)
        ML("   SKIP: not linked into the mega bundle -- %s" % reason[:120])
        results.append(rec)
        json.dump(results, open(MASTER_JSON, "w"), indent=1)
        continue

    os.makedirs(out_dir, exist_ok=True)
    demos = demo_specs_for(mpn) or [(None, label)]
    multi = len(demos) > 1
    rec["multi_demo"] = multi
    _btmo = int(os.environ.get("MPYNODE_BUILD_TIMEOUT", "900"))
    ML("   demos (%d): %s" % (len(demos), [d[1] for d in demos]))

    for func_name, dlabel in demos:
        ma_base = folder if not multi else "%s__%s" % (folder,
                                                       func_name or "demo")
        drec = {"func_name": func_name, "label": dlabel,
                "ma_basename": ma_base, "build": None, "reopen": None,
                "status": "pending"}

        bj, bok, btail = run_step(
            "build_demo_mega.py",
            [mpn, out_dir, BUNDLE, ctype, func_name or "-", ma_base],
            out_dir, "BUILD_JSON:", timeout=_btmo)
        drec["build"] = bj
        if bj is None:
            drec["status"] = "build_failed"
            rec["issues"].append("[%s] build: no result (%s)"
                                 % (dlabel, btail.replace("\n", " | ")[-260:]))
            ML("   BUILD[%s]: NO RESULT" % dlabel)
        else:
            ML("   BUILD[%s]: built=%s swapped=%s ma=%s aux=%d errors=%s"
               % (dlabel, bj.get("built"), bj.get("swapped"),
                  os.path.basename(bj.get("ma") or ""),
                  len(bj.get("aux_interpreted") or []), bj.get("errors")))
            for n in (bj.get("notes") or []):
                rec["issues"].append("[%s] note: %s" % (dlabel, n))
            if not bj.get("built"):
                drec["status"] = "build_failed"
                rec["issues"].append("[%s] build failed: %s"
                                     % (dlabel, bj.get("errors")))
            elif bj.get("ma"):
                rj, rok, rtail = run_step(
                    "reopen_check_mega.py", [bj["ma"], ctype], out_dir,
                    "REOPEN_JSON:", timeout=600)
                drec["reopen"] = rj
                if rj is None:
                    drec["status"] = "reopen_failed"
                    rec["issues"].append("[%s] reopen: no result" % dlabel)
                    ML("   REOPEN[%s]: NO RESULT" % dlabel)
                else:
                    ML("   REOPEN[%s]: reopened=%s compiled_nodes=%s verts=%s "
                       "unknown=%s" % (dlabel, rj.get("reopened"),
                                       rj.get("compiled_nodes"),
                                       rj.get("mesh_verts"),
                                       rj.get("unknown_nodes")))
                    if not (rj.get("reopened") and rj.get("unknown_nodes") == 0
                            and rj.get("compiled_nodes", 0) > 0):
                        rec["issues"].append("[%s] reopen weak: %s"
                                             % (dlabel, rj))
                        drec["status"] = "reopen_weak"
        if drec["status"] == "pending":
            drec["status"] = "ok"
        rec["demos"].append(drec)

    dstat = [d["status"] for d in rec["demos"]]
    for sev in ("build_failed", "reopen_failed", "reopen_weak"):
        if sev in dstat:
            rec["status"] = sev
            break
    else:
        rec["status"] = "ok"
    ML("   STATUS: %s" % rec["status"])
    results.append(rec)
    json.dump(results, open(MASTER_JSON, "w"), indent=1)

dt = time.time() - t_start
ML("=" * 70)
by_status = {}
for r in results:
    by_status[r["status"]] = by_status.get(r["status"], 0) + 1
ML("MEGA REBUILD DONE in %d:%02d.  %s" % (dt // 60, dt % 60, by_status))
_ml.close()
print("MEGA_SUMMARY:" + json.dumps({"seconds": round(dt, 1),
                                    "by_status": by_status,
                                    "n": len(results)}))
