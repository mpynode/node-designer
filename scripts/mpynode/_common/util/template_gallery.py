"""Discover the "New from Template" gallery tree from disk convention.

Maya-free + Qt-free on purpose (same style as
:mod:`mpynode._common.util.docs_locator`) so it is unit-testable without a display
or a running Maya.

Folder convention (design Section 1):
  * Each *template* is a folder containing a file named ``template.mpn``
    (required); optional ``preview.mp4`` / ``preview.gif`` / ``preview.png`` /
    ``preview.jpg`` and optional ``description.md`` sit beside it.
  * A folder WITHOUT ``template.mpn`` is a *category* holding child
    categories / templates (arbitrary nesting depth); it may carry its own
    ``preview.*`` / ``description.md`` landing-page assets.
  * A folder containing BOTH ``template.mpn`` and subfolders is a *hybrid*:
    a buildable template that ALSO expands to its nested child templates.

Optional per-folder manifest (``gallery.json``) -- COMPLETELY optional; when
absent the hardcoded convention above applies unchanged. When present it is a
JSON object whose recognized keys refine how that folder is discovered:

  * ``"order"``: a list of immediate child folder names, in the order they
    should be listed. Named children come first (in this order); any child not
    named is appended after, in the default alphabetical order. Names with no
    matching child are ignored. (Main use: list ``basics`` before ``advanced``.)
  * ``"preview"``: a path (relative to the folder) to use as the preview,
    overriding the ``preview.*`` lookup.
  * ``"description"``: a path (relative to the folder) to use as the
    description, overriding the ``description.md`` lookup.
  * ``"template"``: a path (relative to the folder) to the template envelope,
    overriding the ``template.mpn`` lookup (so a folder's buildable template may
    be named/placed differently).

Unknown keys are ignored (forward-compatible); a manifest that is unreadable, is
not a JSON object, or points at a missing file logs a warning and falls back to
the convention -- a typo never breaks discovery.

``native_type`` for each template is read from the RAW JSON envelope via
:func:`mpynode._common.io.mpn_io.load_mpn_header` -- NO stored-vars decode, NO
``pickle.loads``, regardless of the template's ``has_pickle`` flag. A bad /
unreadable ``template.mpn`` yields ``native_type=None`` (UI renders disabled)
plus a logged warning naming the file; the entry is never silently dropped.
"""

from __future__ import annotations

import json
import logging
import os
from typing import List, NamedTuple, Optional, Tuple

log = logging.getLogger(__name__)

_TEMPLATE_FILENAME = "template.mpn"
_PREVIEW_NAMES = ("preview.mp4", "preview.gif", "preview.png", "preview.jpg")
_DESCRIPTION_NAME = "description.md"
_MANIFEST_NAME = "gallery.json"  # optional per-folder manifest (see module doc)


# --- immutable tree node kinds -------------------------------------------

class TemplateEntry(NamedTuple):
    label: str
    folder: str
    mpn_path: str
    preview_path: Optional[str]
    description_path: Optional[str]
    native_type: Optional[str]
    children: tuple = ()  # nested variant templates (hybrid folders)


class TemplateCategory(NamedTuple):
    label: str
    abs_path: str
    children: tuple  # tuple[TemplateCategory | TemplateEntry, ...]
    preview_path: Optional[str] = None
    description_path: Optional[str] = None


# --- helpers --------------------------------------------------------------


def display_label(name: str) -> str:
    """Return the folder name VERBATIM -- exactly as it appears on disk.

    The gallery does NOT enforce or transform a naming convention: whatever a
    template / category folder is named (case, spaces, underscores, camelCase)
    is exactly what shows in the "New from Template" window. So ``MPyDeformer``
    stays ``MPyDeformer``, ``sine_ripple`` stays ``sine_ripple``, and
    ``My Cool Node`` stays ``My Cool Node``."""
    return name


def find_preview(folder: str) -> Optional[str]:
    """Return the preview path in ``folder``: ``preview.mp4`` preferred, else
    ``preview.gif``, else ``preview.png``, else ``preview.jpg``, else ``None``."""
    for name in _PREVIEW_NAMES:
        p = os.path.join(folder, name)
        if os.path.isfile(p):
            return p
    return None


def find_description(folder: str) -> Optional[str]:
    """Return the ``description.md`` path in ``folder``, else ``None``."""
    p = os.path.join(folder, _DESCRIPTION_NAME)
    return p if os.path.isfile(p) else None


# --- optional per-folder manifest (gallery.json) --------------------------


def read_manifest(folder: str) -> dict:
    """Return ``folder``'s optional ``gallery.json`` manifest as a dict.

    Missing file -> ``{}`` (the hardcoded convention applies unchanged). A file
    that is unreadable or is not a JSON object logs a warning and is treated as
    ``{}`` so a typo never breaks discovery."""
    p = os.path.join(folder, _MANIFEST_NAME)
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        log.warning("gallery manifest %r: unreadable (%s) -- ignored", p, exc)
        return {}
    if not isinstance(data, dict):
        log.warning("gallery manifest %r: not a JSON object -- ignored", p)
        return {}
    return data


def _manifest_file(folder: str, manifest: dict, key: str,
                   fallback: Optional[str]) -> Optional[str]:
    """Resolve a manifest file-pointer (``preview`` / ``description`` /
    ``template``) relative to ``folder``.

    Returns the absolute path when the key is set AND the pointed file exists;
    otherwise ``fallback`` (the hardcoded convention). A set-but-missing pointer
    logs a warning and falls back."""
    rel = manifest.get(key)
    if rel:
        cand = os.path.join(folder, str(rel))
        if os.path.isfile(cand):
            return os.path.abspath(cand)
        log.warning(
            "gallery manifest %r: %s -> %r not found; using convention",
            os.path.join(folder, _MANIFEST_NAME), key, rel)
    return fallback


def _resolve_preview(folder: str, manifest: dict) -> Optional[str]:
    return _manifest_file(folder, manifest, "preview", find_preview(folder))


def _resolve_description(folder: str, manifest: dict) -> Optional[str]:
    return _manifest_file(folder, manifest, "description",
                          find_description(folder))


def _resolve_template(folder: str, manifest: dict) -> Optional[str]:
    """Return the template-envelope path for ``folder`` (manifest override or
    the ``template.mpn`` convention), or ``None`` when the folder holds no
    buildable template."""
    default = os.path.join(folder, _TEMPLATE_FILENAME)
    default = default if os.path.isfile(default) else None
    return _manifest_file(folder, manifest, "template", default)


def _apply_order(children: list, manifest: dict) -> list:
    """Reorder ``children`` per the manifest ``order`` list.

    ``order`` is a list of child folder names, matched against each child's
    verbatim ``label`` (== its folder basename). Named children come first in
    the given order; any child not named is appended after in its existing
    (alphabetical) order. Names with no matching child are ignored. A missing or
    non-list ``order`` leaves ``children`` untouched."""
    order = manifest.get("order")
    if not isinstance(order, (list, tuple)):
        return children
    by_label = {}
    for c in children:
        by_label.setdefault(getattr(c, "label", None), c)
    ordered = []
    seen = set()
    for name in order:
        if not isinstance(name, str):
            continue  # labels are always folder-basename strings; a non-string
            #           entry (nested list / dict / number) is a typo -> skip it
            #           rather than crash on an unhashable dict lookup.
        c = by_label.get(name)
        if c is not None and id(c) not in seen:
            ordered.append(c)
            seen.add(id(c))
    for c in children:
        if id(c) not in seen:
            ordered.append(c)
            seen.add(id(c))
    return ordered


def _read_native_type(mpn_path: str) -> Optional[str]:
    """Read ``native_type`` from a template.mpn via the RAW-JSON header
    accessor (NO pickle decode). Returns ``None`` on any error / missing key
    and logs a warning naming the file."""
    try:
        from mpynode._common.io import mpn_io
        data = mpn_io.load_mpn_header(mpn_path)
        nt = data.get("native_type")
        if not nt:
            log.warning("template %r: missing native_type", mpn_path)
            return None
        return nt
    except Exception as exc:  # bad envelope / version mismatch / IO error
        log.warning("template %r: unreadable header (%s)", mpn_path, exc)
        return None


def _make_entry(folder: str, children: tuple = (),
                manifest: Optional[dict] = None,
                mpn_path: Optional[str] = None) -> TemplateEntry:
    manifest = manifest or {}
    if mpn_path is None:
        mpn_path = os.path.join(folder, _TEMPLATE_FILENAME)
    return TemplateEntry(
        label=display_label(os.path.basename(folder.rstrip(os.sep))),
        folder=folder,
        mpn_path=mpn_path,
        preview_path=_resolve_preview(folder, manifest),
        description_path=_resolve_description(folder, manifest),
        native_type=_read_native_type(mpn_path),
        children=tuple(children),
    )


def _scan_dir(folder: str) -> object:
    """Return a TemplateEntry or TemplateCategory for ``folder``, or ``None``
    when ``folder`` contains no ``template.mpn`` anywhere in its subtree.

    Subfolders are scanned first (sorted, deterministic). A folder with a
    ``template.mpn`` is a buildable entry -- and if it also has subfolders it
    is a *hybrid* (buildable + container), carrying those scanned subfolders
    as its children. A folder without ``template.mpn`` is a category and may
    carry its own landing-page ``preview.*`` / ``description.md``.

    Folders that hold no template.mpn in their whole subtree -- Maya's
    ``.mayaSwatches`` cache dirs, empty category folders, other stray dirs --
    are IGNORED (return ``None``) so they never surface as empty gallery
    categories. A category is kept only when at least one descendant is a
    template.

    An optional ``gallery.json`` manifest in ``folder`` may reorder the children
    (``order``) and/or override the preview / description / template file
    lookups; see the module docstring.
    """
    manifest = read_manifest(folder)
    children = []
    for name in sorted(os.listdir(folder)):
        sub = os.path.join(folder, name)
        if os.path.isdir(sub):
            child = _scan_dir(sub)
            if child is not None:
                children.append(child)
    children = _apply_order(children, manifest)
    mpn_path = _resolve_template(folder, manifest)
    if mpn_path is not None:
        return _make_entry(folder, children=tuple(children),
                           manifest=manifest, mpn_path=mpn_path)
    if not children:
        return None  # no template.mpn anywhere below -> not a gallery folder
    return TemplateCategory(
        label=display_label(os.path.basename(folder.rstrip(os.sep))),
        abs_path=os.path.abspath(folder),
        children=tuple(children),
        preview_path=_resolve_preview(folder, manifest),
        description_path=_resolve_description(folder, manifest),
    )


def scan_root(root: str) -> TemplateCategory:
    """Recursively scan ``root`` into a category tree (design Section 1).
    The returned top node is always a TemplateCategory (the root itself is
    never a template leaf in the gallery model).

    A ``gallery.json`` manifest at ``root`` may reorder the top-level categories
    (e.g. ``basics`` before ``advanced``) and/or override the root's landing-page
    preview / description."""
    root = os.path.abspath(root)
    manifest = read_manifest(root) if os.path.isdir(root) else {}
    children = []
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            sub = os.path.join(root, name)
            if os.path.isdir(sub):
                child = _scan_dir(sub)
                if child is not None:  # drop templateless folders (.mayaSwatches etc.)
                    children.append(child)
    children = _apply_order(children, manifest)
    return TemplateCategory(
        label=display_label(os.path.basename(root.rstrip(os.sep))),
        abs_path=root,
        children=tuple(children),
        preview_path=_resolve_preview(root, manifest),
        description_path=_resolve_description(root, manifest),
    )


def _bundled_templates_root() -> Optional[str]:
    """Return the absolute path to the repo's bundled ``templates/`` directory,
    or ``None`` if it can't be located (e.g. no templates ship in this build).

    Resolution order (mirrors the shipped ``template_search_paths`` default in
    ``mpynode.ui.preferences``):
      1. ``$MPYNODE_ROOT/templates`` when ``MPYNODE_ROOT`` is set and exists.
      2. Walk up from this file until a directory containing ``scripts/mpynode``
         is found (the repo root); return its ``templates`` subdir if it exists.
    """
    env_root = os.environ.get("MPYNODE_ROOT")
    if env_root:
        cand = os.path.join(env_root, "templates")
        if os.path.isdir(cand):
            return os.path.abspath(cand)

    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isdir(os.path.join(d, "scripts", "mpynode")):
            cand = os.path.join(d, "templates")
            return os.path.abspath(cand) if os.path.isdir(cand) else None
        parent = os.path.dirname(d)
        if parent == d:  # reached the filesystem root
            return None
        d = parent


def template_search_roots() -> List[str]:
    """Return the absolute, existing search roots (design Section 1).

    Reads the ``template_search_paths`` preference, expands ``~`` and env
    vars, drops paths that don't exist (logging each once). Falls back to the
    bundled ``<MPYNODE_ROOT>/templates`` root when the pref yields nothing."""
    raw: List[str] = []
    try:
        from mpynode.ui import preferences
        raw = list(preferences.template_search_paths() or [])
    except Exception:
        raw = []

    roots: List[str] = []
    seen = set()
    for p in raw:
        if not p:
            continue
        exp = os.path.abspath(os.path.expanduser(os.path.expandvars(p)))
        if not os.path.isdir(exp):
            log.warning("template search path dropped (not a directory): %r", p)
            continue
        if exp not in seen:
            seen.add(exp)
            roots.append(exp)

    if not roots:
        bundled = _bundled_templates_root()
        if bundled and os.path.isdir(bundled):
            roots.append(os.path.abspath(bundled))
    return roots


def scan_all() -> List[Tuple[str, str, TemplateCategory]]:
    """Scan every configured root into ``(root_label, root_path, tree)`` --
    one branch per root (the gallery's multi-root model)."""
    out: List[Tuple[str, str, TemplateCategory]] = []
    for root in template_search_roots():
        tree = scan_root(root)
        out.append((tree.label, tree.abs_path, tree))
    return out
