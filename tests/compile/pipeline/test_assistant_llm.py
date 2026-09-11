"""Assistant/LLM: config (models, effort), panel layout, CLI deny list, node-targeting, methods tool

Consolidated from: test_assistant_cli_models.py, test_cli_effort_values.py, test_assistant_model_order.py, test_assistant_multiagent.py, test_assistant_node_targeting.py, test_assistant_methods_tool.py.
"""

from __future__ import annotations

# ===================== from test_assistant_cli_models.py =====================
import unittest

from mpynode.ui.llm import config as cfg


class TestClaudeCliModelCandidates(unittest.TestCase):
    """candidates() serves the last SUCCESSFUL fetch -- no hardcoded roster."""

    def setUp(self):
        self._saved = cfg.get_cached_models("claude_cli")
        self.addCleanup(cfg.set_cached_models, "claude_cli", self._saved)

    def test_empty_when_never_fetched(self):
        # A machine with no prior fetch shows an EMPTY dropdown plus panel
        # guidance -- deliberately not a stale baked-in list.
        cfg.set_cached_models("claude_cli", [])
        self.assertEqual(cfg.cli_model_candidates("claude_cli"), [])

    def test_serves_the_cached_fetch(self):
        cfg.set_cached_models("claude_cli", ["opus", "claude-opus-5"])
        self.assertEqual(cfg.cli_model_candidates("claude_cli"),
                         ["opus", "claude-opus-5"])

    def test_cache_round_trips_through_prefs(self):
        fetched = ["opus", "opus[1m]", "claude-opus-5", "claude-sonnet-4-6"]
        cfg.set_cached_models("claude_cli", fetched)
        self.assertEqual(cfg.get_cached_models("claude_cli"), fetched)

    def test_only_claude_cli_is_served(self):
        # gemini_cli / codex_cli still fetch via their own key path; API
        # providers use their list endpoints.
        self.assertEqual(cfg.cli_model_candidates("gemini_cli"), [])
        self.assertEqual(cfg.cli_model_candidates("codex_cli"), [])
        self.assertEqual(cfg.cli_model_candidates("anthropic"), [])
        self.assertEqual(cfg.cli_model_candidates("gemini"), [])

    def test_returns_independent_copies(self):
        # The panel mutates the returned list when populating the combo; it must
        # not alias whatever the cache holds.
        cfg.set_cached_models("claude_cli", ["claude-opus-5"])
        a = cfg.cli_model_candidates("claude_cli")
        a.append("__sentinel__")
        b = cfg.cli_model_candidates("claude_cli")
        self.assertNotIn("__sentinel__", b)

    def test_no_hardcoded_roster_remains(self):
        # The old CLAUDE_CLI_MODELS constant stranded users on 4.8 after Opus 5
        # shipped. It must not come back.
        self.assertFalse(hasattr(cfg, "CLAUDE_CLI_MODELS"))

    def test_no_api_derived_model_ids(self):
        # The CLI and the Anthropic HTTP API are DIFFERENT BACKENDS: the API
        # lists ids this CLI rejects (claude-opus-4-1-20250805, verified), so
        # the list must come from the CLI.
        self.assertFalse(hasattr(cfg, "cli_models_from_api"))
        self.assertFalse(hasattr(cfg, "ONE_M_CONTEXT"))


# A verbatim `claude -p /model` reply, launcher banners and all. The banners are
# the reason the parser must scan lines rather than trust the whole payload.
_CLI_MODEL_REPLY = (
    "Claude Code\n"
    "Using AI Gateway (Vertex upstream)\n"
    "Current model: Opus 5 (1M context) (effort: xhigh)\n"
    "Usage: /model <name>. Available: sonnet, opus, haiku, fable, best, "
    "sonnet[1m], opus[1m], fable[1m], opusplan, default, or a full model ID.\n"
)


class TestClaudeCliModelListing(unittest.TestCase):
    """The Claude CLI list is read FROM THE CLI -- no API key, ever.

    A CLI provider authenticates through the machine's own `claude` login, so
    demanding an Anthropic key to populate the dropdown was wrong. It was also
    incorrect: the HTTP list describes a different backend, and a gateway build
    rejects ids /v1/models returns (claude-opus-4-1-20250805 verified rejected).
    """

    def _parse(self, text):
        from mpynode.ui.llm.claude_cli_client import parse_model_listing

        return parse_model_listing(text)

    def test_parses_real_reply(self):
        names, _ = self._parse(_CLI_MODEL_REPLY)
        self.assertEqual(names, ["sonnet", "opus", "haiku", "fable", "best",
                                 "sonnet[1m]", "opus[1m]", "fable[1m]",
                                 "opusplan", "default"])

    def test_reports_current_model(self):
        # The list is ALIASES, so naming what the active one resolves to is the
        # only way a user can tell which alias is the model they want.
        _, current = self._parse(_CLI_MODEL_REPLY)
        self.assertEqual(current, "Opus 5 (1M context) (effort: xhigh)")

    def test_prose_trailer_is_not_a_model(self):
        names, _ = self._parse(_CLI_MODEL_REPLY)
        self.assertNotIn("or a full model ID", names)
        for n in names:
            self.assertNotIn(" ", n)

    def test_launcher_banners_are_ignored(self):
        names, _ = self._parse(_CLI_MODEL_REPLY)
        self.assertNotIn("Claude", names)
        self.assertNotIn("Using", names)

    def test_bracket_suffix_survives(self):
        names, _ = self._parse("Available: opus[1m], sonnet[1m]")
        self.assertEqual(names, ["opus[1m]", "sonnet[1m]"])

    def test_full_ids_pass_through(self):
        # The CLI also accepts full ids, so the parser must not assume aliases.
        names, _ = self._parse("Available: claude-opus-5, claude-sonnet-5.")
        self.assertEqual(names, ["claude-opus-5", "claude-sonnet-5"])

    def test_duplicates_collapse(self):
        names, _ = self._parse("Available: opus, opus, sonnet")
        self.assertEqual(names, ["opus", "sonnet"])

    def test_unrecognised_output_yields_nothing(self):
        # Wording may drift between CLI versions. Yield nothing rather than junk
        # so the caller keeps whatever the dropdown already had.
        for junk in ("", None, "totally unrelated output", "error: boom"):
            names, current = self._parse(junk)
            self.assertEqual(names, [])
            self.assertEqual(current, "")


class TestClaudeCliFullIdDiscovery(unittest.TestCase):
    """Full versioned ids are DISCOVERED then VALIDATED against the CLI.

    `/model` reports only floating aliases (opus, opus[1m]), which hide which
    model actually runs and re-point on every release -- so they are NOT
    offered. Candidates are scraped from the installed CLI's own binary --
    untrusted guesses -- and every one is confirmed with `/model <id>`, which
    answers locally with no key and no LLM turn.
    """

    def _cli(self):
        import mpynode.ui.llm.claude_cli_client as cli

        return cli

    def test_probe_classifies_the_three_outcomes(self):
        cli = self._cli()
        cases = [
            ("Set model to Opus 5 for this session only", "valid", "Opus 5"),
            ("Model 'claude-opus' not found", "unknown", ""),
            ("API error: 403 Access to Fable is currently restricted.",
             "restricted", ""),
            ("some unrelated banter", "error", ""),
        ]
        for out, want_status, want_label in cases:
            with unittest.mock.patch.object(cli, "_resolve", lambda *_a: "/bin/claude"), \
                 unittest.mock.patch.object(cli, "_run_cli", lambda *a, **k: out):
                status, label = cli.probe_model("claude-opus-5")
            self.assertEqual((status, label), (want_status, want_label), out)

    def test_restricted_model_is_not_offered(self):
        # 403 means the id is REAL but this login cannot use it. Offering it
        # would be a footgun -- the turn fails only after the user picks it.
        cli = self._cli()
        self.assertEqual(cli.probe_model.__doc__ is None, False)
        with unittest.mock.patch.object(cli, "_resolve", lambda *_a: "/bin/claude"), \
             unittest.mock.patch.object(
                 cli, "alias_listing", lambda *a, **k: (["opus"], "Opus 5")), \
             unittest.mock.patch.object(
                 cli, "candidate_model_ids", lambda *a, **k: ["claude-fable-5"]), \
             unittest.mock.patch.object(
                 cli, "probe_model", lambda m, *a, **k: ("restricted", "")):
            names, _cur, displays = cli.list_models()
        self.assertNotIn("claude-fable-5", names)
        self.assertNotIn("claude-fable-5", displays)

    def test_floating_aliases_are_never_offered(self):
        # An alias hides WHICH model runs and silently re-points on release day:
        # "opus" is Opus 5 today and Opus 6 the day that ships, changing a saved
        # node with no edit. Only explicit versioned ids reach the dropdown.
        cli = self._cli()
        with unittest.mock.patch.object(cli, "_resolve", lambda *_a: "/bin/claude"), \
             unittest.mock.patch.object(
                 cli, "alias_listing",
                 lambda *a, **k: (["opus", "opus[1m]"], "Opus 5")), \
             unittest.mock.patch.object(
                 cli, "candidate_model_ids",
                 lambda *a, **k: ["claude-opus-5", "claude-sonnet-4-6"]), \
             unittest.mock.patch.object(
                 cli, "probe_model",
                 lambda m, *a, **k: ("valid", m.replace("[1m]", "").upper())):
            names, _cur, displays = cli.list_models()
        self.assertEqual(names, ["claude-sonnet-4-6", "claude-opus-5"])
        self.assertEqual(displays["claude-opus-5"], "CLAUDE-OPUS-5")

    def test_wide_twin_offered_only_when_its_display_differs(self):
        # `[1m]` is NOT a universal suffix, and we refuse to hardcode which
        # models take it. The CLI decides: keep the twin only when
        # `/model <id>[1m]` reports a DIFFERENT display name than the bare id.
        cli = self._cli()
        labels = {
            "claude-opus-5": "Opus 5",
            "claude-opus-5[1m]": "Opus 5 (1M context)",  # differs -> KEPT
            "claude-sonnet-5": "Sonnet 5",
            "claude-sonnet-5[1m]": "Sonnet 5",           # same -> dropped
            "claude-haiku-4-5": "Haiku 4.5",             # twin 400s -> dropped
        }
        with unittest.mock.patch.object(cli, "_resolve", lambda *_a: "/bin/claude"), \
             unittest.mock.patch.object(
                 cli, "alias_listing", lambda *a, **k: ([], "Opus 5")), \
             unittest.mock.patch.object(
                 cli, "candidate_model_ids",
                 lambda *a, **k: ["claude-opus-5", "claude-sonnet-5",
                                  "claude-haiku-4-5"]), \
             unittest.mock.patch.object(
                 cli, "probe_model",
                 lambda m, *a, **k: (("valid", labels[m]) if m in labels
                                     else ("error", ""))):
            names, _cur, displays = cli.list_models()
        self.assertEqual(names, ["claude-sonnet-5", "claude-opus-5",
                                 "claude-opus-5[1m]", "claude-haiku-4-5"])
        self.assertEqual(displays["claude-opus-5[1m]"], "Opus 5 (1M context)")

    def test_newest_sorts_first_within_each_family(self):
        cli = self._cli()
        got = cli.order_models(["claude-opus-4", "claude-opus-5",
                                "claude-opus-4-8", "claude-haiku-4-5",
                                "claude-sonnet-4-6", "claude-sonnet-5"])
        self.assertEqual(got, ["claude-sonnet-5", "claude-sonnet-4-6",
                               "claude-opus-5", "claude-opus-4-8",
                               "claude-opus-4", "claude-haiku-4-5"])

    def test_two_digit_minor_sorts_above_single_digit(self):
        # Plain string order puts "4-10" BELOW "4-8" ("1" < "8"), which would
        # bury the newest build the day a two-digit minor ships.
        cli = self._cli()
        got = cli.order_models(["claude-opus-4-8", "claude-opus-4-10",
                                "claude-opus-4-9"])
        self.assertEqual(got, ["claude-opus-4-10", "claude-opus-4-9",
                               "claude-opus-4-8"])

    def test_build_stamp_parks_under_its_root(self):
        # 20250514 must NOT outrank the 6 in claude-sonnet-4-6 -- that would
        # hoist the OLDEST id in the family to the top of the dropdown.
        cli = self._cli()
        got = cli.order_models(["claude-sonnet-4", "claude-sonnet-4-20250514",
                                "claude-sonnet-4-6", "claude-sonnet-5"])
        self.assertEqual(got, ["claude-sonnet-5", "claude-sonnet-4-6",
                               "claude-sonnet-4", "claude-sonnet-4-20250514"])

    def test_orphan_build_stamp_is_its_own_entry(self):
        # With no undated root in the list there is nothing to park under, so
        # the dated id must still appear rather than vanish.
        cli = self._cli()
        got = cli.order_models(["claude-opus-4-20250514", "claude-opus-5"])
        self.assertEqual(got, ["claude-opus-5", "claude-opus-4-20250514"])

    def test_order_survives_a_prefs_restore(self):
        # The cache stores a FLAT list; re-deriving the split means a restored
        # list renders exactly like a fresh fetch, with no Refresh needed.
        cli = self._cli()
        flat = ["claude-opus-4-8", "claude-opus-5[1m]", "claude-sonnet-5",
                "claude-opus-5"]
        self.assertEqual(cli.order_display(flat),
                         ["claude-sonnet-5", "claude-opus-5",
                          "claude-opus-5[1m]", "claude-opus-4-8"])

    def test_wide_twin_sits_next_to_its_base(self):
        # A `[1m]` entry IS its base model with a bigger context, so it belongs
        # beside it rather than in a block of its own.
        cli = self._cli()
        got = cli.order_models(["claude-opus-5", "claude-sonnet-5"],
                               ["claude-opus-5[1m]"])
        self.assertEqual(got, ["claude-sonnet-5", "claude-opus-5",
                               "claude-opus-5[1m]"])

    def test_order_dedupes(self):
        cli = self._cli()
        got = cli.order_models(["claude-opus-5", "claude-opus-5"])
        self.assertEqual(got, ["claude-opus-5"])

    def test_alias_pinned_split_is_gone(self):
        # The combo used to render an alias block, a separator, then pinned ids.
        # Aliases are gone, so the helper that computed that split must not
        # linger.
        cli = self._cli()
        self.assertFalse(hasattr(cli, "split_index"))

    def test_candidate_regex_rejects_noise(self):
        # The binary also contains docs and internal suffixes; those are not ids.
        cli = self._cli()
        for good in ("claude-opus-5", "claude-sonnet-4-5-20250929",
                     "claude-haiku-4-5"):
            self.assertTrue(cli._CAND_OK.match(good), good)
        for bad in ("claude-fable-5.md", "claude-sonnet-4.6", "claude-api",
                    "claude-opus"):
            self.assertFalse(cli._CAND_OK.match(bad), bad)

    def test_api_ids_are_candidates_only_still_validated(self):
        # An Anthropic key may supply extra guesses, but the HTTP API is a
        # DIFFERENT BACKEND -- claude-opus-4-1-20250805 is in /v1/models and the
        # CLI rejects it. Nothing bypasses the oracle.
        cli = self._cli()
        seen = []

        def _probe(m, *a, **k):
            seen.append(m)
            return ("unknown", "") if m.endswith("20250805") else ("valid", m)

        with unittest.mock.patch.object(cli, "_resolve", lambda *_a: "/bin/claude"), \
             unittest.mock.patch.object(
                 cli, "alias_listing", lambda *a, **k: (["opus"], "Opus 5")), \
             unittest.mock.patch.object(
                 cli, "candidate_model_ids", lambda *a, **k: []), \
             unittest.mock.patch.object(cli, "probe_model", _probe):
            names, _cur, _d = cli.list_models(
                extra_candidates=["claude-opus-5", "claude-opus-4-1-20250805"])
        self.assertIn("claude-opus-4-1-20250805", seen, "must be probed")
        self.assertIn("claude-opus-5", names)
        self.assertNotIn("claude-opus-4-1-20250805", names, "rejected by CLI")
        self.assertNotIn("opus", names, "the alias must not ride along")


class TestClaudeCliAliasFallback(unittest.TestCase):
    """When discovery finds NOTHING, degrade to the aliases -- never to empty.

    ``list_models`` already asked ``/model`` and holds the alias list, then threw
    it away and returned ``[]``. Measured on the project owner's Windows box: the
    CLI answered with ~10 aliases and the dropdown refreshed to EMPTY, so no
    agent could be selected at all.

    The alias POLICY is unchanged: aliases still never mix into a normal
    listing (``test_floating_aliases_are_never_offered`` is the guard for that,
    and it is untouched). This is a separate last-resort path, and because a
    floating alias silently re-points on release day it must SAY SO through the
    same ``displays`` mapping the panel already renders as a tooltip.
    """

    def _cli(self):
        import mpynode.ui.llm.claude_cli_client as cli

        return cli

    def _list(self, cands, probe=None, aliases=("opus", "sonnet")):
        cli = self._cli()
        probe = probe or (lambda m, *a, **k: ("valid", m.upper()))
        with unittest.mock.patch.object(cli, "_resolve", lambda *_a: "/bin/claude"), \
             unittest.mock.patch.object(
                 cli, "alias_listing", lambda *a, **k: (list(aliases), "Opus 5")), \
             unittest.mock.patch.object(
                 cli, "candidate_model_ids", lambda *a, **k: list(cands)), \
             unittest.mock.patch.object(cli, "probe_model", probe):
            return cli.list_models()

    def test_no_candidates_falls_back_to_the_aliases(self):
        # THE canonical assertion: a CLI build we cannot scrape costs COVERAGE,
        # not a dead dropdown.
        names, cur, _displays = self._list([])
        self.assertEqual(names, ["opus", "sonnet"])
        self.assertEqual(cur, "Opus 5")

    def test_validation_yielding_nothing_falls_back_too(self):
        # Scraping worked, but every id was rejected/restricted -- same dead end,
        # same fallback.
        names, _cur, _d = self._list(["claude-fable-5"],
                                     probe=lambda m, *a, **k: ("restricted", ""))
        self.assertEqual(names, ["opus", "sonnet"])

    def test_a_probe_explosion_falls_back_too(self):
        def _boom(m, *a, **k):
            raise RuntimeError("probe blew up")

        names, _cur, _d = self._list(["claude-opus-5"], probe=_boom)
        self.assertEqual(names, ["opus", "sonnet"])

    def test_the_fallback_says_the_entries_are_floating(self):
        # An UNLABELLED floating alias is a trap: it hides which model runs and
        # re-points with no edit to the saved node.
        _names, _cur, displays = self._list([])
        for a in ("opus", "sonnet"):
            self.assertIn(a, displays, "no display label for the fallback alias")
            self.assertIn("alias", displays[a].lower(), displays[a])

    def test_the_normal_path_is_untouched_no_aliases_mixed_in(self):
        # The twin reports the SAME display name as its base, so it is dropped
        # by the existing rule -- one pinned id survives, and only that.
        names, _cur, displays = self._list(
            ["claude-opus-5"],
            probe=lambda m, *a, **k: ("valid", m.replace("[1m]", "")))
        self.assertEqual(names, ["claude-opus-5"])
        for a in ("opus", "sonnet"):
            self.assertNotIn(a, names, "alias rode along on a WORKING listing")
            self.assertNotIn(a, displays)

    def test_nothing_anywhere_is_still_empty(self):
        # No candidates AND no aliases: there is genuinely nothing to offer.
        names, _cur, displays = self._list([], aliases=())
        self.assertEqual(names, [])
        self.assertEqual(displays, {})

    def test_the_fallback_survives_the_panel_re_sort(self):
        # The panel does not render `names` -- it renders order_display(names)
        # (assistant_panel._populate_cli_models). order_display drops a `[1m]`
        # entry whose BASE is absent, so a fallback that got past list_models
        # could still arrive at the combo short, or empty. Assert the whole
        # real alias set the owner's CLI reports comes out the other side.
        cli = self._cli()
        real = ["sonnet", "opus", "haiku", "fable", "best", "sonnet[1m]",
                "opus[1m]", "fable[1m]", "opusplan", "default"]
        names, _cur, _d = self._list([], aliases=real)
        rendered = cli.order_display(names)
        self.assertEqual(sorted(rendered), sorted(real),
                         "the sorter dropped a fallback alias")


class TestClaudeCliScanIsClaudeRelated(unittest.TestCase):
    """``_scan_files`` must not scrape whatever big binary sits next door.

    It took the largest files >= 2 MB from the resolved binary's dir, its parent
    and every immediate subdir of the parent, with NO relevance check. On macOS
    that works by accident: ``/usr/local/bin/claude`` is a SYMLINK into
    ``/usr/local/bin/claude_code/``, so realpath lands inside Claude's own tree.
    A chocolatey shim is a real .exe, so resolution stays in the SHARED bin dir
    -- measured on the owner's box it scraped gslides.exe / gmail.exe / gmux.exe
    (74 MB each) and produced zero model ids.
    """

    def _cli(self):
        import mpynode.ui.llm.claude_cli_client as cli

        return cli

    def _mk(self, path, size):
        import os

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.truncate(size)  # sparse -- getsize() reports the full size
        return path

    def _tmproot(self):
        import os
        import shutil
        import tempfile

        d = tempfile.mkdtemp(prefix="mpn_scan_")
        self.addCleanup(shutil.rmtree, d, True)
        # _scan_files realpaths the binary; on macOS /var IS /private/var, so
        # comparing raw mkdtemp paths would never match.
        return os.path.realpath(d)

    def test_a_shared_bin_dir_of_unrelated_binaries_is_rejected(self):
        # The chocolatey layout: a small real claude.exe shim beside several
        # large, entirely unrelated binaries.
        import os

        cli = self._cli()
        root = self._tmproot()
        shim = self._mk(os.path.join(root, "bin", "claude.exe"), 392 << 10)
        for n in ("gslides.exe", "gsheets.exe", "gmail.exe", "gmux.exe"):
            self._mk(os.path.join(root, "bin", n), 3 << 20)
        self._mk(os.path.join(root, "lib", "google-api-proxy.exe"), 3 << 20)

        self.assertEqual(cli._scan_files(shim), [])

    def test_a_claude_tree_is_still_scanned(self):
        # The macOS layout in miniature: realpath lands inside claude_code/, so
        # every neighbour genuinely belongs to Claude -- including ones whose own
        # name says nothing ("tpai").
        import os

        cli = self._cli()
        root = self._tmproot()
        tree = os.path.join(root, "claude_code")
        shim = self._mk(os.path.join(tree, "os", "claude"), 1 << 10)
        big = self._mk(os.path.join(tree, "native", "claude"), 4 << 20)
        tpai = self._mk(os.path.join(tree, "bin", "tpai"), 3 << 20)

        got = cli._scan_files(shim)
        self.assertIn(big, got)
        self.assertIn(tpai, got, "a claude_code/ neighbour must still be scanned")

    def test_the_real_local_install_still_scans(self):
        """Regression pin for the macOS case this heuristic already gets right.

        A guard, not a RED test: it passed before the filter and must keep
        passing after. Skipped where the resolved binary does NOT already live
        in a claude-named tree (that IS the broken Windows shape).
        """
        import os

        cli = self._cli()
        binp = cli._resolve()
        if not binp:
            self.skipTest("no claude CLI on this machine")
        d = os.path.dirname(os.path.realpath(binp))
        if "claude" not in d.lower():
            self.skipTest("claude does not resolve into a claude tree here")
        self.assertTrue(cli._scan_files(binp),
                        "the working macOS scan came back EMPTY")


class TestClaudeCliComboRendering(unittest.TestCase):
    """One homogeneous block of explicit ids -- no aliases, no separator."""

    def _panel(self):
        from mpynode.ui.widgets.assistant_panel import NDAssistantPanel

        p = NDAssistantPanel()
        self.addCleanup(p.deleteLater)
        return p

    def test_every_row_is_a_real_model(self):
        # A separator row would make count() disagree with the model count and
        # is meaningless now that there is only one kind of entry.
        p = self._panel()
        p._cli_model_displays = {"claude-opus-5": "Opus 5"}
        p._model_edit.clear()
        models = ["claude-opus-5", "claude-opus-5[1m]", "claude-haiku-4-5"]
        p._populate_cli_models(models)
        self.assertEqual(p._model_edit.count(), len(models))
        for m in models:
            self.assertGreaterEqual(p._model_edit.findText(m), 0, m)

    def test_display_name_becomes_a_tooltip(self):
        from mpynode.ui.qt_wrapper import Qt

        p = self._panel()
        p._cli_model_displays = {"claude-opus-4-20250514": "Opus 4"}
        p._model_edit.clear()
        p._populate_cli_models(["claude-opus-4", "claude-opus-4-20250514"])
        i = p._model_edit.findText("claude-opus-4-20250514")
        self.assertEqual(p._model_edit.itemData(i, Qt.ToolTipRole), "Opus 4")


class TestClaudeCliListNeedsNoKey(unittest.TestCase):
    """Refreshing the claude_cli list must never consult an API key."""

    def test_refresh_routes_to_the_cli_not_the_key_path(self):
        import mpynode.ui.llm.claude_cli_client as cli
        from mpynode.ui.widgets.assistant_panel import NDAssistantPanel

        p = NDAssistantPanel()
        self.addCleanup(p.deleteLater)
        calls = []
        with unittest.mock.patch.object(
            cli, "list_models",
            lambda *a, **k: (calls.append(1), (["opus"], "Opus 5", {}))[1]
        ), unittest.mock.patch.object(
            p, "_list_source",
            lambda prov: (_ for _ in ()).throw(
                AssertionError("key path must not run for claude_cli"))
        ):
            p._fetch_claude_cli_models()
        self.assertEqual(len(calls), 1)

    def test_worker_records_current_model(self):
        import mpynode.ui.llm.claude_cli_client as cli
        from mpynode.ui.widgets.assistant_panel import NDAssistantPanel

        p = NDAssistantPanel()
        self.addCleanup(p.deleteLater)
        with unittest.mock.patch.object(
            cli, "list_models",
            lambda *a, **k: (["opus"], "Opus 5 (1M context)", {"opus": "Opus 5"})
        ):
            models = p._fetch_claude_cli_models()
        self.assertEqual(models, ["opus"])
        self.assertEqual(p._cli_current_model, "Opus 5 (1M context)")

    def test_autorefresh_not_gated_on_a_key(self):
        from mpynode.ui.widgets.assistant_panel import NDAssistantPanel

        p = NDAssistantPanel()
        self.addCleanup(p.deleteLater)
        p._model_cache.pop("claude_cli", None)
        cfg.set_cached_models("claude_cli", [])
        self.addCleanup(cfg.set_cached_models, "claude_cli", [])
        fired = []
        with unittest.mock.patch.object(
            p, "_on_refresh_models", lambda: fired.append(1)
        ), unittest.mock.patch.object(p, "_list_source", lambda prov: ("anthropic", "")):
            p._maybe_autorefresh_models("claude_cli")
        self.assertEqual(fired, [1], "claude_cli must refresh with no key set")


class TestModelSelectionAfterFetch(unittest.TestCase):
    """After a list refresh, what id should the dropdown show?

    Regression guard: auto-populating the Claude CLI list must NOT silently
    display ``models[0]`` (opus-4-8[1m]) while the persisted pref is blank --
    that would SHOW one version but RUN the CLI's default (opus 4.6). For CLI
    providers, blank means 'use the CLI's own default' and must be preserved.
    """

    def test_cli_blank_stays_blank(self):
        sel = cfg.model_selection_after_fetch(
            "claude_cli", "", ["claude-opus-4-8[1m]", "claude-opus-4-8"])
        self.assertEqual(sel, "")

    def test_cli_keeps_explicit_choice(self):
        sel = cfg.model_selection_after_fetch(
            "claude_cli", "claude-opus-4-8[1m]",
            ["claude-opus-4-8[1m]", "claude-opus-4-8"])
        self.assertEqual(sel, "claude-opus-4-8[1m]")

    def test_api_blank_surfaces_first_concrete_id(self):
        # API providers have no 'blank = CLI default' semantics; show a concrete
        # id so the box isn't empty.
        sel = cfg.model_selection_after_fetch(
            "anthropic", "", ["claude-sonnet-4-5", "claude-opus-4-8"])
        self.assertEqual(sel, "claude-sonnet-4-5")

    def test_api_keeps_explicit_choice(self):
        sel = cfg.model_selection_after_fetch(
            "anthropic", "gpt-4o", ["claude-sonnet-4-5"])
        self.assertEqual(sel, "gpt-4o")

    def test_empty_models_never_raises(self):
        self.assertEqual(cfg.model_selection_after_fetch("anthropic", "", []), "")
        self.assertEqual(cfg.model_selection_after_fetch("claude_cli", "", []), "")


# ===================== from test_cli_effort_values.py =====================
import unittest

from mpynode.ui.llm import config as cfg


_VALID_CLI = {"off", "low", "medium", "high", "xhigh", "max"}


class TestCliEffortEnum(unittest.TestCase):
    def test_enum_is_exactly_the_cli_accepted_set(self):
        self.assertEqual(set(cfg.EFFORT_LEVELS_CLI), _VALID_CLI)

    def test_ultracode_and_auto_are_gone(self):
        self.assertNotIn("ultracode", cfg.EFFORT_LEVELS_CLI)
        self.assertNotIn("auto", cfg.EFFORT_LEVELS_CLI)

    def test_effort_levels_for_claude_cli_are_all_cli_valid(self):
        for lv in cfg.effort_levels("claude_cli"):
            self.assertIn(lv, _VALID_CLI, "%r is not a valid claude --effort" % lv)


class TestGetEffortMigration(unittest.TestCase):
    """A stale saved pref must resolve to a CLI-valid value, never raise/abort."""

    def _with_pref(self, value):
        orig = cfg._pref

        def fake(key, default=None):
            if key == "assistant_effort_claude_cli":
                return value
            return orig(key, default)

        cfg._pref = fake
        self.addCleanup(lambda: setattr(cfg, "_pref", orig))

    def test_legacy_ultracode_migrates_to_max(self):
        self._with_pref("ultracode")
        self.assertEqual(cfg.get_effort("claude_cli"), "max")

    def test_legacy_auto_migrates_to_off(self):
        self._with_pref("auto")
        self.assertEqual(cfg.get_effort("claude_cli"), "off")

    def test_unknown_value_falls_back_to_off(self):
        self._with_pref("turbo")
        self.assertEqual(cfg.get_effort("claude_cli"), "off")

    def test_valid_value_passes_through(self):
        self._with_pref("xhigh")
        self.assertEqual(cfg.get_effort("claude_cli"), "xhigh")

    def test_get_effort_never_returns_a_cli_invalid_value(self):
        for val in ("ultracode", "auto", "turbo", "MAX", "High", ""):
            self._with_pref(val)
            self.assertIn(cfg.get_effort("claude_cli"), _VALID_CLI)


class TestPorterBuildsValidEffort(unittest.TestCase):
    """End-to-end at the command layer: a stale 'ultracode' pref must NOT reach
    the CLI as --effort ultracode."""

    def test_build_cli_uses_migrated_effort(self):
        from mpynode.native.ai import porter
        orig = cfg._pref
        cfg._pref = lambda k, d=None: ("ultracode"
                                       if k == "assistant_effort_claude_cli"
                                       else orig(k, d))
        self.addCleanup(lambda: setattr(cfg, "_pref", orig))
        eff = cfg.get_effort("claude_cli")
        cmd, _stdin = porter._build_cli("claude_cli", "claude", "claude-opus-4-8",
                                        eff, "prompt")
        self.assertNotIn("ultracode", cmd)
        # the migrated value (max) is what the CLI gets
        self.assertIn("--effort", cmd)
        self.assertEqual(cmd[cmd.index("--effort") + 1], "max")


class TestPorterStreamJsonAndHygiene(unittest.TestCase):
    """#5: claude_cli stream-json CoT capture + output-hygiene (prose/fence)."""

    def _lc(self):
        from mpynode.native.ai import llm_client
        return llm_client

    def _pr(self):
        from mpynode.native.ai import prompt
        return prompt

    def test_build_cli_stream_json_flag(self):
        cmd, _ = self._lc()._build_cli("claude_cli", "claude", "opus", "max",
                                       "P", stream_json=True)
        self.assertIn("stream-json", cmd)
        self.assertIn("--verbose", cmd)

    def test_build_cli_orchestrate_undenies_task_and_prefixes(self):
        lc = self._lc()
        cmd, stdin = lc._build_cli("claude_cli", "claude", "opus", "max", "P",
                                   orchestrate=True, stream_json=True)
        self.assertIn("--append-system-prompt", cmd)
        deny = cmd[cmd.index("--disallowedTools") + 1]
        self.assertNotIn("Task", deny.split(","))
        self.assertNotIn("ToolSearch", deny.split(","))
        # every other built-in stays denied (no shell/file exploration)
        for t in ("Bash", "Read", "Write", "Edit"):
            self.assertIn(t, deny.split(","))
        # the 'ultracode' keyword goes in the prompt BODY, never argv
        self.assertNotIn("ultracode", cmd)
        self.assertTrue(stdin.startswith("ultracode"))

    def test_build_cli_default_is_plain_text_no_orchestrate(self):
        lc = self._lc()
        cmd, stdin = lc._build_cli("claude_cli", "claude", "opus", "max", "P")
        self.assertIn("text", cmd)
        self.assertNotIn("stream-json", cmd)
        self.assertNotIn("--append-system-prompt", cmd)
        self.assertEqual(stdin, "P")

    def test_build_cli_strict_mcp_config_kills_mcp_tools(self):
        # Root cause of the OSL flail: without --strict-mcp-config the CLI
        # auto-loads the user's MCP servers and burns minutes on
        # mcp__..._search_files, which _CLI_DENY (built-ins only) cannot deny.
        # The flag loads ZERO MCP servers -> pure text completion.
        lc = self._lc()
        cmd, _ = lc._build_cli("claude_cli", "claude", "opus", "max", "P")
        self.assertIn("--strict-mcp-config", cmd)
        # present in orchestrate/stream-json mode too (porter path)
        cmd2, _ = lc._build_cli("claude_cli", "claude", "opus", "max", "P",
                                orchestrate=True, stream_json=True)
        self.assertIn("--strict-mcp-config", cmd2)

    def test_build_cli_no_strict_mcp_for_non_claude(self):
        # The flag is a Claude Code CLI concept; other CLIs must not receive it.
        lc = self._lc()
        cmd, _ = lc._build_cli("gemini_cli", "gemini", "g", "max", "P")
        self.assertNotIn("--strict-mcp-config", cmd)

    def test_parse_stream_json_streams_answer_text_to_log(self):
        # The emerging answer text and each tool's INPUT must be teed to log_cb
        # so the activity strip shows real progress, while the returned ANSWER
        # stays only the text blocks.
        lc = self._lc()
        sj = "\n".join([
            '{"type":"assistant","message":{"content":['
            '{"type":"tool_use","name":"mcp__x__search_files",'
            '"input":{"query":"colorspace"}}]}}',
            '{"type":"assistant","message":{"content":['
            '{"type":"text","text":"shader s(output color outColor=color(0)){}"}]}}',
        ])
        logs = []
        out = lc._parse_stream_json(sj, log_cb=logs.append)
        self.assertEqual(out, "shader s(output color outColor=color(0)){}")
        blob = "\n".join(logs)
        # the emerging shader is visible in the feed
        self.assertIn("shader s(", blob)
        # the tool INPUT (not just its bare name) is visible in the feed
        self.assertIn("colorspace", blob)

    def test_parse_stream_json_returns_text_logs_thinking(self):
        lc = self._lc()
        sj = "\n".join([
            '{"type":"assistant","message":{"content":['
            '{"type":"thinking","thinking":"reasoning"}]}}',
            '{"type":"assistant","message":{"content":['
            '{"type":"text","text":"double y = 3.0;"}]}}',
            '{"type":"result","result":"IGNORED_FALLBACK"}',
        ])
        logs = []
        out = lc._parse_stream_json(sj, log_cb=logs.append)
        self.assertEqual(out, "double y = 3.0;")
        self.assertTrue(any("reasoning" in m for m in logs))
        # the aggregated 'result' is a fallback only, never appended to the answer
        self.assertNotIn("IGNORED_FALLBACK", out)

    def test_parse_stream_json_result_fallback_when_no_text(self):
        lc = self._lc()
        sj = '{"type":"result","result":"h_out.setFloat(1.0);"}'
        self.assertEqual(lc._parse_stream_json(sj), "h_out.setFloat(1.0);")

    def test_parse_stream_json_none_for_plaintext(self):
        lc = self._lc()
        self.assertIsNone(lc._parse_stream_json("double x = 1.0;"))
        self.assertIsNone(lc._parse_stream_json(""))

    def test_parse_stream_json_subagent_text_not_in_answer(self):
        lc = self._lc()
        sj = "\n".join([
            '{"type":"assistant","parent_tool_use_id":"t1","message":{"content":['
            '{"type":"text","text":"SUBAGENT NARRATION"}]}}',
            '{"type":"assistant","message":{"content":['
            '{"type":"text","text":"int n = 1;"}]}}',
        ])
        out = lc._parse_stream_json(sj)
        self.assertEqual(out, "int n = 1;")

    def test_ascii_typography_drops_all_nonascii(self):
        lc = self._lc()
        self.assertEqual(lc._ascii_typography("a — b ✓ c"), "a - b  c")
        self.assertTrue(lc._ascii_typography("x = a − b;").isascii())

    def test_extract_body_fence(self):
        pr = self._pr()
        raw = "Sure, here it is:\n```cpp\nint x = 2;\n```\nHope that helps."
        self.assertEqual(pr._extract_body(raw), "int x = 2;")

    def test_extract_body_peels_edge_prose(self):
        pr = self._pr()
        raw = ("Looking at the SVD I compute the rotation.\n"
               "double x = 1.0;\n"
               "h_out.setFloat(x);\n"
               "Confirmed the math is correct.")
        self.assertEqual(pr._extract_body(raw),
                         "double x = 1.0;\nh_out.setFloat(x);")

    def test_extract_body_pure_code_unchanged(self):
        pr = self._pr()
        code = ("if (a) {\n    x = 1;\n} else {\n"
                "    // fallback here\n    x = 2;\n}")
        self.assertEqual(pr._extract_body(code), code)

    def test_porter_orchestrate_env_override(self):
        lc = self._lc()
        old = os.environ.get("MPYNODE_PORT_ULTRACODE")
        try:
            os.environ["MPYNODE_PORT_ULTRACODE"] = "1"
            self.assertTrue(lc._porter_orchestrate())
            os.environ["MPYNODE_PORT_ULTRACODE"] = "0"
            self.assertFalse(lc._porter_orchestrate())
        finally:
            if old is None:
                os.environ.pop("MPYNODE_PORT_ULTRACODE", None)
            else:
                os.environ["MPYNODE_PORT_ULTRACODE"] = old


# ===================== from test_assistant_model_order.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance()
    if _QAPP is None:
        try:
            _QAPP = _QApplication(["mayapy-model-order-test"])
        except Exception:
            _QAPP = None

import unittest

from tests._setup import standalone_init


def _setUpModule__assistant_model_order():
    standalone_init()


def _vpos(layout, target):
    """Index of ``target`` within ``layout``, searching direct widgets and one
    level of nested layouts (the Model combo lives in a nested QHBoxLayout next to
    its Refresh button). Returns -1 if not found."""
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is target:
            return i
        sub = item.layout()
        if sub is not None:
            for j in range(sub.count()):
                if sub.itemAt(j).widget() is target:
                    return i
    return -1


@unittest.skipUnless(_QAPP is not None, "Qt not available")
class TestModelBetweenReasoningAndApiKey(unittest.TestCase):
    def _panel(self):
        from mpynode.ui.widgets.assistant_panel import NDAssistantPanel
        return NDAssistantPanel()

    def test_model_is_between_reasoning_and_api_key(self):
        panel = self._panel()
        try:
            slay = panel._settings.layout()
            i_reasoning = _vpos(slay, panel._effort_combo)
            i_model = _vpos(slay, panel._model_edit)
            i_api = _vpos(slay, panel._api_section)
            self.assertNotEqual(i_reasoning, -1, "Reasoning combo not in layout")
            self.assertNotEqual(i_model, -1, "Model combo not in layout")
            self.assertNotEqual(i_api, -1, "API-key section not in layout")
            self.assertLess(i_reasoning, i_model,
                            "Model must come AFTER Reasoning")
            self.assertLess(i_model, i_api,
                            "Model must come BEFORE the API-key section")
        finally:
            panel.deleteLater()


# ===================== from test_assistant_multiagent.py =====================
# The "Multi-Agent (ultracode)" mode these pinned was removed on 2026-09-10: its
# one measurement was a net regression and the keyword it relied on is
# deployment-specific. What remains is what it must NOT have loosened -- the
# lean deny list and the nested-text filter -- plus pins that it stays gone.
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-cli-client-test"])

import unittest

from mpynode.ui.llm import config as cfg
from mpynode.ui.llm import claude_cli_client as cc
from tests._setup import standalone_init


def _setUpModule__assistant_cli_client():
    standalone_init()


def _deny_set(cmd):
    """The --disallowedTools value (set of tool names) in a build_cmd argv."""
    if "--disallowedTools" not in cmd:
        return set()
    return set(cmd[cmd.index("--disallowedTools") + 1].split(","))


class TestBuildCmdDenyList(unittest.TestCase):
    def test_default_denies_task_and_toolsearch(self):
        # The lean deny list: no sub-agents, no deferred tool loading.
        cmd = cc.build_cmd("claude", "p", "sid", False)
        deny = _deny_set(cmd)
        self.assertIn("Task", deny)
        self.assertIn("ToolSearch", deny)

    def test_no_multi_agent_mode_remains(self):
        # Removed 2026-09-10 -- see the block comment above. Nothing may
        # un-deny Task/ToolSearch, prefix the keyword, or store the flag.
        import inspect

        from mpynode.ui import preferences

        self.assertNotIn("orchestrate", inspect.signature(cc.build_cmd).parameters)
        self.assertFalse(hasattr(cc, "orchestration_prompt"))
        self.assertFalse(hasattr(cfg, "multiagent_enabled"))
        self.assertFalse(hasattr(cfg, "set_multiagent"))
        self.assertNotIn("assistant_multiagent_claude_cli", preferences.DEFAULT_PREFS)

    def test_build_cmd_has_no_mcp_flags(self):
        # The payload transport carries no MCP config -- the argv must not add
        # --mcp-config / --allowedTools / an mpynode allowlist anymore.
        cmd = cc.build_cmd("claude", "p", "sid", False)
        self.assertNotIn("--mcp-config", cmd)
        self.assertNotIn("--allowedTools", cmd)
        self.assertFalse(any("mcp__mpynode" in str(a) for a in cmd))


@unittest.skipIf(_QAPP is None, "no Qt available")
class TestHandleEventNestedText(unittest.TestCase):
    def _client_capture(self):
        client = cc.ClaudeCliClient()
        cap = {"text": [], "tool": [], "done": []}
        client.assistantText.connect(cap["text"].append)
        client.toolStarted.connect(cap["tool"].append)
        client.toolFinished.connect(cap["done"].append)
        return client, cap

    def test_subagent_text_not_emitted_as_main_bubble(self):
        # Text nested under a tool use (parent_tool_use_id set) is interim
        # chatter, NOT the main answer (the top-level agent emits the node
        # payload), so it must not bubble to the panel.
        client, cap = self._client_capture()
        client._handle_event(json.dumps({
            "type": "assistant", "parent_tool_use_id": "tu1",
            "message": {"content": [
                {"type": "text", "text": "interim sub chatter"}]}}))
        self.assertNotIn("interim sub chatter", cap["text"])

    def test_top_level_text_still_emitted(self):
        client, cap = self._client_capture()
        client._handle_event(json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "final answer"}]}}))
        self.assertIn("final answer", cap["text"])


@unittest.skipIf(_QAPP is None, "no Qt available")
class TestPanelHasNoMultiagentCheckbox(unittest.TestCase):
    def test_panel_has_no_multiagent_checkbox(self):
        from mpynode.ui.widgets.assistant_panel import NDAssistantPanel

        p = NDAssistantPanel()
        try:
            self.assertFalse(hasattr(p, "_multiagent_check"))
            p._apply_provider_visibility("claude_cli")   # no dangling reference
        finally:
            p.deleteLater()


# ===================== from test_assistant_node_targeting.py =====================
import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-targeting-test"])


def _setUpModule__assistant_node_targeting():
    standalone_init()
    ensure_plugins_loaded()


class TestListNodesTool(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.ui.llm import tools as T
        self.T = T

    def test_tool_is_registered(self):
        self.assertIn("list_nodes", self.T.VALID_TOOLS)

    def test_lists_scene_mpy_nodes_with_type(self):
        a = mc.createNode("mPyNode", name="alpha#")
        b = mc.createNode("mPyLocator", name="beta#")
        ctx = self.T.ToolContext()
        res = self.T.dispatch("list_nodes", {}, ctx)
        self.assertNotIn("error", res, "dispatch errored: %r" % res)
        names = {n["name"]: n["type"] for n in res.get("nodes", [])}
        self.assertIn(a, names)
        self.assertIn(b, names)
        self.assertEqual(names[a], "mPyNode")

    def test_excludes_non_mpy_nodes(self):
        mc.createNode("mPyNode", name="onlyMpy#")
        plain = mc.createNode("transform", name="plainXform#")
        ctx = self.T.ToolContext()
        res = self.T.dispatch("list_nodes", {}, ctx)
        names = {n["name"] for n in res.get("nodes", [])}
        self.assertNotIn(plain, names)

    def test_prefilters_unloaded_types_no_spurious_warning(self):
        """cmds.ls(type=X) on an UNLOADED type prints 'Unknown object type: X'
        to the Script Editor (cf. _common/time_utils.py). list_nodes must
        pre-filter against allNodeTypes() and never query an unloaded type."""
        T = self.T
        calls = []
        real_ls, real_ant = T.mc.ls, T.mc.allNodeTypes

        def fake_ls(*a, **k):
            if "type" in k:
                calls.append(k["type"])
                return []
            return real_ls(*a, **k)

        T.mc.ls = fake_ls
        T.mc.allNodeTypes = lambda: ["mPyNode"]  # pretend only mPyNode is loaded
        try:
            res = T.dispatch("list_nodes", {}, T.ToolContext())
        finally:
            T.mc.ls, T.mc.allNodeTypes = real_ls, real_ant
        self.assertNotIn("error", res)
        self.assertTrue(calls and all(t == "mPyNode" for t in calls),
                        "queried unloaded types (would warn): %r" % calls)

    def test_description_carries_edit_existing_steering(self):
        """The API providers steer via the tool DESCRIPTION for the prefer-edit /
        no-probe behavior, so lock the list_nodes description text."""
        ln = next(s for s in self.T.TOOL_SCHEMAS if s["name"] == "list_nodes")
        d = ln["description"].lower()
        self.assertIn("prefer editing", d)
        self.assertIn("probe", d)


class TestPayloadExtract(unittest.TestCase):
    """The .mpn-payload transport that replaced the MCP bridge: extract the JSON
    node payload from an agent's reply, and normalize it to define_node args."""

    def setUp(self):
        from mpynode.ui.llm import payload
        self.P = payload

    def test_extracts_fenced_json_payload(self):
        text = ('Here you go.\n```json\n{"node_type": "mPyNode", '
                '"compute": "self.out = 1"}\n```\nDone.')
        p = self.P.extract_payload(text)
        self.assertIsNotNone(p)
        self.assertEqual(p["node_type"], "mPyNode")

    def test_prefers_last_payload_block(self):
        text = ('```json\n{"node_type": "mPyNode", "name": "draft"}\n```\n'
                '```json\n{"node_type": "mPyNode", "name": "final"}\n```')
        p = self.P.extract_payload(text)
        self.assertEqual(p.get("name"), "final")

    def test_bare_json_object_without_fence(self):
        p = self.P.extract_payload('{"node": "myNode", "compute": "self.o = 2"}')
        self.assertEqual(p.get("node"), "myNode")

    def test_pure_prose_returns_none(self):
        self.assertIsNone(self.P.extract_payload(
            "I can't do that without more detail. What driver do you want?"))

    def test_to_define_args_edit_targets_node(self):
        args = self.P.to_define_args({"node": "gizmo1", "compute": "x"}, None)
        self.assertEqual(args.get("node"), "gizmo1")
        self.assertNotIn("node_type", args)

    def test_to_define_args_create_uses_node_type(self):
        args = self.P.to_define_args({"node_type": "mPyLocator"}, "activeNode")
        self.assertEqual(args.get("node_type"), "mPyLocator")
        self.assertNotIn("node", args)

    def test_to_define_args_falls_back_to_active_node(self):
        args = self.P.to_define_args({"compute": "self.o = 1"}, "activeNode")
        self.assertEqual(args.get("node"), "activeNode")

    def test_to_define_args_accepts_raw_mpn_shape(self):
        # native_type + expression + input_attrs map (serialize_node shape).
        args = self.P.to_define_args({
            "native_type": "mPyNode",
            "expression": "self.o = self.a",
            "input_attrs": {"a": {"attr_type": "float", "order": 0}},
        }, None)
        self.assertEqual(args.get("node_type"), "mPyNode")
        self.assertEqual(args.get("compute"), "self.o = self.a")
        self.assertEqual([i["name"] for i in args["inputs"]], ["a"])
        self.assertEqual(args["inputs"][0]["type"], "float")

    def test_summary_line_names_target_and_counts(self):
        s = self.P.summary_line({"node_type": "mPyNode",
                                 "inputs": [{"name": "a", "type": "float"}],
                                 "compute": "x"})
        self.assertIn("mPyNode", s)
        self.assertIn("1 in", s)
        self.assertIn("compute", s)


class TestPayloadApply(unittest.TestCase):
    """The apply path reuses the tested define_node spine on the wrapper API."""

    def setUp(self):
        from mpynode.ui.llm import payload, tools
        self.P, self.T = payload, tools

    def test_apply_creates_node_and_sets_compute(self):
        mc.file(new=True, force=True)
        ctx = self.T.ToolContext()
        res = self.P.apply_payload(None, {
            "node_type": "mPyNode",
            "inputs": [{"name": "amount", "type": "float"}],
            "compute": "self.amount",
        }, ctx)
        self.assertNotIn("error", res, "apply errored: %r" % res)
        node = res.get("node")
        self.assertTrue(node and mc.objExists(node))
        w = __import__("mpynode").wrap_node(node)
        self.assertIn("amount", (w.get_input_attr_map() or {}))

    def test_apply_edits_active_node_additively(self):
        mc.file(new=True, force=True)
        node = mc.createNode("mPyNode", name="existing#")
        ctx = self.T.ToolContext(working_node=node)
        # Re-declares the (not-yet-present) attr; re-listing an existing one on a
        # later edit must not abort (idempotent add).
        res = self.P.apply_payload(node, {
            "node": node,
            "inputs": [{"name": "blend", "type": "float"}],
            "compute": "self.blend",
        }, ctx)
        self.assertNotIn("error", res)
        self.assertEqual(res.get("node"), node)
        # Second edit re-lists blend + adds gain -> must succeed, keep both.
        res2 = self.P.apply_payload(node, {
            "node": node,
            "inputs": [{"name": "blend", "type": "float"},
                       {"name": "gain", "type": "float"}],
            "compute": "self.blend + self.gain",
        }, ctx)
        self.assertNotIn("error", res2, "additive re-edit errored: %r" % res2)
        w = __import__("mpynode").wrap_node(node)
        ins = w.get_input_attr_map() or {}
        self.assertIn("blend", ins)
        self.assertIn("gain", ins)

    def test_apply_rejects_scene_mutating_expression(self):
        # The define_node guard must still reject a scene-corrupting Compute.
        mc.file(new=True, force=True)
        ctx = self.T.ToolContext()
        res = self.P.apply_payload(None, {
            "node_type": "mPyNode",
            "compute": "import maya.cmds as cmds\ncmds.file(new=True, force=True)",
        }, ctx)
        self.assertIn("error", res)


@unittest.skipIf(_QAPP is None, "no Qt available")
class TestClaudeCliReporting(unittest.TestCase):
    def _client_capture(self):
        from mpynode.ui.llm import claude_cli_client as cc
        client = cc.ClaudeCliClient()
        cap = {"started": [], "finished": [], "text": []}
        client.toolStarted.connect(cap["started"].append)
        client.toolFinished.connect(cap["finished"].append)
        client.assistantText.connect(cap["text"].append)
        return client, cap

    def test_stream_text_is_accumulated_for_extraction(self):
        client, cap = self._client_capture()
        client._append_answer("here is the node ")
        client._append_answer('```json\n{"node_type":"mPyNode"}\n```')
        self.assertIn("mPyNode", client._answer_text)
        self.assertEqual(len(cap["text"]), 2)

    def test_finalize_applies_payload_and_reports(self):
        from mpynode.ui.llm import payload, tools
        mc.file(new=True, force=True)
        client, cap = self._client_capture()
        text = ('Built it.\n```json\n{"node_type": "mPyNode", '
                '"inputs": [{"name": "amount", "type": "float"}], '
                '"compute": "self.amount"}\n```')
        applied = payload.finalize_turn(client, None, tools.ToolContext(), text)
        self.assertTrue(applied)
        self.assertTrue(any("mPyNode" in s for s in cap["started"]),
                        "no start summary: %r" % cap["started"])
        self.assertTrue(cap["finished"], "no finish line emitted")
        self.assertTrue(any("created" in s.lower() for s in cap["finished"]),
                        "finish line didn't report the created node: %r"
                        % cap["finished"])

    def test_finalize_pure_prose_applies_nothing(self):
        from mpynode.ui.llm import payload, tools
        client, cap = self._client_capture()
        applied = payload.finalize_turn(
            client, None, tools.ToolContext(),
            "I need more detail -- which mesh should drive it?")
        self.assertFalse(applied)
        self.assertFalse(cap["started"])
        self.assertFalse(cap["finished"])


class TestNoFreshNodeGuidance(unittest.TestCase):
    """RC-B: the teaching must steer the model to EDIT the active/existing node
    (get_node / list_nodes) rather than building a fresh one or a probe node."""

    def test_system_prompt_teaches_edit_existing_and_no_probe(self):
        from mpynode.ui.llm.system_prompt import build_system_prompt
        sp = build_system_prompt().lower()
        self.assertIn("list_nodes", sp)
        self.assertIn("probe", sp)

    def test_payload_prompt_teaches_edit_active_node(self):
        # CLI providers steer targeting through the payload prompt (edit the
        # active node vs. build a new one), not tool descriptions.
        from mpynode.ui.llm.system_prompt import build_payload_system_prompt
        sp = build_payload_system_prompt().lower()
        self.assertIn("edit", sp)
        self.assertIn("node_type", sp)
        self.assertIn('"node"', sp)


@unittest.skipIf(_QAPP is None, "no Qt available")
class TestPanelCapturesWorkingNode(unittest.TestCase):
    def _panel(self, current):
        from mpynode.ui.widgets.assistant_panel import NDAssistantPanel
        return NDAssistantPanel(get_current_node=lambda: current)

    def test_capture_records_active_node_for_ctx(self):
        # Both provider paths now read the active node through the per-turn
        # ToolContext (_make_ctx) -- CLI providers serialize it into the prompt.
        p = self._panel("activeGizmo")
        try:
            p._capture_working_node()
            self.assertEqual(p._working_node_name, "activeGizmo")
            ctx = p._make_ctx()
            self.assertEqual(ctx.working_node, "activeGizmo")
        finally:
            p.deleteLater()

    def test_clear_does_not_raise(self):
        p = self._panel(None)
        try:
            p._on_clear()  # no MCP bridge to reset -- must still be a clean no-op
        finally:
            p.deleteLater()


# ===================== from test_assistant_methods_tool.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__assistant_methods_tool():
    standalone_init()
    ensure_plugins_loaded()


# A compact twin of the demo scene's _methodsSource: two @maya_command defs, the
# second of which mutates the scene (mc.connectAttr) -- the exact pattern that the
# Compute/Init scene-guard would refuse.
_METHODS_SRC = (
    "from mpynode._common.methods.maya_command import maya_command\n"
    "\n"
    "\n"
    '@maya_command(name="setMeshRegion", undoable=True)\n'
    "def set_region(self, indices=None):\n"
    "    ids = [int(i) for i in (indices or [])]\n"
    '    self.set_variable("region_ids", ids, persistent=True)\n'
    "    return ids\n"
    "\n"
    "\n"
    '@maya_command(name="createMeshRegion", undoable=True)\n'
    "def create_region(self, indices=None):\n"
    "    import maya.cmds as mc\n"
    "    sel = mc.ls(selection=True, long=True) or []\n"
    '    meshes = mc.ls(sel, dag=True, type="mesh", long=True) or []\n'
    "    if meshes:\n"
    '        mc.connectAttr(meshes[0] + ".worldMesh[0]",\n'
    '                       self.get_name() + ".inMesh", force=True)\n'
    "    return self.get_name()\n"
)


class TestSetMethodsSourceSchema(unittest.TestCase):
    def setUp(self):
        from mpynode.ui.llm import tools as T
        self.T = T

    def test_tool_is_registered(self):
        self.assertIn("set_methods_source", self.T.VALID_TOOLS)
        schema = next(s for s in self.T.TOOL_SCHEMAS
                      if s["name"] == "set_methods_source")
        self.assertIn("source", schema["input_schema"]["properties"])

    def test_schema_teaches_the_decorator(self):
        """The description must name @maya_command + the Methods tab so the model
        stops inventing a decorator in a try/except (the reported bug)."""
        schema = next(s for s in self.T.TOOL_SCHEMAS
                      if s["name"] == "set_methods_source")
        desc = schema["description"].lower()
        self.assertIn("maya_command", desc)
        self.assertIn("method", desc)

    def test_define_node_schema_has_methods(self):
        schema = next(s for s in self.T.TOOL_SCHEMAS if s["name"] == "define_node")
        self.assertIn("methods", schema["input_schema"]["properties"])


class TestSetMethodsSourceDispatch(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.ui.llm import tools as T
        self.T = T

    def _node(self):
        return mc.createNode("mPyNode", name="methodsTool#")

    def test_dispatch_round_trips_and_lists_commands(self):
        node = self._node()
        ctx = self.T.ToolContext(working_node=node)
        res = self.T.dispatch("set_methods_source",
                              {"source": _METHODS_SRC}, ctx)
        self.assertNotIn("error", res, "dispatch errored: %r" % res)
        import mpynode
        w = mpynode.wrap_node(node)
        self.assertEqual(w.get_methods_source(), _METHODS_SRC)
        # the statically-detected command names come back in the result
        self.assertIn("setMeshRegion", res.get("commands", []))
        self.assertIn("createMeshRegion", res.get("commands", []))

    def test_methods_allow_scene_mutation(self):
        """KEY differentiator: Methods are explicitly-invoked commands, so a
        scene-mutating call (mc.connectAttr) must be ACCEPTED -- not refused like
        a per-frame Compute/Init expression."""
        node = self._node()
        ctx = self.T.ToolContext(working_node=node)
        res = self.T.dispatch("set_methods_source",
                              {"source": _METHODS_SRC}, ctx)
        self.assertNotIn("error", res, "methods must allow connectAttr: %r" % res)

    def test_compute_still_refuses_scene_mutation(self):
        """Anchor the distinction: a representative scene-mutating call
        (mc.connectAttr -- the same KIND the methods body uses) is still REFUSED
        by the Compute tool's per-frame scene-corruption guard, proving Methods
        are deliberately exempt rather than the guard being globally weakened."""
        node = self._node()
        ctx = self.T.ToolContext(working_node=node)
        bad = ('import maya.cmds as mc\n'
               'mc.connectAttr("a.t", "b.t", force=True)\n')
        res = self.T.dispatch("set_compute_expression", {"source": bad}, ctx)
        self.assertIn("error", res)
        # Non-vacuous: it must be the GUARD refusal, not some unrelated error.
        self.assertIn("forbidden", res["error"].lower())

    def test_syntax_error_is_rejected(self):
        node = self._node()
        ctx = self.T.ToolContext(working_node=node)
        res = self.T.dispatch("set_methods_source",
                              {"source": "def broken(:\n  pass\n"}, ctx)
        self.assertIn("error", res)
        # Non-vacuous: must be the SYNTAX rejection, not the unknown-tool error.
        self.assertIn("syntax", res["error"].lower())

    def test_get_node_surfaces_methods(self):
        node = self._node()
        ctx = self.T.ToolContext(working_node=node)
        self.T.dispatch("set_methods_source", {"source": _METHODS_SRC}, ctx)
        info = self.T.dispatch("get_node", {"node": node}, ctx)
        self.assertIn("methods_source", info)
        self.assertEqual(info["methods_source"], _METHODS_SRC)
        self.assertIn("setMeshRegion", info.get("commands", []))

    def test_define_node_applies_methods(self):
        ctx = self.T.ToolContext()
        res = self.T.dispatch("define_node",
                              {"node_type": "mPyNode", "methods": _METHODS_SRC},
                              ctx)
        self.assertNotIn("error", res, "define_node errored: %r" % res)
        self.assertTrue(res.get("set_methods"))
        import mpynode
        w = mpynode.wrap_node(res["node"])
        self.assertEqual(w.get_methods_source(), _METHODS_SRC)

    def test_tool_summary(self):
        self.assertEqual(
            self.T.tool_summary("set_methods_source", {}),
            "set_methods_source",
        )


class TestSystemPromptTeachesMethods(unittest.TestCase):
    """API providers (anthropic / gemini / openai) learn the API via
    build_system_prompt -- so it, too, must teach the Methods tab + the real
    @maya_command decorator + the set_methods_source tool. This is what makes the
    feature provider-agnostic, not just a Claude-CLI thing."""

    def test_system_prompt_mentions_methods_decorator_and_tool(self):
        from mpynode.ui.llm.system_prompt import build_system_prompt
        sp = build_system_prompt().lower()
        self.assertIn("method", sp)
        self.assertIn("maya_command", sp)
        self.assertIn("set_methods_source", sp)


class TestPayloadPromptTeachesMethods(unittest.TestCase):
    """The CLI providers author companion commands through the payload's
    "methods" field, so the payload prompt must teach the Methods tier + the real
    decorator (instead of dumping commands in Init)."""

    def test_payload_prompt_mentions_methods_and_decorator(self):
        from mpynode.ui.llm.system_prompt import build_payload_system_prompt
        sp = build_payload_system_prompt().lower()
        self.assertIn("method", sp)
        self.assertIn("maya_command", sp)
        self.assertIn('"methods"', sp)  # the payload field the model fills


class TestMethodsToolAvailableToApiProviders(unittest.TestCase):
    """The API providers still author Methods via the set_methods_source tool, so
    it must stay in the tool schema with its teaching description."""

    def test_tool_schema_surfaces_methods_tool_with_teaching(self):
        from mpynode.ui.llm import tools as T
        by_name = {t["name"]: t for t in T.TOOL_SCHEMAS}
        self.assertIn("set_methods_source", by_name)
        tool = by_name["set_methods_source"]
        self.assertIn("maya_command", tool.get("description", "").lower())
        self.assertIn("source", tool["input_schema"]["properties"])


class TestStripPayloadForDisplay(unittest.TestCase):
    """The chat transcript must NOT show the raw fenced .mpn payload the CLI
    providers emit (it is applied via the tool spine, not conversation), while
    keeping prose and ordinary code fences -- and the payload must remain
    extractable for the apply path."""

    def _s(self):
        from mpynode.ui.llm import payload
        return payload

    def test_payload_only_reply_becomes_empty(self):
        p = self._s()
        txt = '```json\n{"native_type":"mPyMesh","expression":"x=1"}\n```'
        self.assertEqual(p.strip_payload_for_display(txt), "")
        self.assertIsNotNone(p.extract_payload(txt))  # still applied

    def test_payload_then_prose_keeps_prose(self):
        p = self._s()
        txt = ('```json\n{"native_type":"mPyMesh","expression":"x=1"}\n```\n\n'
               'I built a Game of Life mesh node.')
        out = p.strip_payload_for_display(txt)
        self.assertEqual(out, "I built a Game of Life mesh node.")
        self.assertNotIn("```", out)

    def test_prose_only_is_untouched(self):
        p = self._s()
        txt = "I need more detail before I can build that node."
        self.assertEqual(p.strip_payload_for_display(txt), txt)

    def test_non_payload_code_fence_is_kept(self):
        p = self._s()
        txt = "Use:\n```python\nprint(1)\n```\nThanks."
        self.assertEqual(p.strip_payload_for_display(txt), txt)

    def test_bare_unfenced_payload_becomes_empty(self):
        p = self._s()
        txt = '{"native_type":"mPyNode","expression":"z=3"}'
        self.assertEqual(p.strip_payload_for_display(txt), "")


# ===================== CLI binary resolution (off-PATH fallback) =============
import unittest.mock


class TestResolveCliBinFallback(unittest.TestCase):
    """The porter/optimizer must resolve `claude` even when it is off the
    process PATH (a dock-launched Maya inherits the minimal launchd PATH), by
    delegating to toolchain.find_executable rather than a bare shutil.which."""

    def setUp(self):
        # A stray CLAUDE_BIN would short-circuit the bare-name resolution path.
        self._saved = os.environ.pop("CLAUDE_BIN", None)

    def tearDown(self):
        if self._saved is not None:
            os.environ["CLAUDE_BIN"] = self._saved

    def test_resolve_cli_bin_uses_toolchain_find_executable(self):
        from mpynode.native.ai import llm_client

        with unittest.mock.patch.object(
                llm_client.toolchain, "find_executable",
                return_value="/usr/local/bin/claude") as fe:
            self.assertEqual(llm_client._resolve_cli_bin("claude_cli"),
                             "/usr/local/bin/claude")
            fe.assert_called_once_with("claude")

    def test_resolve_cli_bin_raises_when_truly_absent(self):
        from mpynode.native.ai import llm_client

        with unittest.mock.patch.object(llm_client.toolchain,
                                        "find_executable", return_value=None):
            with self.assertRaises(RuntimeError):
                llm_client._resolve_cli_bin("claude_cli")

    def test_check_provider_ok_when_fallback_resolves(self):
        from mpynode.native.ai import llm_client

        with unittest.mock.patch.object(llm_client.toolchain,
                                        "find_executable",
                                        return_value="/usr/local/bin/claude") as fe:
            res = llm_client.check_provider("claude_cli")
        # Load-bearing: a revert to a bare shutil.which never consults
        # find_executable, so this call-assert regresses even though `claude`
        # happens to be on PATH in the test env.
        fe.assert_called_once_with("claude")
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["kind"], "cli")


class TestClaudeCliSendGate(unittest.TestCase):
    """The interactive AI Assistant's `send()` must gate on
    toolchain.find_executable (off-PATH fallback), not a bare shutil.which --
    otherwise a dock-launched Maya reports 'claude not found' and the whole
    panel is dead even though `claude` works in a terminal."""

    def test_send_gate_routes_through_find_executable(self):
        from mpynode.ui.llm import claude_cli_client as cc

        client = cc.ClaudeCliClient()
        self.addCleanup(client.deleteLater)
        errs = []
        client.errorOccurred.connect(errs.append)
        with unittest.mock.patch.object(cc.toolchain, "find_executable",
                                        return_value=None) as fe:
            client.send("hi")
        fe.assert_called_once()
        self.assertTrue(errs)
        self.assertIn("not found", errs[0].lower())


class TestBaseCliSendGate(unittest.TestCase):
    """Same off-PATH fallback gate for the shared gemini/codex CLI base."""

    def test_send_gate_routes_through_find_executable(self):
        from mpynode.ui.llm import cli_base

        class _Stub(cli_base.BaseCliClient):
            def _bin(self):
                return "gemini"

            def _build_cmd(self, prompt, images):
                return ["gemini", "-p", prompt]

            def _handle_event(self, line):
                pass

        client = _Stub()
        self.addCleanup(client.deleteLater)
        errs = []
        client.errorOccurred.connect(errs.append)
        with unittest.mock.patch.object(cli_base.toolchain, "find_executable",
                                        return_value=None) as fe:
            client.send("hi")
        fe.assert_called_once()
        self.assertTrue(errs)
        self.assertIn("not found", errs[0].lower())



# ---------------------------------------------------------------------------
# Auth failure: the CLI reports a logged-out session on STDOUT and still exits
# 1 with an EMPTY stderr, so reporting the return code alone showed the user
# "claude exited 1" and nothing about the cure.
# ---------------------------------------------------------------------------


class _FakeProc(object):
    """Minimal stand-in for the Popen the CLI clients drive."""

    def __init__(self, lines=(), rc=0, stderr=""):
        import io as _io

        self.stdout = iter(list(lines))
        self.stderr = _io.StringIO(stderr)
        self.stdin = None
        self.returncode = rc

    def wait(self):
        return self.returncode

    def terminate(self):
        pass


def _auth_stream():
    """The two events a logged-out ``claude -p`` really emits, trimmed."""
    import json as _json

    msg = ("Failed to authenticate: OAuth session expired and could not be "
           "refreshed")
    return [
        _json.dumps({"type": "assistant",
                     "message": {"role": "assistant",
                                 "content": [{"type": "text", "text": msg}]},
                     "error": "authentication_failed",
                     "is_api_error_message": True}),
        _json.dumps({"type": "result", "subtype": "success", "is_error": True,
                     "terminal_reason": "api_error", "result": msg}),
    ]


class TestAuthFailureDetection(unittest.TestCase):
    """``auth_failure`` is pure and keys off the machine-readable code, not
    prose -- the sentence differs by WHY auth failed (no token on disk vs a
    rejected one) while the code does not."""

    def test_error_code_on_assistant_event(self):
        self.assertTrue(cc.auth_failure({"type": "assistant",
                                         "error": "authentication_failed"}))

    def test_expired_token_code(self):
        self.assertTrue(cc.auth_failure({"error": "oauth_token_expired"}))

    def test_result_event_no_token_on_disk(self):
        self.assertTrue(cc.auth_failure({
            "type": "result", "is_error": True,
            "result": "Failed to authenticate: OAuth session expired and "
                      "could not be refreshed"}))

    def test_result_event_rejected_token(self):
        # Different sentence, same failure -- the case a prose match on
        # "OAuth session expired" would miss.
        self.assertTrue(cc.auth_failure({
            "type": "result", "is_error": True,
            "result": "Failed to authenticate. API Error: 401 OAuth access "
                      "token is invalid."}))

    def test_unrelated_error_is_not_auth(self):
        self.assertFalse(cc.auth_failure({"type": "result", "is_error": True,
                                          "result": "Compilation failed"}))

    def test_healthy_result(self):
        self.assertFalse(cc.auth_failure({"type": "result", "is_error": False,
                                          "result": "done"}))

    def test_non_dict_is_safe(self):
        self.assertFalse(cc.auth_failure("not a dict"))
        self.assertFalse(cc.auth_failure(None))

    def test_hint_names_both_recovery_routes(self):
        # A hint that does not say what to RUN is the bug this replaced.
        self.assertIn("claude auth login", cc._AUTH_HINT)
        self.assertIn("claude setup-token", cc._AUTH_HINT)
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", cc._AUTH_HINT)


class TestAuthFailureReporting(unittest.TestCase):
    """End of turn: a logged-out CLI must surface the cure, not the exit code."""

    def _client(self):
        client = cc.ClaudeCliClient()
        self.addCleanup(client.deleteLater)
        return client

    def test_auth_failure_emits_the_hint(self):
        client = self._client()
        errs = []
        client.errorOccurred.connect(errs.append)
        proc = _FakeProc(_auth_stream(), rc=1, stderr="")
        with unittest.mock.patch.object(cc.subprocess, "Popen",
                                        return_value=proc):
            client._run("hi", [])
        self.assertEqual(len(errs), 1, errs)
        self.assertIn("claude auth login", errs[0])
        self.assertNotIn("exited 1", errs[0])

    def test_non_auth_failure_still_reports_exit_code(self):
        client = self._client()
        errs = []
        client.errorOccurred.connect(errs.append)
        proc = _FakeProc([], rc=2, stderr="segfault")
        with unittest.mock.patch.object(cc.subprocess, "Popen",
                                        return_value=proc):
            client._run("hi", [])
        self.assertEqual(len(errs), 1, errs)
        self.assertIn("exited 2", errs[0])
        self.assertIn("segfault", errs[0])

    def test_flag_resets_between_turns(self):
        # A stale flag would mislabel the NEXT unrelated failure as an auth
        # problem, sending the user to re-login over a segfault.
        client = self._client()
        with unittest.mock.patch.object(
                cc.subprocess, "Popen",
                return_value=_FakeProc(_auth_stream(), rc=1)):
            client._run("hi", [])
        self.assertTrue(client._auth_failed)
        errs = []
        client.errorOccurred.connect(errs.append)
        with unittest.mock.patch.object(
                cc.subprocess, "Popen",
                return_value=_FakeProc([], rc=3, stderr="boom")):
            client._run("hi", [])
        self.assertFalse(client._auth_failed)
        self.assertIn("exited 3", errs[0])


class TestCliStdinIsDevNull(unittest.TestCase):
    """stdin=None INHERITS Maya stdin. A GUI Maya has no console, so the agent
    blocks on a handle that never delivers -- the Claude CLI charges 3s per
    request for that ("no stdin data received in 3s") before proceeding. Only
    the image path, which really feeds a stream-json message, gets a PIPE."""

    def _captured_stdin(self, popen_mock):
        self.assertTrue(popen_mock.called)
        return popen_mock.call_args[1]["stdin"]

    def test_claude_text_turn_uses_devnull(self):
        import subprocess as _sp

        client = cc.ClaudeCliClient()
        self.addCleanup(client.deleteLater)
        with unittest.mock.patch.object(cc.subprocess, "Popen",
                                        return_value=_FakeProc()) as po:
            client._run("hi", [])
        self.assertIs(self._captured_stdin(po), _sp.DEVNULL)

    def test_claude_image_turn_still_uses_a_pipe(self):
        import subprocess as _sp

        client = cc.ClaudeCliClient()
        self.addCleanup(client.deleteLater)
        images = [{"name": "a.png", "data": "AAAA", "media_type": "image/png"}]
        with unittest.mock.patch.object(cc.subprocess, "Popen",
                                        return_value=_FakeProc()) as po:
            client._run("hi", images)
        self.assertIs(self._captured_stdin(po), _sp.PIPE)

    def test_shared_cli_base_uses_devnull(self):
        import subprocess as _sp

        from mpynode.ui.llm import cli_base

        class _Stub(cli_base.BaseCliClient):
            def _bin(self):
                return "gemini"

            def _build_cmd(self, prompt, images):
                return ["gemini", "-p", prompt]

            def _handle_event(self, line):
                pass

        client = _Stub()
        self.addCleanup(client.deleteLater)
        with unittest.mock.patch.object(cli_base.subprocess, "Popen",
                                        return_value=_FakeProc()) as po:
            client._run("hi", [])
        self.assertIs(self._captured_stdin(po), _sp.DEVNULL)


# ---------------------------------------------------------------------------
# enum_names had to survive three layers to reach the plug, and cleared none of
# them: the tool schema had no slot, payload._norm_attr_list rebuilt each spec
# from a whitelist, and the apply sites read a whitelist too. The plug came out
# as the documented bare False/True enum and every result reported success, so
# the model kept insisting it had set field names it never actually sent.
# ---------------------------------------------------------------------------

_ROTATE_ORDERS = ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"]


class TestEnumNamesInSchema(unittest.TestCase):
    """A key the schema does not declare is a key the model cannot send."""

    def test_batched_input_item_declares_it(self):
        from mpynode.ui.llm import tools as T

        self.assertIn("enum_names", T._INPUT_ITEM["properties"])

    def test_batched_output_item_declares_it(self):
        from mpynode.ui.llm import tools as T

        self.assertIn("enum_names", T._OUTPUT_ITEM["properties"])

    def test_standalone_add_tools_declare_it(self):
        from mpynode.ui.llm import tools as T

        seen = {}
        for spec in T.TOOL_SCHEMAS:
            if spec["name"] in ("add_input", "add_output"):
                seen[spec["name"]] = spec["input_schema"]["properties"]
        self.assertEqual(sorted(seen), ["add_input", "add_output"])
        for name, props in seen.items():
            self.assertIn("enum_names", props, name)

    def test_it_is_an_array_of_strings(self):
        from mpynode.ui.llm import tools as T

        prop = T._INPUT_ITEM["properties"]["enum_names"]
        self.assertEqual(prop["type"], "array")
        self.assertEqual(prop["items"]["type"], "string")


class TestNormAttrListPreservesEnumNames(unittest.TestCase):
    """payload._norm_attr_list is on the CLI provider's path -- it ran before
    the apply layer and stripped the key first."""

    def test_define_node_shaped_list(self):
        from mpynode.ui.llm import payload as P

        out = P._norm_attr_list([{"name": "rotateOrder", "type": "enum",
                                  "enum_names": _ROTATE_ORDERS}])
        self.assertEqual(out[0]["enum_names"], _ROTATE_ORDERS)

    def test_raw_mpn_attr_map(self):
        from mpynode.ui.llm import payload as P

        out = P._norm_attr_list({"rotateOrder": {"attr_type": "enum",
                                                 "enum_names": _ROTATE_ORDERS}})
        self.assertEqual(out[0]["enum_names"], _ROTATE_ORDERS)

    def test_unknown_keys_ride_through(self):
        # They used to be dropped here, which is why the apply layer never got
        # the chance to report them.
        from mpynode.ui.llm import payload as P

        out = P._norm_attr_list([{"name": "a", "type": "float", "bogusKey": 7}])
        self.assertEqual(out[0]["bogusKey"], 7)

    def test_known_keys_still_normalize(self):
        from mpynode.ui.llm import payload as P

        out = P._norm_attr_list({"a": {"attr_type": "float", "min_value": 1,
                                       "max_value": 2, "default_value": 1.5,
                                       "is_array": True}})
        self.assertEqual(out[0]["min"], 1)
        self.assertEqual(out[0]["max"], 2)
        self.assertEqual(out[0]["default"], 1.5)
        self.assertTrue(out[0]["is_array"])


class TestAttrKwargs(unittest.TestCase):
    """The single builder all four apply sites now share. Pure."""

    def test_input_mapping(self):
        from mpynode.ui.llm import tools as T

        got = T.attr_kwargs({"name": "a", "type": "float", "min": 0, "max": 1,
                             "default": 0.5, "is_array": True}, T._INPUT_EXTRA)
        self.assertEqual(got, {"min_value": 0, "max_value": 1,
                               "default_value": 0.5, "is_array": True})

    def test_enum_names_reaches_the_wrapper_kwarg(self):
        from mpynode.ui.llm import tools as T

        got = T.attr_kwargs({"name": "rotateOrder", "type": "enum",
                             "enum_names": _ROTATE_ORDERS}, T._INPUT_EXTRA)
        self.assertEqual(got["enum_names"], _ROTATE_ORDERS)

    def test_outputs_take_enum_names_but_not_limits(self):
        from mpynode.ui.llm import tools as T

        got = T.attr_kwargs({"name": "o", "type": "enum", "min": 0,
                             "enum_names": _ROTATE_ORDERS}, T._OUTPUT_EXTRA,
                            [])
        self.assertEqual(got["enum_names"], _ROTATE_ORDERS)
        self.assertNotIn("min_value", got)

    def test_bare_enum_raises(self):
        from mpynode.ui.llm import tools as T

        with self.assertRaises(ValueError) as cm:
            T.attr_kwargs({"name": "rotateOrder", "type": "enum"},
                          T._INPUT_EXTRA)
        self.assertIn("enum_names", str(cm.exception))

    def test_unknown_key_warns_without_raising(self):
        from mpynode.ui.llm import tools as T

        warnings = []
        got = T.attr_kwargs({"name": "a", "type": "float", "bogusKey": 1},
                            T._INPUT_EXTRA, warnings)
        self.assertEqual(got, {})
        self.assertEqual(len(warnings), 1)
        self.assertIn("bogusKey", warnings[0])

    def test_spec_keys_are_never_warned_about(self):
        from mpynode.ui.llm import tools as T

        warnings = []
        T.attr_kwargs({"name": "a", "type": "float", "attr_type": "float",
                       "node": "n"}, T._INPUT_EXTRA, warnings)
        self.assertEqual(warnings, [])

    def test_warnings_render_in_the_transcript(self):
        from mpynode.ui.llm import tools as T

        line = T.compact_result("define_node",
                                {"node": "n", "added_inputs": ["a"],
                                 "warnings": ["a: ignored unknown key 'x'"]})
        self.assertIn("ignored unknown key", line)


class TestEnumEndToEnd(unittest.TestCase):
    """Through the real dispatch spine, which is what both the HTTP tool
    bridge and the CLI payload path call."""

    def _dispatch(self, inputs, name):
        from mpynode.ui.llm import tools as T

        return T.dispatch("define_node",
                          {"node_type": "mPyNode", "name": name,
                           "inputs": inputs}, T.ToolContext())

    def test_named_enum_matches_mayas_own_rotate_order(self):
        import maya.cmds as mc

        res = self._dispatch([{"name": "rotateOrder", "type": "enum",
                               "enum_names": _ROTATE_ORDERS}], "enumOk")
        self.assertIsNone(res.get("error"), res)
        node = res.get("created") or res.get("node")
        self.addCleanup(lambda: mc.objExists(node) and mc.delete(node))
        self.assertEqual(
            mc.attributeQuery("rotateOrder", node=node, listEnum=True),
            ["xyz:yzx:zxy:xzy:yxz:zyx"])

    def test_bare_enum_errors_and_leaves_no_orphan(self):
        import maya.cmds as mc

        before = set(mc.ls(type="mPyNode"))
        res = self._dispatch([{"name": "rotateOrder", "type": "enum"}],
                             "enumBare")
        self.assertIn("error", res)
        self.assertIn("enum_names", res["error"])
        self.assertEqual(set(mc.ls(type="mPyNode")) - before, set())


# ---------------------------------------------------------------------------
# The prompt described MatrixView purely as "numpy-transparent, do not recast"
# and never mentioned that it carries the whole MMatrix + MTransformationMatrix
# surface. A model told only that it behaves like numpy reasonably writes its
# own matrix->euler in Init -- which is what it did.
# ---------------------------------------------------------------------------


class TestPromptTeachesPromotedTypes(unittest.TestCase):
    """Both prompts, because they are separate strings: build_system_prompt
    feeds the HTTP tool-bridge clients and build_payload_system_prompt feeds
    the CLI providers. A fix applied to one is invisible to the other."""

    def _prompts(self):
        from mpynode.ui.llm.system_prompt import (build_payload_system_prompt,
                                                  build_system_prompt)

        return {"tool-bridge": build_system_prompt(),
                "payload": build_payload_system_prompt()}

    def test_reader_methods_are_named(self):
        # Named, not merely alluded to: the model cannot invent a method
        # signature it has never been shown and have it be right.
        for label, p in self._prompts().items():
            for m in ("m.translation()", "m.rotation()", "m.scale()",
                      "m.rotationOrder()"):
                self.assertIn(m, p, "%s prompt missing %s" % (label, m))

    def test_chainable_matrix_returns_are_named(self):
        for label, p in self._prompts().items():
            for m in ("m.inverse()", "m.asRotateMatrix()", "m.det4x4()"):
                self.assertIn(m, p, "%s prompt missing %s" % (label, m))

    def test_array_view_methods_are_named(self):
        for label, p in self._prompts().items():
            self.assertIn("A.translation()", p, label)
            self.assertIn("A.rotation(axes=N)", p, label)

    def test_rotate_order_indices_match_the_enum(self):
        # Same 0..5 ordering as a rotateOrder enum plug and as
        # promoted_types._EULER_ORDERS; a mismatch here silently rotates wrong.
        for label, p in self._prompts().items():
            self.assertIn("0=xyz 1=yzx 2=zxy 3=xzy 4=yxz 5=zyx", p, label)

    def test_enum_reads_are_advertised_as_EnumInt(self):
        for label, p in self._prompts().items():
            self.assertIn("EnumInt", p, label)
            self.assertIn(".name()", p, label)
            self.assertNotIn("enum -> int", p, label)

    def test_the_lowering_status_is_stated(self):
        # This line was the opposite claim until the methods were lowered: the
        # prompt used to warn that only .asNumpy() reached C++. It must track
        # the transpiler, in either direction -- a stale pessimistic caveat
        # steers the assistant away from calls that now lower perfectly well.
        for label, p in self._prompts().items():
            self.assertIn("LOWER to C++ deterministically", p, label)
            self.assertNotIn("only .asNumpy() lowers to C++", p, label)

    def test_the_non_lowering_exclusions_are_named(self):
        # Setters and pivots genuinely do NOT lower -- a compiled compute reads
        # a COPY, so mutation would not mean what it means interpreted.
        for label, p in self._prompts().items():
            self.assertIn("setTranslation", p, label)
            self.assertIn("do NOT lower", p, label)

    def test_the_names_are_real(self):
        # Guards the prompt against drift in the other direction: every method
        # advertised has to still exist on the class.
        from mpynode._common.plugs import promoted_types as PT

        for m in ("translation", "rotation", "scale", "shear", "inverse",
                  "transpose", "adjoint", "homogenize", "asRotateMatrix",
                  "asScaleMatrix", "asMatrixInverse", "det3x3", "det4x4",
                  "isSingular", "getElement", "rotationOrder",
                  "reorderRotation", "setTranslation", "setRotation",
                  "setScale", "setShear", "asNumpy"):
            self.assertTrue(hasattr(PT.MatrixView, m),
                            "prompt advertises MatrixView.%s, which is gone" % m)
        for m in ("translation", "rotation", "scale", "shear"):
            self.assertTrue(hasattr(PT.MatrixArrayView, m),
                            "prompt advertises MatrixArrayView.%s, gone" % m)

    def test_the_advertised_methods_actually_lower(self):
        # The prompt's claim is about the transpiler, so assert it against the
        # transpiler rather than trusting the sentence. This test previously
        # asserted the OPPOSITE (that only asNumpy lowered) and failing was how
        # it forced the prompt to be corrected when the ops landed.
        import io
        import os

        from tests import _paths

        src = io.open(os.path.join(_paths.ROOT, "scripts", "mpynode",
                                   "native", "compiler", "py_to_cpp.py"),
                      encoding="utf-8").read()
        for m in ("asNumpy", "translation", "rotation", "rotationOrder",
                  "scale", "shear", "inverse", "getElement", "det3x3",
                  "det4x4", "isSingular", "asRotateMatrix", "asScaleMatrix",
                  "asMatrixInverse", "adjoint", "homogenize"):
            self.assertIn('"%s":' % m, src,
                          "the prompt advertises .%s as lowering, but it has "
                          "no _ARRAY_OPS entry" % m)

    def test_the_excluded_methods_do_not_lower(self):
        # Mutators must stay unlowered: see the prompt exclusion above.
        import io
        import os

        from tests import _paths

        src = io.open(os.path.join(_paths.ROOT, "scripts", "mpynode",
                                   "native", "compiler", "py_to_cpp.py"),
                      encoding="utf-8").read()
        for m in ("setTranslation", "setRotation", "setScale", "setShear",
                  "rotatePivot", "scalePivot"):
            self.assertNotIn('"%s":' % m, src,
                             "%s lowers now -- a compiled compute mutates a "
                             "COPY, so decide what that means before "
                             "advertising it" % m)

def setUpModule():
    _setUpModule__assistant_model_order()
    _setUpModule__assistant_cli_client()
    _setUpModule__assistant_node_targeting()
    _setUpModule__assistant_methods_tool()


if __name__ == "__main__":
    import unittest
    unittest.main()
