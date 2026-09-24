"""Every shipped compiled artifact embeds only its commands and what they use.

A compiled node's @maya_command bodies run as Python embedded in its C++ (the
``kPayloadB64`` array). ``command_dispatch.command_payload_source`` trims that
copy to the command closure -- demos and tests run on the interpreted node,
never in the bundle -- and the bundle's prelude carries no test kit. This
decodes every payload in both trees (each template's stages, final and source,
and the All Templates Plugin) and checks, with Maya stubbed out:

  * the embedded Methods text is already trimmed: trimming it again changes
    nothing, so no demo, test or demo-only helper is in it;
  * no test-kit name (maya_demo, maya_test, the assert helpers) is defined;
  * every command the module can dispatch binds in the bundle's namespace.

A decorator scan would not do: three templates' demo is an undecorated
``def demo``. Refresh the artifacts with ``tools/swap_command_payload.py``.
"""

from __future__ import annotations

import ast
import base64
import glob
import os
import re
import sys
import types
import unittest

from tests import _paths

_TEMPLATES = os.path.join(_paths.ROOT, "templates")
_ARRAY     = re.compile(r"static const char kPayloadB64\[\] = \{\n(.*?)\n\s*0\n\};", re.S)

# 162 payload files across 19 types when this landed. Below this the scan has
# gone vacuous (a moved tree, a renamed array), not green.
_FLOOR = 150


def _payloads():
    """``[(repo-relative path, decoded dispatch module)]``."""
    out = []
    for path in sorted(glob.glob(os.path.join(_TEMPLATES, "**", "build", "**", "*.cpp"),
                                 recursive=True)):
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for m in _ARRAY.finditer(text):
            b64 = "".join(re.findall(r"'([A-Za-z0-9+/=])'", m.group(1)))
            out.append((os.path.relpath(path, _paths.ROOT),
                        base64.b64decode(b64).decode("utf-8")))
    return out


def _exec_module(src):
    maya      = types.ModuleType("maya")
    maya.cmds = types.ModuleType("maya.cmds")
    saved     = {k: sys.modules.get(k) for k in ("maya", "maya.cmds")}
    sys.modules.update({"maya": maya, "maya.cmds": maya.cmds})
    try:
        ns = {"__name__": "mpynode_cmd_scan"}
        exec(compile(src, "<bundle>", "exec", dont_inherit=True), ns)
        return ns
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


class TestShippedPayloadsAreCommandsOnly(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.payloads = _payloads()

    def test_the_payloads_are_on_disk(self):
        self.assertGreaterEqual(len(self.payloads), _FLOOR,
                                "only %d payload(s) found -- the scan has gone "
                                "vacuous" % len(self.payloads))

    def test_the_embedded_methods_are_already_trimmed(self):
        from mpynode.native.compiler.kernels import command_dispatch as cd

        extra = []
        for rel, mod in self.payloads:
            ns = _exec_module(mod)
            if cd.command_payload_source(ns["_METHODS_SRC"]) != ns["_METHODS_SRC"]:
                extra.append(rel)
        self.assertEqual(extra, [],
                         "these artifacts embed Methods code no command uses "
                         "(demos, tests, their helpers). Refresh them with "
                         "tools/swap_command_payload.py:\n  " + "\n  ".join(extra))

    def test_no_test_kit_ships(self):
        from mpynode.native.compiler.kernels import command_dispatch as cd

        kit, found = cd._test_kit_names(), []
        for rel, mod in self.payloads:
            tree  = ast.parse(mod)
            names = {n.name for n in tree.body if hasattr(n, "name")}
            names |= {t.id for n in tree.body if isinstance(n, ast.Assign)
                      for t in n.targets if isinstance(t, ast.Name)}
            if names & kit:
                found.append("%s: %s" % (rel, ", ".join(sorted(names & kit))))
        self.assertEqual(found, [], "\n  ".join(found))

    def test_every_command_binds(self):
        unbound = []
        for rel, mod in self.payloads:
            ns     = _exec_module(mod)
            bundle = ns["build_methods_namespace"](ns["_METHODS_SRC"])
            for func in sorted(set(ns["_FUNCS"].values())):
                if not callable(bundle.get(func)):
                    unbound.append("%s: %s" % (rel, func))
        self.assertEqual(unbound, [], "\n  ".join(unbound))


if __name__ == "__main__":
    unittest.main()
