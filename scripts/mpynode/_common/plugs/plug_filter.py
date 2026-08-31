"""(attributes-tab plug filter): classify a plug as
"framework / Maya base" vs "user-facing" so the Attributes tab
can hide the noise rows that Maya's Node Editor also hides.

Default behavior in the Designer:
 framework attrs are HIDDEN (matches the Node Editor's
 curated view).

Opt-out:
 artist ticks the "Show framework attrs" checkbox in the
 Attributes tab header. State persists via
 ``cmds.optionVar`` key ``mpynodeShowFrameworkAttrs``.

User-added attrs (``is_user_added`` on the walker's RowSpec)
are NEVER filtered -- they're by definition artist-facing.
"""

from __future__ import annotations

import re


# Maya's default name for unnamed Compound-numeric children is
# ``fchildN`` (e.g. ``weightFunction`` declares 3 children which
# the API names ``fchild1``/``fchild2``/``fchild3``). When the
# parent compound itself is hidden by the filter, these orphan
# children would otherwise leak through as meaningless top-level
# rows. Always hide them.
_FCHILD_PATTERN: re.Pattern[str] = re.compile(r"^fchild\d+$")


# ---- ALLOWLIST model (default filter): the inherited plugs to SHOW when "Show
# framework attrs" is OFF. Each wrapper declares a USEFUL_INHERITED_PLUGS
# frozenset; deformer-family wrappers compose this shared base. Leak-proof
# unlike the denylist below -- an attr shows ONLY if explicitly listed. ----
DEFORMER_USEFUL: frozenset[str] = frozenset(
    {
        "input", "inputGeometry", "outputGeometry",
        "originalGeometry", "envelope", "weightList",
    }
)


def is_useful_inherited(short_name, allowlist=()) -> bool:
    """Return True if ``short_name`` is in the node's useful-inherited
    ``allowlist`` (the wrapper's ``USEFUL_INHERITED_PLUGS``). Pure string
    membership -- the inverse of the legacy denylist. Empty name / empty
    allowlist -> False."""
    if not short_name:
        return False
    return short_name in (allowlist or ())


# ---- Blocklist of framework-internal SHORT NAMES that lack the ``_`` prefix:
# Maya DG base attrs, deformer-family base attrs, and mpynode's named attrs
# (Expression / Init / profiling, each surfaced by its own tab). ----
_FRAMEWORK_HIDDEN: frozenset[str] = frozenset(
    {
        # ---- Mpynode named framework attrs (own Designer tabs) ----
        "_computeSource",
        "debug_mode",
        "profile_enabled",
        "deep_profile_enabled",
        "watch_enabled",
        # ---- Maya DG base attrs (MPxNode) ---------------------
        "caching",
        "frozen",
        "isHistoricallyInteresting",
        "nodeState",
        "binMembership",
        "message",
        # ---- Deformer-family base attrs ----------------------
        "blockGPU",
        "function",
        "map64BitIndices",
        "weightFunction",
        # ``weightList``, ``input``, ``outputGeometry``, ``envelope``,
        # ``originalGeometry``, ``envelopeWeightsList`` stay VISIBLE -- the
        # artist actually drives or reads those.
    }
)


# DAG / transform / shape / locator base attrs, declared on EVERY
# DAG-derived node. Without this set the Attributes tab leaked ~250 inherited
# rows the artist never touches.
#
# Parents AND their numeric children are listed: a filtered parent compound
# would otherwise orphan-leak its children as top-level rows (same rationale as
# the fchild pattern).
#
# Safe to hide unconditionally: user-added attrs are removed BEFORE this filter
# runs, and Maya forbids a dynamic attr colliding with an inherited name, so
# these can only match inherited rows. Generated from a stock ``spaceLocator``
# attr dump.
_DAG_BASE_HIDDEN: frozenset[str] = frozenset(
    {
        "antialiasingLevel", "asBackground", "binMembership", "blackBox",
        "borderConnections", "boundingBox", "boundingBoxCenterX",
        "boundingBoxCenterY", "boundingBoxCenterZ", "boundingBoxMax",
        "boundingBoxMaxX", "boundingBoxMaxY", "boundingBoxMaxZ",
        "boundingBoxMin", "boundingBoxMinX", "boundingBoxMinY",
        "boundingBoxMinZ", "boundingBoxSize", "boundingBoxSizeX",
        "boundingBoxSizeY", "boundingBoxSizeZ", "castsShadows", "center",
        "compInstObjGroups", "componentTags", "containerType", "creationDate",
        "creator", "customTreatment", "dagLocalInverseMatrix", "dagLocalMatrix",
        "depthJitter", "displayHandle", "displayLocalAxis", "displayRotatePivot",
        "displayScalePivot", "drawOverride", "dynamics", "geometry",
        "geometryAntialiasingOverride", "ghostColorPost", "ghostColorPostB",
        "ghostColorPostG", "ghostColorPostR", "ghostColorPre", "ghostColorPreB",
        "ghostColorPreG", "ghostColorPreR", "ghostCustomSteps", "ghostDriver",
        "ghostFarOpacity", "ghostFrames", "ghostNearOpacity", "ghostOpacityRange",
        "ghostPostFrames", "ghostPreFrames", "ghostUseDriver", "ghosting",
        "ghostingMode", "ghostsStep", "hardwareFogMultiplier", "hiddenInOutliner",
        "hideOnPlayback", "hyperLayout", "iconName", "identification",
        "ignoreSelfShadowing", "inheritsTransform", "instMaterialAssign",
        "instObjGroups", "intermediateObject", "inverseMatrix", "isCollapsed",
        "isHierarchicalConnection", "layerOverrideColor", "layerRenderable",
        "localPosition", "localPositionX", "localPositionY", "localPositionZ",
        "localScale", "localScaleX", "localScaleY", "localScaleZ", "lodVisibility",
        "matrix", "maxRotLimit", "maxRotLimitEnable", "maxRotXLimit",
        "maxRotXLimitEnable", "maxRotYLimit", "maxRotYLimitEnable", "maxRotZLimit",
        "maxRotZLimitEnable", "maxScaleLimit", "maxScaleLimitEnable",
        "maxScaleXLimit", "maxScaleXLimitEnable", "maxScaleYLimit",
        "maxScaleYLimitEnable", "maxScaleZLimit", "maxScaleZLimitEnable",
        "maxShadingSamples", "maxTransLimit", "maxTransLimitEnable",
        "maxTransXLimit", "maxTransXLimitEnable", "maxTransYLimit",
        "maxTransYLimitEnable", "maxTransZLimit", "maxTransZLimitEnable",
        "maxVisibilitySamples", "maxVisibilitySamplesOverride", "minRotLimit",
        "minRotLimitEnable", "minRotXLimit", "minRotXLimitEnable", "minRotYLimit",
        "minRotYLimitEnable", "minRotZLimit", "minRotZLimitEnable", "minScaleLimit",
        "minScaleLimitEnable", "minScaleXLimit", "minScaleXLimitEnable",
        "minScaleYLimit", "minScaleYLimitEnable", "minScaleZLimit",
        "minScaleZLimitEnable", "minTransLimit", "minTransLimitEnable",
        "minTransXLimit", "minTransXLimitEnable", "minTransYLimit",
        "minTransYLimitEnable", "minTransZLimit", "minTransZLimitEnable",
        "motionBlur", "objectColor", "objectColorB", "objectColorG",
        "objectColorR", "objectColorRGB", "offsetParentMatrix", "outlinerColor",
        "outlinerColorB", "outlinerColorG", "outlinerColorR", "overrideColor",
        "overrideColorA", "overrideColorB", "overrideColorG", "overrideColorR",
        "overrideColorRGB", "overrideDisplayType", "overrideEnabled",
        "overrideLevelOfDetail", "overridePlayback", "overrideRGBColors",
        "overrideShading", "overrideTexturing", "overrideVisibility",
        "parentInverseMatrix", "parentMatrix", "pickTexture", "primaryVisibility",
        "publishedNodeInfo", "receiveShadows", "referenceObject", "renderInfo",
        "renderLayerInfo", "renderType", "renderVolume", "rmbCommand", "rotate",
        "rotateAxis", "rotateAxisX", "rotateAxisY", "rotateAxisZ", "rotateOrder",
        "rotatePivot", "rotatePivotTranslate", "rotatePivotTranslateX",
        "rotatePivotTranslateY", "rotatePivotTranslateZ", "rotatePivotX",
        "rotatePivotY", "rotatePivotZ", "rotateQuaternion", "rotateQuaternionW",
        "rotateQuaternionX", "rotateQuaternionY", "rotateQuaternionZ", "rotateX",
        "rotateY", "rotateZ", "rotationInterpolation", "scale", "scalePivot",
        "scalePivotTranslate", "scalePivotTranslateX", "scalePivotTranslateY",
        "scalePivotTranslateZ", "scalePivotX", "scalePivotY", "scalePivotZ",
        "scaleX", "scaleY", "scaleZ", "selectHandle", "selectHandleX",
        "selectHandleY", "selectHandleZ", "selectionChildHighlighting",
        "shadingSamples", "shadingSamplesOverride", "shear", "shearXY", "shearXZ",
        "shearYZ", "showManipDefault", "specifiedManipLocation", "template",
        "templateName", "templatePath", "templateVersion", "transMinusRotatePivot",
        "transMinusRotatePivotX", "transMinusRotatePivotY",
        "transMinusRotatePivotZ", "translate", "translateX", "translateY",
        "translateZ", "uiTreatment", "underWorldObject", "useObjectColor",
        "useOutlinerColor", "viewMode", "viewName", "visibility", "visibleFraction",
        "visibleInReflections", "visibleInRefractions", "volumeSamples",
        "volumeSamplesOverride", "wireColorB", "wireColorG", "wireColorR",
        "wireColorRGB", "worldInverseMatrix", "worldMatrix", "worldPosition",
        "xformMatrix",
    }
)


def is_framework_attr(short_name: str) -> bool:
    """Return True if ``short_name`` is a framework / Maya-base
    attribute the Designer should hide by default.

    Four rules:
      1. Names starting with ``_`` are mpynode bookkeeping
         (``_initSource``, ``_storedVarsData``, ``_inputAttrs``,
         ``_outputAttrs``, ``_timeIn``, ``_autoEvaluate``).
      2. Names in:data:`_FRAMEWORK_HIDDEN` are named framework
         attrs (curated; see the constant's comment).
      2b. Names in:data:`_DAG_BASE_HIDDEN` are the DAG / transform /
         shape / locator base attrs inherited by every DAG-derived
         mpynode (mPyLocator etc.) -- boundingBox / worldMatrix /
         visibility / objectColorRGB / localPosition / TRS / ... .
      3. Names matching ``fchild\\d+`` are Maya's auto-named
         Compound-numeric children (e.g. ``fchild1``/``fchild2``/
         ``fchild3`` -- the unnamed children of the deformer
         ``weightFunction`` compound). They're meaningless to the
         artist + orphan-leak when the parent compound itself is
         hidden by the filter.
      4. Everything else is user-facing and kept.

    Note: this is string-only by design -- no Maya API query, no
    MFnAttribute construction -- so it's safe to call from any
    context (init-time, in compute, headless, etc.) at zero cost.
    """
    if not short_name:
        return False
    if short_name.startswith("_"):
        return True
    if short_name in _FRAMEWORK_HIDDEN:
        return True
    if short_name in _DAG_BASE_HIDDEN:
        return True
    if _FCHILD_PATTERN.match(short_name):
        return True
    return False


def is_hidden_input_row(short_name, exposed_input_plugs=()) -> bool:
    """Return True if an INPUT-pane row for ``short_name`` should be hidden by
    the default framework filter.

    Same as :func:`is_framework_attr`, except a wrapper may PROMOTE specific
    inherited plugs to always-visible inputs via ``exposed_input_plugs`` (its
    ``EXPOSED_INPUT_PLUGS`` class attr). e.g. mPyTransform surfaces its
    ``translate`` / ``rotate`` / ``scale`` / ``shear`` / ``rotateOrder`` channels
    (+ their X/Y/Z children) as expression INPUTS -- they are DAG framework attrs
    (:data:`_DAG_BASE_HIDDEN`) but the artist must see + drive them. Passing an
    empty ``exposed_input_plugs`` reduces to :func:`is_framework_attr`, so
    non-promoting node types (and the OUTPUT pane) keep the current behaviour."""
    if short_name in (exposed_input_plugs or ()):
        return False
    return is_framework_attr(short_name)


# Internal exposure for tests + future extension.
__all__ = [
    "is_framework_attr",
    "is_useful_inherited",
    "DEFORMER_USEFUL",
    "_FRAMEWORK_HIDDEN",
    "_DAG_BASE_HIDDEN",
    "_FCHILD_PATTERN",
]
