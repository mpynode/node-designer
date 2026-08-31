"""Deterministic numpy->C++ transpiler (no LLM). Package facade: re-exports the
complete former ``codegen`` module surface so ``codegen.<name>`` keeps resolving."""
from .errors import UnsupportedSpec  # noqa: F401
from . import (  # noqa: F401
    spec_model, nd_runtime, emit_hex, emit_attr, emit_compute, emit_deformer,
    emit_iksolver, emit_locator, emit_geo, emit_transform, node_scaffold,
    build_scripts, py_to_cpp, nd_lower, bundler, command_companion, kernels,
)
# The loop below would cover these, but naming them documents the public API.
from .node_scaffold import generate_cpp  # noqa: F401
from .build_scripts import (  # noqa: F401
    generate_build_sh, generate_build_bat, generate_build_script,
    write_plugin, generate_load_test,
)
# COMPLETE facade: this package replaced a monolithic module, so re-export EVERY
# top-level name (public and private) to keep ``codegen.<name>`` resolving for
# callers and tests. setdefault preserves the explicit imports above.
for _mod in (spec_model, nd_runtime, emit_hex, emit_attr, emit_compute,
             emit_deformer, emit_iksolver, emit_locator, emit_geo,
             emit_transform, node_scaffold, build_scripts):
    for _name in dir(_mod):
        if not _name.startswith("__"):
            globals().setdefault(_name, getattr(_mod, _name))
del _mod, _name
