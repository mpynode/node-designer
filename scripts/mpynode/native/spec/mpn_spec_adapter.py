"""Pure (no live Maya) adapter: a loaded ``.mpn`` payload -> porter spec dict.

Reproduces the exact ``spec_extractor.extract_spec`` output shape from a ``.mpn``
payload (``mpn_io.load_mpn``), so external ``.mpn`` files can be compiled to a
native plugin WITHOUT creating a scene node. Uses ONLY the pure helpers in
``spec_extractor`` (and the pure ``import_follower`` / ``maya_command`` /
``metadata_registry`` modules) -- there is NO ``import maya`` here; that is the
whole point.

Documented deltas vs a LIVE ``extract_spec`` (a live node carries a little extra
that a ``.mpn`` template never stores):
  * ``suggested.classification`` -- ABSENT (no live ``cmds.getClassification``;
    codegen falls back to a plain ``registerNode``, so it is not needed to compile).
  * mPyFile PRESET DG attrs (outColor/uvCoord/fileName) -- reproduced via a
    best-effort TRANSIENT node (``spec_extractor.capture_preset_attrs_transient``)
    when Maya + the mPyFile type are available (the usual compile context), so the
    texture interface is present + byte-identical to the live path. Falls back to
    ABSENT (a no-op interface) only when Maya is unavailable (e.g. a pure test).
  * mPyLocator per-input baked default from a live plug value -- NOT captured (no
    live plug). Declare defaults via ``add_input_attr`` to carry them in the .mpn.
  * ``allow_file_read`` -- approximated as ``mpy_type == "mPyFile"`` (the live
    ``texture/2d`` classification path cannot fire without a live node).
``needs_hover`` (mPyLocator) IS reproduced via the pure ``detect_needs_hover``.
"""
from __future__ import annotations

from mpynode.native.spec.spec_extractor import (
    SCHEMA_VERSION,
    _sanitize_ident,
    suggest_type_id,
    map_mpx_base,
    normalize_attr,
    _summarize_var,
    assess_portability,
    detect_needs_hover,
    _PRESET_CAPTURE_TYPES,
    _GEO_GENERATOR_TYPES,
    _IMAGE_READ_BASE_TYPES,
)


def spec_from_mpn_payload(payload: dict) -> dict:
    """Build a porter spec from a loaded ``.mpn`` payload (pure; no live node).

    Mirrors ``extract_spec``: optional keys are OMITTED (never present-empty) so a
    file-sourced spec is byte-identical to the live spec for a plain node -- which
    keeps the ``port_cache`` key stable across the two entry points.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")

    name       = payload.get("node_name") or ""
    class_path = payload.get("class_path") or ""
    mpy_type   = payload.get("native_type") or ""

    raw_in  = payload.get("input_attrs") or {}
    raw_out = payload.get("output_attrs") or {}

    # mPyFile texture interface (uvCoord/outColor/outAlpha/fileName): registered
    # in C++, not via add_input_attr, so it is absent from the .mpn attr maps.
    # Projected from the declarative SSOT (no createNode) so the compiled node has
    # a real interface. User attrs win (setdefault); lazy import keeps this module
    # import-pure. Runs BEFORE the normalize/order pass so presets flow through
    # identically to the live extract_spec path.
    if mpy_type == "mPyFile":
        from mpynode.native.spec import spec_extractor as _se

        _pin, _pout = _se.capture_preset_attrs_transient(
            mpy_type, payload.get("expression") or "",
            payload.get("init_source") or "", raw_in, raw_out)
        if _pin or _pout:
            raw_in  = dict(raw_in)
            raw_out = dict(raw_out)
            for _k, _v in _pin.items():
                raw_in.setdefault(_k, _v)
            for _k, _v in _pout.items():
                raw_out.setdefault(_k, _v)

    # Emit native attrs in the authored add-order (the live ``extract_spec``
    # path gets this for free from ``get_input_attr_map``). The ``.mpn`` stores
    # the map alphabetically (sort_keys), so sort by each meta's ``order`` here.
    # ``normalize_attr`` drops ``order`` (whitelist), so the spec stays
    # byte-identical to the live one for the same node.
    def _ord(items):
        return sorted(items, key=lambda kv: (kv[1].get("order", 1_000_000), kv[0]))

    inputs  = {n: normalize_attr(m) for n, m in _ord(raw_in.items())}
    outputs = {n: normalize_attr(m) for n, m in _ord(raw_out.items())}

    variables = {k: _summarize_var(v)
                 for k, v in (payload.get("stored_vars") or {}).items()}

    compute = payload.get("expression") or ""
    init    = payload.get("init_source") or ""

    # Followed-import helpers: a pure static parse of compute/init (no live node).
    # Added ONLY when non-empty so a helperless node keeps a byte-identical spec.
    external_helpers      = ""
    external_helper_units = []
    try:
        from mpynode.native.ai import import_follower

        _hres                 = import_follower.collect_helper_sources(compute, init)
        external_helpers      = import_follower.render_for_prompt(_hres)
        external_helper_units = _hres.get("sources") or []
    except Exception:
        external_helpers      = ""
        external_helper_units = []

    from mpynode.native.spec.identity import derive_class_identity

    # Per-class compiled identity (mirror extract_spec byte-for-byte). Transitional
    # fallback to the instance name for a class-less / un-migrated payload.
    spec = {
        "schema_version": SCHEMA_VERSION,
        "source_node":    name,
        "mpy_type":       mpy_type,
        "suggested":      derive_class_identity(class_path or name, mpy_type),
        "inputs":         inputs,
        "outputs":        outputs,
        "variables":      variables,
        "compute":        compute,
        "init":           init,
        "affects":        "all",
    }
    if external_helpers:
        spec["external_helpers"] = external_helpers
    if external_helper_units:
        spec["external_helper_units"] = external_helper_units

    # Methods tab + its statically-detected @maya_command defs (pure AST parse).
    # Merge-seed the per-type default setup exactly as node creation does: a
    # template with no setup of its own gets one the moment a user creates it, so
    # compiling straight from the .mpn -- which never instantiates the node --
    # would otherwise drop that setup and the create command it declares.
    # extract_spec needs no equivalent: it reads a LIVE, already-seeded node.
    methods_src = payload.get("methods_source") or ""
    try:
        from mpynode._common import node_setups as _node_setups

        methods_src = _node_setups.merge_type_default(methods_src, mpy_type)
    except Exception:
        pass
    if methods_src.strip():
        from mpynode._common.methods import maya_command as _maya_command

        spec["methods"] = methods_src
        # Mirror extract_spec: an un-named ``creates=True`` command takes the
        # NODE TYPE's name. See resolve_create_command_names for why the name
        # cannot be a literal in a shared per-type setup.
        spec["commands"] = _maya_command.resolve_create_command_names(
            _maya_command.detect_commands(methods_src),
            (spec.get("suggested") or {}).get("node_type_name"))

    # Per-node metadata (already a dict in the .mpn). Coerce + gate on is_empty,
    # mirroring extract_spec (which coerces ``json.loads`` of the plug).
    metadata_raw = payload.get("metadata")
    if isinstance(metadata_raw, dict) and metadata_raw:
        from mpynode._common.lifecycle import metadata_registry as _md

        try:
            _meta = _md.coerce(metadata_raw)
        except Exception:
            _meta = None
        if _meta is not None and not _md.is_empty(_meta):
            spec["metadata"] = _meta

    # Portability: assess_portability takes the RAW attr maps (not normalized).
    # No live classification -> allow_file_read reduces to mPyFile plus the
    # geometry GENERATORS and the other image-wired emitters (same carve-out as
    # extract_spec; the shipped templates compile through .mpn, so the two entry
    # points must agree).
    # Same split as extract_spec: the bases added for the image READ do not also
    # get the binary-open() embedded-staging sanction, which only the types that
    # can emit EMBEDDED_STAGE_CPP may claim.
    allow_embedded_stage = (mpy_type == "mPyFile"
                            or mpy_type in _GEO_GENERATOR_TYPES)
    allow_file_read = (allow_embedded_stage
                       or mpy_type in _IMAGE_READ_BASE_TYPES)
    port = assess_portability(compute, init, raw_in, raw_out, variables,
                              allow_file_read=allow_file_read,
                              allow_embedded_stage=allow_embedded_stage)
    if port.get("reads_image_file"):
        spec["suggested"]["reads_image_file"] = True
        # Ensure the path input exists. A getattr-helper file reader
        # (getattr(slf, "fileName") in _resolve_image) hides fileName from the
        # self.<name> preset scan, so capture it explicitly -- from the same
        # declarative SSOT the live extract_spec path reads, so the entry (and the
        # port_cache key) is byte-identical across the two entry points.
        # setdefault -> a node that already has fileName is untouched. Skipped
        # when the node reads a string ARRAY path input (multi-file composite):
        # filePaths IS the path source, so fileName would be an unused plug.
        _has_array_path = any(
            (v or {}).get("attr_type") == "string" and (v or {}).get("is_array")
            for v in (raw_in or {}).values())
        if (mpy_type in _PRESET_CAPTURE_TYPES and "fileName" not in inputs
                and not _has_array_path):
            from mpynode.native.spec import spec_extractor as _se2

            for _k, _v in _se2.capture_named_presets_transient(
                    mpy_type, ["fileName"]).items():
                inputs.setdefault(_k, _v)
    # Closest-point mesh query -> the scaffold's <maya/MMeshIntersector.h> and the
    # porter's MESH_CLOSEST_POINT guide. Set only-when-true so every other node's
    # spec stays byte-identical, and lifted HERE as well as in extract_spec so the
    # two entry points agree (the shipped templates compile through .mpn).
    if port.get("uses_mesh_intersector"):
        spec["suggested"]["uses_mesh_intersector"] = True
    # Embedded-image fallback: bake a non-empty ``embeddedImage`` byte buffer
    # (mirrors extract_spec) so the .mpn compile path resolves the baked image
    # when fileName is blank/unreadable. The .mpn stores the var as raw bytes.
    # Added ONLY when non-empty bytes exist -> byte-identical spec otherwise.
    if port.get("reads_embedded_image"):
        _emb = (payload.get("stored_vars") or {}).get("embeddedImage")
        if isinstance(_emb, (bytes, bytearray)) and len(_emb):
            import base64 as _b64

            spec["suggested"]["embedded_image_b64"] = \
                _b64.b64encode(bytes(_emb)).decode("ascii")
    spec["portability"] = port

    # mPyLocator: reproduce needs_hover from the draw expression (pure). The live
    # per-input baked default cannot be reproduced (no live plug) -- documented.
    if mpy_type == "mPyLocator" and detect_needs_hover(compute, init):
        spec["needs_hover"] = True

    return spec
