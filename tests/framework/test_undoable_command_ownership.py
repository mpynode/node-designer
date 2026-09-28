"""``runUndoableAPICommand`` is a SESSION-global name that other toolkits ship.

MPyNode folded the former standalone ``undoable_api_command`` plug-in into
``mpynode_api2`` so the toolkit ships two plug-ins. That file still ships
elsewhere -- ``rig`` loads it lazily from ``rig/nodetypes/plugins`` -- and both
copies register the same command name and then monkey-patch
``cmds.runUndoableAPICommand`` with a wrapper taking a python object.

MEASURED in mayapy 2025, loading ``undoable_api_command`` then ``mpynode_api2``:
the second ``registerCommand`` failed into an ``except``, and the wrapper
install then wrapped THE OTHER TOOLKIT'S WRAPPER. The outer calls the inner
with no arguments, the inner requires ``py_class``, so every undoable Designer
action raised ``missing 1 required positional argument: 'py_class'``. The old
guard could not see it: it asked whether THIS plug-in had registered the name,
which is also false on a plain reload while the other plug-in is loaded.
"""

from __future__ import annotations

import unittest
import unittest.mock

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


def _depth(func) -> int:
    """How many wrappers deep ``cmds.runUndoableAPICommand`` is."""
    n = 0
    while func is not None and hasattr(func, "__wrapped__"):
        n += 1
        func = func.__wrapped__
    return n


class _Holder:
    """Stands in for the MPxCommand subclass carrying ``call_class``."""

    call_class = None


class TestTheInstalledWrapperNeverStacks(unittest.TestCase):

    def setUp(self):
        from mpynode._common.lifecycle import undoable_command as uc

        self.uc = uc
        self.calls = []
        self._saved = getattr(mc, uc.COMMAND_NAME, None)

        def _base():                      # stands in for Maya's no-arg command
            self.calls.append(1)
            return "result"

        setattr(mc, uc.COMMAND_NAME, _base)
        self.base = _base
        self.addCleanup(self._restore)

    def _restore(self):
        if self._saved is None:
            delattr(mc, self.uc.COMMAND_NAME)
        else:
            setattr(mc, self.uc.COMMAND_NAME, self._saved)

    def test_installing_twice_wraps_the_command_not_the_wrapper(self):
        """The failure mode, in one assert: a second install must peel the
        first, or the outer wrapper calls a py_class-taking inner with no
        arguments."""
        self.uc.install_wrapper(_Holder)
        second = self.uc.install_wrapper(_Holder)
        self.assertIs(second.__wrapped__, self.base)
        self.assertEqual(_depth(getattr(mc, self.uc.COMMAND_NAME)), 1)

    def test_it_still_dispatches_after_a_reinstall(self):
        self.uc.install_wrapper(_Holder)
        self.uc.install_wrapper(_Holder)
        obj = object()
        self.assertEqual(getattr(mc, self.uc.COMMAND_NAME)(obj), "result")
        self.assertIs(_Holder.call_class, obj)
        self.assertEqual(len(self.calls), 1)

    def test_it_does_not_peel_a_wrapper_that_is_not_ours(self):
        """Only OUR mark is peeled. Another toolkit's wrapper is its command --
        unwrapping it would hand callers a command with the wrong signature."""
        foreign = lambda py_class: "foreign"        # noqa: E731
        setattr(mc, self.uc.COMMAND_NAME, foreign)
        installed = self.uc.install_wrapper(_Holder)
        self.assertIs(installed.__wrapped__, foreign)


class TestClaimDecidesAgainstTheWholeSession(unittest.TestCase):

    def setUp(self):
        from mpynode._common.lifecycle import undoable_command as uc

        self.uc = uc

    def test_a_free_name_is_registered_and_wrapped(self):
        registered = []
        with unittest.mock.patch.object(self.uc, "command_owner",
                                        return_value=None), \
             unittest.mock.patch.object(self.uc, "install_wrapper") as wrap:
            out = self.uc.claim("mpynode_api2", lambda: registered.append(1),
                                _Holder)
        self.assertEqual(out, "registered")
        self.assertEqual(len(registered), 1)
        self.assertEqual(wrap.call_count, 1)

    def test_our_own_name_is_rewrapped_not_reregistered(self):
        """A reload: the command is still ours, so re-apply the wrapper only."""
        registered = []
        with unittest.mock.patch.object(self.uc, "command_owner",
                                        return_value="mpynode_api2"), \
             unittest.mock.patch.object(self.uc, "install_wrapper") as wrap:
            out = self.uc.claim("mpynode_api2", lambda: registered.append(1),
                                _Holder)
        self.assertEqual(out, "rewrapped")
        self.assertEqual(registered, [])
        self.assertEqual(wrap.call_count, 1)

    def test_someone_elses_name_is_left_completely_alone(self):
        """The bug. Registering fails anyway; WRAPPING is what broke it."""
        registered = []
        with unittest.mock.patch.object(self.uc, "command_owner",
                                        return_value="undoable_api_command"), \
             unittest.mock.patch.object(self.uc, "install_wrapper") as wrap:
            out = self.uc.claim("mpynode_api2", lambda: registered.append(1),
                                _Holder)
        self.assertEqual(out, "deferred:undoable_api_command")
        self.assertEqual(registered, [])
        self.assertEqual(wrap.call_count, 0, "wrapped another plug-in's command")


class TestReleaseOnlyGivesUpWhatWeOwn(unittest.TestCase):

    def setUp(self):
        from mpynode._common.lifecycle import undoable_command as uc

        self.uc = uc

    def test_it_deregisters_our_own(self):
        done = []
        with unittest.mock.patch.object(self.uc, "command_owner",
                                        return_value="mpynode_api2"):
            self.assertTrue(self.uc.release("mpynode_api2",
                                            lambda: done.append(1)))
        self.assertEqual(len(done), 1)

    def test_it_leaves_another_plugins_command_registered(self):
        """``deregisterCommand`` takes a NAME, so an unconditional unload would
        pull the command out from under the other toolkit."""
        done = []
        with unittest.mock.patch.object(self.uc, "command_owner",
                                        return_value="undoable_api_command"):
            self.assertFalse(self.uc.release("mpynode_api2",
                                             lambda: done.append(1)))
        self.assertEqual(done, [])


class TestAgainstTheRealLoadedPlugin(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_api2_owns_the_command_in_this_session(self):
        from mpynode._common.lifecycle import undoable_command as uc

        self.assertEqual(uc.command_owner(), "mpynode_api2")

    def test_the_live_command_is_wrapped_exactly_once(self):
        from mpynode._common.lifecycle import undoable_command as uc

        self.assertEqual(_depth(getattr(mc, uc.COMMAND_NAME)), 1)

    def test_run_undoable_still_works(self):
        from mpynode._base.commands import _BaseCommand, run_undoable

        class _Cmd(_BaseCommand):
            def __init__(self):
                self.ran = 0

            def doIt(self):
                self.ran += 1
                return "done"

        cmd = _Cmd()
        self.assertEqual(run_undoable(cmd), "done")
        self.assertEqual(cmd.ran, 1)


if __name__ == "__main__":
    unittest.main()
