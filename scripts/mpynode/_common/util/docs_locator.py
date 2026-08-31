"""Locate the bundled documentation tree + classify doc-to-doc links.

Qt-free on purpose, so it is unit-testable without a display. Consumed by
the Help-menu Markdown viewer (``mpynode.ui.dialogs.doc_viewer``).

Docs layout (since 2026-06-22):

    docs/index.md          -- the home / comprehensive guide
    docs/node_types/*.md   -- one reference page per node type
    docs/PORTING.md        -- platform-port notes
"""

from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple


def slugify(text: str) -> str:
    """Slugify a heading's text into the anchor the in-doc TOC links to.

    Matches the scheme used by ``docs/index.md``'s table of contents:
    lower-case, drop every character that is not ``[a-z0-9 -]`` (so
    backticks, parentheses, slashes, em-dashes AND underscores all
    vanish), then turn spaces into hyphens. Runs of spaces are preserved
    as runs of hyphens (e.g. an em-dash surrounded by spaces collapses to
    a double hyphen), exactly as the TOC was authored.

    Examples::

        "Quick start"                              -> "quick-start"
        "Creating nodes — full API per type"       -> "creating-nodes--full-api-per-type"
        "...(`add_input_attr` / `add_output_attr`)"-> "...-addinputattr--addoutputattr"
    """
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9 \-]", "", s)  # drop punctuation incl. underscores
    return s.replace(" ", "-")


def find_docs_root() -> Optional[str]:
    """Return the absolute path to the repo's ``docs/`` directory, or ``None``.

    Resolution order:
      1. ``$MPYNODE_ROOT/docs`` when ``MPYNODE_ROOT`` is set and valid.
      2. Walk up from this file until a directory containing
         ``docs/node_types`` is found (the dev layout: ``docs/`` beside
         ``scripts/``).
    """
    env_root = os.environ.get("MPYNODE_ROOT")
    if env_root:
        cand = os.path.join(env_root, "docs")
        if os.path.isdir(os.path.join(cand, "node_types")):
            return os.path.abspath(cand)

    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        cand = os.path.join(d, "docs")
        if os.path.isdir(os.path.join(cand, "node_types")):
            return cand
        parent = os.path.dirname(d)
        if parent == d:  # reached the filesystem root
            return None
        d = parent


def home_doc() -> Optional[str]:
    """Absolute path to the documentation home page (``docs/index.md``)."""
    root = find_docs_root()
    if not root:
        return None
    p = os.path.join(root, "index.md")
    return p if os.path.isfile(p) else None


def license_doc() -> Optional[str]:
    """Absolute path to the project's ``LICENSE.md`` (repo root, beside
    ``docs/``), or ``None`` if it can't be found."""
    return _repo_root_doc("LICENSE.md")


def readme_doc() -> Optional[str]:
    """Absolute path to the project's ``README.md`` (repo root, beside
    ``docs/``), or ``None`` if it can't be found."""
    return _repo_root_doc("README.md")


def _repo_root_doc(filename: str) -> Optional[str]:
    root = find_docs_root()
    if not root:
        return None
    p = os.path.join(os.path.dirname(root), filename)
    return p if os.path.isfile(p) else None


def _pretty_title(filename: str) -> str:
    return filename[:-3] if filename.endswith(".md") else filename


def list_node_type_docs(include_helpers: bool = True) -> List[Tuple[str, str]]:
    """Return ``(title, abspath)`` for every ``docs/node_types/*.md``.

    Sorted alphabetically with leading-underscore helper docs (e.g.
    ``_input_type_contract.md``) pushed to the END. ``include_helpers``
    False drops the underscore docs entirely.
    """
    root = find_docs_root()
    if not root:
        return []
    nt_dir = os.path.join(root, "node_types")
    if not os.path.isdir(nt_dir):
        return []
    names = [n for n in os.listdir(nt_dir) if n.endswith(".md")]
    if not include_helpers:
        names = [n for n in names if not n.startswith("_")]
    # node-type docs first (alpha), underscore helper docs last
    names.sort(key=lambda n: (n.startswith("_"), n.lower()))
    return [(_pretty_title(n), os.path.join(nt_dir, n)) for n in names]


# mPyNode is the base + most common type, so the Help -> Node Types submenu
# surfaces its doc FIRST with a separator -- mirroring how the "New" menu pins
# it (see _node_registry.PINNED_NEW_NODE_TYPE / iter_new_node_menu_entries).
_PINNED_DOC_TITLE = "mPyNode"


def _pin_first_with_separator(items, pinned_title):
    """Reorder ``(title, path)`` items so the one whose title matches
    ``pinned_title`` (case-insensitive) comes FIRST, followed by ``None`` (a
    separator marker), then the remaining items in their original order.

    Mirrors ``_node_registry.iter_new_node_menu_entries`` (which yields the
    pinned type, then ``None``, then the rest). If nothing matches, the items
    are returned unchanged with NO leading separator."""
    pl = pinned_title.lower()
    pinned = [it for it in items if it[0].lower() == pl]
    rest = [it for it in items if it[0].lower() != pl]
    if not pinned:
        return list(rest)
    return pinned + [None] + rest


def list_node_type_docs_menu_order(include_helpers: bool = True,
                                   pinned: str = _PINNED_DOC_TITLE):
    """``list_node_type_docs`` reordered for the Help -> Node Types submenu: the
    pinned node-type doc (``mPyNode``) first, then ``None`` (a separator
    marker), then the rest. Consumers insert a menu separator wherever they see
    ``None`` -- the same pattern the toolbar / Node menu use for the New list."""
    return _pin_first_with_separator(
        list_node_type_docs(include_helpers=include_helpers), pinned
    )


def resolve_doc_link(current_doc_path: str, href: str):
    """Classify + resolve a hyperlink clicked inside the doc viewer.

    Returns one of:
      ``("external", url)``        -- http(s) / mailto: open in system browser
      ``("anchor", fragment)``     -- a pure in-page ``#anchor``
      ``("file", abspath, frag)``  -- a local doc to load (``frag`` may be "")
      ``("unknown", href)``        -- could not be resolved (ignored by caller)
    """
    if not href:
        return ("unknown", href)

    if href.lower().startswith(("http://", "https://", "mailto:")):
        return ("external", href)

    if href.startswith("#"):
        return ("anchor", href[1:])

    path_part, frag = href, ""
    if "#" in href:
        path_part, frag = href.split("#", 1)
    if not path_part:
        return ("anchor", frag)

    base_dir = os.path.dirname(os.path.abspath(current_doc_path))
    target = os.path.normpath(os.path.join(base_dir, path_part))

    if os.path.isdir(target):
        idx = os.path.join(target, "index.md")
        return ("file", idx, frag) if os.path.isfile(idx) else ("unknown", href)
    if os.path.isfile(target):
        return ("file", target, frag)
    # tolerate links that omit the .md extension
    if not path_part.endswith(".md") and os.path.isfile(target + ".md"):
        return ("file", target + ".md", frag)
    return ("unknown", href)
