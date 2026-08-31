"""Single source of truth for a compiled node's identity (the ``suggested``
triple), derived from the node's Class.

Collapses the previously-duplicated derivation in
``spec_extractor.extract_spec`` and ``mpn_spec_adapter.spec_from_mpn_payload``
(``porter.apply_type_name`` remains a deliberate name-only override -- see there).

``type_id`` here is only a throwaway suggestion -- the real, collision-free id is
allocated at assemble time by ``typeid_registry`` -- so it must NEVER be treated
as authoritative, and it is excluded from the ``port_cache`` key.
"""
from __future__ import annotations

from mpynode.native.spec.spec_extractor import (
    _sanitize_ident,
    suggest_type_id,
    map_mpx_base,
)


def derive_class_identity(class_path, mpy_type, *, node_type_name_override=None):
    """Return the ``suggested`` identity dict for a Class.

    ``class_path`` is the canonical dotted Class path (e.g.
    ``mpynode_user.Procrustes`` or ``myrig.nodes.BlackWhiteFile``); its short
    name drives the compiled type + C++ class symbol. For the transitional
    class-less path an instance name may be passed instead.

    ``class_name`` is the sanitized short name with a forced UPPERCASE first
    letter -- a no-op for a real PascalCase Class (``Procrustes`` -> ``Procrustes``)
    and byte-identical to the historical derivation for an instance-name fallback
    (``equiv_node`` -> ``Equiv_node``). ``node_type_name`` is its lower-first form
    (or the explicit override). Keys: ``node_type_name``, ``class_name``,
    ``type_id``, plus ``**map_mpx_base(mpy_type)``.
    """
    short = (class_path or "").rpartition(".")[2] or (class_path or "")
    sane = _sanitize_ident(short)
    class_name = sane[:1].upper() + sane[1:]
    if node_type_name_override and str(node_type_name_override).strip():
        node_type_name = _sanitize_ident(node_type_name_override)
    else:
        node_type_name = class_name[:1].lower() + class_name[1:]
    # Seed type_id from node_type_name: per-class deterministic AND byte-identical
    # to the historical ``suggest_type_id(name)`` for the instance-name fallback
    # (node_type_name == the old sanitized name there). type_id is a throwaway
    # suggestion anyway (reallocated at assemble, excluded from the port_cache key).
    return {
        "node_type_name": node_type_name,
        "class_name": class_name,
        "type_id": suggest_type_id(node_type_name),
        **map_mpx_base(mpy_type),
    }
