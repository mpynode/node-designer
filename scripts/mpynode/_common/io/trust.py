"""Trust manager for the (arbitrary-object) PICKLE fallback in stored-var /
python-attr decoding.

Why this exists: ``pickle.loads`` on attacker-controlled ``.ma`` data is remote
code execution on open/import. We keep pickle (so users can store ANY
pickle-able object) but gate the *decode* behind a trust decision so merely
opening a hostile file can't silently run code.

The hard constraint: decoding also happens on Maya EM **worker threads** (the
compute hot path), where a prompt is impossible. So trust is resolved exactly
ONCE, on the MAIN thread, at scene open/import (:func:`resolve_for_open` /
:func:`resolve_for_import`), and the worker path only ever *reads* the resolved
per-scene boolean via :func:`pickle_trusted` — it never prompts.

Trust model:
  * a scene you authored this session is trusted by default;
  * opening a file REPLACES the scene trust with that file's resolution;
  * importing a file can only REDUCE trust (a declined import poisons the
    session's file-literal pickle, fail-closed);
  * ``MPYNODE_TRUST_PICKLE=1`` trusts everything (headless / render farm);
  * "Always" decisions persist to ``~/mpynode/trusted.json`` (per file or per
    folder), overridable via ``MPYNODE_TRUST_STORE`` (tests).

Pure Python + stdlib. No Maya / Qt imports — the prompt is an INJECTED callable
(:func:`resolve_for_open`'s ``prompt_fn``) so this module stays testable.
"""

from __future__ import annotations

import json
import os
import threading

_ENV_TRUST = "MPYNODE_TRUST_PICKLE"

# Per-scene resolved trust. Default True == an authored/empty scene is trusted
# (no untrusted file has been opened). Read lock-free on worker threads.
_scene_trusted = True
# Snapshot of the pre-import/-reference trust, taken at kBeforeImport /
# kBeforeReference so the transition can fail closed WITHOUT losing the
# authored-scene trust that :func:`note_file_imported` must reduce against.
# ``None`` == not currently inside an import/reference transition.
_import_prior = None
_lock = threading.Lock()


# ---- Per-scene flag (resolved on the main thread, read anywhere) ----

def begin_scene_change() -> None:
    """A scene change is starting (kBeforeOpen / kBeforeNew). Fail CLOSED for the
    duration: any compute that fires mid-open (EM eager-eval) before the
    kAfterOpen resolution must NOT decode pickle. The matching after-event
    (:func:`note_file_opened` for open, :func:`reset_for_new_scene` for new)
    sets the real value. Clears any dangling import snapshot (an open/new is an
    absolute reset)."""
    global _scene_trusted, _import_prior
    _scene_trusted = False
    _import_prior = None


def begin_import_change() -> None:
    """An import / reference load is starting (kBeforeImport / kBeforeReference).
    Fail CLOSED for the duration so a mid-load worker compute can't unpickle the
    incoming (untrusted) file before kAfterImport/kAfterReference resolves it --
    BUT snapshot the current authored-scene trust first, because an import can
    only REDUCE trust (:func:`note_file_imported` reduces against this snapshot,
    not against the forced-False transition value)."""
    global _scene_trusted, _import_prior
    if _import_prior is None:  # don't clobber an outer snapshot (nested loads)
        _import_prior = _scene_trusted
    _scene_trusted = False


def reset_for_new_scene() -> None:
    """File > New / fresh session: authored content is trusted."""
    global _scene_trusted, _import_prior
    _scene_trusted = True
    _import_prior = None


def note_file_opened(resolved: bool) -> None:
    """An open REPLACES the scene's trust with the opened file's resolution."""
    global _scene_trusted, _import_prior
    _scene_trusted = bool(resolved)
    _import_prior = None


def note_file_imported(resolved: bool) -> None:
    """An import / reference can only REDUCE trust (never re-raise a dropped
    flag). Reduces against the pre-import snapshot taken by
    :func:`begin_import_change` (falling back to the live flag if no snapshot
    was taken, e.g. a caller that didn't pair the before-event)."""
    global _scene_trusted, _import_prior
    base = _import_prior if _import_prior is not None else _scene_trusted
    _scene_trusted = bool(base and resolved)
    _import_prior = None


def pickle_trusted() -> bool:
    """Worker-safe reader of the current scene's pickle-trust. NEVER prompts."""
    return _scene_trusted


def exec_trusted() -> bool:
    """True if node Python read out of the scene may be exec'd -- Init
    (``init_registry.register_init_source``) and Compute
    (``compute.expression.exec_with_profile_watch``). Worker-safe, NEVER
    prompts.

    Same per-scene decision as :func:`pickle_trusted`, with the
    ``MPYNODE_TRUST_PICKLE`` opt-in checked FIRST: the per-scene flag is forced
    False for the WHOLE kBeforeOpen -> kAfterOpen transition, and both the
    mid-open lazy Init bind and any mid-open compute run inside that window.

    Fails CLOSED if the flag can't be read."""
    try:
        return bool(env_trusted() or _scene_trusted)
    except Exception:
        return False


# ---- Env + persistent store ----

def env_trusted() -> bool:
    val = os.environ.get(_ENV_TRUST, "")
    return val.strip().lower() in ("1", "true", "yes", "on")


def _store_path() -> str:
    from mpynode._common import home
    return home.trust_store_path()


def _load_store() -> dict:
    try:
        with open(_store_path(), "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault("files", [])
            data.setdefault("folders", [])
            return data
    except (OSError, ValueError):
        pass
    return {"files": [], "folders": []}


def _save_store(data: dict) -> None:
    path = _store_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except OSError:
        pass  # best effort; a failed persist just means we prompt again


def is_remembered(path: str) -> bool:
    """True if ``path`` was previously trusted with an 'Always' decision
    (exact file, or any ancestor folder)."""
    ap = os.path.abspath(path)
    store = _load_store()
    if ap in store.get("files", []):
        return True
    for folder in store.get("folders", []):
        f = os.path.abspath(folder)
        if ap == f or ap.startswith(f + os.sep):
            return True
    return False


def remember(path: str, scope: str = "file") -> None:
    """Persist an 'Always' trust decision. ``scope`` is ``"file"`` (this exact
    file) or ``"folder"`` (this file's directory and everything under it).

    A falsy ``path`` (e.g. an unsaved scene, or an import whose path isn't
    known) is a no-op -- there's nothing stable to persist, so the decision is
    treated as one-shot for this session rather than crashing on
    ``os.path.abspath(None)``."""
    if not path:
        return
    with _lock:
        store = _load_store()
        if scope == "folder":
            key = os.path.abspath(os.path.dirname(path))
            if key not in store["folders"]:
                store["folders"].append(key)
        else:
            key = os.path.abspath(path)
            if key not in store["files"]:
                store["files"].append(key)
        _save_store(store)


# ---- Resolution (MAIN THREAD ONLY — may prompt) ----

def resolve_for_open(path, has_pickle: bool, prompt_fn=None) -> bool:
    """Resolve whether to trust pickle in ``path``. MAIN THREAD ONLY.

    Order: nothing-to-gate -> env -> remembered -> prompt -> fail-closed.

    ``prompt_fn(path) -> str`` returns one of ``"yes"`` (this session),
    ``"no"``, ``"always_file"``, ``"always_folder"``. If ``prompt_fn`` is None
    (headless) and the file isn't otherwise trusted, returns False (refuse).
    """
    if not has_pickle:
        return True
    if env_trusted():
        return True
    if path is not None and is_remembered(path):
        return True
    if prompt_fn is None:
        return False
    decision = prompt_fn(path)
    if decision == "always_file":
        remember(path, "file")
        return True
    if decision == "always_folder":
        remember(path, "folder")
        return True
    return decision == "yes"


def resolve_for_import(path, has_pickle: bool, prompt_fn=None) -> bool:
    """Same resolution as :func:`resolve_for_open`; separate name so callers
    pair it with :func:`note_file_imported` (reduce-only)."""
    return resolve_for_open(path, has_pickle, prompt_fn=prompt_fn)
