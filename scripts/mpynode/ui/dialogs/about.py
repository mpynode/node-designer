"""About dialog — renders the project's README.md.

A small modal window that displays ``README.md`` through the same
native Markdown renderer used by the documentation viewer (so headings,
spacing, and formatting are styled consistently).
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import QDialog, QHBoxLayout, QPushButton, QVBoxLayout
from mpynode.ui.dialogs.doc_viewer import MarkdownBrowser
from mpynode._common.util import docs_locator


_NO_README_MD = (
    "# About Node Designer\n\n"
    "`README.md` could not be located (it should sit at the project "
    "root, beside `docs/`)."
)


class AboutDialog(QDialog):
    """Modal About window that renders ``README.md``."""

    def __init__(self, parent=None):
        super(AboutDialog, self).__init__(parent)
        self.setWindowTitle("About Node Designer")
        self.setModal(True)
        self.resize(680, 560)

        layout       = QVBoxLayout(self)
        self.browser = MarkdownBrowser(self)
        layout.addWidget(self.browser)

        path = docs_locator.readme_doc()
        if path:
            self.browser.load(path)
        else:
            self.browser.setMarkdown(_NO_README_MD)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)


def show_about_dialog(parent=None) -> None:
    """Open the modal About dialog (renders LICENSE.md)."""
    dlg = AboutDialog(parent)
    dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
