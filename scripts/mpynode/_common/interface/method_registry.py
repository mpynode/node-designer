"""Maya-free node-type -> blessed-method registry lookup."""
from __future__ import annotations

from mpynode._common.interface import file_method_interface as _file
from mpynode._common.interface import morph_method_interface as _morph
from mpynode._common.interface import skin_method_interface as _skin

_TYPE_TO_METHODS = {
    "mPyFile":        _file.INTERNAL_API_METHODS,
    "mPySkinCluster": _skin.INTERNAL_API_METHODS,
    "mPyBlendShape":  _morph.INTERNAL_API_METHODS,
}


_TYPE_TO_PROPERTIES = {
    "mPyBlendShape": _morph.INTERNAL_API_PROPERTIES,
}


def methods_for_type(type_name):
    return _TYPE_TO_METHODS.get(type_name, ())


def properties_for_type(type_name):
    """Blessed non-plug READ properties for ``type_name`` (the PROPERTY kind).

    SelfProxy binds these in a tier ABOVE the plug tree, so ``self.morphs``
    returns a live object. Empty for every type that declares none, which is
    every type but mPyBlendShape today.
    """
    return _TYPE_TO_PROPERTIES.get(type_name, ())
