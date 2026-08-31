"""Attribute Editor template for ``mPyBlendShape`` -- the aliased ``weight[]``
stack, drawn the way Maya draws a stock blendShape's targets.

Why this file has to exist
--------------------------
``weight[]`` is a DYNAMIC multi. It has to be: the compile spec reaches a static
plug only through the PRESET path, and preset meta carries no ``is_array``, so a
static multi cannot ride it and the compiled node would have no weights at all
(``_api1/mpy_blend_shape.py``). Maya's DEFAULT Attribute Editor renders dynamic
SCALARS -- which is why ``applyCorrectives`` / ``applyCombos`` show up on their
own -- but it does not enumerate the elements of a dynamic MULTI. So the target
stack drew nothing whatsoever.

An earlier version of this note added that the channel box had been showing the
weights correctly all along. It had not. The channel box needs the ``weight``
ATTRIBUTE itself keyable, not just its elements, and that is a separate fix --
``MPyBlendShape.KEYABLE_ARRAY_INPUTS``. The two surfaces failed independently
and for unrelated reasons.

Maya's own blendShape is immune because its ``weight[]`` is a built-in typed
attribute drawn by an internal C++ editor; there is no ``AEblendShapeTemplate.mel``
in the Maya install to copy from. Hence this.

Why there is MEL in a repo that otherwise has none
--------------------------------------------------
Maya resolves an Attribute Editor layout by looking up a MEL global proc named
after the NODE TYPE -- ``AEmPyBlendShapeTemplate`` for type ``mPyBlendShape``.
There is no Python entry point and no wildcard. :func:`register` therefore
defines three one-line MEL shims that immediately delegate back here, and all
the actual logic stays in Python.

That type-name lookup is also the coverage boundary: a COMPILED sibling
registers under its own derived type name (``comboCorrectives``, not
``mPyBlendShape``), so Maya would look for ``AEcomboCorrectivesTemplate`` and
find nothing. Covering those needs registration driven off "this type has an
aliased weight multi" at bundle-load time, which is deliberately NOT built here
-- no compiled blendShape artifact exists in the tree today.
"""
from __future__ import annotations

import maya.cmds as mc


# The node type whose AE this template drives, and the multi it draws.
NODE_TYPE = "mPyBlendShape"
WEIGHT_ATTR = "weight"

# Child layout holding the weight rows. A SHORT name under the parent the AE
# hands us: Maya's UI paths are full paths, so two AE tabs on two different
# nodes get two different parents and cannot collide.
_ROWS_LAYOUT = "ndMPyBlendShapeWeightRows"

# Slider range. Maya's blendShape weights slide 0..1 but are not clamped there,
# so the FIELD range is opened wider than the slider. Stated rather than silent:
# typing beyond +/-100 is refused by the field.
_SLIDER_MIN, _SLIDER_MAX = 0.0, 1.0
_FIELD_MIN, _FIELD_MAX = -100.0, 100.0


def weight_rows(node):
    """``[(logical_index, label)]`` for every shape on ``node``, in index order.

    EVERY shape is listed -- mains, in-betweens and combos alike. They are all
    real, settable channels: ``resolve_weights`` ADDS the driven amount to
    whatever is keyed on a target's own channel rather than replacing it, so a
    corrective can be dialled by hand. Hiding the derived ones would hide half
    the rig.

    A row is emitted for any index that carries an alias OR has a materialised
    element, so an alias whose element has not been re-materialised yet (Maya
    drops multi elements sitting at the attribute default on save -- see
    ``scene_callbacks._restore_blend_shape_weights``) still gets a row instead of
    silently vanishing from the stack.

    Unaliased elements fall back to ``weight[i]``. That keeps a mid-edit target
    visible rather than dropping it on the floor.

    Pure apart from its plug reads, so it is unit-testable without a GUI -- which
    matters because nothing else in this module can be.
    """
    from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

    # Alias decoding is the wrapper's job and it already handles sparse indices
    # and holes; re-deriving it here would be a second implementation to drift.
    bs = MPyBlendShape(node)
    names = bs.target_names
    present = set(mc.getAttr("%s.%s" % (node, WEIGHT_ATTR),
                             multiIndices=True) or [])

    rows = []
    for i in range(len(names)):
        label = names[i]
        if label or i in present:
            rows.append((i, label or "%s[%d]" % (WEIGHT_ATTR, i)))
    return rows


def _rebuild_rows(parent, plug):
    """(Re)draw the weight rows under ``parent``. GUI-only."""
    node = plug.split(".")[0]
    full = "%s|%s" % (parent, _ROWS_LAYOUT)
    if mc.layout(full, exists=True):
        mc.deleteUI(full, layout=True)

    mc.setUITemplate("attributeEditorTemplate", pushTemplate=True)
    try:
        mc.columnLayout(_ROWS_LAYOUT, adjustableColumn=True, parent=parent)
        for index, label in weight_rows(node):
            mc.attrFieldSliderGrp(
                label=label,
                attribute="%s.%s[%d]" % (node, WEIGHT_ATTR, index),
                minValue=_SLIDER_MIN, maxValue=_SLIDER_MAX,
                fieldMinValue=_FIELD_MIN, fieldMaxValue=_FIELD_MAX,
            )
        mc.setParent("..")
    finally:
        mc.setUITemplate(popTemplate=True)


def weights_new(plug):
    """``callCustom`` build half. Maya has already parented us."""
    _rebuild_rows(mc.setParent(query=True), plug)


def weights_replace(plug):
    """``callCustom`` replace half -- a different node, or the same one after a
    target was added, renamed or removed. Rebuilt wholesale rather than patched:
    the row set is derived from the aliases, and a rename changes labels without
    changing the count."""
    _rebuild_rows(mc.setParent(query=True), plug)


def build_template(node):
    """The body of ``AEmPyBlendShapeTemplate``.

    Everything the default AE already showed is preserved -- ``envelope`` here,
    and the node's own dynamic scalars via ``addExtraControls`` -- so this adds
    the target stack without taking anything away.
    """
    import maya.mel as mel

    mc.editorTemplate(beginScrollLayout=True)

    mc.editorTemplate(beginLayout="Blend Shape Attributes", collapse=False)
    mc.editorTemplate(addControl=["envelope"])
    # MEL, in a file that otherwise avoids it, because the Python binding of
    # this one flag does not work. Measured in Maya 2026 against a real AE:
    # BOTH python spellings -- the attribute positional
    # (``editorTemplate("weight", callCustom=[new, replace])``) and the
    # attribute inside the flag (``callCustom=[new, replace, "weight"]``) --
    # are accepted silently, CONSUME the attribute (its default control stops
    # being drawn) and then never invoke either proc. Nothing is logged. The
    # MEL form below fires both procs and draws all 167 rows; the control was
    # Autodesk's own AEfileTemplate, whose callCustom proc does fire in the
    # same session, which is what localised the fault to the binding.
    mel.eval('editorTemplate -callCustom "AEmPyBlendShapeWeightsNew" '
             '"AEmPyBlendShapeWeightsReplace" "%s";' % WEIGHT_ATTR)
    mc.editorTemplate(endLayout=True)

    # Drawn above, so keep addExtraControls from having a second go at it.
    mc.editorTemplate(suppress="weight")

    mel.eval('AEdependNodeTemplate "%s"' % node)
    mc.editorTemplate(addExtraControls=True)

    mc.editorTemplate(endScrollLayout=True)


# The three shims. Each one immediately hands back to Python; keeping them this
# thin is what stops MEL becoming a second place where behaviour lives.
_MEL_SHIMS = """
global proc AEmPyBlendShapeTemplate(string $nodeName)
{
    python("import mpynode.ui.ae_blend_shape as _ndae; "
           + "_ndae.build_template('" + $nodeName + "')");
}

global proc AEmPyBlendShapeWeightsNew(string $plug)
{
    python("import mpynode.ui.ae_blend_shape as _ndae; "
           + "_ndae.weights_new('" + $plug + "')");
}

global proc AEmPyBlendShapeWeightsReplace(string $plug)
{
    python("import mpynode.ui.ae_blend_shape as _ndae; "
           + "_ndae.weights_replace('" + $plug + "')");
}
"""


def register():
    """Define the MEL shims so Maya can find this template.

    Called from ``initializePlugin``. There is no lazier hook available: Maya
    looks the proc up by name at the moment it builds the AE, so it has to
    already exist.

    A no-op in batch, where there is no AE to draw and ``python()`` inside a MEL
    proc has nothing to serve. Returns True when the procs were defined.
    """
    try:
        if mc.about(batch=True):
            return False
    except Exception:
        return False

    import maya.mel as mel
    mel.eval(_MEL_SHIMS)
    return True
