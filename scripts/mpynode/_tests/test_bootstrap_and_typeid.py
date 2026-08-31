"""The install bootstrap (``mpynode.ini``) + deterministic MTypeId assignment.

Two changes are pinned here:

  * every writable location resolves env -> mpynode.ini -> built-in default, so a
    studio can relocate the home (or just the compile output) by editing ONE file
    that ships next to the code, while env keeps overriding for tests/CI;
  * MTypeIds are DERIVED from the node's Class rather than allocated out of a
    per-user registry file. Same Class -> same id, on any machine, with nothing
    to write -- so an unwritable home can no longer fail a build.
"""
import json
import os
import tempfile
import unittest

from mpynode._tests import _setup  # noqa: F401  (env + sys.path)

from mpynode._common import bootstrap, home
from mpynode._common.lifecycle import metadata_registry as md
from mpynode.native.toolchain import port_cache, typeid_registry


class _Env:
    """Set/restore env vars around a block."""

    def __init__(self, **kw):
        self._kw = kw
        self._saved = {}

    def __enter__(self):
        for k, v in self._kw.items():
            self._saved[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        bootstrap._reset_for_tests()
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        bootstrap._reset_for_tests()
        return False


def _write_ini(d, text):
    path = os.path.join(d, "mpynode.ini")
    with open(path, "w") as fh:
        fh.write(text)
    return path


# ---------------------------------------------------------------------------
# bootstrap
# ---------------------------------------------------------------------------
class TestBootstrapFile(unittest.TestCase):
    def test_ships_next_to_the_code(self):
        """The canonical location is inside the package, so it is reachable
        whenever the code is importable -- no env needed to FIND the config."""
        pkg_ini = bootstrap._package_config()
        self.assertTrue(pkg_ini.endswith(os.path.join("mpynode", "mpynode.ini")))
        self.assertTrue(os.path.isfile(pkg_ini),
                        "the shipped mpynode.ini must exist at %s" % pkg_ini)

    def test_shipped_file_changes_nothing(self):
        """Every entry ships commented out, so a stock install behaves exactly as
        it did before the file existed."""
        with _Env(MPYNODE_CONFIG=None, MPYNODE_HOME=None):
            self.assertIsNone(bootstrap.path("home"))
            self.assertEqual(home.home_dir(),
                             os.path.join(os.path.expanduser("~"), "mpynode"))

    def test_ini_redirects_the_home(self):
        with tempfile.TemporaryDirectory() as d:
            # Build the ini value and the expectation from ONE os.path.join.
            # Hardcoding "%s/data" made the ini say C:\...\tmp/data while the
            # assertion said C:\...\tmp\data, so this failed on Windows purely
            # on the separator (the value round-trips correctly either way).
            target = os.path.join(d, "data")
            ini = _write_ini(d, "[paths]\nhome = %s\n" % target)
            with _Env(MPYNODE_CONFIG=ini, MPYNODE_HOME=None):
                self.assertEqual(home.home_dir(), target)

    def test_env_beats_the_ini(self):
        """Env must stay on top: the whole test suite and every harness script
        drives MPYNODE_HOME."""
        with tempfile.TemporaryDirectory() as d:
            ini = _write_ini(d, "[paths]\nhome = %s/from-ini\n" % d)
            with _Env(MPYNODE_CONFIG=ini, MPYNODE_HOME=os.path.join(d, "from-env")):
                self.assertEqual(home.home_dir(), os.path.join(d, "from-env"))

    def test_locations_relocate_independently(self):
        """The point of splitting them: move ONLY the compile output."""
        with tempfile.TemporaryDirectory() as d:
            data = os.path.join(d, "data")
            plugins = os.path.join(d, "plugins")
            ini = _write_ini(
                d, "[paths]\nhome = %s\ncompiled = %s\n" % (data, plugins))
            with _Env(MPYNODE_CONFIG=ini, MPYNODE_HOME=None,
                      MPYNODE_COMPILED=None, MPYNODE_PORT_CACHE=None):
                self.assertEqual(home.compiled_dir(), plugins)
                # everything unset still hangs off the home
                self.assertEqual(home.port_cache_dir(),
                                 os.path.join(data, "port_cache"))

    def test_relative_paths_resolve_against_the_ini(self):
        """So a self-contained checkout can stay portable."""
        with tempfile.TemporaryDirectory() as d:
            sub = os.path.join(d, "install")
            os.makedirs(sub)
            ini = _write_ini(sub, "[paths]\nhome = ../local-home\n")
            with _Env(MPYNODE_CONFIG=ini, MPYNODE_HOME=None):
                self.assertEqual(home.home_dir(),
                                 os.path.join(d, "local-home"))

    def test_user_and_var_expansion(self):
        with tempfile.TemporaryDirectory() as d:
            ini = _write_ini(d, "[paths]\nhome = %s\n"
                             % os.path.join("$MPY_TEST_ROOT", "h"))
            with _Env(MPYNODE_CONFIG=ini, MPYNODE_HOME=None,
                      MPY_TEST_ROOT=d):
                self.assertEqual(home.home_dir(), os.path.join(d, "h"))

    def test_broken_ini_falls_through_to_defaults(self):
        """A malformed config must never stop Node Designer from starting."""
        with tempfile.TemporaryDirectory() as d:
            ini = _write_ini(d, "this is not ini at all ][\n")
            with _Env(MPYNODE_CONFIG=ini, MPYNODE_HOME=None):
                self.assertEqual(home.home_dir(),
                                 os.path.join(os.path.expanduser("~"), "mpynode"))

    def test_blank_value_reads_as_unset(self):
        with tempfile.TemporaryDirectory() as d:
            ini = _write_ini(d, "[paths]\nhome =\n")
            with _Env(MPYNODE_CONFIG=ini, MPYNODE_HOME=None):
                self.assertEqual(home.home_dir(),
                                 os.path.join(os.path.expanduser("~"), "mpynode"))

    def test_typeid_base_is_configurable(self):
        with tempfile.TemporaryDirectory() as d:
            ini = _write_ini(d, "[typeid]\nbase = 0x00020000\nend = 0x00020fff\n")
            with _Env(MPYNODE_CONFIG=ini):
                self.assertEqual(typeid_registry.configured_base(), 0x00020000)
                self.assertEqual(typeid_registry.configured_end(), 0x00020FFF)
                got = typeid_registry.deterministic_id("someNode")
                self.assertTrue(0x00020000 <= got <= 0x00020FFF)


# ---------------------------------------------------------------------------
# deterministic ids
# ---------------------------------------------------------------------------
class TestDeterministicId(unittest.TestCase):
    def test_same_key_same_id_across_instances(self):
        """The .mb argument: a rebuild must not silently orphan saved nodes."""
        a = typeid_registry.TypeIdRegistry(path="/nonexistent/pins.json")
        b = typeid_registry.TypeIdRegistry(path="/nonexistent/pins.json")
        self.assertEqual(a.allocate("patchRelax"), b.allocate("patchRelax"))

    def test_id_is_not_process_salted(self):
        """sha256, not hash() -- a salted hash would give a different id every
        Maya session, which is the exact failure this scheme exists to avoid."""
        self.assertEqual(typeid_registry.deterministic_id("kdTree", 0x10000,
                                                          0x7FFFF),
                         typeid_registry.deterministic_id("kdTree", 0x10000,
                                                          0x7FFFF))
        self.assertEqual(
            "0x%08x" % typeid_registry.deterministic_id("kdTree", 0x10000,
                                                        0x7FFFF),
            "0x%08x" % typeid_registry.deterministic_id("kdTree", 0x10000,
                                                        0x7FFFF))

    def test_distinct_keys_get_distinct_ids(self):
        reg = typeid_registry.TypeIdRegistry(path="/nonexistent/pins.json")
        names = ["nodeA", "nodeB", "nodeC", "nodeD", "nodeE"]
        got = reg.allocate_many(names)
        self.assertEqual(len(set(got.values())), len(names))

    def test_ids_stay_inside_mayas_range(self):
        reg = typeid_registry.TypeIdRegistry(path="/nonexistent/pins.json")
        for nm in ("a", "zzz", "someVeryLongNodeTypeName", "1"):
            val = int(reg.allocate(nm), 16)
            self.assertGreaterEqual(val, typeid_registry.DEFAULT_BASE)
            self.assertLessEqual(val, 0x0007FFFF)

    def test_no_file_is_written_by_a_build(self):
        """The EPERM class of failure, gone: resolving ids touches no disk."""
        with tempfile.TemporaryDirectory() as d:
            pins = os.path.join(d, "pins.json")
            reg = typeid_registry.TypeIdRegistry(path=pins)
            reg.allocate_many(["one", "two", "three"])
            self.assertFalse(os.path.exists(pins),
                             "a compile must not write the pin file")

    def test_unwritable_home_does_not_break_allocation(self):
        reg = typeid_registry.TypeIdRegistry(path="/proc/definitely/not/writable")
        self.assertTrue(reg.allocate("stillWorks").startswith("0x"))

    def test_allocate_is_idempotent_within_a_build(self):
        reg = typeid_registry.TypeIdRegistry(path="/nonexistent/pins.json")
        first = reg.allocate("dup")
        self.assertEqual(first, reg.allocate("dup"))
        self.assertEqual(first, reg.allocate_many(["dup"])["dup"])


class TestCollisionHandling(unittest.TestCase):
    """A derived id is a hash, so an in-bundle clash is possible. It must be
    resolved deterministically AND reported -- never silently absorbed."""

    def test_collision_is_probed_and_recorded(self):
        # A 2-wide pool forces a clash within three keys.
        reg = typeid_registry.TypeIdRegistry(path="/nonexistent/pins.json",
                                             base=0x00070000, end=0x00070001)
        got = reg.allocate_many(["x", "y"])
        self.assertEqual(len(set(got.values())), 2, "ids must stay unique")
        if reg.collisions:
            name, wanted, final = reg.collisions[0]
            self.assertNotEqual(wanted, final)
            self.assertTrue(reg.sources[name].endswith("+probed"))

    def test_pool_exhaustion_is_a_clear_error(self):
        reg = typeid_registry.TypeIdRegistry(path="/nonexistent/pins.json",
                                             base=0x00070000, end=0x00070000)
        reg.allocate("first")
        with self.assertRaises(RuntimeError) as ctx:
            reg.allocate("second")
        self.assertIn("pool exhausted", str(ctx.exception))

    def test_two_nodes_in_a_bundle_never_share_an_id(self):
        reg = typeid_registry.TypeIdRegistry(path="/nonexistent/pins.json")
        names = ["n%03d" % i for i in range(200)]
        got = reg.allocate_many(names)
        self.assertEqual(len(set(got.values())), len(names))


class TestPinPrecedence(unittest.TestCase):
    def test_manual_pin_wins(self):
        reg = typeid_registry.TypeIdRegistry(path="/nonexistent/pins.json")
        reg.pin("myNode", "0x00012345")
        self.assertEqual(reg.allocate("myNode"), "0x00012345")
        self.assertEqual(reg.sources["myNode"], "pinned")

    def test_pin_file_is_read_but_never_written(self):
        """Ids already shipped keep working -- the legacy registry survives as a
        pure override."""
        with tempfile.TemporaryDirectory() as d:
            pins = os.path.join(d, "pins.json")
            with open(pins, "w") as fh:
                json.dump({"base": "0x00010000",
                           "map": {"legacyNode": "0x00078000"}}, fh)
            reg = typeid_registry.TypeIdRegistry(path=pins)
            self.assertEqual(reg.allocate("legacyNode"), "0x00078000")
            self.assertEqual(reg.sources["legacyNode"], "pin-file")
            reg.allocate("brandNew")
            with open(pins) as fh:
                self.assertEqual(json.load(fh)["map"],
                                 {"legacyNode": "0x00078000"},
                                 "resolving ids must not rewrite the pin file")

    def test_manual_pin_beats_the_pin_file(self):
        with tempfile.TemporaryDirectory() as d:
            pins = os.path.join(d, "pins.json")
            with open(pins, "w") as fh:
                json.dump({"map": {"n": "0x00078000"}}, fh)
            reg = typeid_registry.TypeIdRegistry(path=pins)
            reg.pin("n", "0x00011111")
            self.assertEqual(reg.allocate("n"), "0x00011111")

    def test_corrupt_pin_file_is_ignored_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            pins = os.path.join(d, "pins.json")
            with open(pins, "w") as fh:
                fh.write("{ not json")
            reg = typeid_registry.TypeIdRegistry(path=pins)
            self.assertTrue(reg.allocate("n").startswith("0x"))
            self.assertEqual(reg.sources["n"], "derived")

    def test_unusable_pin_is_rejected_so_the_derived_id_is_used(self):
        reg = typeid_registry.TypeIdRegistry(path="/nonexistent/pins.json")
        for bad in ("", "  ", "not-hex", "0x99999999", None):
            self.assertIsNone(reg.pin("n", bad), "%r must be rejected" % (bad,))
        self.assertEqual(reg.sources.get("n", ""), "")
        self.assertEqual(reg.allocate("n"), reg.get("n"))

    def test_write_pins_is_explicit_and_freezes_the_build(self):
        with tempfile.TemporaryDirectory() as d:
            pins = os.path.join(d, "pins.json")
            reg = typeid_registry.TypeIdRegistry(path=pins)
            reg.allocate_many(["a", "b"])
            reg.write_pins()
            with open(pins) as fh:
                doc = json.load(fh)
            self.assertEqual(sorted(doc["map"]), ["a", "b"])
            # Re-reading the frozen file must reproduce the same ids.
            again = typeid_registry.TypeIdRegistry(path=pins)
            self.assertEqual(again.allocate_many(["a", "b"]),
                             {k: v for k, v in doc["map"].items()})

    def test_get_previews_without_claiming(self):
        reg = typeid_registry.TypeIdRegistry(path="/nonexistent/pins.json")
        preview = reg.get("preview")
        self.assertEqual(reg.sources, {}, "get() must not allocate")
        self.assertEqual(reg.allocate("preview"), preview)


# ---------------------------------------------------------------------------
# the manual pin's route from the Node Info dialog to the allocator
# ---------------------------------------------------------------------------
class TestMetadataTypeIdField(unittest.TestCase):
    def test_type_id_is_a_metadata_field(self):
        self.assertIn("type_id", md.FIELDS)
        self.assertEqual(md.coerce({})["type_id"], "")

    def test_spellings_canonicalize_to_one_value(self):
        """Same pin written three ways must not split the port cache."""
        for spelling in ("0x0001a2b3", "0X1A2B3", "1a2b3", "  1A2B3  "):
            self.assertEqual(md.coerce({"type_id": spelling})["type_id"],
                             "0x0001a2b3", "failed for %r" % spelling)

    def test_garbage_is_kept_verbatim_so_the_typo_stays_visible(self):
        self.assertEqual(md.coerce({"type_id": "oops"})["type_id"], "oops")
        self.assertEqual(md.coerce({"type_id": "0x99999999"})["type_id"],
                         "0x99999999")

    def test_a_type_id_only_node_is_not_empty(self):
        """is_empty gates whether metadata reaches the spec at all -- a pin-only
        node must survive to the compile."""
        self.assertFalse(md.is_empty({"type_id": "0x00012345"}))
        self.assertTrue(md.is_empty({}))

    def test_type_id_never_inherits_a_global_default(self):
        """Inheriting one would hand every node the same id."""
        merged = md.merge_metadata({"version": ""},
                                   {"version": "9.9", "type_id": "0x00012345"})
        self.assertEqual(merged["version"], "9.9", "other fields still inherit")
        self.assertEqual(merged["type_id"], "")

    def test_pin_is_excluded_from_the_port_cache_key(self):
        """The id is rewritten by bundler and never survives into the binary, so
        changing it must not force a re-port -- and adding the field must not
        invalidate every existing entry."""
        base = {"suggested": {"node_type_name": "n"}, "compute": "pass"}
        with_meta = dict(base, metadata=md.coerce({"authors": ["A"]}))
        pinned = dict(base,
                      metadata=md.coerce({"authors": ["A"],
                                          "type_id": "0x00012345"}))
        self.assertEqual(
            port_cache.cache_key(with_meta, provider="p", model="m"),
            port_cache.cache_key(pinned, provider="p", model="m"))

    def test_pin_only_metadata_keys_the_same_as_no_metadata(self):
        """A node whose ONLY metadata is a pinned id is byte-identical in the
        generated C++ to a node with none -- so it must key identically too.

        Caught by tools/probe_pinned_typeid_end_to_end.py, NOT by the test above:
        that one has metadata on both sides, so it never exercised the case where
        pinning INTRODUCES the metadata dict. Leaving the emptied husk in the
        payload made merely pinning an id force a full LLM re-port."""
        base = {"suggested": {"node_type_name": "n"}, "compute": "pass"}
        pin_only = dict(base, metadata=md.coerce({"type_id": "0x00012345"}))
        self.assertEqual(
            port_cache.cache_key(base, provider="p", model="m"),
            port_cache.cache_key(pin_only, provider="p", model="m"))

    def test_real_metadata_still_keys_differently(self):
        """The emptied-husk drop must not swallow metadata that DOES reach the
        C++ banner -- otherwise an authorship edit would serve a stale .cpp."""
        base = {"suggested": {"node_type_name": "n"}, "compute": "pass"}
        authored = dict(base, metadata=md.coerce({"authors": ["A"]}))
        self.assertNotEqual(
            port_cache.cache_key(base, provider="p", model="m"),
            port_cache.cache_key(authored, provider="p", model="m"))

    def test_suggested_is_never_dropped_wholesale(self):
        """``suggested`` shares the nested-deny machinery; its surviving names
        ARE baked into the registered type string, so it must stay in the key."""
        a = {"suggested": {"node_type_name": "alpha", "type_id": "0x1"}}
        b = {"suggested": {"node_type_name": "beta", "type_id": "0x1"}}
        self.assertNotEqual(port_cache.cache_key(a, provider="p", model="m"),
                            port_cache.cache_key(b, provider="p", model="m"))


if __name__ == "__main__":
    unittest.main()
