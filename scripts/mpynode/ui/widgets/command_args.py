"""The args dialog a parameterised ``@maya_command`` prompts before it runs.

Moved out of ``script_pane.py`` when the Methods pane was deleted: the pane's
outline was replaced by the Script tab's navigator, but running a command with
parameters still has to ask for them. Behaviour is unchanged -- one line-edit
per param, blank fields omitted so the command's own defaults apply.
"""

from __future__ import annotations

import ast

from mpynode.ui.qt_wrapper import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
)


# "Field left blank -> omit the kwarg entirely".
_UNSET = object()


def _parse_arg_value(text):
    """Parse one args-dialog field into a Python value.

    Blank (or whitespace-only) -> the :data:`_UNSET` sentinel so the caller omits
    the kwarg. Otherwise ``ast.literal_eval`` interprets literals (ints, lists,
    dicts, ...); anything that isn't a valid literal falls back to the raw string
    (so ``foo`` is passed as ``"foo"``, never a NameError)."""
    text = text.strip()
    if not text:
        return _UNSET
    try:
        return ast.literal_eval(text)
    except Exception:
        return text


def prompt_command_args(command_name, params, parent=None):
    """Modal dialog: one line-edit per param; return a kwargs dict or ``None``.

    Blank fields are skipped (see :func:`_parse_arg_value`), so the command runs
    with its own defaults for anything the user didn't fill in. Returns ``None``
    if the dialog is cancelled/closed."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Run %s" % command_name)
    form = QFormLayout(dlg)
    edits = {}
    for name in params:
        edit = QLineEdit(dlg)
        edits[name] = edit
        form.addRow(str(name), edit)
    buttons = QDialogButtonBox(
        QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dlg)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    form.addRow(buttons)

    exec_ = getattr(dlg, "exec_", None) or dlg.exec
    if not exec_():
        return None
    kwargs = {}
    for name, edit in edits.items():
        value = _parse_arg_value(edit.text())
        if value is _UNSET:
            continue
        kwargs[name] = value
    return kwargs
