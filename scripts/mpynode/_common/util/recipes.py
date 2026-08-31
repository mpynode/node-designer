"""Hydration recipes: declarative metadata for each ``mPy*`` node type.

A recipe describes:
  * Which inherited Maya plugs the node exposes (e.g. mPyConstraint inherits
    ``target[]``, ``restTranslate``, ``restRotate`` from MPxConstraint)
  * Which synthetic context variables the bridge injects into the user
    expression namespace (e.g. mPyIkSolver receives ``joints``,
    ``end_effector``, etc. \u2014 these have NO real plug)

Identifying a synthetic entry: ``source_plug == ""`` (input) or
``target_plug == ""`` (output). The Node Designer UI filters synthetics
out of the Inputs/Outputs panels and shows them in the Solver Context
panel instead.

The module ships the dataclasses + registry + ``get_recipe`` lookup.
Each node type registers its own recipe as it comes online.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HydrationInputEntry:
    """One INPUT entry in a recipe. Either real plug OR synthetic context."""

    name: str
    """Variable name in the expression namespace."""

    source_plug: str
    """Maya plug name on the node, e.g. ``"target"``. May be a DOTTED child
    path when the entry names a child of a compound/multi, e.g.
    ``"input.inputGeometry"`` for mPyDeformer's ``input[i].inputGeometry``
    (the index is not written here). EMPTY STRING means synthetic (not a real
    plug; bridge populates from elsewhere)."""

    kind: str
    """Type tag: ``"float"``, ``"vector"``, ``"matrix"``, ``"bool"``,
    ``"enum"``, ``"string"``, ``"constraint_target"``, ``"draw_items"``,..."""

    arity: str = "scalar"
    """One of ``"scalar"``, ``"list"``, ``"list_of_dict"``."""

    children: dict = field(default_factory=dict)
    """For ``list_of_dict`` entries, the child key->kind mapping."""

    description: str = ""
    """Human-readable description for the UI tooltip."""


@dataclass
class HydrationOutputEntry:
    """One OUTPUT entry in a recipe. Either real plug OR synthetic buffer."""

    name: str
    target_plug: str
    """Maya plug name on the node. EMPTY STRING means synthetic
    (e.g. ``joint_rotations``, ``draw_items``)."""

    kind: str
    arity: str = "scalar"
    shape_from_input: str = ""
    """If non-empty, this output's shape is derived from the named input."""

    mode: str = "read"
    """``"read"`` (downstream nodes pull) or ``"compute"`` (bridge writes
    back to scene from the buffer)."""

    description: str = ""


@dataclass
class HydrationRecipe:
    native_type: str
    """Maya node type name, e.g. ``"mPyIkSolver"``."""

    inputs: list[HydrationInputEntry] = field(default_factory=list)
    outputs: list[HydrationOutputEntry] = field(default_factory=list)


# ---- Registry ----


HYDRATION_RECIPES: dict[str, HydrationRecipe] = {}


def register_recipe(recipe: HydrationRecipe) -> None:
    """Register a recipe by its native_type. Idempotent (replaces on dup)."""
    HYDRATION_RECIPES[recipe.native_type] = recipe


def get_recipe(native_type: str) -> Optional[HydrationRecipe]:
    """Look up a recipe by Maya node type name. Returns None if missing."""
    return HYDRATION_RECIPES.get(native_type)
