"""MPyNode native C++ pipeline (curated facade).

Ports a live mPyNode into a compiled C++ MPxNode plugin. The pipeline is
organized into subpackages:

  * ``spec``      -- read-only introspection of a live mpynode into a
                     structured, JSON-serializable spec (+ portability
                     assessment) that codegen and the AI porter consume.
  * ``compiler``  -- deterministic numpy->C++ transpiler + scaffold codegen,
                     bundler, and command companion emission.
  * ``ai``        -- LLM-backed porter fallback for compute bodies the
                     deterministic transpiler cannot lower.
  * ``toolchain`` -- platform compile/link decisions, port cache, typeid
                     registry, and the compile controller + verifier.

The parity/codegen harnesses that prove this pipeline are NOT here: they live
with the suite, in ``tests/compile/native/``. Nothing under ``scripts/`` loads
them, so there is nothing to import lazily and nothing to ship.
"""

from . import compiler, ai, toolchain, spec  # noqa: F401
