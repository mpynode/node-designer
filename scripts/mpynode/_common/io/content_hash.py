"""Normalized-source content hash for divergence detection.

Two instances of one Class should have identical authored STRUCTURE. This hash
covers the expression/init/methods source plus attribute and persistent-var
NAMES -- with comments and insignificant whitespace stripped and names sorted --
so it is invariant to values, comments, and formatting. It is NOT an identity
(editing code changes it); it is only used to warn-and-fork divergent instances
at compile and, optionally, to group class-less nodes for discovery.
"""
from __future__ import annotations

import hashlib
import io
import tokenize


def _strip(src):
    """Return ``src`` reduced to its significant tokens (comments + insignificant
    whitespace removed). Falls back to whitespace-collapsed text if tokenizing
    fails (e.g. an in-progress edit that doesn't tokenize)."""
    if not src:
        return ""
    try:
        toks = []
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                            tokenize.INDENT, tokenize.DEDENT,
                            tokenize.ENCODING, tokenize.ENDMARKER):
                continue
            if tok.type == tokenize.STRING:
                toks.append(tok.string)
            else:
                s = tok.string.strip()
                if s:
                    toks.append(s)
        return "\x1f".join(toks)
    except Exception:
        return " ".join(src.split())


def source_hash(compute, input_names, output_names,
                init="", methods="", persistent_names=None):
    """md5 hex of the normalized authoring structure."""
    parts = [
        _strip(compute or ""),
        _strip(init or ""),
        _strip(methods or ""),
        ",".join(sorted(input_names or [])),
        ",".join(sorted(output_names or [])),
        ",".join(sorted(persistent_names or [])),
    ]
    blob = "\x1e".join(parts).encode("utf-8", "replace")
    return hashlib.md5(blob).hexdigest()


def node_content_hash(py_node):
    """Content hash for a live wrapper (best-effort)."""
    def _get(fn, default=""):
        f = getattr(py_node, fn, None)
        try:
            return (f() if f else default) or default
        except Exception:
            return default
    return source_hash(
        _get("get_compute_expression"),
        list((_get("get_input_attr_map", {}) or {}).keys()),
        list((_get("get_output_attr_map", {}) or {}).keys()),
        init=_get("get_init_expression"),
        methods=_get("get_methods_source"),
        persistent_names=list(_get("get_variable_names", []) or []),
    )
