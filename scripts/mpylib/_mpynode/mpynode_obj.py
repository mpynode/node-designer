import sys
import copy
import cProfile
import codecs
import traceback
#from collections import UserDict

import maya.api.OpenMaya as om
import maya.api.OpenMayaUI as omui
import maya.api.OpenMayaRender as omr

try:
    import cPickle as pickle # python2
except:
    import pickle # python3
    
    
from ._openmaya import MAngle, MColor, MColorArray, MEulerRotation
from ._openmaya import MFnNurbsCurve, MMatrix, MMatrixArray, MPoint 
from ._openmaya import MPointArray, MQuaternion, MTime, MTimeArray, MVector, MVectorArray


class MPyNode(om.MPxNode):
    """
    Defines a Maya node type called *mPyNode*. This node can be used to write custom Maya nodes without 
    writing new API classes.
    """
    
    PX_CLASS = om.MPxNode

    NODE_NAME = "mPyNode"
    NODE_ID = om.MTypeId(0x001255C3)
    
    CALLBACK_MANAGER = None

    _expression_plug = om.MObject()
    EXPRESSION_ATTR_NAME = "expression"
    EXPRESSION_ATTR_SHORT_NAME = "ex"
    
    ##----stores an internal python dictionary as a string. Dictionary has names and types of all inputs attrbiutes---##
    _in_attrs_str_plug = om.MObject()
    _INPUTS_STR_ATTR_NAME = "_inputAttrs"

    ##----stores an internal python dictionary as a string. Dictionary has names and types of all output attrbiutes---##
    _out_attrs_str_plug = om.MObject()
    _OUTPUTS_STR_ATTR_NAME = "_outputAttrs"
    
    ##----stores an internal python dictionary as a string. Dictionary has names and types of all output attrbiutes---##
    _stored_var_names_plug = om.MObject()
    _STORED_VARS_ATTR_NAME = "_storedVarNames"
    
    _stored_var_data_plug = om.MObject()
    _STORED_VARS_DATA_ATTR_NAME = "_storedVarsData"
    
    _STORED_VARS_PICKLE_PROTOCOL = 0

    ##---attribute types for creation of new nodes---##
    INT_ATTR_TYPE = "int"
    INT_LIST_TYPE = list
    
    FLOAT_ATTR_TYPE = "float"
    FLOAT_LIST_TYPE = list
    
    BOOL_ATTR_TYPE = "bool"
    BOOL_LIST_TYPE = list
    
    ENUM_ATTR_TYPE = "enum"
    ENUM_LIST_TYPE = list
    
    VECTOR_TYPE = "vector"
    VECTOR_LIST_TYPE = MVectorArray
    
    MATRIX_ATTR_TYPE = "matrix"
    MATRIX_LIST_TYPE = MMatrixArray
    
    COLOR_TYPE = "color"
    COLOR_LIST_TYPE = MColorArray
    
    TIME_TYPE = "time"
    TIME_LIST_TYPE = MTimeArray
    
    ANGLE_TYPE = "angle"
    ANGLE_LIST_TYPE = list
    
    EULER_TYPE = "euler"
    EULER_LIST_TYPE = MVectorArray
    
    STRING_TYPE = "string"
    STRING_LIST_TYPE = list
    
    MESH_TYPE = "mesh"
    MESH_LIST_TYPE = list
    
    NURBS_CURVE_TYPE = "nurbsCurve"
    NURBS_CURVE_LIST_TYPE = list
    
    NURBS_SURFACE_TYPE = "nurbsSurface"
    NURBS_SURFACE_LIST_TYPE = list
    
    PY_ATTR_TYPE = "python"
    PY_ATTR_LIST_TYPE = list
    
    ##---default attribute values----##
    DEFAULT_INT = int
    DEFAULT_FLOAT = float
    DEFAULT_BOOL = bool
    DEFAULT_VECTOR = MVector
    DEFAULT_COLOR = MColor
    DEFAULT_MATRIX = MMatrix
    DEFAULT_ANGLE = MAngle
    DEFAULT_STRING = str
    DEFAULT_TIME = MTime
    
    DEFAULT_MESH = None
    DEFAULT_NURBS_CURVE = None
    DEFAULT_NURBS_SURFACE = None
    
    DEFAULT_PY_ATTR = None
    
    ##---dictionary containing get/set methods and default values for each attribute type----##
    ##---keys are strings of attribute types with tuples as values------##
    ##---value tuples are constructed as - "getMethod", "setMethod", default_value, array_type)
    ATTR_TYPES_MAP = {INT_ATTR_TYPE:("_getIntInput", "_setIntOutput", DEFAULT_INT, INT_LIST_TYPE),
                      FLOAT_ATTR_TYPE:("_getFloatInput", "_setFloatOutput", DEFAULT_FLOAT, FLOAT_LIST_TYPE),
                      BOOL_ATTR_TYPE:("_getBoolInput", "_setBoolOutput", DEFAULT_BOOL, BOOL_LIST_TYPE),
                      ENUM_ATTR_TYPE:("_getEnumInput", "_setEnumOutput", DEFAULT_INT, INT_LIST_TYPE),
                      VECTOR_TYPE:("_getVectorInput", "_setVectorOutput", DEFAULT_VECTOR, VECTOR_LIST_TYPE),
                      MATRIX_ATTR_TYPE:("_getMatrixInput", "_setMatrixOutput", DEFAULT_MATRIX, MATRIX_LIST_TYPE),
                      COLOR_TYPE:("_getVectorInput", "_setVectorOutput", DEFAULT_COLOR, COLOR_LIST_TYPE),
                      ANGLE_TYPE:("_getAngleInput", "_setAngleOutput", DEFAULT_ANGLE, ANGLE_LIST_TYPE),
                      EULER_TYPE:("_getVectorInput", "_setVectorOutput", DEFAULT_VECTOR, EULER_LIST_TYPE),
                      STRING_TYPE:("_getStringInput", "_setStringOutput", DEFAULT_STRING, STRING_LIST_TYPE),
                      TIME_TYPE:("_getTimeInput", "_setTimeOutput", DEFAULT_TIME, TIME_LIST_TYPE),
                      MESH_TYPE:("_getMeshInput", None, DEFAULT_MESH, MESH_LIST_TYPE),
                      NURBS_CURVE_TYPE:("_getNurbsCurveInput", None, DEFAULT_NURBS_CURVE, NURBS_CURVE_LIST_TYPE),
                      NURBS_SURFACE_TYPE:("_getNurbsSurfaceInput", None, DEFAULT_NURBS_SURFACE, NURBS_SURFACE_LIST_TYPE),
                      PY_ATTR_TYPE:("_getPythonInput", "_setPythonOutput", DEFAULT_PY_ATTR, PY_ATTR_LIST_TYPE)}
    
    ##----callbacks---##
    PROFILE_CALLBACK_NAME = "emitMPyNodeProfileCallback"
    VAR_VALUES_CALLABCK_NAME = "emitMPyNodeInputValuesCallback"
    LOG_ERROR_CALLBACK_NAME = "emitMPyNodeErrorCallback"
    LOG_TXT_CALLBACK_NAME = "emitMPyNodeTextCallback"
    

    def __init__(self):
        """
        Initialize a new instance of mPyNode
        """
        
        self.PX_CLASS.__init__(self)

        self._node_fn = None

        self._exp_str = None
        self._exp_code_obj = None
        self._exec_vars = None
        
        self.run_profiler = False
        self._watch_var_values = False

        self._input_plug_map = {}
        self._output_plug_map = {}
        
        self._scene_read_cb_id = None
        self._scene_write_cb_id = None
        

    def compute(self, plug, data_block):
        """
        Recompute the given output based on the nodes inputs. The plug represents the data value that needs to be
        recomputed, and the data block holds the storage for all of the node's attributes.
        """
        
        inputs = self._getInputValues(data_block)
        self._exec_vars = self._getInitOutputValues()
        self._exec_vars.update(inputs)
        self._exec_vars["self"] = self
        
        if self.run_profiler:
            profiler = cProfile.Profile()
            profiler.runcall(self._execExpression)
            om.MUserEventMessage.postUserEvent(self.PROFILE_CALLBACK_NAME, (self.thisMObject(), profiler.getstats()))
            
        else:
            self._execExpression()
        
        if self._watch_var_values:
            om.MUserEventMessage.postUserEvent(self.VAR_VALUES_CALLABCK_NAME, (self.thisMObject(), self._exec_vars))          
    
        self._setOutputValues(data_block)
    
        return None
    
    
    def isValid(self):
        """
        Returns whether this MObject is "valid" base on the API definition.
        
        **RETURNS**		*bool*
        """
        
        return om.MObjectHandle(self.thisMObject()).isValid()
    
    
    def isAlive(self):
        """
        Returns whether this MObject is "alive" base on the API definition.
        
        **RETURNS**		*bool*
        """
        
        return om.MObjectHandle(self.thisMObject()).isAlive()
    
    
    def getHashCode(self):
        """
        Returns a unique hash value for this object
        
        **RETURNS**		*int*
        """
        
        return om.MObjectHandle(self.thisMObject()).hashCode()
    
    
    def setStoredVariable(self, var_name, var_val):
        """
        Sets the value of the variable name on this node to the given value. Note that this simply stores a value and does 
        not mark the variable as "stored"
        """
        
        setattr(self, var_name, var_val)
        
        
    def print_(self, txt):
        
        om.MUserEventMessage.postUserEvent(self.LOG_TXT_CALLBACK_NAME, (self.thisMObject(), str(txt)))
    
    
    def readStoredVariables(self):
        """
        Read the curent values of the "stored variable" from the node's internal attribute into properties on the node.
        
        **RETURNS**		*None*
        """
        
        var_val_plug = self._node_fn.findPlug(self._STORED_VARS_DATA_ATTR_NAME, False)
        
        var_val_str = var_val_plug.asString()
        
        if var_val_str:
            var_val_map = self._loadPickle(var_val_str)
            
            if var_val_map:
                for var_name, val in var_val_map.items():
                    setattr(self, var_name, val)
        
    
    def writeStoredVariables(self):
        """
        Store the values of the "stored vairables" from their node properties to the nodes internal attribute so
        they can be saved to disc.
        
        **RETURNS**		*None*
        """        
        
        var_attr_plug = self._node_fn.findPlug(self._stored_var_names_plug, False)
        var_names_str = var_attr_plug.asString()
        
        var_names = self._loadPickle(var_names_str) if var_names_str else None
        var_val_map = {}
        
        if var_names:
            for var_name in var_names:
                if hasattr(self, var_name):
                    var_val_map[var_name] = getattr(self, var_name)
        
        var_map_str = self._dumpPickle(var_val_map)
        var_data_plug = self._node_fn.findPlug(self._stored_var_data_plug, False)
        var_data_plug.setString(var_map_str)
        

    def _getInitOutputValues(self):
        """
        Creates intial values for all output attributes on the node.
        """
        
        outputs = {}

        for attr_name, attr_data in self._output_plug_map.items():
            
            #---if atribute is array, set its default to a list of the correct length----##
            if attr_data[3]:
                outputs[attr_name] = attr_data[4]([attr_data[2]] * attr_data[0].numElements())

            else:
                outputs[attr_name] = attr_data[2]

        return outputs


    def copyInternalData(self, orig_node):
        """
        On duplication this method is called on the duplicated node with the node being duplicated passed as the
        parameter. Overriding this method gives your node a chance to duplicate any internal data you've been storing
        and manipulating outside of normal attribute data.
        """

        self._refreshPlugArrays()
        
        self._node_fn = om.MFnDependencyNode(self.thisMObject())
        self._exp_str = self._getExpressionFromPlug()
        self._exp_code_obj = compile(self._exp_str, "<string>", "exec")


    def setInternalValueInContext(self, plug, data_handle, ctx):
        """
        This method is overriden by nodes that store attribute data in some internal format.
        
        This catches changes to this internal string attributes on this node.
        """

        if plug == self.__class__._expression_plug:
            self._exp_str = self._getDataHandleString(data_handle)
            self._exp_code_obj = compile(self._exp_str, "<string>", "exec")

        elif plug == self.__class__._in_attrs_str_plug:
            attr_str = self._getDataHandleString(data_handle)
            self._refreshInputPlugArrays(attr_str)

        elif plug == self.__class__._out_attrs_str_plug:
            attr_str = self._getDataHandleString(data_handle)
            self._refreshOutputPlugArrays(attr_str)

        return False


    def _setOutputValues(self, data_block):
        """
        Sets all output plugs to the values created by the expression.
        """

        if not self._output_plug_map:
            self._refreshOutputPlugArrays()

        if self._output_plug_map:

            for attr_name, plug_data in self._output_plug_map.items():

                if attr_name in self._exec_vars:

                    ##----call the appropriate _set method for the current plug----##
                    plug_data[1](data_block, plug_data[0], self._exec_vars[attr_name], is_array=plug_data[3])


    def _getInputValues(self, data_block):
        """
        Returns the current values of input plugs as an arg dictionary
        """

        if not self._input_plug_map:
            self._refreshInputPlugArrays()

        inputs = {}

        if self._input_plug_map:

            for attr_name, plug_data in self._input_plug_map.items():

                inputs[attr_name] = plug_data[1](data_block, plug_data[0], is_array=plug_data[2]) ## pass the data handle to the proper _get method

        return inputs
    
    
    def setDependentsDirty(self, plug, affected_plugs):
        """
        This method can be overridden in user defined nodes to specify which plugs should be set dirty based upon an
        input plug which Maya is marking dirty. The list of plugs for Maya to mark dirty is returned by the plug
        array [affected_plugs].
        """
        
        if (not self._input_plug_map) or (not self._output_plug_map):
            self._refreshPlugArrays()
            
        plug_name = plug.partialName() if not plug.isChild else plug.parent().partialName()
        
        ##---look for the attribute name in the input map...handling array attr syntax as needed---##
        if (plug_name.split("[")[0] in self._input_plug_map) or (plug == self.__class__._expression_plug):
        

            ##---set affected_plugs equal to all output plugs----##
            for out_plug_name in self._output_plug_map.keys():
            
                out_plug = self._output_plug_map[out_plug_name][0]

                affected_plugs.append(out_plug)

                if out_plug.isArray and out_plug.numElements() > 0:

                    for e in range(out_plug.numElements()):
                        
                        e_plug = out_plug.elementByPhysicalIndex(e)
                        affected_plugs.append(e_plug)
                        
                        if e_plug.isCompound:
                            map(affected_plugs.append, map(e_plug.child, range(e_plug.numChildren())))
                        
                elif (not out_plug.isArray) and out_plug.isCompound:
                    map(affected_plugs.append, map(out_plug.child, range(out_plug.numChildren())))


    def postConstructor(self):
        """
        Internally maya creates two objects when a user defined node is created, the internal MObject and the
        user derived object. The association between the these two objects is not made until after the MPxNode
        constructor is called. This implies that no MPxNode member function can be called from the MPxNode constructor.
        The postConstructor will get called immediately after the constructor when it is safe to call any MPxNode member function.
        """

        ##---make sure Maya does not deleted the node if it's output/input nodes are deleted----##
        ##----this no longer works after Maya update??? This was removed from MPxNode class---##
        self.existWithoutInConnections = True
        self.existWithoutOutConnections = True

        self._node_fn = om.MFnDependencyNode(self.thisMObject())
        
        if MPyNode.CALLBACK_MANAGER is not None:
            MPyNode.CALLBACK_MANAGER.addNodeToQueue(self)


    def _refreshPlugArrays(self):
        """
        Rebuild internal input and output plug data.
        """

        self._refreshInputPlugArrays()
        self._refreshOutputPlugArrays()


    def _refreshInputPlugArrays(self, attr_str=None):
        """
        Rebuild internal input plug data. Optional attr_str arg, is the string value of the internal string attr _inputAttrs.
        If attr_str is not given, it will be pulled from the _inputAttrs attr directly.
        """        

        self._input_plug_map = {}
        
        ##---string value not passed into method, get it from internal string attr----## 
        if attr_str is None:
            attr_plug = self._node_fn.findPlug(self._INPUTS_STR_ATTR_NAME, False)
            attr_str = attr_plug.asString()

        if attr_str:
            attr_dict = self._loadPickle(attr_str) ##convert string to python dictionary

            if attr_dict:

                for attr_name, attr_properties in attr_dict.items():
                    
                    if self._node_fn.hasAttribute(attr_name):
                        plug = self._node_fn.findPlug(attr_name, False)
                        
                        attr_type_map = self.ATTR_TYPES_MAP[attr_properties[0]] ##get proper dict based on attribute type
                        get_func_name = attr_type_map[0] ##get the string name of the function to 'get' values for this attribute
    
                        ##----value indices are (MPlug of this plug, the 'get' function, bool whether this if an array attribute)
                        self._input_plug_map[plug.partialName()] = (plug, getattr(self, get_func_name), plug.isArray)


    def _refreshOutputPlugArrays(self, attr_str=None):
        """
        Rebuild internal output plug data. Optional attr_str arg, is the string value of the internal string attr _outputAttrs.
        If attr_str is not given, it will be pulled from the _outputAttrs attr directly.
        """
        
        self._output_plug_map = {}
        
        ##---string value not passed into method, get it from internal string attr----## 
        if attr_str is None:
            attr_plug = self._node_fn.findPlug(self._OUTPUTS_STR_ATTR_NAME, False)
            attr_str = attr_plug.asString()

        if attr_str:
            attr_dict = self._loadPickle(attr_str) ##convert string to python dictionary

            if attr_dict:

                for attr_name, attr_properties in attr_dict.items():
                    
                    if self._node_fn.hasAttribute(attr_name):
                        
                        plug = self._node_fn.findPlug(attr_name, False)
    
                        attr_type_map = self.ATTR_TYPES_MAP[attr_properties[0]]
                        set_func_name = attr_type_map[1] ##get the string name of the function to 'set' values for this attribute
                        default_val = attr_type_map[2]() if  attr_type_map[2] is not None else None ##get default value for this plug type
                        array_type = attr_type_map[3]
    
                        ##----value indices are (MPlug of this plug, the 'set' function, default value for the plug, bool whether this if an array attribute)
                        self._output_plug_map[plug.partialName()] = (plug, getattr(self, set_func_name), default_val, plug.isArray, array_type)
                        
                        
    def _refreshInternalPlugArrays(self, attr_str=None):
        """
        Rebuild plug data for 'internal' attributes. Optional attr_str arg, is the string value of the internal string attr _internalAttrs.
        If attr_str is not given, it will be pulled from the _internalAttrs attr directly.
        """

        self._stored_var_map = {}
        
        ##---string value not passed into method, get it from internal string attr----## 
        if attr_str is None:
            attr_plug = self._node_fn.findPlug(self._STORED_VARS_ATTR_NAME, False)
            attr_str = attr_plug.asString()

        if attr_str:
            attr_dict = self._loadPickle(attr_str) ##convert string to python dictionary

            if attr_dict:

                for attr_name, attr_properties in attr_dict.items():
                    
                    if self._node_fn.hasAttribute(attr_name):
                        
                        plug = self._node_fn.findPlug(attr_name, False)
    
                        attr_type_map = self.ATTR_TYPES_MAP[attr_properties[0]]
                        get_func_name = attr_type_map[0] ##get the string name of the function to 'get' values for this attribute
                        set_func_name = attr_type_map[1] ##get the string name of the function to 'set' values for this attribute
                        default_val = attr_type_map[2]() ##get default value for this plug type
                        array_type = attr_type_map[3]
    
                        ##----value indices are (MPlug of this plug, the 'set' function, default value for the plug, bool whether this if an array attribute)
                        self._stored_var_map[plug.partialName()] = (plug, getattr(self, set_func_name), default_val, plug.isArray, array_type)    
                        

    def _getDataHandleString(self, data_handle):
        """
        Return the current string value of the given data handle
        """

        exp_str_data = None

        exp_str_data = om.MFnStringData(data_handle.data())
        exp_str = exp_str_data.string()

        return exp_str
    

    def _getExpressionFromPlug(self):
        """
        Return the current value of the expression string
        """        

        node_fn = om.MFnDependencyNode(self.thisMObject())
        plug = node_fn.findPlug(self.EXPRESSION_ATTR_NAME, False)

        return plug.asString()


    def _execExpression(self):
        """
        Runs the expression that was given in the node's *expression* attribute using the given input and output
        lists.
        """

        if self._exp_code_obj:
            
            try:
                #exec(self._exp_code_obj, None, self._exec_vars)
                exec(self._exp_code_obj, self._exec_vars, self._exec_vars) # fixes nested vars and namepaces
                
            except:            
                except_data = sys.exc_info()
                tb_lines = traceback.format_exception(except_data[0], except_data[1], except_data[2])
                err_str = "Expression failed for " + self._node_fn.name() + ":\n" + "".join(tb_lines)
                om.MUserEventMessage.postUserEvent(self.LOG_ERROR_CALLBACK_NAME, (self.thisMObject(), err_str))
                
                print (err_str)      
                
          
            
            
    def _getGenericInput(self, data_block, plug, data_class, get_func_name, is_array=False, array_type=list):
        """
        Generic method fot getting the plugs input value using the given MDataHandle function name (get_func_name).
        Returns a value or tuple of values depending on the is_array arg.
        """        
        
        if not is_array:
            in_handle = data_block.inputValue(plug)
            
            ##---use the appropriate 'get' method on the MDataHandle---##
            return data_class(getattr(in_handle, get_func_name)())

        else:
            in_handles = data_block.inputArrayValue(plug)

            num_elements = len(in_handles)

            if num_elements > 0:

                values = array_type()

                for i in range(num_elements):

                    in_handle = in_handles.inputValue()
                    ##---use the appropriate 'get' method on the MDataHandle---##
                    values.append(getattr(in_handle, get_func_name)())

                    if i != (num_elements - 1):
                        in_handles.next()

                return values

        return None
            

    def _getFloatInput(self, data_block, plug, is_array=False):
        """
        Get the given plugs input value as a float. Returns a float value or tuple of floats
        depending on the is_array arg.
        """
        return self._getGenericInput(data_block, plug, float, "asDouble", is_array=is_array, array_type=self.FLOAT_LIST_TYPE)



    def _getIntInput(self, data_block, plug, is_array=False):
        """
        Get the given plugs input value as an int. Returns an int value or tuple of ints
        depending on the is_array arg.
        """
        
        return self._getGenericInput(data_block, plug, int, "asInt", is_array=is_array)
    
    
    def _getEnumInput(self, data_block, plug, is_array=False):
        """
        Get the given plugs input value as an short. Returns an int value or tuple of ints
        depending on the is_array arg.
        """
        
        return self._getGenericInput(data_block, plug, int, "asShort", is_array=is_array)    


    def _getBoolInput(self, data_block, plug, is_array=False):
        """
        Get the given plugs input value as a bool. Returns an bool value or tuple of bools
        depending on the is_array arg.
        """
        
        return self._getGenericInput(data_block, plug, bool, "asBool", is_array=is_array, array_type=self.BOOL_LIST_TYPE)


    def _getVectorInput(self, data_block, plug, is_array=False):
        """
        Get the given plugs input value as 3 float tuple. Returns an 3 float tuple value or tuple of 3 float tuples
        depending on the is_array arg.
        """
        
        return self._getGenericInput(data_block, plug, MVector, "asVector", is_array=is_array, array_type=self.VECTOR_LIST_TYPE)
    
    
    def _getAngleInput(self, data_block, plug, is_array=False):
        """
        Get the given plugs input value as a angle. Returns an angle value or tuple of angles
        depending on the is_array arg.
        """
        
        return self._getGenericInput(data_block, plug, MAngle, "asAngle", is_array=is_array, array_type=self.ANGLE_LIST_TYPE)
    
    
    def _getStringInput(self, data_block, plug, is_array=False):
        """
        Get the given plugs input value as a float. Returns a float value or tuple of floats
        depending on the is_array arg.
        """
        
        return self._getGenericInput(data_block, plug, str, "asString", is_array=is_array)
    
    
    def _getPythonInput(self, data_block, plug, is_array=False):
        """
        Get the given plugs input value as a pickled string. Returns a python object or list of tuple objects
        depending on the is_array arg.
        """
        
        if not is_array:
            in_handle = data_block.inputValue(plug)
            return self._loadPickle(in_handle.asString())

        else:
            in_handles = data_block.inputArrayValue(plug)

            num_elements = len(in_handles)

            if num_elements > 0:

                values = []

                for i in range(num_elements):

                    in_handle = in_handles.inputValue()
                    values.append(self._loadPickle(in_handle.asString()))

                    if i != (num_elements - 1):
                        in_handles.next()

                return values

        return None
    
    
    def _getTimeInput(self, data_block, plug, is_array=False):
        """
        Get the given plugs input value as time. Returns a time value or tuple of time values
        depending on the is_array arg.
        """
        
        if not is_array:
            in_handle = data_block.inputValue(plug)
            
            return MTime(in_handle.asTime())

        else:
            in_handles = data_block.inputArrayValue(plug)

            num_elements = len(in_handles)

            if num_elements > 0:

                values = MTimeArray()

                for i in range(num_elements):

                    in_handle = in_handles.inputValue()
                    ##---use the appropriate 'get' method on the MDataHandle---##
                    values.append(in_handle.asTime())

                    if i != (num_elements - 1):
                        in_handles.next()

                return values

        return None
    
    
    def _getGeoInput(self, data_block, plug, get_func_name, fn_class, is_array=False, array_type=list):
        """
        Get the given plugs input value as geometry. Returns a instance of the appropriate geo MFn class based on the
        given args
        """        
        
        if not is_array:
            in_handle = data_block.inputValue(plug)
            
            ##---use the appropriate 'get' method on the MDataHandle and wrap it in the function set class---##
            return fn_class(getattr(in_handle, get_func_name)())

        else:
            in_handles = data_block.inputArrayValue(plug)

            num_elements = len(in_handles)

            if num_elements > 0:

                values = array_type()

                for i in range(num_elements):

                    in_handle = in_handles.inputValue()
                    ##---use the appropriate 'get' method on the MDataHandle---##
                    values.append(fn_class(getattr(in_handle, get_func_name)()))

                    if i != (num_elements - 1):
                        in_handles.next()

                return tuple(values)

        return None        
    
    
    def _getMeshInput(self, data_block, plug, is_array=False):
        
        """
        Get the given plugs input value as a mesh. Returns a mesh or tuple of meshes
        depending on the is_array arg.
        """
        
        return self._getGeoInput(data_block, plug, "asMesh", om.MFnMesh, is_array=is_array,
                                 array_type=self.MESH_LIST_TYPE)
    
    
    def _getNurbsCurveInput(self, data_block, plug, is_array=False):
        
        """
        Get the given plugs input value as a nurbs curve. Returns a curve or tuple of curves
        depending on the is_array arg.
        """
        
        return self._getGeoInput(data_block, plug, "asNurbsCurve", MFnNurbsCurve, is_array=is_array,
                                 array_type=self.NURBS_CURVE_LIST_TYPE)
    
    
    def _getNurbsSurfaceInput(self, data_block, plug, is_array=False):
        
        """
        Get the given plugs input value as a nurbs curve. Returns a curve or tuple of curves
        depending on the is_array arg.
        """
        
        return self._getGeoInput(data_block, plug, "asNurbsSurface", om.MFnNurbsSurface, is_array=is_array,
                                 array_type=self.NURBS_SURFACE_LIST_TYPE)


    def _getMatrixInput(self, data_block, plug, is_array=False):
        """
        Get the given plugs input value as 4x4 float tuple. Returns an 4x4 float tuple value or tuple of float 4x4 tuples
        depending on the is_array arg.
        """
        
        return self._getGenericInput(data_block, plug, MMatrix, "asMatrix", is_array=is_array, array_type=self.MATRIX_LIST_TYPE)


    def _setGenericOutput(self, data_block, plug, func_name, val, is_array=False):
        """
        Sets the value of the given output plug to the given numeric value.
        """         

        if not is_array:
            out_handle = data_block.outputValue(plug)

            if val is not None:
                ##---get the appropriate 'set' function from the MDataHandle----##
                set_func = getattr(out_handle, func_name)
                set_func(val)     

            out_handle.setClean()

        else:
            out_handles = data_block.outputArrayValue(plug)

            if val is not None:
                num_elements = len(out_handles)

                if num_elements > 0:

                    for i, cur_val in enumerate(val):

                        out_handle = out_handles.outputValue()
                        ##---get the appropriate 'set' function from the MDataHandle----##
                        set_func = getattr(out_handle, func_name)
                        set_func(cur_val)

                        if i < (num_elements - 1):
                            out_handles.next()
                        else:
                            break

            data_block.setClean(plug.attribute())
            out_handles.setAllClean()


    def _setFloatOutput(self, data_block, plug, val, is_array=False):
        """
        Sets the value of the given output plug to the given float value 
        """         

        self._setGenericOutput(data_block, plug, "setDouble", val, is_array=is_array)


    def _setIntOutput(self, data_block, plug, val, is_array=False):
        """
        Sets the value of the given output plug to the given int value 
        """         

        self._setGenericOutput(data_block, plug, "setInt", val, is_array=is_array)
        
        
    def _setEnumOutput(self, data_block, plug, val, is_array=False):
        """
        Sets the value of the given output plug to the given enum (short) value 
        """         

        self._setGenericOutput(data_block, plug, "setShort", val, is_array=is_array)    


    def _setBoolOutput(self, data_block, plug, val, is_array=False):
        """
        Sets the value of the given output plug to the given bool value 
        """         

        self._setGenericOutput(data_block, plug, "setBool", val, is_array=is_array)


    def _setVectorOutput(self, data_block, plug, val, is_array=False):
        """
        Sets the value of the given output plug to the given vector value 
        """
        if val is not None:
            
            if not is_array:
                out_handle = data_block.outputValue(plug)
                out_handle.set3Double(val[0], val[1], val[2]) #allows lists len > 3 to be used
                out_handle.setClean()
    
            else:
                out_handles = data_block.outputArrayValue(plug)
                num_elements = len(out_handles)
    
                if num_elements > 0:
    
                    for i, cur_val in enumerate(val):
    
                        out_handle = out_handles.outputValue()
                        out_handle.set3Double(cur_val[0], cur_val[1], cur_val[2]) #allows lists len > 3 to be used
    
                        if i < (num_elements - 1):
                            out_handles.next()
                        else:
                            break                        
    
                data_block.setClean(plug.attribute())
                out_handles.setAllClean()        
        
        
    def _setAngleOutput(self, data_block, plug, val, is_array=False):
        """
        Sets the value of the given output plug to the given int value 
        """         

        self._setGenericOutput(data_block, plug, "setMAngle", val, is_array=is_array)    
        
        
    def _setTimeOutput(self, data_block, plug, val, is_array=False):
        """
        Sets the value of the given output plug to the given vector value
        """
        
        if not is_array:
            out_handle = data_block.outputValue(plug)

            if val is not None:
                out_handle.setMTime(val)

            out_handle.setClean()

        else:
            out_handles = data_block.outputArrayValue(plug)

            if val:
                num_elements = len(out_handles)

                if num_elements > 0:

                    for i, cur_val in enumerate(val):

                        out_handle = out_handles.outputValue()
                        out_handle.setMTime(cur_val)

                        if i < (num_elements - 1):
                            out_handles.next()
                        else:
                            break                            
            
            data_block.setClean(plug.attribute())
            out_handles.setAllClean()


    def _setMatrixOutput(self, data_block, plug, val, is_array=False):
        """
        Sets the value of the given output plug to the given matrix value 
        """        

        if not is_array:
            out_handle = data_block.outputValue(plug)

            if val is not None:
                out_handle.setMMatrix(om.MMatrix(val))

            out_handle.setClean()

        else:
            out_handles = data_block.outputArrayValue(plug)

            if val is not None:
                num_elements = len(out_handles)

                if num_elements > 0:

                    for i, cur_val in enumerate(val):

                        out_handle = out_handles.outputValue()                    

                        out_handle.setMMatrix(om.MMatrix(cur_val))

                        if i < (num_elements - 1):
                            out_handles.next()
                        else:
                            break                            

            data_block.setClean(plug.attribute())
            out_handles.setAllClean()
            
            
    def _setStringOutput(self, data_block, plug, val, is_array=False):
        """
        Sets the value of the given output plug to the given float value 
        """
        
        self._setGenericOutput(data_block, plug, "setString", val, is_array=is_array)
        
        
    def _setPythonOutput(self, data_block, plug, val, is_array=False):
        """
        Sets the value of the given output plug to the pickled value of the given python object or list of
        python objects if is_array=True
        """
        
        if not is_array:
            out_handle = data_block.outputValue(plug)
            out_handle.setString(self._dumpPickle(val))

            out_handle.setClean()

        else:
            out_handles = data_block.outputArrayValue(plug)

            if val is not None:
                num_elements = len(out_handles)

                if num_elements > 0:

                    for i, cur_val in enumerate(val):

                        out_handle = out_handles.outputValue()
                        out_handle.setString(self._dumpPickle(cur_val))

                        if i < (num_elements - 1):
                            out_handles.next()
                        else:
                            break                            

            data_block.setClean(plug.attribute())
            out_handles.setAllClean()
            
            
    def _dumpPickle(self, data):
        """
        Use base64 encoding to convert python data to a pure ASCII string via pickle at its highest protocol
        """
        
        return codecs.encode(pickle.dumps(data,protocol=pickle.HIGHEST_PROTOCOL), "base64").decode()
    
    
    def _loadPickle(self, data):
        """
        Use base64 decoding to convert a pure ASCII string back to a python data via pickle
        """
        try:
            try:
                return pickle.loads(codecs.decode(data.encode(), "base64"))
            except:
                return pickle.loads(str(data)) # backwards compatibility with default pickle protocol    
        except:
            pass
        
        return None
    

    @classmethod
    def nodeCreator(cls):
        """
        @classmethod - Returns a new instance of the node to Maya
        """

        return cls()
    
    
    @classmethod
    def _baseInitializer(cls):
        
        ##---create expression string attr----##
        exp_str_data = om.MFnStringData()
        exp_str_creator = exp_str_data.create("None")
        exp_attr = om.MFnTypedAttribute()
        cls._expression_plug = exp_attr.create(cls.EXPRESSION_ATTR_NAME, cls.EXPRESSION_ATTR_SHORT_NAME,
                                               om.MFnStringData.kString, exp_str_creator)

        exp_attr.connectable = True
        exp_attr.writable = True
        exp_attr.storable = True
        exp_attr.internal = True 
        exp_attr.keyable = True
        exp_attr.hidden = True

        ##----create internal input attr string data---##
        in_str_data = om.MFnStringData()
        in_str_creator = in_str_data.create("")
        in_data_attr = om.MFnTypedAttribute()
        cls._in_attrs_str_plug = in_data_attr.create(cls._INPUTS_STR_ATTR_NAME, cls._INPUTS_STR_ATTR_NAME,
                                                         om.MFnStringData.kString, in_str_creator)

        in_data_attr.connectable = False
        in_data_attr.readable = False
        in_data_attr.writable = True
        in_data_attr.storable = True
        in_data_attr.internal = True
        in_data_attr.keyable = False
        in_data_attr.hidden = True

        ##----create internal output attr string data---##
        out_str_data = om.MFnStringData()
        out_str_creator = out_str_data.create("")
        out_data_attr = om.MFnTypedAttribute()
        cls._out_attrs_str_plug = out_data_attr.create(cls._OUTPUTS_STR_ATTR_NAME, cls._OUTPUTS_STR_ATTR_NAME,
                                                           om.MFnStringData.kString, out_str_creator)

        out_data_attr.connectable = False
        out_data_attr.readable = False
        out_data_attr.writable = True
        out_data_attr.storable = True
        out_data_attr.internal = True
        out_data_attr.keyable = False
        out_data_attr.hidden = True
        
        ##----create attrs for storing variables to disk---##
        var_list_str_data = om.MFnStringData()
        var_list_str_creator = var_list_str_data.create("")
        var_list_attr = om.MFnTypedAttribute()
        cls._stored_var_names_plug = var_list_attr.create(cls._STORED_VARS_ATTR_NAME, cls._STORED_VARS_ATTR_NAME,
                                                                 om.MFnStringData.kString, var_list_str_creator)

        var_list_attr.connectable = False
        var_list_attr.readable = False
        var_list_attr.writable = True
        var_list_attr.storable = True
        var_list_attr.internal = True
        var_list_attr.keyable = False
        var_list_attr.hidden = True
        
        var_vals_str_data = om.MFnStringData()
        var_vals_str_creator = var_vals_str_data.create("")
        var_vals_attr = om.MFnTypedAttribute()
        cls._stored_var_data_plug = var_vals_attr.create(cls._STORED_VARS_DATA_ATTR_NAME, cls._STORED_VARS_DATA_ATTR_NAME,
                                                         om.MFnStringData.kString, var_vals_str_creator)
        
        var_vals_attr.connectable = False
        var_vals_attr.readable = False
        var_vals_attr.writable = True
        var_vals_attr.storable = True
        var_vals_attr.internal = True
        var_vals_attr.keyable = False
        var_vals_attr.hidden = True        

        ##------add all attributes to the node----##
        cls.addAttribute(cls._expression_plug)
        cls.addAttribute(cls._in_attrs_str_plug)
        cls.addAttribute(cls._out_attrs_str_plug)
        cls.addAttribute(cls._stored_var_names_plug)
        cls.addAttribute(cls._stored_var_data_plug)
        

    @classmethod
    def nodeInitializer(cls):
        """
        @classmethod - Defines the node's default attributes and the relationships to each other.
        Maya creates some sort of weird static link to this function that makes overriding it in child class impossible(??).
        To get around this...call a seperate function _baseInitializer which can be called from the nodeInitializer() of all
        child classes
        """
        
        cls._baseInitializer()
        
        
class MPyNodeEventManager(object):
    """
    Class for handling all callbacks related to MPyNode. Listens for scene save events and writes internal data to attributes
    to be stored with the scene.
    """
    
    SET_VAR_CALLBACK_NAME = "setVarCallback"
    WRITE_STORED_VARS_CALLBACK_NAME = "writeStorableVarCallback"
    
    
    def __init__(self):
        """
        Initalizes a new MPyNodeEventManager instance
        """
        
        self._py_nodes = {}
        self._add_node_queue = []
        self._py_nodes_removed = {}
        
        self._scene_open_cb_id = None
        self._scene_read_cb_id = None
        self._scene_new_cb_id = None
        self._scene_write_cb_id = None
        
        self._node_added_cb_id = None
        self._node_removed_cb_id = None
        
        self._set_var_cb_id = None
        self._write_var_cb_id = None
        
    
    def startCallbacks(self):
        """
        Starts all callbacks managed by this class
        
        **RETURNS**		*None*
        """
        
        self._scene_open_cb_id = om.MSceneMessage.addCallback(om.MSceneMessage.kBeforeOpen, self._onBeforeSceneOpened, None)
        self._scene_read_cb_id = om.MSceneMessage.addCallback(om.MSceneMessage.kAfterFileRead, self._onPostSceneRead, None)
        self._scene_new_cb_id = om.MSceneMessage.addCallback(om.MSceneMessage.kBeforeNew, self._onBeforeSceneOpened, None)
        self._scene_write_cb_id = om.MSceneMessage.addCallback(om.MSceneMessage.kBeforeSave, self._onSceneSaved, None)
        
        self._node_added_cb_id = om.MDGMessage.addNodeAddedCallback(self._onNodeAdded, MPyNode.NODE_NAME, None)
        self._node_removed_cb_id = om.MDGMessage.addNodeRemovedCallback(self._onNodeRemoved, MPyNode.NODE_NAME, None)
        
        self._set_var_cb_id = om.MUserEventMessage.addUserEventCallback(self.SET_VAR_CALLBACK_NAME, self._onSetStoredVariable, None)
        self._write_var_cb_id = om.MUserEventMessage.addUserEventCallback(self.WRITE_STORED_VARS_CALLBACK_NAME, self._onWriteStoredVariables, None)
    
    
    def stopCallbacks(self):
        """
        Stops all callbacks managed by this class
        
        **RETURNS**		*None*
        """        
        
        om.MMessage.removeCallback(self._scene_open_cb_id)
        om.MMessage.removeCallback(self._scene_read_cb_id)
        om.MMessage.removeCallback(self._scene_new_cb_id)
        om.MMessage.removeCallback(self._scene_write_cb_id)
        
        om.MMessage.removeCallback(self._node_added_cb_id)
        om.MMessage.removeCallback(self._node_removed_cb_id)
        
        om.MMessage.removeCallback(self._set_var_cb_id)
        om.MMessage.removeCallback(self._write_var_cb_id)
        
        self.clear()
        
        
    def _onNodeAdded(self, m_obj, data):
        """
        Called by this class' MDGMessage.addNodeAddedCallback
        """
        
        self._processNodeQueue(m_obj=m_obj)
        
        
    def _onNodeRemoved(self, m_obj, data):
        """
        Called by this class' MDGMessage.addNodeRemovedCallback
        """        
        
        if not m_obj.isNull():
            hash_code = om.MObjectHandle(m_obj).hashCode()
            
            if hash_code in self._py_nodes:
                
                if not hash_code in self._py_nodes_removed:
                    self._py_nodes_removed[hash_code] = self._py_nodes[hash_code]
                
                del(self._py_nodes[hash_code])
        
        
    def _onBeforeSceneOpened(self, data):
        """
        Called by this class' MSceneMessage.kBeforeNew callback
        """
        
        self.clear()
        
        
    def _onSceneSaved(self, data):
        """
        Called by this class' MSceneMessage.kBeforeSave callback
        """        
        
        self._processNodeQueue()
        
        if self._py_nodes:
            
            for py_node in self._py_nodes.values():
                
                if py_node.isValid():
                    py_node.writeStoredVariables()
                
                elif not py_node.isAlive():
                    self.removeNode(py_node)
        
        
    def _onPostSceneRead(self, data):
        """
        Called by this class' MSceneMessage.kAfterSceneReadAndRecordEdits callback
        """
        
        self._processNodeQueue()
        
        if self._py_nodes:
            for py_node in self._py_nodes.values():
                py_node.readStoredVariables()
                
                
    def _onSetStoredVariable(self, data):
        """
        Called by custom callback "setStorableVarCallback" to set a stored variable to a given value
        """
        
        for node_hash, var_vals in data.items():
            
            if node_hash in self._py_nodes:
                for var_name, var_val in var_vals.items():
                    self._py_nodes[node_hash].setStoredVariable(var_name, var_val)
            
            else:
                raise RuntimeError("Unable to set storable variable data for node: " + str(node_hash) + " = " + str(var_vals))
            
            
    def _onWriteStoredVariables(self, data):
        """
        Called by custom callback "writeStorableVarCallback" to write the current value of all stored variables on the
        given node to the node.
        """
        
        for node_hash in data:
            
            if node_hash in self._py_nodes and self._py_nodes[node_hash].isValid():
                self._py_nodes[node_hash].writeStoredVariables()
            
            else:
                raise RuntimeError("Unable to write storable variables for node: " + str(node_hash))
            
        
    def _processNodeQueue(self, m_obj=None):
        """
        Safely moves added nodes from the 'queue' to the main node list
        """
        
        if self._add_node_queue:
            for py_node in self._add_node_queue:
                self.addNode(py_node)
                
            self._add_node_queue = []
            
        if m_obj:
            hash_code = om.MObjectHandle(m_obj).hashCode()
            
            if hash_code in self._py_nodes_removed:
                self.addNode(self._py_nodes_removed[hash_code])
                del(self._py_nodes_removed[hash_code])
            
        #if m_obj:
            #self.addNode(MPyNode(m_obj))
    
    
    def addNodeToQueue(self, py_node):
        """
        Safe way to add a brand new MPyNode to the callback list during its postConstructor() method. Using this will
        delay accessing the node's underlying API structure until it's fully intialized and it is safe to do so.
        
        **py_node**		instance of *MPyNode*
        
        **RETURNS**		*None*
        """
        
        self._add_node_queue.append(py_node)
    
    
    def addNode(self, py_node):
        """
        Add a MPyNode to the callback list. Note the this not safe to use until the node it fully intialized. Use
        addNodeToQueue() method to add a node while its being intialized.
        
        **py_node**		instance of *MPyNode*
        
        **RETURNS**		*None*
        """
        
        hash_code = py_node.getHashCode()
        
        if not hash_code in self._py_nodes:
            self._py_nodes[hash_code] = py_node
        
    
    def removeNode(self, py_node):
        """
        Remove a MPyNode from the callback list.
        
        **py_node**		instance of *MPyNode*
        
        **RETURNS**		*None*
        """        
        
        hash_code = py_node.getHashCode()
        
        if hash_code in self._py_nodes:
            del(self._py_nodes[hash_code])
            
            
    def _clearNodeMap(self):
        """
        Remove all MPyNodes from the callback dict only
        """
        
        self._py_nodes = {}
    
    
    def clear(self):
        """
        Remove all MPyNodes from the callback list.
        
        **RETURNS**		*None*
        """          
        
        self._clearNodeMap()
        self._py_nodes_removed = {}
        self._add_node_queue = []