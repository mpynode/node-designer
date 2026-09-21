"""Gemini CLI: listing models WITHOUT an API key.

The assistant panel used to send every CLI provider except ``claude_cli`` down
the API-key path, so switching to "Gemini CLI (experimental)" and pressing
Refresh answered *"To list Gemini CLI (experimental) model versions, set the
Gemini (Google API) API key under that provider"* -- for a provider that signs
in with the machine's own Google login, has no key field in its UI, and talks to
a different backend than the HTTP API anyway.

The CLI has no ``models list`` command either (``-m`` takes a free string and the
binary validates it), so the roster is read where it actually lives: the model
table compiled into the bundle the CLI ships. These tests pin that reading --
structural, never a blind sweep for anything id-shaped, because the same bundle
carries test fixtures and truncated prefixes the CLI would reject.
"""
from __future__ import annotations

import io
import os
import shutil
import tempfile
import unittest

from mpynode.ui.llm import config as cfg
from mpynode.ui.llm import gemini_cli_client as gcli
from tests import _paths, _setup


def setUpModule():
    _setup.standalone_init()


#: Shaped like the real bundle's packages/core/src/config/models.ts region.
_BUNDLE_JS = (
    'var PREVIEW_GEMINI_MODEL = "gemini-3-pro-preview";\n'
    'var DEFAULT_GEMINI_MODEL = "gemini-2.5-pro";\n'
    'var DEFAULT_GEMINI_FLASH_MODEL = "gemini-2.5-flash";\n'
    'var PREVIEW_GEMINI_FLASH_LITE_MODEL = "none";\n'
    'var GEMMA_4_31B_IT_MODEL = "gemma-4-31b-it";\n'
    'var DEFAULT_GEMINI_EMBEDDING_MODEL = "gemini-embedding-001";\n'
    'var GEMINI_MODEL_ALIAS_AUTO = "auto";\n'
    'var GEMINI_MODEL_ALIAS_PRO = "pro";\n'
    'var GEMINI_MODEL_ALIAS_FLASH = "flash";\n'
    'var VALID_GEMINI_MODELS = /* @__PURE__ */ new Set([\n'
    '  PREVIEW_GEMINI_MODEL,\n'
    '  DEFAULT_GEMINI_MODEL,\n'
    '  DEFAULT_GEMINI_FLASH_MODEL,\n'
    '  PREVIEW_GEMINI_FLASH_LITE_MODEL,\n'
    '  "gemini-3.1-flash-lite",\n'
    '  GEMMA_4_31B_IT_MODEL\n'
    ']);\n'
    'it("resolves", () => expect(resolve("gemini-9001-super-duper")).toBe(0));\n'
)


class TestGeminiCliModelTable(unittest.TestCase):
    """The table is READ from the installed CLI -- never baked in here."""

    def test_membership_table_resolves_its_constants(self):
        ids = gcli.parse_model_table(_BUNDLE_JS)
        self.assertIn("gemini-3-pro-preview", ids)
        self.assertIn("gemini-2.5-pro",       ids)
        self.assertIn("gemini-2.5-flash",     ids)

    def test_literal_entries_are_kept_too(self):
        self.assertIn("gemini-3.1-flash-lite", gcli.parse_model_table(_BUNDLE_JS))

    def test_sentinels_and_embeddings_are_dropped(self):
        # "none" is what the CLI stores for "no preview flash-lite", and an
        # embedding model cannot answer a prompt -- neither belongs in the
        # model dropdown.
        ids = gcli.parse_model_table(_BUNDLE_JS)
        self.assertNotIn("none", ids)
        self.assertNotIn("gemini-embedding-001", ids)

    def test_ids_outside_the_table_are_not_offered(self):
        # The bundle also carries test fixtures. A blind sweep for anything
        # id-shaped would put them in the dropdown, where the CLI rejects them.
        self.assertNotIn("gemini-9001-super-duper",
                         gcli.parse_model_table(_BUNDLE_JS))

    def test_constants_carry_it_when_there_is_no_table(self):
        # A future bundle may rename or drop the Set; the constants alone are
        # still the CLI's own names, so the dropdown degrades instead of
        # emptying.
        js  = _BUNDLE_JS.split("var VALID_GEMINI_MODELS")[0]
        ids = gcli.parse_model_table(js)
        self.assertIn("gemini-2.5-pro", ids)
        self.assertNotIn("none", ids)

    def test_nothing_recognisable_yields_nothing(self):
        # Better an empty dropdown plus the panel's "type a model id" guidance
        # than invented ids.
        self.assertEqual(gcli.parse_model_table("var x = 1;"), [])

    def test_no_hardcoded_roster_in_the_module(self):
        # Same rule the Claude CLI list follows: a baked-in roster goes stale
        # the day a family ships.
        src = io.open(os.path.join(_paths.ROOT, "scripts", "mpynode", "ui",
                                   "llm", "gemini_cli_client.py"),
                      encoding="utf-8").read()
        self.assertNotIn('"gemini-2.5-pro"', src)
        self.assertNotIn('"gemini-3-pro-preview"', src)


class TestGeminiCliAliases(unittest.TestCase):
    """`auto` is offered, unlike the Claude CLI's floating aliases.

    Gemini CLI has no effort/thinking control of its own; `auto` IS the knob --
    it picks the model per task, including the thinking-capable one -- and no
    pinned id expresses that, so suppressing it would hide the CLI's headline
    behaviour behind a typed string.
    """

    def test_aliases_are_read_from_the_bundle(self):
        self.assertEqual(gcli.parse_model_aliases(_BUNDLE_JS),
                         ["auto", "pro", "flash"])

    def test_aliases_lead_the_list(self):
        ids = gcli.list_models(self._shim())
        self.assertEqual(ids[:3], ["auto", "pro", "flash"])
        self.assertIn("gemini-2.5-pro", ids)

    def test_no_alias_is_repeated_as_an_id(self):
        ids = gcli.list_models(self._shim())
        self.assertEqual(len(ids), len(set(ids)))

    def _shim(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        bundle = os.path.join(tmp, "node_modules", "@google", "gemini-cli",
                              "bundle")
        os.makedirs(bundle)
        io.open(os.path.join(bundle, "chunk.js"), "w",
                encoding="utf-8").write(_BUNDLE_JS)
        path = os.path.join(tmp, "gemini.cmd")
        io.open(path, "w", encoding="utf-8").write("nonsense\n")
        return path


class TestGeminiCliModelOrder(unittest.TestCase):
    """Newest first, pro before flash -- and the same order after a prefs
    restore, which hands the list back in whatever order it was saved."""

    def test_newest_first_pro_before_flash_gemma_last(self):
        got = gcli.order_models([
            "gemma-4-31b-it", "gemini-2.5-flash", "gemini-3-pro-preview",
            "gemini-3.1-flash-lite", "gemini-2.5-pro", "gemini-3.5-flash",
        ])
        self.assertEqual(got, [
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
            "gemini-3-pro-preview",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemma-4-31b-it",
        ])

    def test_two_digit_minor_sorts_above_single_digit(self):
        # Plain string order puts "3.10" before "3.2" and would bury the newest
        # build the day a two-digit minor ships.
        self.assertEqual(gcli.order_models(["gemini-3.2-pro", "gemini-3.10-pro"])[0],
                         "gemini-3.10-pro")

    def test_order_dedupes(self):
        self.assertEqual(gcli.order_models(["gemini-2.5-pro", "gemini-2.5-pro"]),
                         ["gemini-2.5-pro"])


class TestGeminiCliBundleDiscovery(unittest.TestCase):
    """npm installs a SHIM, so the bundle is never beside the launcher."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bundle = os.path.join(self.tmp, "node_modules", "@google",
                                   "gemini-cli", "bundle")
        os.makedirs(self.bundle)
        self.big = os.path.join(self.bundle, "chunk-BIG.js")
        io.open(self.big, "w", encoding="utf-8").write(_BUNDLE_JS + " " * 4096)
        io.open(os.path.join(self.bundle, "gemini.js"), "w",
                encoding="utf-8").write("// entry\n")

    def _shim(self, text):
        path = os.path.join(self.tmp, "gemini.cmd")
        io.open(path, "w", encoding="utf-8").write(text)
        return path

    def test_windows_shim_text_names_the_bundle(self):
        shim = self._shim('@ECHO off\r\n"%_prog%" "%dp0%\\node_modules\\@google'
                          '\\gemini-cli\\bundle\\gemini.js" %*\r\n')
        roots = [os.path.normpath(r) for r in gcli._package_roots(shim)]
        self.assertIn(os.path.normpath(self.bundle), roots)

    def test_standard_npm_layout_is_found_without_a_readable_shim(self):
        shim  = self._shim("binary nonsense with no path in it\n")
        roots = [os.path.normpath(r) for r in gcli._package_roots(shim)]
        self.assertIn(os.path.normpath(os.path.dirname(self.bundle)), roots)

    def test_biggest_file_is_scanned_first(self):
        # The table lives in the big bundled chunk; scanning it first usually
        # means reading exactly one file.
        self.assertEqual(gcli.bundle_files(self._shim("nonsense\n"))[0], self.big)

    def test_list_models_reads_the_installed_bundle(self):
        ids = gcli.list_models(self._shim("nonsense\n"))
        # Aliases lead (see TestGeminiCliAliases); the pinned ids follow in
        # newest-first order.
        pinned = [m for m in ids if m.startswith(("gemini-", "gemma-"))]
        self.assertEqual(pinned[0], "gemini-3.1-flash-lite")
        self.assertIn("gemini-2.5-pro", ids)

    def test_a_missing_cli_lists_nothing_rather_than_guessing(self):
        self.assertEqual(gcli.list_models(os.path.join(self.tmp, "nope")), [])


class TestPromptTravelsOnStdin(unittest.TestCase):
    """A node payload must never ride in argv.

    The prompt carries the node cheat-sheet plus the active node, which runs to
    tens of KB. npm's Windows launcher is a ``.cmd``, so the call goes through
    cmd.exe, whose command line caps at ~8 KB: the first real request died with
    ``gemini exited 1: The command line is too long.`` before the model ever saw
    it. The CLI documents ``-p`` as "Appended to input on stdin (if any)", so
    the payload goes to stdin and argv keeps only a short tail.
    """

    _BIG = "a line of cheat-sheet\n" * 2000          # ~42 KB, as a real one is

    def test_argv_carries_only_the_tail(self):
        cmd = gcli.build_cmd("gemini", model="gemini-x")
        self.assertIn(gcli.PROMPT_TAIL, cmd)
        self.assertNotIn(self._BIG, cmd)
        self.assertLess(sum(len(a) + 1 for a in cmd), 2048)

    def test_a_huge_prompt_does_not_reach_argv(self):
        # The client's own builder, driven with a stand-in for the Qt signal it
        # uses to warn about images -- no widget needed.
        class _Fake:
            notice = type("_S", (), {"emit": lambda *_: None})()

        cmd = gcli.GeminiCliClient._build_cmd(_Fake(), self._BIG, [])
        self.assertNotIn(self._BIG, cmd)
        self.assertLess(sum(len(a) + 1 for a in cmd), 2048,
                        "argv must stay far below cmd.exe's ~8 KB limit")

    def test_the_payload_is_what_goes_to_stdin(self):
        # Unbound: the method uses no instance state, and instantiating the
        # client would need Qt.
        out = gcli.GeminiCliClient._stdin_payload(None, self._BIG, [])
        self.assertTrue(out.startswith("a line of cheat-sheet"))
        self.assertEqual(len(out), len(self._BIG) + 1)   # one trailing newline

    def test_the_run_is_trusted_and_sandboxed(self):
        """Gemini CLI refuses to start in an untrusted folder.

        Maya's working directory has never been trusted interactively, so a
        headless run exits 55 ("not running in a trusted directory"). The CLI
        names ``--skip-trust`` as the automated-environment answer -- and since
        that grants the workspace trust, the workspace is a scratch directory
        rather than whatever the user's Maya was launched from.
        """
        self.assertIn("--skip-trust", gcli.build_cmd("gemini"))

        class _Shim:
            _workdir = None

        shim = _Shim()
        got  = gcli.GeminiCliClient._cwd(shim)
        self.addCleanup(shutil.rmtree, got, True)
        self.assertTrue(os.path.isdir(got))
        self.assertNotEqual(os.path.normcase(got), os.path.normcase(os.getcwd()))
        self.assertEqual(gcli.GeminiCliClient._cwd(shim), got)  # stable per run

    def test_the_tail_is_never_empty(self):
        # `-p ""` is falsy to the CLI's arg parser, which drops it back into
        # interactive mode -- and with no TTY that just hangs.
        self.assertTrue(gcli.PROMPT_TAIL.strip())


class TestCliListingNeverAsksForAnApiKey(unittest.TestCase):

    def test_the_panel_lists_every_self_listing_cli(self):
        # The panel's table and the config tuple must agree: a CLI in one and
        # not the other is exactly how the Gemini CLI ended up on the key path.
        from mpynode.ui.widgets import assistant_panel as ap

        self.assertEqual(sorted(ap._CLI_MODEL_FETCHERS),
                         sorted(cfg.SELF_LISTING_CLI_PROVIDERS))
        for provider, meth in ap._CLI_MODEL_FETCHERS.items():
            self.assertTrue(callable(getattr(ap.NDAssistantPanel, meth, None)),
                            "%s -> %s is not a panel method" % (provider, meth))

    def test_a_self_listing_cli_keeps_its_fetch_across_restarts(self):
        saved = cfg.get_cached_models("gemini_cli")
        self.addCleanup(cfg.set_cached_models, "gemini_cli", saved)
        cfg.set_cached_models("gemini_cli", ["gemini-3-pro-preview"])
        self.assertEqual(cfg.cli_model_candidates("gemini_cli"),
                         ["gemini-3-pro-preview"])

    def test_every_self_listing_cli_is_a_cli_provider(self):
        for provider in cfg.SELF_LISTING_CLI_PROVIDERS:
            self.assertIn(provider, cfg.CLI_PROVIDERS)


if __name__ == "__main__":
    unittest.main()
