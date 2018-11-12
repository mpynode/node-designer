
import maya.api.OpenMaya as om
import maya.api.OpenMayaRender as omr

from ._mpynode import MPyNode, MPyNodeEventManager

NODE_PY_CLASS = None

try:
    from ._mpynode import MPyNodeC
except:
    NODE_PY_CLASS = MPyNode
else:
    NODE_PY_CLASS = MPyNodeC

    
def maya_useNewAPI():
    """
    The presence of this function tells Maya that the plugin produces, and
    expects to be passed, objects created using the Maya Python API 2.0.
    """
    pass


def initializePlugin(obj):
    """
    Maya's entry point for loading the plugin.
    """

    plugin = om.MFnPlugin(obj, "Trion", "1.0", "Any")

    try:
        plugin.registerNode(NODE_PY_CLASS.NODE_NAME, NODE_PY_CLASS.NODE_ID, NODE_PY_CLASS.nodeCreator, NODE_PY_CLASS.nodeInitializer)

    except:
        raise Exception("Failed to register node: " + NODE_PY_CLASS.NODE_NAME)
    
    try:
        om.MUserEventMessage.registerUserEvent(MPyNodeEventManager.SET_VAR_CALLBACK_NAME)

    except:
        raise Exception("Failed to register user event: " + MPyNodeEventManager.SET_VAR_CALLBACK_NAME)
    
    try:
        om.MUserEventMessage.registerUserEvent(MPyNodeEventManager.WRITE_STORED_VARS_CALLBACK_NAME)

    except:
        raise Exception("Failed to register user event: " + MPyNodeEventManager.WRITE_STORED_VARS_CALLBACK_NAME)
    
    try:
        om.MUserEventMessage.registerUserEvent(MPyNode.PROFILE_CALLBACK_NAME)

    except:
        raise Exception("Failed to register user event: " + MPyNode.PROFILE_CALLBACK_NAME)
    
    try:
        om.MUserEventMessage.registerUserEvent(MPyNode.VAR_VALUES_CALLABCK_NAME)

    except:
        raise Exception("Failed to register user event: " + MPyNode.VAR_VALUES_CALLABCK_NAME)
    
    try:
        om.MUserEventMessage.registerUserEvent(MPyNode.LOG_ERROR_CALLBACK_NAME)

    except:
        raise Exception("Failed to register user event: " + MPyNode.LOG_ERROR_CALLBACK_NAME)
    
    try:
        om.MUserEventMessage.registerUserEvent(MPyNode.LOG_TXT_CALLBACK_NAME)

    except:
        raise Exception("Failed to register user event: " + MPyNode.LOG_TXT_CALLBACK_NAME)    
    
    ##----start callbacks----##
    MPyNode.CALLBACK_MANAGER = MPyNodeEventManager()
    MPyNode.CALLBACK_MANAGER.startCallbacks()


def uninitializePlugin(obj):
    """
    Maya's entry point for unloading the plugin.
    """
    
    ##---shutdown callbacks-----##
    if MPyNode.CALLBACK_MANAGER is not None:
        MPyNode.CALLBACK_MANAGER.stopCallbacks()

    plugin = om.MFnPlugin(obj)

    try:
        plugin.deregisterNode(NODE_PY_CLASS.NODE_ID)

    except:
        raise Exception("Failed to unregister node: " + NODE_PY_CLASS.NODE_NAME)
    
    try:
        om.MUserEventMessage.deregisterUserEvent(MPyNodeEventManager.SET_VAR_CALLBACK_NAME)

    except:
        raise Exception("Failed to unregister user event: " + MPyNodeEventManager.SET_VAR_CALLBACK_NAME)
    
    try:
        om.MUserEventMessage.deregisterUserEvent(MPyNodeEventManager.WRITE_STORED_VARS_CALLBACK_NAME)

    except:
        raise Exception("Failed to unregister user event: " + MPyNodeEventManager.WRITE_STORED_VARS_CALLBACK_NAME)
    
    try:
        om.MUserEventMessage.deregisterUserEvent(MPyNode.PROFILE_CALLBACK_NAME)

    except:
        raise Exception("Failed to unregister user event: " + MPyNode.PROFILE_CALLBACK_NAME)
    
    try:
        om.MUserEventMessage.deregisterUserEvent(MPyNode.VAR_VALUES_CALLABCK_NAME)

    except:
        raise Exception("Failed to unregister user event: " + MPyNode.VAR_VALUES_CALLABCK_NAME)
    
    try:
        om.MUserEventMessage.deregisterUserEvent(MPyNode.LOG_ERROR_CALLBACK_NAME)

    except:
        raise Exception("Failed to unregister user event: " + MPyNode.LOG_ERROR_CALLBACK_NAME)
    
    try:
        om.MUserEventMessage.deregisterUserEvent(MPyNode.LOG_TXT_CALLBACK_NAME)

    except:
        raise Exception("Failed to unregister user event: " + MPyNode.LOG_TXT_CALLBACK_NAME)        
    
