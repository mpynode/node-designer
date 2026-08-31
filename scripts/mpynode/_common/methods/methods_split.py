"""Split/join the single ``_methodsSource`` string into a Methods view (class-
bound defs) and a Functions view (module-level material). Pure + Qt/Maya-free.

The split is a UI VIEW only -- the node keeps ONE ``_methodsSource`` plug, so
backward compat, native compile, ``.mpn``/``.ma`` round-trip, ``port_cache``
stability, and cross-kind references (one ``exec`` of the joined source) are all
untouched. Scope -- class-bound vs module-level -- is the only real boundary, and
it is exactly what ``py_export._classify_funcdef`` already computes for the
one-way bake, so this reuses it as the single source of truth.

``split`` -> ``join`` is byte-identical when the source is empty, all-Methods,
all-Functions, or already in canonical order (module preamble above the methods).
A source that interleaves module statements between methods re-joins in canonical
order (Functions first, then Methods) -- a deliberate canonicalization that only
happens when the user actually edits + saves (the pane guards on dirty).
"""
from __future__ import annotations

import ast

from mpynode._common.io.py_export import _classify_funcdef


def split_methods_source(source: str) -> tuple:
    """Return ``(functions_text, methods_text)`` for ``source``.

    Class-bound ``def``s (``self``/``cls``-first or ``@classmethod`` /
    ``@staticmethod``) go to Methods; every other top-level statement (module
    functions, imports, constants, helper classes, ``async def``) goes to
    Functions. Empty/whitespace source -> ``("", "")``. A parse failure routes
    EVERYTHING to Methods (``("", source)``) so no text is lost and the user can
    fix the syntax in the primary tab -- ``join("", source) == source``.
    """
    if not source or not source.strip():
        return ("", "")
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return ("", source)

    lines = source.splitlines(keepends=True)
    functions_parts: list = []
    methods_parts: list = []
    cursor = 0  # 0-based index of the next unconsumed line
    # A statement-less source (pure comments / blank lines -- e.g. the seeded
    # new-node Methods header) has no funcdefs to classify. Route it to the
    # PRIMARY Methods view rather than Functions, so a comment-only header shows
    # where method material belongs. join("", header) == header keeps the
    # round-trip byte-identical either way.
    last_bucket = methods_parts if not tree.body else functions_parts
    for stmt in tree.body:
        end = stmt.end_lineno  # 1-based, inclusive
        chunk = "".join(lines[cursor:end])
        cursor = end
        if isinstance(stmt, ast.FunctionDef) and \
                _classify_funcdef(stmt)[0] == "class":
            methods_parts.append(chunk)
            last_bucket = methods_parts
        else:
            functions_parts.append(chunk)
            last_bucket = functions_parts
    # Trailing lines after the last statement (comments / blank lines) stay with
    # whichever bucket the last statement went to.
    if cursor < len(lines):
        last_bucket.append("".join(lines[cursor:]))
    return ("".join(functions_parts), "".join(methods_parts))


def join_methods_source(functions_text: str, methods_text: str) -> str:
    """Join the two views back into one ``_methodsSource`` string.

    Canonical order is Functions (module preamble) first, then Methods, so a
    method can reference a module-level helper/constant at ``exec`` time. When
    one bucket is empty the other is returned verbatim (byte-identical).
    """
    if not functions_text:
        return methods_text
    if not methods_text:
        return functions_text
    if not functions_text.endswith("\n"):
        functions_text += "\n"
    return functions_text + methods_text
