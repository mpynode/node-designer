"""User-facing wrapper for the mPyConstraint plug-in.

Constraint usage (script-friendly equivalent of pointConstraint /
parentConstraint with arbitrary user math)::

 from mpynode.wrappers.mpy_constraint import MPyConstraint

 src = mc.polyCube(name="srcCube")[0]
 dst = mc.polyCube(name="drivenCube")[0]
 mc.setAttr(dst + ".translateZ", 5) # offset so they're visually distinct

 c = MPyConstraint.create(name="myConstraint")
 mc.connectAttr(src + ".translate", c.get_name() + ".targetTranslate")
 c.add_output_attr("constrained_pos", "vector")
 c.set_compute_expression("constrained_pos = self.targetTranslate")
 mc.connectAttr(c.get_name() + ".constrained_pos", dst + ".translate", force=True)

The ``targetTranslate`` / ``targetRotate`` / ``targetWeight`` /
``restTranslate`` / ``restRotate`` preset inputs are always
available via ``self.X`` (no ``add_input_attr`` needed).
"""

from __future__ import annotations

from mpynode.wrappers._mpy_node import MPyNode as _MPyNodeWrapper


class MPyConstraint(_MPyNodeWrapper):
    """Same wrapper API as MPyNode but the underlying node type is
    mPyConstraint (with preset constraint-style inputs)."""

    # No bridge-injected non-plug ``self.X`` names: every ``self.X`` the
    # expression touches is either a plug (visible in Attributes) or per-call
    # user storage (visible in Variables-User).
    INTERNAL_API_SLOTS = ()

    # No wrapper-level authoring API. Declared EMPTY on purpose rather than
    # omitted, so "nothing to offer" reads as a decision: list_preset_inputs is
    # introspection over the five preset plugs the Attributes tab already shows.
    AUTHORING_API = ()

    # Preset plug values the bridge pre-reads into compute_locals (EM
    # worker-thread safety), plus the geometry-data side channel. This tier
    # wins on read, so a stored var of the same name is unreachable. Read by
    # mpynode._common.interface.reserved_names.
    RESERVED_COMPUTE_LOCALS = (
        ("targetTranslate", "read", "np.ndarray(3,) -- the targetTranslate plug, pre-read from the data block"),
        ("targetRotate",    "read", "np.ndarray(3,) -- the targetRotate plug, pre-read from the data block"),
        ("restTranslate",   "read", "np.ndarray(3,) -- the restTranslate plug, pre-read from the data block"),
        ("restRotate",      "read", "np.ndarray(3,) -- the restRotate plug, pre-read from the data block"),
        ("targetWeight",    "read", "float -- the targetWeight plug, pre-read from the data block"),
        ("_mpy_geom_data",  "read", "framework side channel -- the EM-safe geometry DATA MObjects keyed by input name"),
    )

    # Attributes-tab allowlist (framework OFF): the constraint's own
    # target/rest I/O; everything else inherited is framework noise.
    USEFUL_INHERITED_PLUGS = frozenset({
        "targetTranslate", "targetTranslateX", "targetTranslateY",
        "targetTranslateZ", "targetRotate", "targetRotateX", "targetRotateY",
        "targetRotateZ", "targetWeight", "restTranslate", "restTranslateX",
        "restTranslateY", "restTranslateZ", "restRotate", "restRotateX",
        "restRotateY", "restRotateZ",
    })
    NATIVE_TYPE = "mPyConstraint"

    @classmethod
    def create(cls, name: str = None,
               skip_selection: bool = False) -> "MPyConstraint":
        # Inherit MPyNode's create(); name=None derives from the Class there.
        return super().create(name=name, skip_selection=skip_selection)

    PRESET_INPUTS = (
        "targetTranslate",
        "targetRotate",
        "targetWeight",
        "restTranslate",
        "restRotate",
    )

    def list_preset_inputs(self) -> list[str]:
        """Return the 5 preset constraint-style input plug names."""
        return list(self.PRESET_INPUTS)
