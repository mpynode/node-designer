"""Does a manual `type_id` pin actually reach the compiled binary?

Unit tests cover ``reg.pin`` and the metadata field in isolation. This proves the
whole chain a user exercises from the Node Info dialog:

    metadata.type_id  ->  spec  ->  compile_controller applies the pin
                      ->  bundler rewrites MTypeId  ->  the shipped .cpp

...by compiling ONE deterministic template twice -- unpinned, then pinned -- and
reading the ``MTypeId`` literal out of the generated source both times.

Also checks the three things that would make the feature a trap:
  * an UNUSABLE pin must fall back to the derived id, not fail the build;
  * the pin must NOT change the port-cache key (the id never survives to the
    binary via the cache, so pinning must not force a re-port);
  * a pin must be recorded in the manifest as ``type_id_source: pinned``.

Run with the standard mayapy env:
    mayapy tools/probe_pinned_typeid_end_to_end.py
"""
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL  = os.path.join(ROOT, "templates")
# A deterministically-lowered template: no LLM call, so this probe is cheap and
# never depends on a provider being reachable.
MPN = os.path.join(TPL, "MPyNode", "Bubble Sort", "template.mpn")

PIN = "0x0002dead"


def L(m=""):
    print(m, flush=True)


def _ids_in(cpp_dir):
    """Every ``MTypeId X::id(0x...)`` literal in the generated source."""
    out = {}
    for dirpath, _d, files in os.walk(cpp_dir):
        for fn in files:
            if not fn.endswith(".cpp"):
                continue
            with open(os.path.join(dirpath, fn)) as fh:
                for cls, hx in re.findall(
                        r"MTypeId\s+(\w+)::id\((0x[0-9a-fA-F]+)\)", fh.read()):
                    out[cls] = hx.lower()
    return out


def _compile(spec, out_dir, plugin):
    from mpynode.native.toolchain import compile_controller as cc
    return cc.compile_plugin([spec], plugin_name=plugin, out_dir=out_dir,
                             strict=False, verify=False)


def main():
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as mc
    for p in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(p, q=True, loaded=True):
            mc.loadPlugin(p)

    from mpynode._common.io import mpn_io
    from mpynode._common.lifecycle import metadata_registry as md
    from mpynode.native.spec.mpn_spec_adapter import spec_from_mpn_payload
    from mpynode.native.toolchain import port_cache, typeid_registry as tr

    scratch = tempfile.mkdtemp(prefix="pin-e2e-")
    ok      = True
    L("=" * 78)
    L("PINNED MTypeId -- end to end")
    L("=" * 78)

    payload   = mpn_io.load_mpn(MPN, trusted=True)
    base_spec = spec_from_mpn_payload(payload)
    type_name = (base_spec.get("suggested") or {}).get("node_type_name")
    derived   = "0x%08x" % tr.deterministic_id(type_name)
    L("  template   %s" % os.path.relpath(MPN, ROOT))
    L("  type name  %s" % type_name)
    L("  derived id %s" % derived)
    L("  pin to     %s" % PIN)
    L("")

    # ---- 1. unpinned -------------------------------------------------------
    out_a = os.path.join(scratch, "unpinned")
    res_a = _compile(json.loads(json.dumps(base_spec)), out_a, "pinProbeA")
    ids_a = _ids_in(out_a)
    L("  [unpinned] bundle ok=%s ids=%s" % (bool(res_a.get("ok")), ids_a))
    if derived not in ids_a.values():
        L("  FAIL: unpinned build did not use the derived id %s" % derived)
        ok = False
    else:
        L("  PASS: unpinned build baked the DERIVED id")

    # ---- 2. pinned ---------------------------------------------------------
    pinned_spec = json.loads(json.dumps(base_spec))
    pinned_spec["metadata"] = md.coerce(
        dict(pinned_spec.get("metadata") or {}, type_id=PIN))
    out_b = os.path.join(scratch, "pinned")
    res_b = _compile(pinned_spec, out_b, "pinProbeB")
    ids_b = _ids_in(out_b)
    L("  [pinned]   bundle ok=%s ids=%s" % (bool(res_b.get("ok")), ids_b))
    if PIN not in ids_b.values():
        L("  FAIL: the pin %s did NOT reach the generated source" % PIN)
        ok = False
    else:
        L("  PASS: the pin reached the shipped C++")

    rows_b = res_b.get("nodes") or res_b.get("rows") or []
    srcs   = [r.get("type_id_source") for r in rows_b]
    L("  [pinned]   manifest type_id_source=%s" % srcs)
    if "pinned" not in srcs:
        L("  FAIL: manifest did not record the id as 'pinned'")
        ok = False
    else:
        L("  PASS: manifest records type_id_source=pinned")

    # ---- 3. an unusable pin must NOT fail the build ------------------------
    bad_spec = json.loads(json.dumps(base_spec))
    bad_spec["metadata"] = md.coerce(
        dict(bad_spec.get("metadata") or {}, type_id="0x99999999"))
    out_c = os.path.join(scratch, "badpin")
    res_c = _compile(bad_spec, out_c, "pinProbeC")
    ids_c = _ids_in(out_c)
    L("  [bad pin]  bundle ok=%s ids=%s" % (bool(res_c.get("ok")), ids_c))
    if not res_c.get("ok"):
        L("  FAIL: an unusable pin FAILED the build (it must be ignored)")
        ok = False
    elif derived not in ids_c.values():
        L("  FAIL: an unusable pin did not fall back to the derived id")
        ok = False
    else:
        L("  PASS: an unusable pin is ignored; the derived id is used")

    # ---- 4. pinning must not move the port-cache key -----------------------
    k_plain  = port_cache.cache_key(base_spec, provider="p", model="m")
    k_pinned = port_cache.cache_key(pinned_spec, provider="p", model="m")
    L("")
    L("  cache key unpinned %s" % k_plain[:24])
    L("  cache key pinned   %s" % k_pinned[:24])
    if k_plain != k_pinned:
        L("  FAIL: pinning moved the port-cache key -- it would force a re-port")
        ok = False
    else:
        L("  PASS: pinning does NOT move the port-cache key")

    shutil.rmtree(scratch, ignore_errors=True)
    L("")
    L("VERDICT: %s" % ("ALL PASS" if ok else "FAILURES ABOVE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
