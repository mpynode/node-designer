"""
Author: Gene Hansen

This module contains the MNode class and all standalone functions that support
the MNode class. MNode provides an object oriented interface for querying/editing DG nodes inside Maya.
An instance of the MNode class provides storage and access to a single Maya node. MNode uses
a MObject pointer at its core to iteract with the Maya node it represents.

>>> node = MNode("node_1")
>>> print (node.getName())
>>> 'node_1'

Methods within the class replace the most commonly used maya commands. Public methods operate on
the MObject stored within the MNode.

Note that most methods support the same keywords arguments as their maya.cmds equivalents. However,
some keyword args may not make sense relative to the object stored within the MNode.

>>> # without MNode
>>> cons = maya.cmds.listConnections("node_1", source=True, destination=True)
>>> # with MNode
>>> cons = node.listConnections(source=True, destination=True)

Because MNode is a MObject, there is no need to keep track of the current "name"
of an object. MNode handles this for you so you are free to parent, unparent, rename as you wish.

>>> # without MNode
>>> import maya.cmds as mc
>>> node = "node"
>>> node = mc.parent(node, "node_2")
>>> node = mc.parent(node, world=True)
>>> node = mc.rename(node, "node_1")
>>> print (node)
>>> ## 'node_1'
>>>
>>>
>>> # with MNode
>>> node = MNode("node")
>>> node.parent("node_2")
>>> node.parent(world=True)
>>> node.rename("node_1")
>>> print (node)
>>> ## 'node_1'

Because MNode has a __str__ method, passing an MNode object to a standard Maya command will function
properly. All Maya commands call __str__ when taking object input.

"""

import os
import inspect
import codecs
from collections import OrderedDict

import maya.cmds as mc
import maya.api.OpenMaya as om


try:
    import cPickle as pickle # python2
except:
    import pickle # python3
    unicode = str


class MNode(om.MObject):
    """
    :purpose: 	Provides object oriented interface for querying/editing DAG or DG nodes inside Maya.
    			An instance of the MNode class provides storage and access to a single
                Maya node. Methods within the class replace the most commonly use maya
                commands. Public methods operate on the object stored within the MNode.
                Note that most methods support the same keywords arguments as their
                maya.cmds equivalent.
    :extends:	*OpenMaya.MObject*
    """

    ATTR_AT_TYPES = ("bool", "long", "short", "byte", "char", "enum", "float", "double",
                     "doubleAngle", "doubleLinear", "compound", "message", "time", "matrix",
                     "fltMatrix", "reflectance", "spectrum", "float2", "float3", "double2", "double3",
                     "long2", "long3", "short2", "short3")

    ATTR_DT_TYPES = ("string", "stringArray", "reflectanceRGB", "spectrumRGB",
                     "float2", "float3", "double2", "double3", "long2", "long3", "short2",
                     "short3", "doubleArray", "Int32Array", "vectorArray", "nurbsCurve",
                     "nurbsSurface", "mesh", "lattice", "pointArray")

    NODE_TYPE = None
    NODE_LIST_CLASS = None #has to initalzied at bottom of module

    ##---for overriding with specific function sets in child classes---##
    DG_FN_CLASS = om.MFnDependencyNode
    DAG_FN_CLASS = om.MFnDagNode

    DG_FN_FUNCS = ("absoluteName", "addAttribute", "addExternalContentForFileAttr", "allocateFlag", "attribute",
                   "attributeClass", "attributeCount", "canBeWritten", "classification", "create",
                   "deallocateAllFlags", "deallocateFlag", "dgCallbackIds", "dgCallbacks", "dgTimer", "dgTimerOff",
                   "dgTimerOn", "dgTimerQueryState", "dgTimerReset", "findAlias", "findPlug", "getAffectedAttributes",
                   "getAffectingAttributes", "getAliasAttr", "getAliasList", "getConnections", "getExternalContent",
                   "hasAttribute", "hasObj", "isFlagSet", "isNewAttribute", "isTrackingEdits", "name", "object",
                   "plugsAlias", "removeAttribute", "reorderedAttribute", "setAlias", "setDoNotWrite",
                   "setExternalContent", "setExternalContentForFileAttr", "setFlag", "setName", "setObject",
                   "setUuid", "type", "userNode", "uuid")

    DAG_FN_FUNCS = DG_FN_FUNCS + ("addChild", "dagRoot", "partialPathName", "isParentOf", "childCount",
                                  "isInstancedAttribute", "instanceCount", "transformationMatrix", "child", "isChildOf",
                                  "removeChild", "getAllPaths", "getConnectedSetsAndMembers", "fullPathName",
                                  "parentCount", "hasParent", "removeChildAt", "parent", "dagPath", "hasChild", "isInstanced")

    DAG_NODE_TYPES = (om.MFn.kTransform, om.MFn.kPluginLocatorNode, om.MFn.kShape, om.MFn.kWorld)

    MENU_ATTR_PREFIX = "menuCmd_"
    MENU_STR_SEPERATOR = "@"
    MENU_OBJ_NAME_STR = "~obj~"

    PLUGIN_CHECK = False
    PLUGIN_DIR = None
    PLUGINS = None


    def __init__(self, node=None, node_type=None, name=None):
        """
        __init__(node=None, node_type=None, name=None)

            Initialize a new MNode object

            Parameters
            ----------
            node : *str* name, *MNode* or *MObject*
                an existing node to intialize from. A new node is created if this arg is not provided and
                a node type provided with the *node_type* or class property *NODE_TYPE*

            node_type : *str*, optional
                string node type to create. Ignored if initializing from an existing node

            name : *str*, optional
                optional name to give the node if creating a new one. Ignored if initializing from an existing node

            Returns
            -------
            *None*

            Examples
            --------
            >>> existing_node = MNode("existingNode")
            >>>
            >>> new_node = MNode(node_type="transform", name="newNode")
        """

        self._obj_hndl = None
        self._fn_set = None
        self._fn_set_funcs = None
        self._dag_path = None

        m_obj = None

        ##----build a new node in the scene to wrap----##
        if node is None:
            m_obj = self._buildNew(node_type if node_type else self.NODE_TYPE, name)

        ##----wrap an existing node---##
        else:

            if isinstance(node, om.MObject):
                m_obj = node

            elif isinstance(node, (str, unicode)):
                m_obj = self._getMObjectByName(node)

            elif isinstance(node, MNode):
                m_obj = node.getMObject()

            else:
                raise TypeError("Expected type string, MObject or MNode..got type " + str(type(node)))

        try:
            super().__init__(m_obj) # python3
        except:
            super(MNode, self).__init__(m_obj) # python2
            

        ##----use a dag function set if this is a dag node---##
        if list(filter(self.hasFn, self.DAG_NODE_TYPES)):

            self._dag_path = om.MDagPath()
            fn_set = om.MFnDagNode(self)
            self._dag_path = fn_set.getPath()

            self._fn_set = self.DAG_FN_CLASS(self._dag_path)
            self._fn_set_funcs = self.DAG_FN_FUNCS

        else:
            self._fn_set = self.DG_FN_CLASS(self)
            self._fn_set_funcs = self.DG_FN_FUNCS

        self._obj_hndl = om.MObjectHandle(self)
        self._linkFnMethods()


    def _linkFnMethods(self):
        """
        Called by __init__ to link the funcations of the underlying Maya function set with this instance
		"""

        if self._fn_set_funcs:
            for attr in self._fn_set_funcs:
                if hasattr(self._fn_set, attr) and not hasattr(self, attr):
                    setattr(self, attr, getattr(self._fn_set, attr))


    def _buildNew(self, node_type, name):

        kargs = {"name":name} if name else {}
        node_name = mc.createNode(*(node_type,), **kargs)

        return self._getMObjectByName(node_name)


    @classmethod
    def pluginCheck(cls):
        """
        @classmethod - Not used in the base MNode class. Can be used in child classes to check for and load plugin dependencies
        automatically.

        Check for any plugins uses by this class. If any plugin names are defined in class
        property PLUGINS, they will be loaded if they are not already. Class property PLUGIN_CHECK
        is set to False on completion of this method so it is only called once per class.

        To use in child class....implement class properties PLUGIN_CHECK and PLUGINS and call this method in __init__().
        Optionally this method can be called outside of __init__ to check for plugins at any time.

        PLUGIN_CHECK is a bool that should be set to True by default.

        PLUGIN_CHECK is a tuple of plugin string names to check for and load if not already loaded.

        ::

        	class MyAwesomeNode(MNode):

        		PLUGIN_CHECK = True
        		PLUGINS = ("superPlugin", "coolPlugin")

        		def __init__(self, node):

        			self.__class__._pluginCheck()

        		 	MNode.__init__(self, node)

        """

        if cls.PLUGIN_CHECK:

            if cls.PLUGIN_DIR:

                cur_dir = os.path.dirname(inspect.getfile(cls))
                plug_dir = os.path.normpath(os.path.join(cur_dir, cls.PLUGIN_DIR)).replace("\\", "/")

                #if os.environ.has_key("MAYA_PLUG_IN_PATH"):
                if "MAYA_PLUG_IN_PATH" in os.environ:
                    if not plug_dir in os.environ["MAYA_PLUG_IN_PATH"]:
                        os.environ["MAYA_PLUG_IN_PATH"] += ";" + plug_dir

                else:
                    os.environ["MAYA_PLUG_IN_PATH"] = plug_dir

            if cls.PLUGINS:

                for plugin_name in cls.PLUGINS:

                    if not mc.pluginInfo(plugin_name, q=True, loaded=True):

                        mc.loadPlugin(plugin_name)

            cls.PLUGIN_CHECK = False


    @classmethod
    def createNode(cls, node_type=None, **kargs):
        """
        createNode(node_type=None, \*\*kargs)

            Wrapper class method for maya.cmds.createNode thats returns a MNode object
            instead of a string name

            Parameters
            ----------
            node_type : *str* node type to create

            kargs : *dict*
                keyword args supported by *maya.cmds.createNode*

            Returns
            -------
            *MNode* of newly created node

            Examples
            --------
        	>>> new_node = MNode.createNode("transform", name="new_node")
        	>>> new_node = MNode.createNode("time")
        """

        if node_type is None:
            if cls.NODE_TYPE:
                node_type = cls.NODE_TYPE

            else:
                raise RuntimeError("No node type given")

        node = mc.createNode(*(node_type,), **kargs)

        if node is None:
            return None

        return cls(node)


    @classmethod
    def ls(cls, *args, **kargs):
        """
        Wrapper class method for *maya.cmds.ls* thats returns a *MNodeList* result
        instead of a list of string names

        **args**		args supported by *maya.cmds.ls*

        **kargs**		keyword args supported by *maya.cmds.ls*

        **RETURNS** 	*MNodeList* of nodes or *None*

        >>> foo_nodes = MNode.ls("foo*")
        >>> time_nodes = MNode.ls(type="time")

        """

        if cls.NODE_TYPE:
            kargs["type"] = cls.NODE_TYPE

        nodes = mc.ls(*args, **kargs)

        if nodes:
            return cls.NODE_LIST_CLASS(nodes)

        return None


    def addAttr(self, long_name=None, attr_type=None, **kargs):
        """
        Adds an attribute of the given long name and given type to the node.
        Supports all keyword args of maya.cmds.addAttr except "dt" and "at"
        which are replaced by the attr_type arg.

        **long_name** 	*string* long name of the attribute to add. This is optional if you prefer to use the
        				standard Maya *longName* and/or *shortName* keywaords instead.

        **attr_type** 	*string* type of attribute to add. Supports all string types supported by
        				the "dt" and "at" args of maya.cmds.addAttr

        **kargs**		keyword args supported by maya.cmds.addAttr and keyword 'channelBox'

        **RETURNS** 	*None*

        >>> node_1.addAttr("test", "float")

        """

        if long_name:
            kargs["longName"] = long_name

        if attr_type:
            if attr_type in self.ATTR_AT_TYPES:
                kargs["at"] = attr_type

            elif attr_type in self.ATTR_DT_TYPES:
                kargs["dt"] = attr_type

            else:
                raise TypeError("Cannot add attribute of unknown type " + str(attr_type) + " to node: " + str(self))

        cb = None

        #if kargs.has_key("channelBox"):
        if "channelBox" in kargs:
            cb = kargs["channelBox"]
            del kargs["channelBox"]

        mc.addAttr(*(self,), **kargs)

        if cb is not None:
            self.setAttr(kargs["longName"], channelBox=cb)


    def addMenuCmd(self, ui_name, cmd_str):
        """
        Add a context sensitive making menu to this node.

        **ui_name**		*string* menu item name to give this command in the marking menu

        **cmd**			*string* of python code to run when the menu item is selected

        **RETURNS**		None

        """

        attr_name = self.getNextAttr(self.MENU_ATTR_PREFIX)
        attr_str = str(ui_name) + self.MENU_STR_SEPERATOR + str(cmd_str)

        self.setStringAttr(attr_name, attr_str)


    def getMenuCmds(self):
        """
        Return all custom marking menu items on this node.

        **RETURNS**		OrderedDict with *string* menu item names as keys and *string* python commands as values

        """

        attr_names = self.listAttr(self.MENU_ATTR_PREFIX + "*", userDefined=True)

        if attr_names:

            menu_map = OrderedDict()

            for attr_name in attr_names:

                attr_val = self.getAttr(attr_name)

                if attr_val:
                    attr_tokens = attr_val.split(self.MENU_STR_SEPERATOR)

                    if len(attr_tokens) == 2:
                        menu_map[attr_tokens[0]] = attr_tokens[1]

                    else:
                        om.MGlobal.displayWarning("Could not precess making menu: " + str(attr_val))

            if menu_map:
                return menu_map

        return None


    def attachMenuItems(self, parent_menu):
        """
        This method attaches any defined menu cmds on this node to the given Maya menu item. Defined menu commands should
        be created using the *addMenuCmd* method.

        This is designed to be used in Maya's dagMenuProc.mel but can be used with any Maya menu item.

        To get this to work with default dag marking menu, Maya's dagMenuProc.mel must be modified with the following mel
        code at the top of global proc dagMenuProc() ---

        ::

        	python("import mpylib; mpylib.MNode('" + $object + "').attachMenuItems('" + $parent + "')");

        **parent_menu**			*string* parent menu item to attach to

        **RETURNS**				None

        """

        menu_cmds = self.getMenuCmds()

        if menu_cmds:

            mc.setParent(parent_menu, menu=True)

            for cmd_name, cmd_str in menu_cmds.items():

                if self.MENU_OBJ_NAME_STR in cmd_str:
                    cmd_str = cmd_str.replace(self.MENU_OBJ_NAME_STR, "'" + str(self) + "'")

                mc.menuItem(label=cmd_name, command=cmd_str)

            mc.menuItem(divider=True)



    def attributeQuery(self, attr_name, **kargs):
        """
        Query information about the given attribute.

        **attr_name**	string name of the attribute to query

        **kargs**		keyword args supported by maya.cmds.attributeQuery

        **RETURNS** 	results of the attribute query

        >>> ## query the string values of an enum attr
        >>> node.attributeQuery("myEnumAttr", listEnum=True)
        >>>
        >>> ## tset if the attr is an enum
        >>> node.attributeQuery("myEnumAttr", enum=True)

        """

        kargs["node"] = self

        return mc.attributeQuery(attr_name, **kargs)


    def bakeResults(self, *args, **kargs):
        """
        Run bakeResults on this node with the given options

        **args**		optional string args of attributes to bake. If args are given,
        				any value given to the *attribute* flag will be overridden
        **kargs** 		keyword args supported by maya.cmds.bakeResults

        **RETURNS** 	*None*

        >>> node_1.bakeResults("translateX", "scaleY", simulate=True)

        """

        if args:
            kargs["attribute"] = args

        mc.bakeResults(self, **kargs)


    def connectAttr(self, src_attr, dst_node, dst_attr, **kargs):
        """
        Connects the given attribute of this node to the given node and attribute.

        **src_attr**	string name of the source attr on this node

        **dst_node** 	string name or MNode of the destination node

        **dst_attr**	string name of the destination node

        **kargs**		keywords arg supported by maya.cmds.connectAttr

        **RETURNS**		*None*

        >>> ## connect node_a translateX to node_b translateZ
        >>> node_a.connectAttr("tx", node_b, "tz")

        """

        dst = dst_node + "." + dst_attr

        mc.connectAttr(*(self + "." + src_attr, dst), **kargs)


    def delete(self):
        """
        Delete the node from the scene. Trying to access the node after running this method will
        raise a RuntimeError.

        **RETURNS**		*None*

        >>> node.delete()

        """

        if self.isValid():
            mc.delete(self)
        else:
            self._raiseInvalidError()


    def deleteAttr(self, attr_name):
        """
        Delete the attr with the given name from this node.

        **src_attr** 	string name of the attr to delete

        **RETURNS**		*None*

        >>> node.addAttr("foo", "float")
        >>> node.deleteAttr("foo")

        """

        mc.deleteAttr(self + "." + attr_name)


    def duplicate(self, **kargs):
        """
        Duplicate the node with the given options

        **kargs**	keywords arg supported by maya.cmds.duplicate

        **RETURNS** MNode of the new node

        >>> new_node = node.duplicate()

        """

        results = mc.duplicate(self, **kargs)[0]

        if results:
            return self.__class__(results)

        return None


    def getAttr(self, attr_name, **kargs):
        """
        Returns the value of the given attr on this node.

        **attr_name**	string name of attr
        **kargs** 		keywords arg supported by maya.cmds.getAttr

        **RETURNS**		value of the attribute

        >>> tx_val = node.getAttr("translateX")

        """

        return mc.getAttr(*(self + "." + attr_name,), **kargs)


    def setAttrsFromMap(self, attr_map, skip_missing=True):
        """
        Set attribute values from a dictionary object that has attribute names as keys and attribute
        values as values

        **attr_map**		dict or OrderedDict that has has attribute names as keys and attribute
        values as values
        **skip_missing**	bool - whether to skip over attributes that exist in the incomming data
        					but not on the node. default=True

        **RETURNS**			None

        >>> data = {"tx":1.0, "ty":2.0, "tz":3.0}
        >>> node.setAttrsFromMap(data)

        """

        for attr_name, val in attr_map.items():

            if (not skip_missing) or self.hasAttr(attr_name):

                self.setAttr(attr_name, val)


    def getAttrMap(self, *args, **kargs):
        """
        Returns an OrderedDict of attributes as keys and their values as values.
        This method supports all arguments and keyword arguments used by maya.cmds.listAttr.

        **args**		optional specific string pattern of an attribute to query on the node. This supports multiple string args

        **kargs** 		keywords args supported by maya.cmds.listAttr

        **RETURNS**		*OrderedDict* or *None*

        >>> ## get the names and values of all keyable attributes on this node
        >>> keyable_map = node.getAttrMap(keyable=True)
        >>>
        >>> ## get names and values of all attributes that start with "trans"
        >>> trans_attrs = node.getAttrMap("trans*")

        """

        skip_multi = "skip_multi" in kargs

        if skip_multi:
            del kargs["skip_multi"]

        attr_names = self.listAttr(*args, **kargs)

        if attr_names:
            attr_map = OrderedDict()

            for attr_name in attr_names:

                if (not skip_multi) or (not "." in attr_name):

                    try:
                        attr_map[attr_name] = self.getAttr(attr_name)

                    except Exception as err:
                        raise RuntimeError("Error trying to query attr: '" + str(attr_name) + ".'\n" + err.message)

            return attr_map

        return None


    def applyAttrMap(self, attr_map, skip_missing=False, skip_errors=False):
        """
        Apply the attribute values in the given dictionary object to this node.

        **attr_map**		dictionary object with str attribute names as keys and attribute values as values

        **skip_missing**	*bool* - whether to skip over attributes that are missing from the scene. If False,
        					a missing attribute will raise a RuntimeError

        **skip_errors**		*bool* - whether to skip over setAttr errors. The default, False, will raise an exception
        					if a setAttr error occurs.

        **RETURNS**			None

        >>> attr_map = {"translateX":100.0, "visibility":True}
        >>> node.applyAttrMap(attr_map)

        """

        for attr_name, attr_val in attr_map.items():

            if (not skip_missing) or (self.hasAttr(attr_name)):

                try:
                    self.setAttr(attr_name, attr_val)

                except Exception as err:
                    if not skip_errors:
                        raise err


    def getMessageAttr(self, attr_name):
        """
        Returns the node that is connected to the given message attribute.

        **attr_name**		string name of the message attr

        **RETURNS**			*MNode* or *None*

        >>> connected_node = node.getMessageAttr("msgAttr")

        """

        if mc.attributeQuery(attr_name, node=self, exists=True):

            if mc.attributeQuery(attr_name, node=self, message=True):
                nodes, attrs = self.listConnections(attr_name, source=True,
                                                    destination=False, shapes=True)

                if nodes:
                    return nodes[0]

                return None

            else:
                raise RuntimeError("Given attribute is not type 'message': " + str(attr_name))

        return None


    def getMObject(self):
        """
        Returns the MObject of this node

        **RETURNS**		*OpenMaya.MObject*

        >>> m_obj = node.getMObject()

        """

        return om.MObject(self)


    def getMObjectHandle(self):
        """
        Returns the MObjectHandle of this node

        **RETURNS**		*OpenMaya.MObjectHandle*

        >>> m_obj_hndl = node.getMObjectHandle()

        """

        return self._obj_hndl


    def getHashCode(self):
        """
        Returns a hash code for the internal Maya object referenced by the MObject within this MNode

        **RETURNS**		*int* hash code

        >>> hash_code = node.getHashCode()

        """

        return self._obj_hndl.hashCode()


    def getNextAttr(self, attr_prefix, start_num=0, max_search=500):
        """
        Finds the next available attribute that is available with the given prefix. An int is added to
        the end of the given attr prefix. The attribute is not added.

        **attr_prefix**		*string* prefix to use for the attr

        **start_num** 		*int* number to start from. default = 0

        **max_search**		*int* protection against infinite loop. An error RuntimeError is raised if an
        					attribute slot is not found after this many tries. default = 500

        **RETURNS**			string attribute name

        >>> new_attr = node.getNextAttr("foo")
        >>> ## RESULT: "foo0"
        >>>
        >>> node.addAttr(new_attr, "float")
        >>> next_atr = node.getNextAttr("foo")
        >>> ## RESULT: "foo1"

        """

        next_attr = None
        i = start_num
        loop_check = 0

        while next_attr is None:
            if not self.hasAttr(attr_prefix + str(i)):
                next_attr = attr_prefix + str(i)

            if loop_check >= max_search:
                raise RuntimeError("Search count reached: " + str(max_search))
            i += 1
            loop_check += 1

        return next_attr


    def getName(self):
        """
        Returns the string name of this node. Note that is is the short name of the object.
        This method does not return DAG node full paths. Returned name will include all parent namespaces.

        **RETURNS**		*string* name

        >>> node_a = MNode.createNode("transform", name="testNode")
        >>> node.getName()
        >>> ## RESULT: "testNode"

        """

        if self.isValid():
            return str(self._fn_set.name())

        else:
            self._raiseInvalidError()


    def getBasename(self):
        """
        Returns the string name of this node any namespaces.

        **RETURNS**		*string* base name

        >>> node.getName()
        >>> ## RESULT: "char:weapon:model:foo:testNode"
        >>>
        >>> node.getBasename()
        >>> ## RESULT: "testNode"

        """

        name = self.getName()

        return name.split(":")[-1]


    def getNamespace(self):
        """
        Return the namespace this node belongs to, if any. Any returned namespace
        will always start with ":".

        **RETURN**		*string* namespace or None if node is in the default namespace

        >>> node = MNode.createNode("transform", name="test_node")
        >>> mc.namespace(add="test")
        >>> node.rename("test:test_node")
        >>>
        >>> namespace = node.getNamespace()
        >>> ##RESULT - ':test'

        """

        name = self.getName()

        name_tokens = name.split(":")

        if len(name_tokens) > 1:
            namespace = ":".join(name_tokens[0:-1])

            return ":" + namespace

        return None


    def getPluginName(self):
        """
        Return the name of the plugin that defines this node, if any

        **RETURNS**		string name of the plugin where this node is defined or None if the node is native
        """

        if self._fn_set.pluginName:
            return str(self._fn_set.pluginName)

        return None


    def getSetAttrCmds(self, attr_name, long_names=False, non_defaults_only=True):
        """
        Returns an tuple of strings containing mel setAttr commands for given attribute and
        all of its descendent attrs. This string could be used in a mayaAscii like format. This
        can be used to, if *non_defaults_only* is *True, test if the attribute has changed since the
        node was created.

        **attr_name**		*string* name of the attribute to query

        **long_names**		*bool* - whether to return cmds with long attribute names. default=False

        **non_defaults_only**	*bool* - If True, return a value only if the attribute has been change
        						from its default value or if its referenced and has been changed from
                                its referenced value. default=True

        **RETURNS**				tuple of string mel setAttr commands like you would see in a mayaAscii file or
        						None

        >>> node = MNode.createNode("transform")
        >>> node.setAttr("tx", 100.0)
        >>> node.getSetAttrCmds("tx")
        >>> #RESULT - [u'\tsetAttr ".tx" 100.0;']
        >>>
        >>> #translateY has not changed so it will return None with non_defaults_only set to True
        >>> node.getSetAttrCmds("ty")
        >>> #RESULT - None

        """

        if self.hasAttr(attr_name):

            mode = om.MPlug.kChanged if non_defaults_only else om.MPlug.kAll

            plug = self._fn_set.findPlug(attr_name, False)
            cmd_str = plug.getSetAttrCmds(mode, long_names)

            if cmd_str:
                return tuple(cmd_str)

            return None

        else:
            raise RuntimeError("Attribute " + str(attr_name) + " does not exist on node: " + str(self))


    def getAddAttrCmd(self, attr_name, use_long_names=False):
        """
        Returns a string containing mel addAttr command for re-creating given dynamic attribute.
        This string could be used in a mayaAscii like format.

        **attr_name**		*string* name of the dynamic attribute to query

        **long_names**		*bool* - whether to return cmds with long attribute names. default=False

        **RETURNS**			*string* mel addAttr commands like you would see in a mayaAscii file or *None*

        >>> node = MNode.createNode("transform")
        >>> node.addAttr("test", "float")
        >>> node.getAddAttrCmd("test")
        >>> #RESULT - '\taddAttr -ci true -sn "test" -ln "test" -at "float";'
        """

        attr_fn = om.MFnAttribute(self._fn_set.attribute(attr_name))

        return str(attr_fn.getAddAttrCmd(use_long_names))


    def getAddAttrMaps(self):
        """
        Returns a dictionary that contains addAttr details for all user defined dynamic
        attributes on the current node.

        *RETURNS*	*dict* containing keywords: "long_name", "short_name", "attr_type"
        """

        attr_list = []
        user_attrs = self.listAttr(userDefined=True)

        if user_attrs:
            for attr_name in user_attrs:
                attr_map = {}
                attr_map["long_name"] = self.attributeQuery(attr_name, longName=True)
                attr_map["short_name"] = self.attributeQuery(attr_name, shortName=True)
                attr_map["attr_type"] = self.getAttr(attr_name, type=True)

                attr_list.append(attr_map)

        return tuple(attr_list) if attr_list else None


    def hasUniqueName(self):
        """
        Indicates whether or not this node's name is unique within the scene.

        *RETURNS*	*bool*

        >>> node.hasUniqueName()

        """

        return bool(self._fn_set.hasUniqueName())


    def isLocked(self):
        """
        Indicates whether or not this node is locked.

        *RETURNS*	*bool*

        >>> node.isLocked()

        """

        return self._fn_set.isLocked


    def isFromReferencedFile(self):
        """
        Indicates whether or not this node came from a referenced file.

        **RETURNS**		*bool*
        """

        return self._fn_set.isFromReferencedFile


    def getObjectType(self):
        """
        Returns the string node type of this node.

        *RETURNS*	*string* node type

        >>> node = MNode.createNode("transform", name="testNode")
        >>>
        >>> node.getObjectType()
        >>> ## RESULT: "transform"

        """

        return mc.objectType(self)


    def getInheritedNodeTypes(self):
        """
        Returns the node classes that this node type is inherited from.

        **RETURNS**		*tuple* of *string* node types or *None*

        >>> node = MNode.createNode("transform", name="testNode")
        >>>
        >>> node.getInheritedNodeTypes()
        >>> ## RESULT: ("containerBase", "entity", "dagNode", "transform")

        """

        parent_types = mc.nodeType(self, inherited=True)

        if parent_types:
            return tuple([str(node_type) for node_type in parent_types])

        return None


    def getPath(self):
        """
        Returns the full path name of this node. This is equivalent to casting the node as a string.
        If this node is not DAG, the name of the node will be returned.

        **RETURNS** 	*string*

        >>> node_a = MNode.createNode("transform", name="testNode")
        >>> node.getName()
        >>> ## RESULT: "testNode"
        >>>
        >>> node.getPath()
        >>> ## RESULT: "|testNode"
        >>>
        >>> str(node)
        >>> ## RESULT: "|testNode"

        """

        if self._obj_hndl.isValid():

            if hasattr(self._fn_set, "fullPathName"):
                return str(self._fn_set.fullPathName())

            return self.getName()

        else:
            raise RuntimeError("Attempted to acces an invalid MObject handle")


    def getPlugs(self):
        """
        Returns the string names of all attributes that have incoming connections.

        **RETURNS**		*tuple* of attribute *string* names or *None*

        >>>	plugs = node.getPlugs()
        >>> ## RESULT: None
        >>>
        >>> node_b.connectAttr("tx", node, "tz")
        >>>
        >>>	plugs = node.getPlugs()
        >>> ## RESULT: ("translateZ",)

        """

        all_plugs = mc.listConnections(self, destination=False, source=True, connections=True)

        if all_plugs:
            return tuple([".".join(all_plugs[i].split(".")[1:]) for i in range(0, len(all_plugs), 2)])

        return None


    def hasAttr(self, attr_name, parent_attr=None):
        """
        Returns whether this node has an attribute with the given name.

        **attr_name**		string attr name

        **RETURNS**			*bool*

        >>> node.hasAttr("foo")
        >>> ## RESULT: False
        >>>
        >>> node.addAttr("foo", "float")
        >>> node.hasAttr("foo")
        >>> ## RESULT: True

        """

        if not parent_attr:
            return mc.attributeQuery(attr_name, node=self, exists=True)

        else:

            if mc.attributeQuery(parent_attr, node=self, exists=True):

                child_attrs = mc.attributeQuery(parent_attr, node=self, listChildren=True)

                if child_attrs and (attr_name in child_attrs):
                    return True

        return False


    def isValid(self):
        """
        Tests whether this node is still valid. Nodes become invalid if deleted from the scene or a
        new scene is opened.

        **RETURNS**			*bool*

        >>> node.isValid()
        >>> ## RESULT: True
        >>>
        >>> node.delete()
        >>> node.isValid()
        >>> ## RESULT: False

        """

        return self._obj_hndl.isValid()


    def listAttr(self, *args, **kargs):
        """
        List the atributes on this node

        **args**		specific string pattern of an attribute to query on the node. This supports
                    	multiple string args
        **kargs** 		keywords args supported by maya.cmds.listAttr
        **RETURNS**		List of string atribute names or None

        >>> ## list all attributes ##
        >>> attrs = node.listAttr()
        >>>
        >>> ## list all translate attrs
        >>> attrs = node.listAttr("translate*")
        >>>
        >>> ## list translate and rotate attrs
        >>> attrs = node.listAttr("translate*", "rotate*")

        """

        if args:
            kargs["string"] = args

        return mc.listAttr(self, **kargs)


    def listConnections(self, attr_name=None, **kargs):
        """
        List connections to this node

        **attr_name**	optional *string* name of an connected atribute.
        **kargs** 		keywords args supported by maya.cmds.listConnections
        **RETURNS**		(*MNodeList*, *None*) if the "plugs" karg is not used.
        				(*MNodeList*, *tuple*(*string* attr_names)) if "plugs" is used.
                    	(*None*, *None*) if there are no results.

        >>>	nodes, plugs = node.listConnections(source=True)

        """

        #return_plugs = kargs.has_key("plugs") or kargs.has_key("p")
        return_plugs = "plugs" in kargs or "p" in kargs
        node = self + "." + attr_name if attr_name else self

        results = mc.listConnections(node, **kargs)

        if results:

            if return_plugs:
                node_list = []
                attr_list = []

                for item in results:
                    tokens = item.split(".")
                    node_list.append(tokens[0])
                    attr_list.append(".".join(tokens[1:]))

                return MNodeList(node_list), tuple(attr_list)

            return MNodeList(results), None

        return None, None


    def rename(self, new_name, **kargs):
        """
        Rename this node

        **new_name**	*string* new name
        **kargs** 		keywords args supported by maya.cmds.rename

        **RETURNS**		*None*
        """

        mc.rename(*(self, new_name), **kargs)


    def renameAttr(self, attr_name, new_name):
        """
        Rename the given user created attribute

        **attr_name**	*string* new name

        **new_name**	*string* new name

        **RETURNS**		*string* new name
        """

        obj_attr = self + "." + attr_name

        return mc.renameAttr(*(obj_attr, new_name))


    def select(self, **kargs):
        """
        Selects this node with the given options.

        **kargs**		keywords args supported by maya.cmds.select
        **RETURNS**		*None*

        >>> node.select(repalce=True)
        >>> node.select(deselect=True)

        """

        return mc.select(*(self,), **kargs)


    def removeInputConnections(self, attr_name):
        """
        Remove any incoming connections to the attribute with the given name.

        **attr_name**		*string* name of the attribute

        **RETURNS**			None

        """

        dst_attrs = [attr_name]

        if (not "[" in attr_name) and self.attributeQuery(attr_name, multi=True):
            array_size = self.getAttr(attr_name, size=True)

            if array_size:
                dst_attrs = [attr_name + "[" + str(i) + "]" for i in range(array_size)] + [attr_name]

        for dst_attr in dst_attrs:

            nodes, plugs = self.listConnections(dst_attr, destination=False, source=True, plugs=True)

            if nodes:

                #for node, plug in map(None, nodes, plugs):
                for node, plug in zip(nodes, plugs):

                    mc.disconnectAttr(str(node) + "." + plug, str(self) + "." + dst_attr)


    def removeOutputConnections(self, attr_name):
        """
        Remove any output connections from the attribute with the given name.

        **attr_name**		*string* name of the attribute

        **RETURNS**			None

        """

        dst_attrs = [attr_name]
        indices = self.getAttr(attr_name, multiIndices=True)

        if indices:
            dst_attrs = [attr_name + "[" + str(i) + "]" for i in range(len(indices))] + [attr_name]

        for dst_attr in dst_attrs:
            nodes, plugs = self.listConnections(dst_attr, destination=True, source=False, plugs=True)

            if nodes:
                #for node, plug in map(None, nodes, plugs):
                for node, plug in zip(nodes, plugs):
                    mc.disconnectAttr(str(self) + "." + dst_attr, str(node) + "." + plug)




    def setAttr(self, attr_name, *args, **kargs):
        """
        Sets the given attr to the given value

        **attr_name**	string name of attr to set
        **args**		args supported by maya.cmds.setAttr

        **kargs**		keywords arg supported by maya.cmds.setAttr

        **RETURNS**		*None*

        >>> node.setAttr("translateX", 40.0)

        """

        if args:
            mc.setAttr(*(str(self) + "." + attr_name,) + args, **kargs)

        else:
            mc.setAttr(*(str(self) + "." + attr_name,), **kargs)


    def setDrivenKeyframe(self, attr, driver, driver_attr, **kargs):
        """
        Sets a set driven key on the current node using the given options

        **attr**			*string* name of the attr to be driven. Use this instead of the standard 'attribute' option
        **driver** 			*MNode* of the node to use as the driver. Use this with the driver_attr
        					arg instead of using the standard 'currentDriver' option
        **driver_attr**		*string* name of the attribute on the dirver node to use
        **kargs**			keywords arg supported by maya.cmds.setDrivenKeyframe
        **RETURNS**			*None*
        """

        current_driver = str(driver) + "." + driver_attr
        kargs["attribute"] = attr
        kargs["currentDriver"] = current_driver

        return mc.setDrivenKeyframe(*(self,), **kargs)


    def setStringAttr(self, attr_name, val, **kargs):
        """
        Sets the given value on the given string attr. If the attr does not exist, it is created.
        **attr_name**		string name of the string attr
        **val** 			value to set the attr to. Non-string values will be cast to string.

        **RETURNS**			*None*

        >>> node.setStringAttr("fooAttr", "fooVal")

        """

        if not self.hasAttr(attr_name):
            self.addAttr(attr_name, attr_type="string", **kargs)

        ##---unlock, set value and then relock-----##
        self.setAttr(attr_name, lock=False)
        self.setAttr(attr_name, str(val), type="string", lock=True)


    def setMessageAttr(self, attr_name, node, lock=True):
        """
        Connects the given node to the given message attribute on this node. If the attr does not exist, it is created.

        **attr_name**		*string* name of the message attr

        **node**			*MNode* of the node to connect

        **RETURNS**			*MNode* or None

        >>> node_a = MNode.createNode("transform")
        >>> node_b = MNode.createNode("transform")
        >>>
        >>> node_a.setMessageAttr("nodeB", node_b)

        """

        if not self.hasAttr(attr_name):
            self.addAttr(attr_name, "message")

        lock_on = self.getAttr(attr_name, lock=True)

        if lock_on:
            self.setAttr(attr_name, lock=False)

        node.connectAttr("message", self, attr_name, force=True)

        if lock_on or lock:
            self.setAttr(attr_name, lock=True)


    def __reduce__(self):
        """
		Built-in method. Handles pickling of the current Maya node.
		"""

        kargs = {"name":self.getBasename()}

        add_attr_map = self.getAddAttrArgs()

        return (_unpickleNode, (self.__class__, self.getObjectType(), add_attr_map, None, kargs))


    def __reduce_ex__(self, protocol):
        """
        Built-in method. Handles pickling of the current Maya node. Same as __reduce__() but handles a protocol argument.
		"""

        return self.__reduce__()


    def __add__(self, other):
        """
        Built-in method. Handles use of the '+' symbol. Returns a string of the string equivalent
        of this object plus the string equivalent of the second item


        >>> node = MNode("fooNode")
        >>> node + ".translateX"
        >>> #Result: "fooNode.translateX"
        """

        return self.getName() + other.getName() if isinstance(other, MNode) else self.getName() + str(other)


    def __radd__(self, other):
        """
        Built-in method. Handles use of the '+' symbol (reverse add). Returns a string of the second item
        plus the string equivalent of this node


        >>> node = MNode("fooNode")
        >>> "char:" + node
        >>> #Result:  "char:fooNode"
        """

        return other.getName() + self.getName() if isinstance(other, MNode) else str(other) + self.getName()


    def __repr__(self):
        """
        Built-in method. Returns the string representation of this object
        """

        return type(self).__name__ + "(" + self.getName() + ")"


    def __str__(self):
        """
        Built-in method. Returns the string full path representation the Maya node represented by this
        object.
        """

        return self.getPath()


    def capitalize(self, include_namespaces=False):
        """
        String operartion just like str.capitalize().
        Return a copy of the objects shortname with only its first character
        capitalized

        **include_namespaces**		*bool* - If False, returned string will not include namespaces. default=False

        **RETURNS**		*string*

        """

        if not include_namespaces:
            return self.getBasename().capitalize()

        return self.getName().capitalize()


    def count(self, sub, start=None, end=None, include_namespaces=False):
        """
        String operartion just like str.count().
        Return the number of (non-overlapping) occurrences of substring sub in string s[start:end].

        **sub**						*string* substring to find with the object's shortname

        **start**					optional *int* start index

        **end**						optional *int* end index

        **include_namespaces**		*bool* - If False, namespaces in the object's name will be ignored. default=False

        **RETURNS**					*int* index or *int* -1 is sub-string not found

        """

        name = self.getBasename() if not include_namespaces else self.getName()

        return name.count(sub, start, end)


    def find(self, sub, start=None, end=None, include_namespaces=False):
        """
        String operartion just like str.find().

        Return the lowest index in objects shortname where the substring *sub* is found such that sub is wholly
        contained in s[start:end]. Return -1 on failure

        **sub**						*string* substring to find with the object's shortname

        **start**					optional *int* start index

        **end**						optional *int* end index

        **include_namespaces**		*bool* - If False, namespaces in the object's name will be ignored. default=False

        **RETURNS**					*int* index or *int* -1 is sub-string not found

        """

        name = self.getBasename() if not include_namespaces else self.getName()

        return name.find(sub, start, end)


    def rfind(self, sub, start=None, end=None, include_namespaces=False):
        """
        String operartion just like str.rfind().
        Return the highest index in objects shortname where the substring *sub* is found such that sub is wholly
        contained in s[start:end]. Return -1 on failure

        **sub**						*string* substring to find with the object's shortname

        **start**					optional *int* start index

        **end**						optional *int* end index

        **include_namespaces**		*bool* - If False, namespaces in the object's name will be ignored. default=False

        **RETURNS**					*int* index or *int* -1 is sub-string not found

        """

        name = self.getBasename() if not include_namespaces else self.getName()

        return name.rfind(sub, start, end)


    def index(self, sub, start=None, end=None, include_namespaces=False):
        """
        String operartion just like str.index().
        Return the lowest index in objects shortname where the substring *sub* is found such that sub is wholly
        contained in s[start:end]. Raises ValueError when the substring is not found.

        **sub**						*string* substring to find with the object's shortname

        **start**					optional *int* start index

        **end**						optional *int* end index

        **include_namespaces**		*bool* - If False, namespaces in the object's name will be ignored. default=False

        **RETURNS**					*int* index

        """

        try:
            name = self.getBasename() if not include_namespaces else self.getName()

            return name.index(sub, start, end)

        except ValueError as err:
            raise ValueError("substring " + str(sub) + " not found in node name: " + name)


    def rindex(self, sub, start=None, end=None, include_namespaces=False):
        """
        String operartion just like str.rindex().

        Return the highest index in objects shortname where the substring *sub* is found such that sub is wholly
        contained in s[start:end]. Raises ValueError when the substring is not found.

        **sub**						*string* substring to find with the object's shortname

        **start**					optional *int* start index

        **end**						optional *int* end index

        **include_namespaces**		*bool* - If False, namespaces in the object's name will be ignored. default=False

        **RETURNS**					*int* index

        """

        try:
            name = self.getBasename() if not include_namespaces else self.getName()

            return name.rindex(sub, start, end)

        except ValueError as err:
            raise ValueError("substring " + str(sub) + " not found in node name: " + name)


    def isalnum(self, include_namespaces=False):
        """
        String operartion just like str.isalnum().

        Return true if all characters in the nodes's shortname are alphanumeric and there is at least one character,
        false otherwise. If *include_namespaces* arg is *True*, any ':' characters in the node's name will be ignored
        and not count towards the result of this method.

        **RETURNS**					*bool*

        """

        name = self.getBasename() if not include_namespaces else self.getName().replace(":", "")

        return name.isalnum()


    def isalpha(self, include_namespaces=False):
        """
        String operartion just like str.isalpha().

        Return true if all characters in the nodes's shortname are alpha and there is at least one character,
        false otherwise. If *include_namespaces* arg is *True*, any ':' characters in the node's name will be ignored
        and not count towards the result of this method.

        **include_namespaces**		*bool* - If False, namespaces in the object's name will be ignored. default=False

        **RETURNS**					*bool*

        """

        name = self.getBasename() if not include_namespaces else self.getName().replace(":", "")

        return name.isalpha()


    def islower(self, include_namespaces=False):
        """
        String operartion just like str.islower().

        Return true if all cased characters in the nodes's shortname are lowercase and there is at least one cased character,
        false otherwise. If *include_namespaces* arg is *True*, any ':' characters in the node's name will be ignored
        and not count towards the result of this method.

        **include_namespaces**		*bool* - If False, namespaces in the object's name will be ignored. default=False

        **RETURNS**					*bool*

        """

        name = self.getBasename() if not include_namespaces else self.getName().replace(":", "")

        return name.islower()


    def istitle(self, include_namespaces=False):
        """
        String operartion just like str.istitle().

        Return true if the nodes's shortname is a titlecased string and there is at least one character, for example uppercase
        characters may only follow uncased characters and lowercase characters only cased ones. Return false otherwise.
        If *include_namespaces* arg is *True*, any ':' characters in the node's name will be ignored
        and not count towards the result of this method.

        **include_namespaces**		*bool* - If False, namespaces in the object's name will be ignored. default=False

        **RETURNS**					*bool*

        """

        name = self.getBasename() if not include_namespaces else self.getName().replace(":", "")

        return name.istitle()


    def isupper(self, include_namespaces=False):
        """
        String operartion just like str.isupper().

        Return true if all cased characters in the nodes's shortname are upercase and there is at least one cased character,
        false otherwise. If *include_namespaces* arg is *True*, any ':' characters in the node's name will be ignored
        and not count towards the result of this method.

        **include_namespaces**		*bool* - If False, namespaces in the object's name will be ignored. default=False

        **RETURNS**					*bool*

        """

        name = self.getBasename() if not include_namespaces else self.getName().replace(":", "")

        return name.isupper()


    def join(self, iterable, include_namespaces=False):
        """
        String operartion just like str.join().

        Return a string which is the concatenation of the strings in the iterable. The separator while be the node's shortname.

        **iterable**	sequence of *strings* to join using the node's shortname as the separator

        **include_namespaces**		*bool* - If False, namespaces in the nodes's name will be ignored. default=False

        **RETURNS**		*string*
        """

        name = self.getBasename() if not include_namespaces else self.getName()

        return name.join(iterable)


    def lower(self, include_namespaces=False):
        """
        String operartion just like str.lower().

        Return a copy of nodes's shortname, but with upper case letters converted to lower case.

        **include_namespaces**		*bool* - If False, namespaces in the nodes's name will be ignored. default=False

        **RETURNS**					*string*

        """

        name = self.getBasename() if not include_namespaces else self.getName()

        return name.lower()


    def partition(self, sep, include_namespaces=False):
        """
        String operartion just like str.partition().

        Split the nodes's shortname at the first occurrence of sep, and return a 3-tuple containing the part before the
        separator, the separator itself, and the part after the separator. If the separator is not found, return
        a 3-tuple containing the nodes's shortname itself, followed by two empty strings.

        **include_namespaces**		*bool* - If False, namespaces in the nodes's name will be ignored. default=False

        **RETURNS**					3-tuple containing the part before the separator, the separator itself, and the part after the separator

        """

        name = self.getBasename() if not include_namespaces else self.getName()

        return name.partition(sep)


    def rpartition(self, sep, include_namespaces=False):
        """
        String operartion just like str.rpartition().

        Split the nodes's shortname at the last occurrence of sep, and return a 3-tuple containing the part before the separator,
        the separator itself, and the part after the separator. If the separator is not found, return a 3-tuple
        containing two empty strings, followed by the string itself.

        **include_namespaces**		*bool* - If False, namespaces in the nodes's name will be ignored. default=False

        **RETURNS**					3-tuple containing the part before the separator, the separator itself, and the part after the separator

        """

        name = self.getBasename() if not include_namespaces else self.getName()

        return name.rpartition(sep)


    def replace(self, old, new, count=None, include_namespaces=False):
        """
        String operartion just like str.replace().

        Return a copy of the string with all occurrences of substring old replaced by new. If the optional
        argument count is given, only the first count occurrences are replaced

        **old**		sub *string* in the objects name to replace

        **new**		*string* to replace sub-string *old* with

        **RETURNS** *string*

        """

        name = self.getBasename() if not include_namespaces else self.getName()

        if count is None:
            return name.replace(old, new)

        return name.replace(old, new, count)


    def endswith(self, suffix, start=None, end=None, include_namespaces=False):
        """
        String operartion just like str.endswith().

        Return True if the string ends with the specified suffix, otherwise return False.
        suffix can also be a tuple of suffixes to look for. With optional start, test beginning at that position.
        With optional end, stop comparing at that position.
        Operrates only on the node's name itself and NOT it's full path if DAG

        **suffix**				*string* or *tuple* of strings to test against

        **start**				optional *int* test beginning at position

        **end**					optional *int* stop comparing at position

        **include_namespaces**	optional *bool* to include namespace in the test (default=False)

        **RETURNS**		*bool*


        >>> node = MNode("cool_node")
        >>> node.endswith("_node")
        >>> #RESULT - True

        """

        name = self.getBasename() if not include_namespaces else self.getName()

        args = [item for item in (suffix, start, end) if not item is None]

        return name.endswith(*args)


    def split(self, sep, maxsplit=None, include_namespaces=False):
        """
        String operartion just like str.split().

        Return a list of the words in the node name, using sep as the delimiter string. If maxsplit is given, at most
        maxsplit splits are done (thus, the list will have at most maxsplit+1 elements). If maxsplit is not specified
        or -1, then there is no limit on the number of splits (all possible splits are made).


        If sep is given, consecutive delimiters are not grouped together and are deemed to delimit empty strings
        (for example, '1,,2'.split(',') returns ['1', '', '2']). The sep argument may consist of multiple characters
        (for example, '1<>2<>3'.split('<>') returns ['1', '2', '3']). Splitting an empty string with a specified
        separator returns [''].


        If sep is not specified or is None, a different splitting algorithm is applied:
        runs of consecutive whitespace are regarded as a single separator, and the result will contain no empty strings
        at the start or end if the string has leading or trailing whitespace. Consequently, splitting an empty string or
        a string consisting of just whitespace with a None separator returns [].


        **sep**					*string* delimiter to split by

        **maxsplit**			optional *int* limit the amount of splits

        **include_namespaces**	optional *bool* to include namespace in the test (default=False)

        **RETURNS**				*list* of *strings*


        >>> node = MNode("super_awesome_naming_convention")
        >>> node.split("_")
        >>>	#RESULT - ['super', 'awesome', 'naming', 'convention']

        """

        name = self.getBasename() if not include_namespaces else self.getName()

        args = [item for item in (sep, maxsplit) if not item is None]

        return name.split(*args)


    def rsplit(self, sep, maxsplit=None, include_namespaces=False):
        """
        String operartion just like str.rsplit().

        Return a list of the words of the nodes's shortname, scanning from the end. To all intents and purposes, the resulting
        list of words is the same as returned by split(), except when the optional third argument maxsplit is explicitly
        specified and nonzero. If maxsplit is given, at most maxsplit number of splits (the rightmost ones) occur,
        and the remainder of the string is returned as the first element of the list (thus, the list will have at most
        maxsplit+1 elements).

        **sep**					*string* delimiter to split by

        **maxsplit**			optional *int* limit the amount of splits

        **include_namespaces**	optional *bool* to include namespace in the test (default=False)

        **RETURNS**				*list* of *strings*


        >>> node = MNode("super_awesome_naming_convention")
        >>> node.split("_")
        >>>	#RESULT - ['super', 'awesome', 'naming', 'convention']

        """

        name = self.getBasename() if not include_namespaces else self.getName()

        args = [item for item in (sep, maxsplit) if not item is None]

        return name.rsplit(*args)


    def startswith(self, prefix, start=None, end=None, include_namespaces=False):
        """
        String operartion just like str.startswith().

        Return True if nodes' shortname starts with the prefix, otherwise return False. prefix can also be a tuple of
        prefixes to look for. With optional start, test string beginning at that position. With optional end, stop
        comparing string at that position.

        **prefix**				*string* or *tuple* of strings to test against

        **start**				optional *int* test beginning at position

        **end**					optional *int* stop comparing at position

        **include_namespaces**	optional *bool* to include namespace in the test (default=False)

        **RETURNS**		*bool*


        >>> node = MNode("cool_node")
        >>> node.startswith("cool_")
        >>> #RESULT - True

        """

        name = self.getBasename() if not include_namespaces else self.getName()

        args = [item for item in (prefix, start, end) if not item is None]

        return name.startswith(*args)


    def strip(self, chars=None, include_namespaces=False):
        """
        String operartion just like str.strip().

        Return a copy of the node's shortname with leading and trailing characters removed. If chars is omitted or None,
        whitespace characters are removed. If given and not None, chars must be a string; the characters in the string
        will be stripped from the both ends of the string this method is called on.

        **chars**			optional *string* to strip from the node's shortname

        **RETURNS**			*string*
        """

        name = self.getBasename() if not include_namespaces else self.getName()

        return name.strip(chars)


    def lstrip(self, chars=None, include_namespaces=False):
        """
        String operartion just like str.lstrip().

        Return a copy of the node's shortname with leading characters removed. If chars is omitted or None, whitespace characters
        are removed. If given and not None, chars must be a string; the characters in the string will be stripped from
        the beginning of the string this method is called on.

        **chars**			optional *string* to strip from the node's shortname

        **RETURNS**			*string*
        """

        name = self.getBasename() if not include_namespaces else self.getName()

        return name.lstrip(chars)


    def rstrip(self, chars=None, include_namespaces=False):
        """
        String operartion just like str.lstrip().

        Return a copy of the node's shortname with trailing characters removed. If chars is omitted or None, whitespace characters
        are removed. If given and not None, chars must be a string; the characters in the string will be stripped from
        the beginning of the string this method is called on.

        **chars**			optional *string* to strip from the node's shortname

        **RETURNS**			*string*
        """

        name = self.getBasename() if not include_namespaces else self.getName()

        return name.rstrip(chars)


    def swapcase(self, include_namespaces=False):
        """
        String operartion just like str.swapcase().

        Return a copy of node's shortname, but with lower case letters converted to upper case and vice versa.

        **RETURNS**			*string*
        """

        name = self.getBasename() if not include_namespaces else self.getName()

        return name.swapcase()


    def upper(self, include_namespaces=False):
        """
        String operartion just like str.upper().
        Return a copy of object's shortname, but with lower case letters converted to upper case.

        **RETURNS**					*string*

        """

        name = self.getBasename() if not include_namespaces else self.getName()

        return name.upper()


    def __eq__(self, other):
        """
        Built-in method. Enables the use of '==' syntax with the MNode class
        """

        if str(self) == str(other):
            return True

        return False


    def __ne__(self, other):
        """
        Built-in method. Enable the use of "!=" syntax with the MNode class
        """

        if str(self) != str(other):
            return True

        return False


    def __hash__(self):
        """
        Built-in method. For operations on members of hashed collections including set, frozenset, and dict
        """

        return self._obj_hndl.hashCode()


    def __nonzero__(self):
        """
        Built-in method. Called to implement truth value testing and the built-in operation bool()
        """

        return self.isValid()


    def _getMObjectByName(self, node_name):
        """
        PRIVATE METHOD: Returns the MObject of the node with the given string name
        """

        if mc.objExists(node_name):
            sel_list = om.MGlobal.getSelectionListByName(node_name)
            m_obj = sel_list.getDependNode(0)

        else:
            raise RuntimeError("Object dose not exist: " + str(node_name))

        return m_obj


    def _raiseInvalidError(self):
        """
        PRIVATE METHOD: Called when the core MObject has become invalid (has been deleted from
        scene) but is still being accessed.
        """

        raise RuntimeError("Node is invalid.")


    def _dumpPickle(self, data):
        """
        Use base64 encoding to convert python data to a pure ASCII string via pickle at its highest protocol
        """

        return codecs.encode(pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL), "base64").decode()


    def _loadPickle(self, data):
        """
        Use base64 decoding to convert a pure ASCII string back to a python data via pickle
        """

        try:
            return pickle.loads(codecs.decode(data.encode(), "base64"))

        except:
            #return pickle.loads(str(data)) # backwards compatibility with default pickle protocol
            try:
                return pickle.loads(str.encode(data)) # python3
            except:
                return pickle.loads(str(data)) # python2




def _unpickleNode(cls, node_type, add_attr_args, set_attr_args, kargs):
    """
    Entry point for pickler to unpickle a pickled Maya node. Must be a module level function for whatever reason.
	"""

    new_node = MNode.createNode(node_type, **kargs)

    if add_attr_args:
        for args, key_args in add_attr_args:
            new_node.addAttr(*args, **key_args)

    return cls(new_node)



class MNodeList(object):
    """
    List type object, used for storing MNode type objects
    """

    NODE_CLASS = MNode


    def __init__(self, nodes=None):
        """
        Initialize a new MNodeList object

        **nodes** 		list/tuple of MNodes or string names. Default = None (create empty list)
        **RETURNS**		*None*
        """

        self._node_list = []

        if nodes:
            self._node_list = [self.NODE_CLASS(node) for node in nodes]



    def delete(self):
        """
        Delete all nodes in the list. List will be empty after caliing this method.

        **RETURNS**		*None*
        """

        self._applyFunction("delete")
        self._node_list = []


    def __contains__(self, item):
        """
        Built-in method.
        """

        for node in self._node_list:
            if str(node) == str(item):
                return True

        return False


    def __nonzero__(self):
        """
        Built-in method. Called to implement truth value testing and the built-in operation bool()
        """

        return True if self._node_list else False


    def __delitem__(self, key):
        """
        Built-in method.
        """

        del self._node_list[key]


    def __getitem__(self, key):
        """
        Built-in method.
        """

        return self._node_list[key]


    def __iter__(self):
        """
        Built-in method.
        """

        for item in self._node_list:
            yield item


    def __len__(self):
        """
        Built-in method.
        """

        return len(self._node_list)


    def __setitem__(self, key, value):
        """
        Built-in method.
        """

        self._node_list[key] = self.NODE_CLASS(value)


    def __str__(self):
        """
        Built-in method.
        """

        if self._node_list:

            return "[" + ", ".join(["\"" + node.__str__() + "\""for node in self._node_list]) + "]"

        return "[]"


    def __repr__(self):
        """
        Built-in method.
        """

        if self._node_list:

            return "[" + ", ".join(["\"" + node.__repr__() + "\"" for node in self._node_list]) + "]"

        return "[]"


    def append(self, item):
        """
        Built-in method.
        """

        item = self.NODE_CLASS(item)

        self._node_list.append(item)


    def count(self, node):
        """
        :purpose:	Returns the number of occurances of the given node in the list
        :returns:	int
        """

        node = self.NODE_CLASS(node)

        return self._node_list.count(node)


    def extend(self, item):
        """
        Built-in method.
        """

        item_list = [self.NODE_CLASS(node) for node in item]

        self._node_list.extend(item_list)


    def getAttr(self, attr_name, skip_missing=False, **kargs):
        """
        Returns the value of the given attr on every node in the list. Can optionally
        skip or error on missing attributes. If a missing attr is skipped, the resulting
        tuple will have placeholder None values representing those nodes.

        :arg		attr_name: string name of attr
        :arg		skip_missing: bool - True to quietly skip any nodes that are missing the
        			given attr. Missing attrs will result of None in the returned tuple.
                    False will throw an exception on missing attr. default=False
        :arg		kargs: keywords arg supported by maya.cmds.getAttr
        :returns:	tuple of attribute values or None. Returned tuple indices will correspond to
        			the indices of the nodes in this list.

        """

        result = []

        for node in self._node_list:

            if (node.hasAttr(attr_name)) or (not skip_missing):

                result.append(node.getAttr(attr_name, **kargs))

            elif skip_missing:

                result.append(None)

        if result:
            return tuple(result)

        return None


    def setAttr(self, attr_name, val=None, skip_missing=False, **kargs):
        """
        Sets the given attr to the given value on all nodes in the list

        :arg		attr_name: string name of attr to set
        :arg		val: value to set the attribute to. This arg is optional if setting attribute
        			properties instead of value.
        :arg		skip_missing: bool - True to quietly skip any nodes that are missing the
        			given attr. False will throw an exception on missing attr. default=False
        :arg		kargs: keywords arg supported by maya.cmds.setAttr
        :returns:	None

        """

        for node in self._node_list:

            if (node.hasAttr(attr_name)) or (not skip_missing):

                node.setAttr(attr_name, val, **kargs)


    def addAttr(self, long_name, attr_type, **kargs):
        """
        Adds an attribute of the given long name and given type to all the nodes in the list.
        Supports all keyword args of maya.cmds.addAttr except "dt" and "at" which are replaced by the attr_type arg.

        :arg 		long_name: string long name of the attribute to add
        :arg 		attr_type: string type of attribute to add. Supports all string
        			types supported by the "dt" and "at" args of maya.cmds.addAttr
        :arg		kargs: keyword args supported by maya.cmds.addAttr
        :returns: 	None

        >>> node_list.addAttr("test", "float", keyable=True)

        """

        return self._applyFunction("addAttr", *(long_name, attr_type), **kargs)


    def bakeResults(self, *args, **kargs):
        """
        Run bakeResults on nodes in this list with the given options

        **args**		optional string args of attributes to bake. If args are given,
        				any value given to the *attribute* flag will be overridden
        **kargs** 		keyword args supported by maya.cmds.bakeResults
        **RETURNS** 	*None*

        >>> node_list.bakeResults()

        """

        if args:
            kargs["attribute"] = args

        mc.bakeResults(self, **kargs)



    def getAttrMap(self, *args, **kargs):
        """
        Returns an OrderedDict of all MNodes is this list as keys and OrderedDict of
        attributes/values as values. This method supports all arguments and keyword arguments used
        by maya.cmds.listAttr.

        **args**		optional specific string pattern of an attribute to query on the node. This supports multiple string args

        **kargs** 		keywords args supported by maya.cmds.listAttr

        **RETURNS**		*OrderedDict* or *None*

        >>> ## get the names and values of all keyable attributes on this node
        >>> keyable_map = node_list.getAttrMap(keyable=True)
        >>>
        >>> ## get names and values of all attributes that start with "trans"
        >>> trans_attrs = node_list.getAttrMap("trans*")

        """

        attr_map = OrderedDict()

        for node in self._node_list:

            attr_vals = node.getAttrMap(*args, **kargs)

            if attr_vals:
                attr_map[node] = attr_vals

        if attr_map:
            return attr_map

        return None


    def listNodesOfType(self, node_type):
        """
        Return the nodes within this list that match the given node type.

        **node_type**		*string* node type

        **RETURNS**			*MNodeList* or *None*
        """

        if self._node_list:

            results = [node for node in self._node_list if node.getObjectType() == node_type]

            if results:
                return self.__class__(results)

        return None


    def listNodesWithAttr(self, attr_name):
        """
        Return the nodes within this list that have an attribute with the given name.

        **attr_name**		*string* attribute name

        **RETURNS**			*MNodeList* or *None*
        """

        if self._node_list:

            results = [node for node in self._node_list if node.hasAttr(attr_name)]

            if results:
                return self.__class__(results)

        return None


    def _applyFunction(self, func_name, *args, **kargs):
        """
        Shorthand for calling a MNode method on all nodes in the list
        """

        result = []

        for node in self._node_list:
            func = getattr(node, func_name)

            result.append(func(*args, **kargs))

        return tuple(result)


    def index(self, x):

        return self._node_list.index(x)


##---defered intializations----##
MNode.NODE_LIST_CLASS = MNodeList
