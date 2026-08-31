"""Leaf error module — imported by codegen/nd_lower/py_to_cpp to break the cycle."""


class UnsupportedSpec(NotImplementedError):
    pass
