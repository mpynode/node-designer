"""The args dialog a parameterised ``@maya_command`` prompts before it runs.

What survives of ``test_script_pane.py``. The Methods pane is deleted -- its
outline became the Script tab's navigator and its editor became the API view --
but running a command with parameters still has to ask for them, so
``prompt_command_args`` moved to ``ui/widgets/command_args.py`` rather than
going with it.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest


class TestParseArgValue(unittest.TestCase):
    """Pure helper -- no Qt guard needed."""

    def test_parse_arg_value(self):
        from mpynode.ui.widgets.command_args import _parse_arg_value, _UNSET

        self.assertEqual(_parse_arg_value("42"), 42)
        self.assertEqual(_parse_arg_value("[1, 2]"), [1, 2])
        self.assertEqual(_parse_arg_value("foo"), "foo")
        self.assertIs(_parse_arg_value("  "), _UNSET)

    def test_the_run_path_still_reaches_it(self):
        # The prompt is only useful if the Run handler actually calls it; the
        # pane that used to do so is gone.
        import inspect

        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        src = inspect.getsource(NDScriptTabContent._on_run_requested)
        self.assertIn("prompt_command_args", src)
        self.assertIn("_run_params", src)


if __name__ == "__main__":
    unittest.main()
