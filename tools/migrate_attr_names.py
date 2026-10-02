"""Translate every attr_type name in the repo's data files to its stored name.

Each type has one stored name (``scripts/mpynode/_common/attr_types.py``). A
name that is not stored -- an alias (``attr_types.ALIASES``: ``int`` ->
``long``, ``vector`` -> ``double3``, ``angle`` -> ``doubleAngle``,
``float64`` -> ``double`` ...) or a retired name (``attr_types.RETIRED``:
``python`` -> ``pickle``) -- is rewritten to the stored name in:

  * ``templates/*/*/template.mpn``: ``input_attrs`` / ``output_attrs``
    ``attr_type``;
  * every tracked ``.ma``: the JSON inside ``setAttr "._inputAttrs"`` /
    ``"._outputAttrs"`` strings (escaped quotes);
  * every ``build/manifest.json`` and ``mega_manifest*.json`` under
    ``templates``: ``nodes[].spec.inputs|outputs[].type``;
  * ``tests/data/mpyfile_spec_golden.json`` and
    ``tools/parity_sweep/fixtures/*/spec.json``: ``inputs|outputs[].type``;
  * every generated ``verify_in_maya.py``: the embedded spec data and the
    generated-code literals (``if t == "int"``, ``t in ("vector", "euler")``)
    -- old stored names only (``int``, ``vector``, ``angle``, ``python``).

The map is the table's own (``ALIASES`` + ``RETIRED``), read from
``attr_types.py`` by path, so the tool follows the table.

Every other byte is preserved. Each rewrite is a token replacement, and each
file is then re-parsed and checked: the only change allowed is the type value
at the paths above. A spec's ``cpp`` block (``"cpp": "int"`` is a C++ type,
``"cat": "vector"`` a category), stored-variable kinds and dict KEYS (an attr
may be named ``angle``) are left alone.

Dry run by default: reports what would change, per file and per name.
``--apply`` writes. A second dry run after ``--apply`` reports 0.

Plain Python 3, no Maya:

    python tools/migrate_attr_names.py            # report
    python tools/migrate_attr_names.py --apply    # rewrite in place
"""

from __future__ import annotations

import argparse
import ast
import collections
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_attr_types():
    """``scripts/mpynode/_common/attr_types.py``, loaded by path: the module
    imports nothing, but importing it through the ``mpynode._common`` package
    needs Maya."""
    path = os.path.join(ROOT, "scripts", "mpynode", "_common", "attr_types.py")
    spec = importlib.util.spec_from_file_location("_migrate_attr_types", path)
    mod  = importlib.util.module_from_spec(spec)
    # dataclasses looks the defining module up in sys.modules.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_ATTR_TYPES = _load_attr_types()

# Non-stored name -> stored name: every alias and every retired name.
RENAME = dict(_ATTR_TYPES.ALIASES)
RENAME.update(_ATTR_TYPES.RETIRED)
# Longest first, so no name matches as the prefix of a longer one.
_OLD = "|".join(re.escape(n) for n in sorted(RENAME, key=len, reverse=True))

# The names a generated verify script can hold as a bare code literal
# (``if t == "int"``): the old stored names only, since the generator only
# ever wrote stored names. Every other alias (``double4``, ``float3``, ``uv``,
# ``distance`` ...) was never stored, so a bare one in a script means something
# else -- a ``setAttr`` type, a uvSet -- and is left alone. The embedded spec
# is still renamed by structure, with the full map.
_CODE_NAMES = frozenset(("int", "vector", "angle")
                        + tuple(_ATTR_TYPES.RETIRED))


class MigrationError(Exception):
    pass


def _tracked(*patterns):
    """Tracked files matching the git pathspecs, as repo-relative paths."""
    out = subprocess.run(
        ["git", "-C", ROOT, "ls-files", "--", *patterns],
        capture_output=True, text=True, check=True).stdout
    return sorted(p for p in out.split("\n") if p)


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8", newline="") as fh:
        return fh.read()


def _write(rel, text):
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8",
              newline="") as fh:
        fh.write(text)


def _sub(pattern, text, counts):
    """Replace group 'name' of every ``pattern`` match; count per old name."""
    def repl(m):
        old = m.group("name")
        counts[old] += 1
        s, e = m.span("name")
        base  = m.start()
        whole = m.group(0)
        return whole[:s - base] + RENAME[old] + whole[e - base:]
    return re.sub(pattern, repl, text)


# ---------------------------------------------------------------- structure

def _rename_meta(meta, key):
    if isinstance(meta, dict) and meta.get(key) in RENAME:
        meta[key] = RENAME[meta[key]]


def _rename_attr_map(attr_map, key):
    if isinstance(attr_map, dict):
        for meta in attr_map.values():
            _rename_meta(meta, key)


def _rename_spec(spec):
    if isinstance(spec, dict):
        for side in ("inputs", "outputs"):
            _rename_attr_map(spec.get(side), "type")


def _expect_mpn(doc):
    data = doc.get("data") if isinstance(doc, dict) else None
    if isinstance(data, dict):
        for side in ("input_attrs", "output_attrs"):
            _rename_attr_map(data.get(side), "attr_type")


def _expect_manifest(doc):
    for row in (doc.get("nodes") or []) if isinstance(doc, dict) else []:
        if isinstance(row, dict):
            _rename_spec(row.get("spec"))


def _expect_golden(doc):
    if isinstance(doc, dict):
        for spec in doc.values():
            _rename_spec(spec)


def _check_json(rel, old_text, new_text, expect):
    """``new_text`` must parse to ``old_text`` with only ``expect``'s renames."""
    want = json.loads(old_text)
    expect(want)
    if json.loads(new_text) != want:
        raise MigrationError(
            "%s: the token rewrite changed something other than the type "
            "values" % rel)


# ---------------------------------------------------------------- stores

def migrate_mpn(rel, text, counts):
    new = _sub(r'"attr_type": "(?P<name>%s)"' % _OLD, text, counts)
    if new != text:
        _check_json(rel, text, new, _expect_mpn)
    return new


def migrate_manifest(rel, text, counts):
    new = _sub(r'"type": "(?P<name>%s)"' % _OLD, text, counts)
    if new != text:
        _check_json(rel, text, new, _expect_manifest)
    return new


def migrate_golden(rel, text, counts):
    new = _sub(r'"type": "(?P<name>%s)"' % _OLD, text, counts)
    if new != text:
        _check_json(rel, text, new, _expect_golden)
    return new


def migrate_spec_json(rel, text, counts):
    new = _sub(r'"type": "(?P<name>%s)"' % _OLD, text, counts)
    if new != text:
        _check_json(rel, text, new, _rename_spec)
    return new


# A ``setAttr`` on an attr-map plug: the plug and everything up to the ``;``.
_MA_SETATTR = re.compile(
    r'setAttr "\.(?:_inputAttrs|_outputAttrs)" -type "string" (?P<val>.*?);\n',
    re.S)
_MA_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _ma_value(val):
    """The MEL string expression -> its text (``"a" + "b"`` concatenations)."""
    parts = _MA_STRING.findall(val)
    return "".join(re.sub(r"\\(.)", r"\1", p) for p in parts)


def migrate_ma(rel, text, counts):
    def one(m):
        val = m.group("val")
        new_val = _sub(r'\\"attr_type\\": ?\\"(?P<name>%s)\\"' % _OLD, val,
                       counts)
        if new_val == val:
            return m.group(0)
        try:
            want = json.loads(_ma_value(val))
        except ValueError:
            raise MigrationError("%s: an attr-map plug that is not JSON "
                                 "holds an old name" % rel)
        _rename_attr_map(want, "attr_type")
        if json.loads(_ma_value(new_val)) != want:
            raise MigrationError("%s: the token rewrite changed something "
                                 "other than the type values" % rel)
        s, e = m.span("val")
        return m.group(0)[:s - m.start()] + new_val + m.group(0)[e - m.start():]
    return _MA_SETATTR.sub(one, text)


_SKIP = (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT,
         tokenize.DEDENT)


def _significant(toks, i, step):
    """The nearest real token before (``step=-1``) or after (``+1``) ``i``."""
    j = i + step
    while 0 <= j < len(toks):
        if toks[j].type not in _SKIP:
            return toks[j]
        j += step
    return None


def _is_dict_key(toks, i):
    """``{"angle": ...`` / ``, "angle": ...``: an attr NAME, not a type."""
    prev, nxt = _significant(toks, i, -1), _significant(toks, i, +1)
    return (prev is not None and prev.type == tokenize.OP
            and prev.string in ("{", ",")
            and nxt is not None and nxt.type == tokenize.OP
            and nxt.string == ":")


def _is_keyword_value(toks, i):
    """``initialize(name="python")``: a keyword argument's value, not a
    type."""
    prev = []
    j    = i - 1
    while j >= 0 and len(prev) < 3:
        if toks[j].type not in _SKIP:
            prev.append(toks[j])
        j -= 1
    return (len(prev) == 3
            and prev[0].type == tokenize.OP and prev[0].string == "="
            and prev[1].type == tokenize.NAME
            and prev[2].type == tokenize.OP and prev[2].string in ("(", ","))


def migrate_verify_script(rel, text, counts):
    """Generated parity script. A string token that IS an old stored name
    (:data:`_CODE_NAMES`) is renamed unless it is a dict key (an attr name) or
    a keyword argument's value. The ``json.loads('<spec>')`` payload is
    renamed structurally, with every alias, and re-dumped the way the
    generator wrote it (``repr(json.dumps(spec))``), after proving that round
    trip is byte-identical."""
    toks  = list(tokenize.generate_tokens(io.StringIO(text).readline))
    lines = text.split("\n")
    edits = []
    for i, tok in enumerate(toks):
        if tok.type != tokenize.STRING:
            continue
        try:
            val = ast.literal_eval(tok.string)
        except (ValueError, SyntaxError):
            continue
        if not isinstance(val, str):
            continue
        new = None
        if val in RENAME:
            if val not in _CODE_NAMES:
                continue  # never stored, so not a type literal here
            if _is_dict_key(toks, i):
                continue  # an attr name, not a type
            if _is_keyword_value(toks, i):
                continue  # e.g. initialize(name="python")
            counts[val] += 1
            new = tok.string[0] + RENAME[val] + tok.string[0]
        elif val.startswith("{") and '"inputs"' in val:
            prev = toks[i - 2] if i >= 2 else None
            if not (prev is not None and prev.string == "loads"):
                continue
            spec = json.loads(val)
            if repr(json.dumps(spec)) != tok.string:
                raise MigrationError("%s: the embedded spec does not round "
                                     "trip byte-identically" % rel)
            before = json.dumps(spec)
            for side in ("inputs", "outputs"):
                for meta in (spec.get(side) or {}).values():
                    if isinstance(meta, dict) and meta.get("type") in RENAME:
                        counts[meta["type"]] += 1
            _rename_spec(spec)
            if json.dumps(spec) != before:
                new = repr(json.dumps(spec))
        if new is not None:
            if tok.start[0] != tok.end[0]:
                raise MigrationError("%s: multi-line string at line %d"
                                     % (rel, tok.start[0]))
            edits.append((tok.start[0], tok.start[1], tok.end[1], new))
    for row, c0, c1, new in sorted(edits, reverse=True):
        ln             = lines[row - 1]
        lines[row - 1] = ln[:c0] + new + ln[c1:]
    out = "\n".join(lines)
    if out != text:
        compile(out, rel, "exec")
    return out


def _stores():
    """(label, repo-relative path, migrate function) for every store."""
    out = []
    for rel in _tracked("templates/*/*/template.mpn"):
        out.append(("mpn", rel, migrate_mpn))
    for rel in _tracked("*.ma"):
        out.append(("ma", rel, migrate_ma))
    for rel in _tracked("templates/**/manifest.json",
                        "templates/**/mega_manifest*.json"):
        out.append(("manifest", rel, migrate_manifest))
    for rel in _tracked("tests/data/mpyfile_spec_golden.json"):
        out.append(("golden", rel, migrate_golden))
    for rel in _tracked("tools/parity_sweep/fixtures/*/spec.json"):
        out.append(("spec", rel, migrate_spec_json))
    for rel in _tracked("templates/**/verify_in_maya.py"):
        out.append(("verify", rel, migrate_verify_script))
    return out


def run(apply=False, stream=sys.stdout):
    """Migrate (or, without ``apply``, report). Returns the per-name totals."""
    totals    = collections.Counter()
    per_store = collections.defaultdict(collections.Counter)
    files     = collections.Counter()
    for label, rel, fn in _stores():
        text = _read(rel)
        if "\r\n" in text:
            raise MigrationError("%s: CRLF; the repo is LF" % rel)
        counts = collections.Counter()
        new    = fn(rel, text, counts)
        if not counts:
            continue
        if new == text:
            raise MigrationError("%s: counted renames but changed nothing"
                                 % rel)
        files[label] += 1
        per_store[label].update(counts)
        totals.update(counts)
        stream.write("%-8s %s: %s\n" % (label, rel, ", ".join(
            "%s %d" % (k, counts[k]) for k in RENAME if counts[k])))
        if apply:
            _write(rel, new)
    for label in ("mpn", "ma", "manifest", "golden", "spec", "verify"):
        if files[label]:
            stream.write("[%s] %d files: %s\n" % (label, files[label], ", ".join(
                "%s %d" % (k, per_store[label][k]) for k in RENAME
                if per_store[label][k])))
    stream.write("%s: %d renames in %d files (%s)\n" % (
        "applied" if apply else "dry run", sum(totals.values()),
        sum(files.values()),
        ", ".join("%s %d" % (k, totals[k]) for k in RENAME)))
    return totals


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="write the renames (default: report only)")
    args = ap.parse_args(argv)
    try:
        run(apply=args.apply)
    except MigrationError as exc:
        sys.stderr.write("migrate_attr_names: %s\n" % exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
