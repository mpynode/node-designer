"""The unit suite never touches the user's real MPyNode home.

Importing the ``tests`` package points ``MPYNODE_HOME`` at a temp folder for the
run (``tests/__init__.py``). Every test module imports that package first,
before anything from the project, and ``tools/_unittest_exit.py`` imports it
before it loads a test. Before that, only ``tests/_setup.standalone_init`` set
the home, from a module's ``setUpModule``, so whatever came earlier used
``~/.mpynode``: ``test_optimizer_compile_hook`` run alone rewrote a real
port-cache entry, and ``preferences.PREFS_PATH``, read when the module is
imported, named the real ``preferences.json`` for a whole run. Then a module
run on its own, or discovered from its own folder, still reached it: 106
modules imported mpynode before the package or never imported it, and
``test_media_preview`` and ``test_editor_widgets`` run that way rewrote the
real ``preferences.json``.

``TestThisRunIsIsolated`` checks the process it runs in. ``TestEntryPoints``
runs it again in fresh processes, one per way a test is started, with the
user's folder moved to a temp folder and every home variable naming that
folder's ``.mpynode``. ``TestEveryModuleImportsTestsFirst`` checks the import
order of every test module.
"""

from __future__ import annotations

import tests  # noqa: F401 -- first: keeps the run out of ~/.mpynode

import ast
import os
import subprocess
import sys
import tempfile
import unittest

from mpynode._common import bootstrap, home
from mpynode.native.toolchain import port_cache
from mpynode.ui import preferences

from tests import _paths

_ME = "tests.authoring.test_suite_home_isolation"
_UT = os.path.join(_paths.ROOT, "tools", "_unittest_exit.py")

# A test module outside the tests package that imports mpynode before
# anything else: only _unittest_exit.py's own import of tests can have
# isolated the home by the time it loads.
_OUTSIDE = '''\
import os
import unittest

from mpynode._common import home
from mpynode.ui import preferences


def _inside(path, folder):
    path   = os.path.normcase(os.path.abspath(path))
    folder = os.path.normcase(os.path.abspath(folder))
    return path.startswith(folder.rstrip(os.sep) + os.sep)


class TestOutsideThePackage(unittest.TestCase):
    def test_the_home_is_a_test_home(self):
        self.assertTrue(os.path.basename(home.home_dir())
                        .startswith("mpynode-test-home-"), home.home_dir())

    def test_preferences_resolve_under_it(self):
        self.assertTrue(_inside(preferences.PREFS_PATH, home.home_dir()),
                        preferences.PREFS_PATH)

    def test_the_port_cache_resolves_under_it(self):
        from mpynode.native.toolchain import port_cache

        self.assertTrue(_inside(port_cache.cache_dir(), home.home_dir()),
                        port_cache.cache_dir())
'''


def _norm(path):
    return os.path.normcase(os.path.abspath(path))


def _inside(path, folder):
    """``path`` is ``folder`` or under it."""
    path, folder = _norm(path), _norm(folder)
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def _real_homes():
    """Every home MPyNode would have used without the tests package."""
    out = [os.path.join(tests.USER_DIR, ".mpynode")]
    if tests.OUTER_HOME:
        out.append(tests.OUTER_HOME)
    if bootstrap.path("home"):
        out.append(bootstrap.path("home"))
    return out


class TestThisRunIsIsolated(unittest.TestCase):
    def test_the_home_is_a_temp_folder_for_this_run(self):
        run = tests.isolate_home()
        self.assertEqual(os.environ.get(tests.HOME_ENV), run)
        self.assertEqual(_norm(home.home_dir()), _norm(run))
        self.assertTrue(os.path.isdir(run), run)
        self.assertTrue(os.path.basename(run).startswith("mpynode-test-home-"),
                        run)
        self.assertTrue(_inside(run, tempfile.gettempdir()),
                        "%s is not under the temp folder %s"
                        % (run, tempfile.gettempdir()))

    def test_the_home_is_outside_the_users_real_home(self):
        run = home.home_dir()
        for real in _real_homes():
            self.assertFalse(_inside(run, real) or _inside(real, run),
                             "the run's home %s overlaps %s" % (run, real))

    def test_every_location_resolves_under_it(self):
        run = home.home_dir()
        paths = {
            "preferences.PREFS_PATH":  preferences.PREFS_PATH,
            "preferences.PREFS_DIR":   preferences.PREFS_DIR,
            "home.preferences_path()": home.preferences_path(),
            "port_cache.cache_dir()":  port_cache.cache_dir(),
            "home.trust_store_path()": home.trust_store_path(),
            "home.typeid_pins_path()": home.typeid_pins_path(),
            "home.compiled_dir()":     home.compiled_dir(),
        }
        for name, path in paths.items():
            self.assertTrue(_inside(path, run),
                            "%s is %s, outside the run's home %s"
                            % (name, path, run))


class TestEntryPoints(unittest.TestCase):
    """Each way a test is started, in a fresh process whose user folder is a
    temp folder. ``MPYNODE_HOME`` and the per-location variables all name
    that folder's ``.mpynode``, so a run that keeps any of them fails
    ``TestThisRunIsIsolated`` there, and a write lands where this test sees
    it, never in the real one."""

    def _run(self, args, inherit=False):
        user = tempfile.mkdtemp(prefix="mpynode-fake-user-")
        self.addCleanup(_rmtree, user)
        tmp = os.path.join(user, "tmp")
        os.makedirs(tmp)
        real = os.path.join(user, ".mpynode")
        env  = dict(os.environ)
        env.update({"USERPROFILE": user, "HOME": user,
                    "TEMP": tmp, "TMP": tmp, "TMPDIR": tmp})
        # The launchers' path: mpynode, and the repo root for `tests`.
        env["PYTHONPATH"] = os.pathsep.join(
            [_paths.SCRIPTS, _paths.ROOT]
            + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
        if not inherit:
            env.pop(tests.RUN_HOME_ENV, None)
            env[tests.HOME_ENV] = real
            env.update({
                "MPYNODE_PREFS":           os.path.join(real, "preferences.json"),
                "MPYNODE_PORT_CACHE":      os.path.join(real, "port_cache"),
                "MPYNODE_TRUST_STORE":     os.path.join(real, "trusted.json"),
                "MPYNODE_TYPEID_REGISTRY": os.path.join(real, "typeid.json"),
                "MPYNODE_COMPILED":        os.path.join(real, "compiled"),
            })
        p = subprocess.run([sys.executable] + args, cwd=_paths.ROOT, env=env,
                           capture_output=True, text=True, timeout=300)
        out = p.stdout + p.stderr
        self.assertFalse(os.path.exists(real),
                         "the run wrote into the user's home: %s" % real)
        return p.returncode, out

    def _assert_isolated(self, args):
        rc, out = self._run(args)
        self.assertEqual(rc, 0, out)
        self.assertRegex(out, r"(?m)^Ran 3 tests in ")
        self.assertRegex(out, r"(?m)^OK$")

    def test_one_module_through_the_launchers_shim(self):
        """What ``run_tests.bat`` / ``run_tests.sh <module>`` run."""
        self._assert_isolated([_UT, _ME + ".TestThisRunIsIsolated"])

    def test_discover_through_the_launchers_shim(self):
        """What a bare ``run_tests.bat`` / ``run_tests.sh`` runs, cut to this
        class. A sharded run discovers the same way."""
        self._assert_isolated([_UT, "discover", "-s", "tests", "-t", ".",
                               "-p", "test_suite_home_isolation.py",
                               "-k", "TestThisRunIsIsolated"])

    def test_a_module_outside_the_tests_package(self):
        """A module that imports mpynode before anything else, discovered
        from a folder outside the tests package: _unittest_exit.py's import
        of tests is all that isolates it."""
        folder = tempfile.mkdtemp(prefix="mpynode-outside-")
        self.addCleanup(_rmtree, folder)
        with open(os.path.join(folder, "test_outside_probe.py"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_OUTSIDE)
        self._assert_isolated([_UT, "discover", "-s", folder, "-t", folder,
                               "-p", "test_outside_probe.py"])

    def test_plain_unittest(self):
        """``-m unittest`` without the shim: the package import alone."""
        self._assert_isolated(["-m", "unittest",
                               _ME + ".TestThisRunIsIsolated"])

    def test_a_module_run_on_its_own(self):
        """``mayapy tests/authoring/test_suite_home_isolation.py``: no
        package import and no shim, only the module's own first import."""
        self._assert_isolated([os.path.abspath(__file__),
                               "TestThisRunIsIsolated"])

    def test_discover_from_its_own_folder(self):
        """``-m unittest discover -s tests/authoring`` without ``-t``: the
        module is imported by its bare name, outside the package, and no
        shim runs. Only the module's own first import isolates it."""
        self._assert_isolated(["-m", "unittest", "discover",
                               "-s", os.path.join("tests", "authoring"),
                               "-p", "test_suite_home_isolation.py",
                               "-k", "TestThisRunIsIsolated"])

    def test_a_child_process_keeps_the_runs_home(self):
        rc, out = self._run(["-c", "import tests; print(tests.isolate_home())"],
                            inherit=True)
        self.assertEqual(rc, 0, out)
        self.assertEqual(_norm(out.strip().splitlines()[-1]),
                         _norm(tests.isolate_home()))


class TestEveryModuleImportsTestsFirst(unittest.TestCase):
    """A test module run on its own, or discovered from its own folder, is
    not imported through the tests package, so nothing but the module itself
    can isolate the home before it imports mpynode. Every test module imports
    the package at module level, before anything from the project (mpynode,
    the plug-in modules, tools)."""

    def test_each_imports_tests_before_the_project(self):
        project = _project_names()
        seen, bad = [], []
        for folder, dirs, files in os.walk(_paths.TESTS):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for name in sorted(files):
                if not (name.startswith("test_") and name.endswith(".py")):
                    continue
                path = os.path.join(folder, name)
                rel  = os.path.relpath(path, _paths.ROOT).replace(os.sep, "/")
                seen.append(rel)
                with open(path, "rb") as fh:
                    tree = ast.parse(fh.read(), rel)
                why = _import_order_problem(tree, project)
                if why:
                    bad.append("%s: %s" % (rel, why))
        self.assertIn("tests/authoring/test_suite_home_isolation.py", seen)
        self.assertEqual(bad, [], "%d of %d test modules:\n%s"
                         % (len(bad), len(seen), "\n".join(bad)))


def _project_names():
    """Top-level names the project provides: mpynode (``scripts/``), the
    plug-in modules (``plug-ins/``) and ``tools``."""
    names = {"tools"}
    for sub in ("scripts", "plug-ins"):
        folder = os.path.join(_paths.ROOT, sub)
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if name.endswith(".py"):
                names.add(name[:-3])
            elif os.path.isfile(os.path.join(path, "__init__.py")):
                names.add(name)
    return names


def _module_imports(body):
    """Module-level imports in order, inside if / try / with blocks too,
    never inside a def or a class."""
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node
            continue
        for field in ("body", "orelse", "finalbody"):
            yield from _module_imports(getattr(node, field, None) or [])
        for handler in getattr(node, "handlers", None) or []:
            yield from _module_imports(handler.body)


def _import_order_problem(tree, project):
    """Why the module's imports break the rule, or None."""
    for node in _module_imports(tree.body):
        if isinstance(node, ast.Import):
            tops = {a.name.split(".")[0] for a in node.names}
        elif node.level:
            continue
        else:
            tops = {(node.module or "").split(".")[0]}
        if "tests" in tops:
            return None
        hit = sorted(tops & project)
        if hit:
            return ("line %d imports %s before the tests package"
                    % (node.lineno, hit[0]))
    return "never imports the tests package at module level"


def _rmtree(path):
    import shutil

    shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
