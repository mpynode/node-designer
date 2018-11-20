import os
import copy
import cPickle
from collections import OrderedDict

import maya.cmds as mc
import maya.api.OpenMaya as om

from .._base import MNode


class MPyNode(MNode):
    """
    Universal Python API node
    """

    NODE_TYPE = "mPyNode"

    PLUGIN_CHECK = True
    PLUGINS = ("mpynode_plugin.py",)

    ATTR_TYPE_INT = "int"
    ATTR_TYPE_FLOAT = "float"
    ATTR_TYPE_BOOL = "bool"
    ATTR_TYPE_VECTOR = "vector"
    ATTR_TYPE_MATRIX = "matrix"
    ATTR_TYPE_COLOR = "color"
    ATTR_TYPE_TIME = "time"
    ATTR_TYPE_ANGLE = "angle"
    ATTR_TYPE_EULER = "euler"
    ATTR_TYPE_STRING = "string"
    ATTR_TYPE_ENUM = "enum"
    ATTR_TYPE_PY = "python"

    ATTR_TYPE_MESH = "mesh"
    ATTR_TYPE_NURBS_CURVE = "nurbsCurve"
    ATTR_TYPE_NURBS_SURFACE= "nurbsSurface"

    _NODE_NUMERIC_TYPES = (ATTR_TYPE_INT, ATTR_TYPE_FLOAT, ATTR_TYPE_TIME, ATTR_TYPE_ANGLE)
    _PY_TYPE_INT = int
    _PY_TYPE_FLOAT = float
    _PY_TYPE_BOOL = bool
    _PY_TYPE_VECTOR = list
    _PY_TYPE_COLOR = list
    _PY_TYPE_MATRIX = list
    _PY_TYPE_ANGLE = float
    _PY_TYPE_EULER = list
    _PY_TYPE_STRING = str
    _PY_TYPE_TIME = float
    _PY_TYPE_ENUM = int
    _PY_TYPE_PY = str

    _ATTR_TO_PY_MAP = {ATTR_TYPE_INT:_PY_TYPE_INT, ATTR_TYPE_FLOAT:_PY_TYPE_FLOAT, ATTR_TYPE_BOOL:_PY_TYPE_BOOL,
                       ATTR_TYPE_VECTOR:_PY_TYPE_VECTOR, ATTR_TYPE_MATRIX:_PY_TYPE_MATRIX, ATTR_TYPE_COLOR:_PY_TYPE_COLOR,
                       ATTR_TYPE_TIME:_PY_TYPE_TIME, ATTR_TYPE_ANGLE:_PY_TYPE_ANGLE, ATTR_TYPE_EULER:_PY_TYPE_EULER,
                       ATTR_TYPE_STRING:_PY_TYPE_STRING, ATTR_TYPE_PY:_PY_TYPE_PY, ATTR_TYPE_ENUM:_PY_TYPE_ENUM}

    _ATTR_DEFAULT_VAL_TYPES = (ATTR_TYPE_INT, ATTR_TYPE_FLOAT, ATTR_TYPE_BOOL, ATTR_TYPE_TIME, ATTR_TYPE_ANGLE, ATTR_TYPE_ENUM)

    _NEW_INPUT_TYPES = {ATTR_TYPE_INT:"long", ATTR_TYPE_FLOAT:"double", ATTR_TYPE_BOOL:"bool", ATTR_TYPE_VECTOR:"double3", ATTR_TYPE_MATRIX:"matrix", ATTR_TYPE_ENUM:"enum",
                        ATTR_TYPE_COLOR:"double3", ATTR_TYPE_ANGLE:"doubleAngle", ATTR_TYPE_EULER:"double3", ATTR_TYPE_STRING:"string", ATTR_TYPE_TIME:"time", ATTR_TYPE_PY:"string",
                        ATTR_TYPE_MESH:"mesh", ATTR_TYPE_NURBS_CURVE:"nurbsCurve", ATTR_TYPE_NURBS_SURFACE:"nurbsSurface"}
    _NEW_INPUT_ATTR_KARGS = {"storable":True, "writable":True, "readable":False, "multi":False}

    _NEW_OUTPUT_TYPES = {ATTR_TYPE_INT:"long", ATTR_TYPE_FLOAT:"double", ATTR_TYPE_BOOL:"bool", ATTR_TYPE_VECTOR:"double3", ATTR_TYPE_MATRIX:"matrix", ATTR_TYPE_ENUM:"enum",
                         ATTR_TYPE_COLOR:"double3", ATTR_TYPE_ANGLE:"doubleAngle", ATTR_TYPE_EULER:"double3", ATTR_TYPE_STRING:"string", ATTR_TYPE_TIME:"time", ATTR_TYPE_PY:"string"}
    _NEW_OUTPUT_ATTR_KARGS = {"storable":False, "writable":False, "readable":True, "multi":False}

    _VECTOR_COMP_NAMES = {ATTR_TYPE_VECTOR:("X", "Y", "Z"), ATTR_TYPE_COLOR:("R", "G", "B"), ATTR_TYPE_EULER:("X", "Y", "Z")}
    _VECTOR_COMP_TYPES = {ATTR_TYPE_VECTOR:"double", ATTR_TYPE_COLOR:"double", ATTR_TYPE_EULER:"doubleAngle"}

    _ENUM_ATTR_TYPES = ("enum",)
    _NUMERIC_ATTR_TYPES = ("long", "short", "byte", "float", "double", "doubleAngle", "doubleLinear", "time", "bool") + _ENUM_ATTR_TYPES
    _MATRIX_ATTR_TYPES = ("matrix", "fltMatrix")
    _VECTOR_ATTR_TYPES = ("float3", "double3", "reflectance", "spectrum")
    _STRING_ATTR_TYPES = ("char", "string")
    _MESH_ATTR_TYPES = ("mesh",)
    _NURBS_CURVE_ATTR_TYPES = ("nurbsCurve",)
    _NURBS_SURFACE_ATTR_TYPES = ("nurbsSurface",)

    _INPUT_TYPES_INT = _NUMERIC_ATTR_TYPES
    _INPUT_TYPES_FLOAT = _NUMERIC_ATTR_TYPES
    _INPUT_TYPES_BOOL = _NUMERIC_ATTR_TYPES
    _INPUT_TYPES_VECTOR = _VECTOR_ATTR_TYPES
    _INPUT_TYPES_MATRIX = _MATRIX_ATTR_TYPES
    _INPUT_TYPES_COLOR = _VECTOR_ATTR_TYPES
    _INPUT_TYPES_TIME = _NUMERIC_ATTR_TYPES
    _INPUT_TYPES_ANGLE = _NUMERIC_ATTR_TYPES
    _INPUT_TYPES_EULER = _VECTOR_ATTR_TYPES
    _INPUT_TYPES_STRING = _STRING_ATTR_TYPES
    _INPUT_TYPES_PY = _STRING_ATTR_TYPES
    _INPUT_TYPES_ENUM = _NUMERIC_ATTR_TYPES
    _INPUT_TYPES_MESH = _MESH_ATTR_TYPES
    _INPUT_TYPES_NURBS_CURVE = _NURBS_CURVE_ATTR_TYPES
    _INPUT_TYPES_NURBS_SURFACE = _NURBS_SURFACE_ATTR_TYPES

    _INPUT_TYPES_MAP = {ATTR_TYPE_INT:_INPUT_TYPES_INT, ATTR_TYPE_FLOAT:_INPUT_TYPES_FLOAT, ATTR_TYPE_BOOL:_INPUT_TYPES_BOOL,
                        ATTR_TYPE_VECTOR:_INPUT_TYPES_VECTOR, ATTR_TYPE_MATRIX:_INPUT_TYPES_MATRIX, ATTR_TYPE_COLOR:_INPUT_TYPES_COLOR,
                        ATTR_TYPE_TIME:_INPUT_TYPES_TIME, ATTR_TYPE_ANGLE:_INPUT_TYPES_ANGLE, ATTR_TYPE_EULER:_INPUT_TYPES_EULER,
                        ATTR_TYPE_STRING:_INPUT_TYPES_STRING, ATTR_TYPE_ENUM:_INPUT_TYPES_ENUM, ATTR_TYPE_PY:_INPUT_TYPES_PY,
                        ATTR_TYPE_MESH:_INPUT_TYPES_MESH,
                        ATTR_TYPE_NURBS_CURVE:_INPUT_TYPES_NURBS_CURVE, ATTR_TYPE_NURBS_SURFACE:_INPUT_TYPES_NURBS_SURFACE}

    _OUTPUT_TYPES_INT = _NUMERIC_ATTR_TYPES
    _OUTPUT_TYPES_FLOAT = _NUMERIC_ATTR_TYPES
    _OUTPUT_TYPES_BOOL = _NUMERIC_ATTR_TYPES
    _OUTPUT_TYPES_VECTOR = _VECTOR_ATTR_TYPES
    _OUTPUT_TYPES_MATRIX = _MATRIX_ATTR_TYPES
    _OUTPUT_TYPES_COLOR = _VECTOR_ATTR_TYPES
    _OUTPUT_TYPES_TIME = _NUMERIC_ATTR_TYPES
    _OUTPUT_TYPES_ANGLE = _NUMERIC_ATTR_TYPES
    _OUTPUT_TYPES_EULER = _VECTOR_ATTR_TYPES
    _OUTPUT_TYPES_STRING = _STRING_ATTR_TYPES
    _OUTPUT_TYPES_PY = _STRING_ATTR_TYPES
    _OUTPUT_TYPES_ENUM = _NUMERIC_ATTR_TYPES

    _OUTPUT_TYPES_MAP = {ATTR_TYPE_INT:_OUTPUT_TYPES_INT, ATTR_TYPE_FLOAT:_OUTPUT_TYPES_FLOAT, ATTR_TYPE_BOOL:_OUTPUT_TYPES_BOOL,
                         ATTR_TYPE_VECTOR:_OUTPUT_TYPES_VECTOR, ATTR_TYPE_MATRIX:_OUTPUT_TYPES_MATRIX, ATTR_TYPE_COLOR:_OUTPUT_TYPES_COLOR,
                         ATTR_TYPE_TIME:_OUTPUT_TYPES_TIME, ATTR_TYPE_ANGLE:_OUTPUT_TYPES_ANGLE, ATTR_TYPE_EULER:_OUTPUT_TYPES_EULER,
                         ATTR_TYPE_STRING:_OUTPUT_TYPES_STRING, ATTR_TYPE_PY:_OUTPUT_TYPES_PY, ATTR_TYPE_ENUM:_OUTPUT_TYPES_ENUM}

    _EXPRESSION_ATTR_NAME = "expression"

    _INPUTS_STR_ATTR_NAME = "_inputAttrs"
    _OUTPUTS_STR_ATTR_NAME = "_outputAttrs"

    _STORED_VARS_ATTR_NAME = "_storedVarNames"
    _STORED_VARS_DATA_ATTR_NAME = "_storedVarsData"

    _RUN_PROFILER_VAR_NAME = "run_profiler"
    _WATCH_VALUES_VAR_NAME = "_watch_var_values"

    ##----------------##
    _TYPE_ATTR = "type"
    _INIT_EXPRESSION_STR = None

    _ATTR_MAP_TYPE_KEY = "attr_type"
    ATTR_MAP_ARRAY_KEY = "is_array"

    ##-----callbacks--------##
    _SET_VAR_CALLBACK_NAME = "setVarCallback"
    _WRITE_STORED_VARS_CALLBACK_NAME = "writeStorableVarCallback"

    ##-------------these are for subclassing to create new node 'types'------------------##

    ##----dictionary with string attribute names as keys and keyword argument dictionaries as values for intializing new input attributes---##
    ##----The keywords in the argument dictionaries are those supported be the addInputAttr() method of this class---##
    INIT_INPUT_ATTRS = None

    ##----dictionary with string attribute names as keys and keyword argument dictionaries as values for intializing new output attributes---##
    ##----The keywords in the argument dictionaries are those supported be the addOutputAttr() method of this class---##
    INIT_OUTPUT_ATTRS = None

    ##----dictionary with string attribute names as keys and keyword argument dictionaries as values for intializing generic attributes---##
    ##----these attribute will NOT be accessible from within the compute process of node-----##
    ##----The keywords in the argument dictionaries are those supported be the addAttr() method of this class---## 
    INIT_ATTRS = None
    
    ##----dictionary with storable variable names as keys and the variable's value as values---##     
    INIT_STORED_VARS = None


    ##----properties for saving the current node to a python file on disk----##
    _CODE_CLASS_MODULE = "pylib.nodes"
    _CODE_CLASS = "MPyNode"
    _CODE_TAB = "    "
    _CODE_COMPUTE_FUNC_NAME = "_compute"

    _CODE_IMPORT_STR = "from " +  _CODE_CLASS_MODULE + " import " + _CODE_CLASS + "\n\n\n"
    _CODE_COMPUTE_DEF = _CODE_TAB + "def " + _CODE_COMPUTE_FUNC_NAME + "(self):\n"

    _CODE_INIT_EXPRESSION_STR = ""
    _CODE_INIT_PROPERTIES = {"INIT_INPUT_ATTRS":None, "INIT_INPUT_ATTR_ARGS":None,
                             "INIT_OUTPUT_ATTRS":None, "INIT_OUTPUT_ATTR_ARGS":None}

    _ASCII_FILE_EXT = "mpya"
    _BINARY_FILE_EXT = "mpyb"


    def __init__(self, node=None, name=None, exp_str=None, input_map=None, output_map=None, stored_var_map=None):
        """
        Initialize a new MPyNode object

        **node**		*string* name or *MNode* of an existing mPyNode to intialize from. A new mPyNode is created
        if this arg is not provided.

        **name**		optional *string* name to give the node if creating a new node. Ignored 
        if initializing from an existing mPyNode

        **RETURNS**		*None*

        >>> ## create new mPyNode
        >>> node = MPyNode()
        >>>
        >>> ## create new mPyNode and set its name at same time
        >>> node = MPyNode(name="fooFoo")
        >>>
        >>> ## intialize a new MPyNode instance from an existing mPyNode node
        >>> node = MPyNode("existingNodeName")

        """

        self._pluginCheck()

        if not node:
            new_node = self._createNew(name)

        else:
            new_node = node

        MNode.__init__(self, new_node)

        if not node:

            if self._INIT_EXPRESSION_STR:
                self.setExpression(self._INIT_EXPRESSION_STR)

            if self.INIT_INPUT_ATTRS:
                self._initInputAttrs()

            if self.INIT_OUTPUT_ATTRS:
                self._initOutputAttrs()

            if self.INIT_ATTRS:
                self._initGenAttrs()

            if exp_str:
                self.setExpression(exp_str)

            if input_map:
                self._initInputsFromMap(input_map)

            if output_map:
                self._initOutputsFromMap(output_map)
                
            if stored_var_map:
                self._initStoredVarsFromMap(stored_var_map)
                
            elif self.INIT_STORED_VARS:
                self._initStoredVarsFromMap(self.INIT_STORED_VARS)

            self._addTypeAttr()


    def _createNew(self, name=None, input_map=None, output_map=None, stored_var_map=None):
        """
        Build a new node and return it as MNode
        """

        if not name:
            classname = self.__class__.__name__
            name = classname[0].lower() + classname[1:] + "1"

        return MNode.createNode(self.NODE_TYPE, name=name)


    def _initInputsFromMap(self, input_map):
        """
        Create input attributes from the given dictionary
        """

        cur_inputs = self.listInputAttrs()

        if not cur_inputs:
            cur_inputs = {}

        for input_name in input_map.keys():
            if not cur_inputs.has_key(input_name):
                self.addInputAttr(input_name, **input_map[input_name])


    def _initOutputsFromMap(self, output_map):
        """
        Create output attributes from the given dictionary
        """        

        cur_outputs = self.listOutputAttrs()

        if not cur_outputs:
            cur_outputs = {}

        for output_name in output_map.keys():

            if not cur_outputs.has_key(output_name):
                self.addOutputAttr(output_name, **output_map[output_name])


    def _initStoredVarsFromMap(self, stored_var_map):
        """
        Initialize stored variables from the given dictionary
        """

        for var_name, var_val in stored_var_map.items():
            self.setStoredVariable(var_name, var_val)


    def _addTypeAttr(self):
        """
        Sets an string attr on the node to mark its 'type'
        """

        if not self.__class__ == MPyNode:

            self.setStringAttr(self._TYPE_ATTR, self.__class__.__name__, hidden=True)


    def _initInputAttrs(self):
        """
        Creates input attributes if the INIT_INPUT_ATTRS and INIT_INPUT_ATTR_ARGS properties are set
        """

        for attr_name, attr_args in self.INIT_INPUT_ATTRS.items():
            self.addInputAttr(attr_name, **attr_args)


    def _initOutputAttrs(self):
        """
        Creates input attributes if the INIT_OUTPUT_ATTRS property is set
        """

        for attr_name, attr_args in self.INIT_OUTPUT_ATTRS.items():
            self.addOutputAttr(attr_name, **attr_args) 


    def _initGenAttrs(self):
        """
        Creates input attributes if the INIT_OUTPUT_ATTRS property is set
        """    

        for attr_name, attr_args in self.INIT_ATTRS.items():
            self.addAttr(attr_name, **attr_args)


    def _appendInternalDictAttr(self, internal_attr, attr_name, attr_type):
        """
        Appends the given long_name, attr_type pair to the node's internal dictionary that keeps track of input/output
        attributes
        """

        py_data = self._getInternalPyAttr(internal_attr)

        if not py_data:
            py_data = {str(attr_name):[str(attr_type)]}

        elif not py_data.has_key(attr_name):
            py_data[attr_name] = [attr_type]

        self._setInternalPyAttr(internal_attr, py_data)


    def _appendInternalListAttr(self, internal_attr, val):
        """
        Appends the given val to the node's attribute of the given name as a python list
        """

        py_list = self._getInternalPyAttr(internal_attr)

        if not py_list:
            py_list = []

        py_list.append(val)

        self._setInternalPyAttr(internal_attr, py_list)


    def _setInternalPyAttr(self, internal_attr, py_data):
        """
        Sets the given internal string attribute to the string value of the given dictionary
        """

        str_val = self._dumpPickle(py_data) if py_data else self._dumpPickle(None)

        self.setAttr(internal_attr, str_val, type="string")


    def _getInternalPyAttr(self, attr_name):
        """
        Gets the given internal string attribute as its dictionary value
        """

        str_val = self.getAttr(attr_name)

        if str_val:

            py_data = self._loadPickle(str_val)

            if py_data:
                return py_data

        return None


    def _getInternalAttrMap(self, attr_name):
        """
        Returns the attribute data stored in the given internal string attribute as a dictionary of lists.
        Keys of the list are the attribute names while the values are [str(attr_type)]
        """        

        str_val = self.getAttr(attr_name)

        if str_val:
            return self._loadPickle(str_val)

        return None


    def _getAttrStringList(self, attr_name):
        """
        Returns the attribute names stored in the given internal string attribute.
        """

        attr_dict = self._getInternalAttrMap(attr_name)

        if attr_dict:
            return tuple(attr_dict.keys())

        return None


    def _getInternalInputString(self):
        """
        For unit testing use only. Returns the value of the internal input string so it can be validated
        """

        str_val = self.getAttr(self._INPUTS_STR_ATTR_NAME)

        if str_val:
            return str(str_val)

        return None


    def _getInternalOutputString(self):
        """
        For unit testing use only. Returns the value of the internal output string so it can be validated
        """        

        str_val = self.getAttr(self._OUTPUTS_STR_ATTR_NAME)

        if str_val:
            return str(str_val)

        return None    


    def _addNewAttribute(self, long_name, attr_type, attr_map, karg_map, internal_str_attr, is_array=False, **kargs):
        """
        Adds a new input or output attibute to the node using the given args.
        """

        if not self.hasAttr(long_name):

            if not attr_type in attr_map.keys():
                raise TypeError("attribute type " + str(attr_type) + " not supported by mPyNode")

            attr_mel_type = attr_map[attr_type]

            kargs.update(karg_map)
            orig_kargs = copy.deepcopy(kargs)

            if is_array:
                kargs["multi"] = True
                kargs["indexMatters"] = True

            self.addAttr(long_name, attr_mel_type, **kargs)

            if self._VECTOR_COMP_NAMES.has_key(attr_type):
                for axis in self._VECTOR_COMP_NAMES[attr_type]:
                    self.addAttr(long_name + axis, self._VECTOR_COMP_TYPES[attr_type], parent=long_name, **orig_kargs)

        self._appendInternalDictAttr(internal_str_attr, long_name, attr_type)


    def _getFormattedExpression(self):

        return None


    def _getAttrMap(self, internal_attr_name, is_input=False):
        """
        Handles building a dictionary of input or output attr data based on the give attribute query function
        """

        internal_attr_map = self._getInternalAttrMap(internal_attr_name)
        attr_map = OrderedDict()

        if internal_attr_map:

            for attr_name, attr_data in internal_attr_map.items():

                cur_attr_map = {}
                attr_type = attr_data[0]
                is_array = False

                cur_attr_map[self._ATTR_MAP_TYPE_KEY] = attr_data[0]

                if self.attributeQuery(attr_name, multi=True):
                    cur_attr_map[self.ATTR_MAP_ARRAY_KEY] = is_array = True

                if is_input:
                    if self.getAttr(attr_name, keyable=True):
                        cur_attr_map["keyable"] = True

                    elif self.getAttr(attr_name, channelBox=True):
                        cur_attr_map["channelBox"] = True

                if attr_type in self._ENUM_ATTR_TYPES:
                    enum_names = self.attributeQuery(attr_name, listEnum=True)

                    if enum_names is not None:
                        cur_attr_map["enumName"] = self.attributeQuery(attr_name, listEnum=True)[0]

                if attr_type in MPyNode._ATTR_DEFAULT_VAL_TYPES and (not is_array):
                    default_value = self.attributeQuery(attr_name, listDefault=True)

                    if default_value is not None:
                        cur_attr_map["defaultValue"] = MPyNode._ATTR_TO_PY_MAP[attr_type](default_value[0]) 

                if (attr_type in self._NODE_NUMERIC_TYPES) and (not is_array):
                    if self.attributeQuery(attr_name, minExists=True):
                        cur_attr_map["min"] = self.attributeQuery(attr_name, minimum=True)[0]

                    if self.attributeQuery(attr_name, maxExists=True):
                        cur_attr_map["max"] = self.attributeQuery(attr_name, maximum=True)[0]

                attr_map[attr_name] = cur_attr_map

            return attr_map

        return None


    def setExpression(self, exp_str):
        """
            setExpression(exp_str)

            Set the expression within the node to the given string of python code.

            Parameters
            ----------
            exp_str : *str*
                python code to set the expression to.

            Returns
            -------
            *None*

            See Also
            --------
            getExpression : Returns the current python expression within the node.

            Examples
            --------
            >>> py_node.setExpression('outAttr = inAttr * 2')

        """

        self.setAttr(self._EXPRESSION_ATTR_NAME, str(exp_str), type="string")


    def hasStoredVariable(self, var_name):
        """
        hasStoredVariable(var_name)

            Returns whether the node has an instance property with the given name that has been flagged for storage on disc.

            Parameters
            ----------
            var_name : *str*
                name of the variable

            Returns
            -------
            *bool*

            See Also
            --------
            addStoredVariable : Removes the given output attribute from the node.

            Examples
            --------
            >>> node.hasStoredVariable("myVar")

        """

        all_vars = self.listStoredVariables()

        if all_vars:
            return var_name in all_vars

        return False


    def setStoredVariable(self, var_name, var_val):
        """
        setStoredVariable(var_name, var_val)

            Used to set an instance property on the node for use in the expression and storage on disc when the file is saved. The name given
            should refer to a property on the node instance created/used by the expression (i.e. self.var_name)

            Parameters
            ----------
            var_name : *str*
                name of the variable to set

            var_val : *object*
                python value to assign to the variable

            Returns
            -------
            *None*

            See Also
            --------
            getStoredVariable : Returns the nodes "stored variables" as a dictionary.

            Examples
            --------
            >>> node.setStoredVariable("myVar", var_val)

        """

        if not self.hasStoredVariable(var_name):
            self.addStoredVariable(var_name)

        self.setVariable(var_name, var_val)


    def setVariable(self, var_name, var_val):
        """
        setVariable(var_name, var_val)

            Used to set an instance property on the node for use in the expression. The name given should refer to a
            property on the node instance created/used by the expression (i.e. self.var_name). This value variable is destroyed
            when the Maya scene is closed.

            Parameters
            ----------
            var_name : *str*
                name of the variable to set

            var_val : *object*
                python value to assign to the variable

            Returns
            -------
            *None*

            Examples
            --------
            >>> node.setVariable("myVar", 1.0)

        """

        ##---send data to the MPx version of the node----##
        callback_data = {self.getHashCode():{var_name:var_val}}
        om.MUserEventMessage.postUserEvent(self._SET_VAR_CALLBACK_NAME, callback_data)    


    def getStoredVariables(self):
        """
        getStoredVariables()
    
            Returns the nodes "stored variables" as a dictionary.
    
            Returns
            -------
            *dict* or *None* - Keys are string names of the variables and values are their current values
            
            See Also
            --------
            addStoredVariable : Removes the given output attribute from the node.
            setStoredVariable : Used to set an instance property on the node for use in the expression and storage on disc when the file is saved
    
            Examples
            --------
            >>> var_map = node.getStoredVariables()
    
        """

        ##---write current variables values to there stored attribute so we can get their current values---##
        om.MUserEventMessage.postUserEvent(self._WRITE_STORED_VARS_CALLBACK_NAME, (self.getHashCode(),))

        return self._getInternalPyAttr(self._STORED_VARS_DATA_ATTR_NAME)


    def getExpression(self):
        """
        getExpression()

            Returns the current python expression within the node.

            Returns
            -------
            *str* or *None*

            See Also
            --------
            setExpression : Set the expression within the node to the given string of python code.

            Examples
            --------
            >>> exp = node.getExpression()

        """

        exp_str = self.getAttr(self._EXPRESSION_ATTR_NAME)

        if not exp_str or exp_str == "None":
            return None

        return str(exp_str)


    def addInputAttr(self, long_name, attr_type, is_array=False, **kargs):
        """
        addInputAttr(long_name, attr_type, is_array=False, \*\*kargs)

            Adds an input attribute of the given long name and given type to the node.
            Use MPyNode.listSupportedAttrTypes() to list supported types

            Parameters
            ----------
            long_name : *str*
                long name of the attribute to add. This will be the name of its variable in the expression

            attr_type : *str*
                type of attribute to add. Use MPyNode.listSupportedAttrTypes() to list supported types

            is_array : *bool*, optional, default = False
                whether to make this an array attribute

            kargs : *keyword args*, optional
                keyword args supported by maya.cmds.addAttr

            Returns
            -------
            *None*

            See Also
            --------
            addOutputAttr : Adds an output attribute of the given long name and given type to the node.
            addStoredVariable : Used to flag an instance property on the node for storage on disc when the file is saved

            Examples
            --------
            >>> node.addInputAttr("floatAttr", "float")
            >>> node.addInputAttr("floatArrayAttr", "float", is_array=True)

        """

        kargs["storable"] = True

        self._addNewAttribute(long_name, attr_type, self._NEW_INPUT_TYPES, self._NEW_INPUT_ATTR_KARGS,
                              self._INPUTS_STR_ATTR_NAME, is_array=is_array, **kargs)


    def addOutputAttr(self, long_name, attr_type, is_array=False, **kargs):
        """
        addOutputAttr(long_name, attr_type, is_array=False, \*\*kargs)

            Adds an output attribute of the given long name and given type to the node.
            Use MPyNode.listSupportedAttrTypes() to list supported types

            Parameters
            ----------
            long_name : *str*
                long name of the attribute to add. This will be the name of its variable in the expression

            attr_type : *str*
                type of attribute to add. Use MPyNode.listSupportedAttrTypes() to list supported types

            is_array : *bool*, optional, default = False
                whether to make this an array attribute

            kargs : *keyword args*, optional
                keyword args supported by maya.cmds.addAttr

            Returns
            -------
            *None*

            See Also
            --------
            addInputAttr : Adds an output attribute of the given long name and given type to the node.
            addStoredVariable : Used to flag an instance property on the node for storage on disc when the file is saved

            Examples
            --------
            >>> node.addOutputAttr("floatAttr", "float")
            >>> node.addOutputAttr("floatArrayAttr", "float", is_array=True)

        """

        self._addNewAttribute(long_name, attr_type, self._NEW_OUTPUT_TYPES, self._NEW_OUTPUT_ATTR_KARGS,
                              self._OUTPUTS_STR_ATTR_NAME, is_array=is_array, **kargs)


    def addStoredVariable(self, var_name):
        """
        addStoredVariable(var_name)

            Used to flag an instance property on the node for storage on disc when the file is saved. The name given 
            should refer to a property on the node instance created/used by the expression (i.e. self.var_name)

            Parameters
            ----------
            var_name : *str*
                name of the variable to store

            Returns
            -------
            *None*

            See Also
            --------
            addInputAttr : Adds an input attribute of the given long name and given type to the node.
            addOutputAttr : Adds an output attribute of the given long name and given type to the node.

            Examples
            --------
            >>> node.addStoredVariable("myVar")

        """

        self._appendInternalListAttr(self._STORED_VARS_ATTR_NAME, var_name)


    def listInputAttrs(self):
        """
        listInputAttrs()

            Returns the names of the node's input attributes

            Returns
            -------
            *tuple* of *str* attribute names or *None*

            See Also
            --------
            addInputAttr : Adds an input attribute of the given long name and given type to the node.

            Examples
            --------
            >>> input_attrs = node.listInputAttrs()

        """

        return self._getAttrStringList(self._INPUTS_STR_ATTR_NAME)


    def listOutputAttrs(self):
        """
        listOutputAttrs()

            Returns the names of the node's output attributes

            Returns
            -------
            *tuple* of *str* attribute names or *None*

            See Also
            --------
            addOutputAttr : Adds an output attribute of the given long name and given type to the node.

            Examples
            --------
            >>> output_attrs = node.listOutputAttrs()

        """

        return self._getAttrStringList(self._OUTPUTS_STR_ATTR_NAME)


    def listStoredVariables(self):
        """
        listStoredVariables()

            Returns the names of the node's internally stored variables

            Returns
            -------
            *tuple* of *str* variable names or *None*

            See Also
            --------
            addStoredVariable : Used to flag an instance property on the node for storage on disc when the file is saved.

            Examples
            --------
            >>> stored_vars = node.listStoredVariables()

        """

        return self._getInternalPyAttr(self._STORED_VARS_ATTR_NAME)


    def getInputAttrMap(self):
        """
        getInputAttrMap()
        
            Returns a dictionary with all input attr names as keys and attribute data as values.
            The values of the dictionary are also dictiontaries with the proper addInputAttr() keyword args and values. Note
            that only non-default keyword args are returned. So if an attribute is not "keyable", for example, no "keyable"
            keyword will be returned in dictionary.
    
            Returns
            -------
            *dict* with all input attr names as keys and attribute data as values or *None*
            
            See Also
            --------
            addInputAttr : Adds an input attribute of the given long name and given type to the node.
    
            Examples
            --------
            >>> input_map = node.getInputAttrMap()
    
        """

        return self._getAttrMap(self._INPUTS_STR_ATTR_NAME, is_input=True)


    def getOutputAttrMap(self):
        """
        getOutputAttrMap()
    
            Returns a dictionary with all output attr names as keys and attribute data as values.
            The values of the dictionary are also dictiontaries with the proper addOutputAttr() keyword args and values. Note
            that only non-default keyword args are returned. So if an attribute is not "keyable", for example, no "keyable"
            keyword will be returned in dictionary.
    
            Returns
            -------
            *dict* with all output attr names as keys and attribute data as values or *None*
            
            See Also
            --------
            addOutputAttr : Adds an output attribute of the given long name and given type to the node.
    
            Examples
            --------
            >>> input_map = node.getOutputAttrMap()
    
        """

        return self._getAttrMap(self._OUTPUTS_STR_ATTR_NAME)


    def removeStoredVariable(self, var_name):
        """
        removeStoredVariable(var_name)

            Removes the given variable name from the list of variables that will stored to file

            Parameters
            ----------
            var_name : *str*
                name of the variable to remove

            Returns
            -------
            *None*

            See Also
            --------
            addStoredVariable : Used to flag an instance property on the node for storage on disc when the file is saved

            Examples
            --------
            >>> node.removeStoredVariable("floatAttr")

        """

        cur_vars = self.listStoredVariables()

        if cur_vars and var_name in cur_vars:

            updated_vars = filter(lambda a: a != var_name, cur_vars)

            self._setInternalPyAttr(self._STORED_VARS_ATTR_NAME, updated_vars)


    @classmethod
    def listValidInputTypes(cls):
        """
        listStoredVariables()

            Class method returns the types of supported input attributes

            Returns
            -------
            *tuple* of *str* attribute types or *None*

            See Also
            --------
            addInputAttr : Adds an input attribute of the given long name and given type to the node.

            Examples
            --------
            >>> attr_types = MPyNode.listValidInputTypes()

        """

        attr_types = cls._NEW_INPUT_TYPES.keys()
        attr_types.sort()

        return tuple(attr_types)


    @classmethod
    def listValidOutputTypes(cls):
        """
        listValidOutputTypes()

            Class method returns the types of supported output attributes

            Returns
            -------
            *tuple* of *str* attribute types or *None*

            See Also
            --------
            addOutputAttr : Adds an output attribute of the given long name and given type to the node.

            Examples
            --------
            >>> attr_types = MPyNode.listValidInputTypes()

        """

        attr_types = cls._NEW_OUTPUT_TYPES.keys()
        attr_types.sort()

        return tuple(attr_types) 


    def deleteInputAttr(self, attr_name):
        """
        deleteInputAttr(attr_name)

            Removes the given input attribute from the node.

            Parameters
            ----------
            attr_name : *str*
                string name of the input attribute to remove

            Returns
            -------
            *None*

            See Also
            --------
            deleteOutputAttr : Removes the given output attribute from the node.
            removeStoredVariable : Removes the given variable name from the list of variables that will stored to file

            Examples
            --------
            >>> node.deleteInputAttr("myVar")

        """

        in_attrs = self.listInputAttrs()

        if in_attrs and (attr_name in in_attrs):

            in_attr_dict = self._getInternalPyAttr(self._INPUTS_STR_ATTR_NAME)

            if in_attr_dict and in_attr_dict.has_key(attr_name):
                del(in_attr_dict[attr_name])

                self._setInternalPyAttr(self._INPUTS_STR_ATTR_NAME, in_attr_dict)

            self.deleteAttr(attr_name)

        else:
            raise RuntimeError(str(self) + " has no input attr called: " + str(attr_name))


    def deleteOutputAttr(self, attr_name):
        """
        deleteOutputAttr(attr_name)

            Removes the given output attribute from the node.

            Parameters
            ----------
            attr_name : *str*
                string name of the output attribute to remove

            Returns
            -------
            *None*

            See Also
            --------
            deleteInputAttr : Removes the given input attribute from the node.
            removeStoredVariable : Removes the given variable name from the list of variables that will stored to file

            Examples
            --------
            >>> node.deleteOutputAttr("myVar")

        """

        out_attrs = self.listOutputAttrs()

        if out_attrs and (attr_name in out_attrs):

            out_attr_dict = self._getInternalPyAttr(self._OUTPUTS_STR_ATTR_NAME)

            if out_attr_dict and out_attr_dict.has_key(attr_name):
                del(out_attr_dict[attr_name])

                self._setInternalPyAttr(self._OUTPUTS_STR_ATTR_NAME, out_attr_dict)

            self.deleteAttr(attr_name)

        else:
            raise RuntimeError(str(self) + " has no input attr called: " + str(attr_name))


    def exportToFile(self, file_path, use_binary=True):
        """
        exportToFile(file_path, use_binary=True)

            Export this node to an external file

            Parameters
            ----------
            file_path : *str*
                string file path to export to. Directory structure must exist

            use_binary : *bool*, optional, default=True
                By default, a binary file is exported. If a text format is desired, set this to False

            Returns
            -------
            *None*

            See Also
            --------
            importFromFile : Import a MPyNode from an external file. An nstance of the node will be constructed in the current Maya scene

            Examples
            --------
            >>> node.exportToFile("C:/temp/file_name.ext")
            >>> node.exportToFile("C:/temp/file_name.ext", use_binary=False)

        """

        path_exists = os.path.exists(file_path)

        if path_exists and not os.access(file_path, os.W_OK):
            raise IOError("Cannot write to path: " + str(file_path))

        if not os.path.exists(os.path.dirname(file_path)):
            raise IOError("Directory does not exist: " + str(os.path.dirname(file_path)))

        protocol = 2 if use_binary else 0

        fh = open(file_path, "wb") if use_binary else open(file_path, "w")

        try:
            cPickle.dump(self, fh, protocol=protocol)

        except:
            fh.close()
            raise

        else:
            fh.close()


    #def saveToFile(self, class_name, file_path):

        #if os.path.exists(file_path) and os.access(file_path, os.W_OK):
            #raise IOError("Cannot write to path: " + str(file_path))

        #if not os.path.exists(os.path.dirname(file_path)):
            #raise IOError("Directory does not exist: " + str(os.path.dirname(file_path)))

        #code_str = self.CODE_IMPORT_STR
        #code_str += "class " + str(class_name) + "(" + self.CODE_CLASS + "):\n\n"
        #code_str += self.CODE_COMPUTE_DEF

        #expr_str = self._getFormattedExpression()

        #if expr_str:
            #code_str += expr_str

        #fh = open(file_path, "w") 
        #fh.write(code_str)
        #fh.close()


    def __reduce__(self):

        node_name = self.getName()
        input_map = self.getInputAttrMap()
        output_map = self.getOutputAttrMap()
        stored_var_map = self.getStoredVariables()
        expr_str = self.getExpression()

        return (self.__class__, (None, node_name, expr_str, input_map, output_map, stored_var_map))


    def __reduce_ex__(self, protocol):
        """
        Built-in method. Handles pickling of the current Maya node. Same as __reduce__() but handles a protocol argument.
        """

        return self.__reduce__()    


    @classmethod
    def ls(cls, *args, **kargs):
        """
        ls(\*args, \*\*kargs)

            class method - returns the nodes of type 'mPyNode' in the current scene. Works just like maya.cmds.ls

            Parameters
            ----------
            args : *str*
                args supported by maya.cmds.ls

            kargs : *str*
                keyword args supported by maya.cmds.ls

            Returns
            -------
            *tuple* of *MPyNode* nodes or *None*

            Examples
            --------
            >>> ## get all mPyNode nodes in the scene
            >>> nodes = MPyNode.ls()
            >>>
            >>> ## get all mPyNode nodes whose names start with \"Foo\"
            >>> foo_nodes = MPyNode.ls("Foo*")

        """

        cls._pluginCheck()

        kargs["type"] = cls.NODE_TYPE

        nodes = MNode.ls(*args, **kargs)

        if nodes:
            if cls == MPyNode:
                return tuple([cls(m_node) for m_node in nodes])

            else:
                filtered_nodes = []
                for node in nodes:
                    if node.hasAttr(cls._TYPE_ATTR):
                        node_type = node.getAttr(cls._TYPE_ATTR)

                        if node_type == cls.__name__:
                            filtered_nodes.append(cls(node))

                if filtered_nodes:
                    return tuple(filtered_nodes)

        return None


    @staticmethod
    def importFromFile(file_path):
        """
        importFromFile(file_path)

            Import a MPyNode from an external file. An instance of the node will be constructed in the current Maya scene

            Parameters
            ----------
            file_path : *str*
                file path to import from

            Returns
            -------
            *MPyNode* of the newly created node

            See Also
            --------
            importFromFile : Export this node to an external file

            Examples
            --------
            >>> new_node = MPyNode.importFromFile("C:/temp/file_name.ext")

        """

        if os.path.exists(file_path):

            fh = open(file_path, "r")
            node = cPickle.load(fh)

            return node

        else:
            raise IOError("given path does not exist: " + str(file_path))

