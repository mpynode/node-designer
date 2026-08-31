"""Confirm dialogs \u2014 Save/Discard/Cancel + delete-confirm.

Ships ``confirm_delete_node``. The Save/Discard/Cancel for tab
close is implemented inline in ``NDScriptTabWidget._showSaveConfirmDialog``
to keep the dialog logic close to its sole caller.
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import QMessageBox


def confirm_delete_node(parent, names: list[str], entity: str = "node") -> bool:
    """Yes/No modal asking the user to confirm deletion of one or more
    items. ``entity`` is the noun shown in the prompt ("node",
    "variable", "attribute", ...).

    Returns True if the user confirms deletion.
    """
    if not names:
        return False
    if len(names) == 1:
        text = f"Delete {entity} '{names[0]}'?"
    else:
        text = f"Delete {len(names)} {entity}s?"

    msg = QMessageBox(parent)
    msg.setWindowTitle(f"Delete {entity.capitalize()}")
    msg.setText(text)
    if len(names) > 1:
        msg.setInformativeText(", ".join(names))
    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg.setDefaultButton(QMessageBox.No)
    response = msg.exec_() if hasattr(msg, "exec_") else msg.exec()
    return response == QMessageBox.Yes
