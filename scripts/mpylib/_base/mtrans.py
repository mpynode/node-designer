import math
from collections import OrderedDict

import maya.cmds as mc
import maya.api.OpenMaya as om

from mnode import MNode, MNodeList
from mshape import MShape, MShapeList


class MTrans(MNode):
    """
    Provides object oriented interface for querying/editing DAG nodes inside Maya. An instance of the MTrans class
    provides storage and access to a single Maya transform node. Methods within the class replace the most
    commonly used maya DAG commands. Public methods operate on the object stored within the MTrans instance. Note that most 
    methods support the same keywords arguments as their maya.cmds equivalent.
    """    

    NODE_TYPE = "transform"
    
    DAG_FN_CLASS = om.MFnTransform
    
    DAG_FN_FUNCS = MNode.DAG_FN_FUNCS + ("clearRestPosition", "enableLimit", "isLimited", "limitValue",
                                         "resetFromRestPosition", "restPosition", "rotateBy", "rotateByComponents",
                                         "rotateOrientation", "rotatePivot", "rotatePivotTranslation", "rotation",
                                         "rotationComponents", "rotationOrder", "scaleBy", "scalePivot",
                                         "scalePivotTranslation", "setLimit", "setRestPosition",
                                         "setRotateOrientation", "setRotatePivot", "setRotatePivotTranslation",
                                         "setRotation", "setRotationComponents", "setRotationOrder", "setScale",
                                         "setScalePivot", "setScalePivotTranslation", "setShear",
                                         "setTransformation", "setTranslation", "shear", "shearBy",
                                         "transformation", "translateBy", "translation")

    X_AXIS_VECT = (1.0, 0.0, 0.0)
    Y_AXIS_VECT = (0.0, 1.0, 0.0)
    Z_AXIS_VECT = (0.0, 0.0, 1.0)
    NEG_X_AXIS_VECT= (-1.0, 0.0, 0.0)
    NEG_Y_AXIS_VECT = (0.0, -1.0, 0.0)
    NEG_Z_AXIS_VECT = (0.0, 0.0, -1.0)

    WORLD_VECT_LOOKUP = {"x":(1.0, 0.0, 0.0), "y":(0.0, 1.0, 0.0), "z":(0.0, 0.0, 1.0)}

    WORLD_VECTS = ("x", "y", "z", "-x", "-y", "-z")

    AXIS_LOOKUP = {"x":X_AXIS_VECT,
                   "y":Y_AXIS_VECT,
                   "z":Z_AXIS_VECT,
                   "-x":NEG_X_AXIS_VECT,
                   "-y":NEG_Y_AXIS_VECT,
                   "-z":NEG_Z_AXIS_VECT}    

    ALL_AXES = (X_AXIS_VECT, Y_AXIS_VECT, Z_AXIS_VECT,
                NEG_X_AXIS_VECT, NEG_Y_AXIS_VECT, NEG_Z_AXIS_VECT)

    POS_AXES = (X_AXIS_VECT, Y_AXIS_VECT, Z_AXIS_VECT)

    INIT_POSE_ATTR_PREFIX = "init_"


    def __init__(self, node=None, name=None):
        """
        Initialize a new MTrans object

        **node**		*string* name or *MNode* of dag node to intialize from. A new transform is created if this
        				arg is not provided.
        **name**		optional *string* name to give the node if creating a new node. Ignored 
        				if initializing from an existing transform
        **RETURNS**		*None*

        >>> ## create new transform
        >>> trans = MTrans()
        >>>
        >>> ## create new transform and set its name at same time
        >>> trans = MTrans(name="fooFoo")
        >>>
        >>> ## intialize a new MTrans instance from an existing transform node
        >>> trans = MTrans("existingTransNode")

        """
        
        super(MTrans, self).__init__(node, name=name)

        if not self.hasFn(om.MFn.kTransform):
            raise TypeError("Given node must be " + self.NODE_TYPE + " type. " + str(self))


    def convertLocalVectToWorld(self, vct):
        """
        Converts transform's given local vector to world space
        
        **vct**		 	3 float tuple/list
        **RETURNS**		3 float tuple
        
        
        >>> ## convert the x-axis to world space
        >>> ws_vect = node.convertLocalVectToWorld((1.0, 0.0, 0.0))
        
        """

        world_mtx = self.xform(q=True, ws=True, matrix=True)

        return ((vct[0]*world_mtx[0]) + (vct[1]*world_mtx[4]) + (vct[2]*world_mtx[8]),
                (vct[0]*world_mtx[1]) + (vct[1]*world_mtx[5]) + (vct[2]*world_mtx[9]),
                (vct[0]*world_mtx[2]) + (vct[1]*world_mtx[6]) + (vct[2]*world_mtx[10]))


    def freeze(self, **kargs):
        """
        Freezes (makeIdentity) the transform
        
        **kargs**		keyword args supported by maya.cmds.makeIdentity
        
        **RETURNS**	None
        
        >>>	## freeze just rotation
        >>> node.freeze(apply=True, rotate=True, translate=False, scale=False, jointOrient=True)
        
        """        

        mc.makeIdentity(*(self,), **kargs)


    def getBaseParent(self):
        """
        Returns the transform node's furthest parent/grandparent transform
        
        **RETURNS** 	MTrans or None
        
        """

        ##---use path tokens to find top parent string name---##
        path_tokens = [token for token in str(self).split("|") if token]

        if len(path_tokens) > 1:
            return MTrans(path_tokens[0])

        return None


    def getChildren(self, obj_type=None):
        """
        Returns the direct children of the transform
        
        **obj_type**	*string* - limit to only children of this node type
        
        **RETURNS**		*MTransList* or *None*
        """

        kargs = {"children":True, "shapes":False, "fullPath":True}

        if obj_type:
            kargs["type"] = obj_type
            
        #listRelatives has a bug where it does not consider locatorShapes as shapes
        #if obj_type is not specified, set type to transform which will include any node type derived from transform class
        else:
            kargs["type"] = "transform" 

        children = self.listRelatives(**kargs)

        if children:
            return self.NODE_LIST_CLASS(children)

        return None


    def getDescendents(self, include_root=False, obj_type=None, **kargs):
        """
        Returns all children/grandchildren of the transform
        
    	**include_root**		*bool* - return this transform in the results. default=False
        **obj_type**			*string* - limit returned object to this node type. default=None
        
        **RETURNS**				*MTransList* or *None*
        """        

        results = self.NODE_LIST_CLASS()
        kargs = {"children":True, "shapes":False, "fullPath":True, "allDescendents":True}

        if obj_type:
            kargs["type"] = obj_type

        children = self.listRelatives(**kargs)

        if include_root:
            results.append(self)

        if children:
            results.extend(children)

        if results:
            return results

        return None
    
    
    def getDagPath(self):
        """
        Get this object's MDagPath for working with Maya API
        
        **RETURNS**		MDagPath
		"""
        
        return self._dag_path


    def getDistance(self, other):
        """
        Return the distance from this transform to another
        
        **other**		*MNode* or *string* name of another transform
        
        **RETURNS**		*float* distance
        
        >>> # get distance from node_a to node_b
        >>> distance = node_a.getDistance(node_b)
        
        """        

        other = MTrans(other)

        pos_a = self.xform(q=True, ws=True, rp=True)
        pos_b = other.xform(q=True, ws=True, rp=True)

        return math.sqrt(((pos_a[0]-pos_b[0])*(pos_a[0]-pos_b[0]))\
                         + ((pos_a[1]-pos_b[1])*(pos_a[1]-pos_b[1]))\
                         + ((pos_a[2]-pos_b[2])*(pos_a[2]-pos_b[2])))


    def getParent(self):
        """
        Returns the transform's parent node
        
        **RETURNS**	 	*MTrans* or *None*
        """         

        parent = mc.listRelatives(self, parent=True, fullPath=True)

        if parent:
            return MTrans(parent[0])

        return None
    
    
    def getParentOfType(self, obj_type):
        """
        Recursive method walks up the hierarchy from this node in search of the first parent/grandparent
        node that matches the given type.
        
        **obj_type**		*string* node type to seach for
        
        **RETURNS**			*MTrans* or None
        
		"""
        
        def _walkParentNodes(node):
            
            par = node.getParent()
            
            if par and (par.getObjectType() != obj_type):
                par = _walkParentNodes(par)
            
            return par
        
        parent_node = self.getParent()
        
        if parent_node and (parent_node.getObjectType() == obj_type):
            
            return parent_node
        
        elif parent_node:
            return _walkParentNodes(parent_node)
        
        return None
    
    
    def getWorldSpacePosition(self):
        """
        Get the world space position of this transform.
        
        **RETURNS**		*tuple* of 3 *floats* 
		"""
        
        return tuple(self.xform(q=True, ws=True, rp=True))
    
    
    def setWorldSpacePosition(self, ws_pos):
        
        self.xform(ws=True, translation=ws_pos)
    
    
    def getRotationAsQuaternion(self, world_space=True, py_list=False):
        """
        Return the orientation of the current transform as a quaternion.
        
        **world_space**		bool - get rotation in world space. default=True. If False,
        					quaterion will be returned in transform space.
                            
        **py_list**			bool - If True, returns quaterion as a 4 float tuple. If False, returns a MQuaternion object.
        					default=False
                            
        **RETURNS**			MQuaternion or 4 float tuple, depending on the *py_list* arg
		"""
        
        space = om.MSpace.kWorld if world_space else om.MSpace.kTransform
        rot = self._fn_set.rotation(space, asQuaternion=True)
        
        if py_list:
            return (rot.x, rot.y, rot.z, rot.w)
        
        return rot
    
    
    def setRotationFromQuaternion(self, rot, world_space=True):
        """
        Set the orientation of the current transform to the given quaterion.
        
        **rot**				MQuaternion or 4 float tuple of the quaterion to set

        **world_space**		bool - set rotation as world space. default=True. If False,
                            quaterion will be set in transform space.

        **RETURNS**			MQuaternion or 4 float tuple, depending on the *py_list* arg
        """ 
        
        space = om.MSpace.kWorld if world_space else om.MSpace.kTransform
        
        if type(rot) != om.MQuaternion:
            rot = om.MQuaternion(rot[0], rot[1], rot[2], rot[3])
            
        self._fn_set.setRotation(rot, space)
        
    
    
    def getHierarchyAttrMap(self, include_root=True, obj_type=None, child_first=False, stop_on_type=False,
                            attr_strs=None, **kargs):
        """
        Returns an OrderedDict of attribute values of nodes within the hierarchy of this nodes.
        Keys of the OrderedDict will be MTrans of nodes with OderderdDict of attributes as values.
        Attribute OrderedDicts will have attribute names as keys and their values as values.
        This method supports all arguments and keyword arguments used by maya.cmds.listAttr.
        
        **include_root**	*bool* - return transform itself in the results. default=False
        
        **obj_type**		*string* - limit returned object to this node type. default=None

        **attr_strs**		optional list of specific string patterns of an attribute to query on the node. This supports multiple string args

        **kargs** 			keywords args supported by maya.cmds.listAttr

        **RETURNS**			*OrderedDict* or *None*
        
        >>> #get all the keyable attributes
        >>> a.getHierarchyAttrMap(keyable=True)
        >>> 
        >>>	#get all keyable translate and rotate attributes
        >>> a.getHierarchyAttrMap(attr_strs=('translate?', 'rotate?'), keyable=True)

		"""
        
        node_map = OrderedDict()
        node_gen = self.walkChildren(include_root=include_root, obj_type=obj_type,
                                     child_first=child_first, stop_on_type=stop_on_type)
        
        for trans_node in node_gen:
            
            args = attr_strs if attr_strs else ()
            
            attr_map = trans_node.getAttrMap(*args, **kargs)
            
            if attr_map:
                
                node_map[trans_node] = attr_map
                
        if node_map:
            return node_map
        
        return None
    
    
    def isChildOf(self, other, recursive=False):
        """
        Test whether this transform is a child of the given transform
        
        **other**		*string* name or MNode of a transform node to test
        
        **recursive**	*bool* - False, only test against the direct parent node. True, consider
        				grandparent transforms.
                        
        **RETURNS**		*bool*
        
        >>> a.isChildOf(b)
        
		"""
        
        other = MTrans(other)
        
        if not recursive:
            
            return self.getParent() == other
        
        return bool(self._fn_set.hasParent(other))


    def getShapes(self, shape_type=None):
        """
        Returns the transform's shape nodes
        
        **RETURNS**		MShapeList or None
        
        """
        
        kargs = {"shapes":True, "fullPath":True}
        
        if shape_type:
            kargs["type"] = shape_type

        shapes = mc.listRelatives(self, **kargs)

        if shapes:
            return MShapeList(shapes)

        return None


    def getWorldVectors(self):
        """
        Converts the vectors of this transform's local axes to world space
        
        **RETURNS**		tuple of 3 tuples of 3 float values
        """

        world_vectors = []

        for axis in self.POS_AXES:

            world_vectors.append(self.convertLocalVectToWorld(axis))

        return tuple(world_vectors)


    def goToInitialPose(self, attrs=None):
        """
        Recalls attribute values stored by methods *setCurrentPoseToInitial* or *setInitialPose*
        and sets them to the current values. By default, all stored attribute values will be restored,
        unless specifc attribute names are provided.
        
        **attrs**		*tuple/list* of *string* attribrute names to restore or None. If None,
        				all stored attributes will be recalled. default=None
                        
        **RETURNS**		*None*

        >>> self.goToInitialPose()
        >>> 
        >>> self.goToInitialPose(attrs=("translateX", "translateY"))
        
		"""

        if not attrs:
            attrs = self.listAttr(self.INIT_POSE_ATTR_PREFIX + "*", userDefined=True)
            
        else:
            attrs = [self.INIT_POSE_ATTR_PREFIX + attr for attr in attrs]
            
        if attrs:
            
            for attr in attrs:
                
                target_attr = attr.replace(self.INIT_POSE_ATTR_PREFIX, "")
                
                if self.hasAttr(attr) and self.hasAttr(target_attr):
                    
                    attr_val = self.getAttr(attr)
                    self.setAttr(target_attr, attr_val)


    def setCurrentPoseToInitial(self, attrs=None):
        """
        Sets the current 'pose' of the transform as its 'initial pose'. By default, all keyable
        attributes are stored in the pose unless specific attributes are given.

        **attrs**		*tuple/list* of *string* attribrute names to query or None. If None,
        				all keyable attributes will be stored. default=None

        **RETURNS**		*None*

        >>> self.setCurrentPoseToInitial()
        >>> 
        >>> self.setCurrentPoseToInitial(attrs=("translateX", "translateY"))

        """

        if not attrs:
            attrs = self.listAttr(keyable=True)

        for attr in attrs:

            attr_val = self.getAttr(attr)

            self.setInitialPose(attr, attr_val)


    def setInitialPose(self, attr, val):
        """
        Sets the 'intial pose' of the given attribute to the given value

        **attr**		*string* attribute name to query
        **val**			value to store as initial

        **RETURNS**		*None*

        >>> self.setInitialPose("translateX", 999.9)
        """


        ##---resolve passed in attribute names to long version---##
        attr = self.attributeQuery(attr, longName=True)

        attr_type = self.attributeQuery(attr, attributeType=True)
        init_attr = self.INIT_POSE_ATTR_PREFIX + attr

        if not self.hasAttr(init_attr):
            self.addAttr(init_attr, attr_type)

        else:
            self.setAttr(init_attr, lock=False)

        self.setAttr(init_attr, val, lock=True)



    def listRelatives(self, **kargs):
        """
        :purpose: 	Fucntions just like maya.cmds.listRelatives
        :arg		kargs: all keyword args supported by maya.cmds.listRelatives
        :returns: 	MTransList or None
        """         

        results = mc.listRelatives(*(self,), **kargs)

        if results:
            return self.NODE_LIST_CLASS(results)

        return None


    def match(self, other, parent=False, match_pos=True, match_rot=True, match_rot_order=True,
              match_pivots=True):
        """
        *Match this transform to another. The transform is matched in position, rotation, rotateOrder, and pivot settings.
        
        **other**		MTrans or string name of a transform node to match
        **parent**		bool - Whether to parent the joint to the same parent as the node it's matching.
        
        **RETURNS**		None
        
        """          

        other = MTrans(other)
        
        if match_rot_order:
            self.setAttr("rotateOrder", other.getAttr("rotateOrder"))    

        if match_pos:
            self.snapTranslate(other)

        if match_rot:
            self.snapRotate(other)
            
        if match_pivots:
            for key in ("scalePivot", "scaleTranslation", "rotatePivot", "rotateAxis"):
                kargs = {key:True}
                val = other.xform(q=True, absolute=True, worldSpace=True, **kargs)
    
                kargs = {key:val}
                self.xform(absolute=True, worldSpace=True, preserve=True, **kargs)            

        if parent:
            src_parent = other.getParent()

            if src_parent:
                self.parent(src_parent)  


    def move(self, val, **kargs):
        """
        :purpose: 	Moves the transform in space based on given args. Fucntions just like
        			maya.cmds.move.
        :arg		val: 3 float list/tuple value to move
        :arg		kargs: all keyword args supported by maya.cmds.move
        :returns: 	None
        """          

        mc.move(*(val[0], val[1], val[2], self), **kargs)


    def orientConstraint(self, *args, **karg):
        """
        :purpose: 	Orient constrain the current transform node to other transform node
        :arg	 	args: string names, MNodes or MTransforms of an existing transform nodes to 
        			constrain to.
        :arg		kargs: any keyword argument supported by maya.cmds.orientConstraint command
        :returns: 	MTrans of the newly created constraint node
        """

        con = mc.orientConstraint(args, self, **karg)
        return MTrans(con[0])


    def parent(self, parent_node, **kargs):
        """
        Parents this transform to another node or to the world. Functions just like maya.cmds.parent.
        
        **parent_node**		*MNode* or *string* name of a DAG node to parent to
        
        **kargs**			all keyword args supported by maya.cmds.parent
        
        **RETURNS**			*None*
        
        """        

        args = (self, parent_node)

        mc.parent(*args, **kargs)
        
        
    def aimConstraint(self, *args, **karg):
        """
        Aim constrain the current transform node to other transform nodes
        
        **args**		*string* names, *MNodes* of existing transform nodes to constrain to
        
        **kargs**		any keyword argument supported by maya.cmds.aimConstraint command
        
        **RETURNS**		*MTrans* of the newly created constraint node
        
        >>> trans_a = MTrans()
        >>> trans_b = MTrans()
        >>> aim_con = trans_a.aimConstraint(trans_b, aimVector=(1.0, 0.0, 0.0), upVector=(0.0, 1.0, 0.0), worldUpType="scene")
        """

        con = mc.aimConstraint(args, self, **karg)

        return MTrans(con[0])      


    def parentConstraint(self, *args, **karg):
        """
        Parent constrain the current transform node to other transform nodes
    
        **args**		*string* names, *MNodes* of existing transform nodes to constrain to
    
        **kargs**		any keyword argument supported by maya.cmds.parentConstraint command
    
        **RETURNS**		*MTrans* of the newly created constraint node
    
        >>> trans_a = MTrans()
        >>> trans_b = MTrans()
        >>> par_con = trans_a.parentConstraint(trans_b)
        """

        con = mc.parentConstraint(args, self, **karg)

        return MTrans(con[0])      


    def pointConstraint(self, *args, **karg):
        """
        Point constrain the current transform node to other transform nodes

        **args**		*string* names, *MNodes* of existing transform nodes to constrain to

        **kargs**		any keyword argument supported by maya.cmds.pointConstraint command

        **RETURNS**		*MTrans* of the newly created constraint node

        >>> trans_a = MTrans()
        >>> trans_b = MTrans()
        >>> point_con = trans_a.pointConstraint(trans_b)
        """

        con = mc.pointConstraint(args, self, **karg)
        return MTrans(con[0])
    
    
    def scaleConstraint(self, *args, **karg):
        """
        Scale constrain the current transform node to other transform nodes

        **args**		*string* names, *MNodes* of existing transform nodes to constrain to

        **kargs**		any keyword argument supported by maya.cmds.scaleConstraint command

        **RETURNS**		*MTrans* of the newly created constraint node

        >>> trans_a = MTrans()
        >>> trans_b = MTrans()
        >>> scale_con = trans_a.scaleConstraint(trans_b)
        """

        con = mc.scaleConstraint(args, self, **karg)
        return MTrans(con[0])


    def pointOnPolyConstraint(self, comp_str=None, *args, **kargs):

        con = mc.pointOnPolyConstraint(args, self, **karg)
        
        
    def walkChildren(self, include_root=False, obj_type=None, stop_on_type=False, child_first=False):
        """
        Generator function that will recursively walk down the dag hierarchy, returning child
        transforms as it goes. The order that child nodes are returned can be controlled with the 
        child_first arg.
        
        **include_root**		*bool* - include this node in the result. default=False
        
        **obj_type**			*string* node type to return or None. If None, all nodes in the
        						hierarchy will be returned. When paired with the stop_on_type arg,
                                finding a node that doesn't match this type will prevent recursion
                                past that node. default=None
                                
        **stop_on_type**		*bool* - when paired with the *obj_type* arg, turning this on will 
    							will prevent recursion past nodes that don't match *obj_type*
        
        **child_first**			*bool* - If True, return from the bottom of the hierarchy up to this node.
        						If False, return from this node to the bottom most nodes.
                                default=False (top down)
                                
        **RETURNS**				generator of MTrans objects
        
        >>> a = MTrans(name="a")
        >>> b = MTrans(name="b")
        >>> c = MTrans(MNode.createNode("joint", name="c"))
        >>> d = MTrans(name="d")
        >>> e = MTrans(name="e")
        >>> f = MTrans(name="f")
        >>>
        >>> b.parent(a)
        >>> c.parent(b)
        >>> e.parent(c)
        >>> f.parent(e)
        >>> d.parent(c)
        >>>
        >>> a.walkChildren()
        >>> ## RESULT - (b, c, e, f, d)
        >>>
        >>> a.walkChildren(child_first=True)
        >>> ## RESULT - (f, e, d, c, b)
        >>>
        >>> a.walkChildren(obj_type="transform")
        >>> ## RESULT - (b, e, f, d)
        >>> 
        >>> a.walkChildren(include_root=True)
        >>> ## RESULT - (a, b, c, e, f, d)
        >>> 
        >>> a.walkChildren(include_root=True, obj_type="transform", stop_on_type=True)
        >>> ## RESULT - (a, b) ## joint stops recursion
        
		"""
        
        def _walkChildNodes(parent_node):
            """
            Recursive walking function
			"""
            
            if not child_first:
                if (not obj_type) or (parent_node.getObjectType() == obj_type):
                    yield parent_node
                
            child_nodes = parent_node.getChildren()
            
            if child_nodes:
                
                for child_node in child_nodes:
                    
                    ##----stop recursion if the option to stop on node type miss-match is set---##
                    if ((not obj_type) or (child_node.getObjectType() == obj_type)) or (not stop_on_type):
                    
                        for node in _walkChildNodes(child_node):
                            yield node
                
            if child_first:
                if (not obj_type) or (parent_node.getObjectType() == obj_type):
                    yield parent_node
        
        ##---entry point-----------------------------##
        if include_root:
            for child in _walkChildNodes(self):
                yield child
                
        else:
            children = self.getChildren(obj_type=obj_type)
            
            if children:
                for child in children:
                    for sub_child in _walkChildNodes(child):
                        yield sub_child
                


    def removeDrivers(self, trans=True, rot=True, scale=True, delete_constraints=True, delete_anim=True):
        """
        Optionally removes any incoming connections to the translate, rotate or scale channels of the transform node.
        
        :arg		trans: bool - remove any connections to the translate channels (default = True)
        :arg		rot: bool - remove any connections to the rotate channels (default = True)
        :arg		scale: bool - remove any connections to the scale channels (default = True)
        :arg		delete_constraints: bool - delete any incoming nodes that are constaints (default = True)
        :arg		delete_anim: bool - delete any incoming nodes that are animation (default = True)
        :returns:	None
        """
        
        delete_list = MNodeList()

        for channel, attr in map(None, (trans, rot, scale), ("translate", "rotate", "scale")):

            if channel:
                
                for axis in ("X", "Y", "Z"):
                    attr_name = attr + axis
                    in_cons, plugs = self.listConnections(attr_name=attr_name, plugs=True,
                                                          source=True, destination=False,
                                                          skipConversionNodes=True)

                    if in_cons:
                        mc.disconnectAttr(str(in_cons[0]) + "." + plugs[0],
                                          str(self) + "." + attr_name)

                        if delete_constraints and not in_cons[0] in delete_list:
                            if in_cons[0].getObjectType().endswith("Constraint"):
                                delete_list.append(in_cons[0])
                                
                        if delete_anim and not in_cons[0] in delete_list:
                            if in_cons[0].getObjectType().startswith("animCurve"):
                                delete_list.append(in_cons[0])
                                
        if delete_list:
            delete_list.delete()
                                

    def rotate(self, val, **kargs):
        """
        :purpose: 	Rotates the transform in space based on given args. Fucntions just like
        			maya.cmds.rotate.
        :arg		val: 3 float list/tuple value to rotate
        :arg		kargs: all keyword args supported by maya.cmds.rotate
        :returns: 	None
        """       

        mc.rotate(*(val[0], val[1], val[2], self), **kargs)


    def scale(self, val, **kargs):
        """
        :purpose: 	Scales the transform in size based on given args. Fucntions just like
                    maya.cmds.scale.
        :arg		val: 3 float list/tuple value to scale
        :arg		kargs: all keyword args supported by maya.cmds.scale
        :returns: 	None
        """        

        mc.scale(*(val[0], val[1], val[2], self), **kargs)
        
        
    def snapTranslate(self, other):
        """
        Snap the world space position of this transform to the given one.
        
        **other**		MTrans or *string* name of a transform node to snap to
        
        **RETURNS**		None
        
        """
        
        other = MTrans(other)
        
        pos = other.xform(q=True, ws=True, rp=True)
        self.xform(ws=True, t=pos)
        
        
    def snapRotate(self, other):
        """
        Snap the world space rotation of this transform to the given one.

        **other**		MTrans or *string* name of a transform node to snap to

        **RETURNS**		None

        """        
        
        other = MTrans(other)
        rot_quat = other.getRotationAsQuaternion()
        
        self.setRotationFromQuaternion(rot_quat)


    def xform(self, **kargs):
        """
        Functions just like maya.cmds.xform
        
        **kargs**		all keyword args supported by maya.cmds.xform
        
        **RETURNS**		value based on a xform query or None
        """         

        return mc.xform(*(self,), **kargs)



class MTransList(MNodeList):
    """
    :purpose:	List like object for storing and interacting with multiple transform nodes.
    :extends:	MNodeList
    """

    NODE_CLASS = MTrans

    def __init__(self, nodes=None):
        """
        :purpose:	Initialize a new MNodeList
        :arg		nodes: list/tuple of transform nodes or None for a blank list
        """

        MNodeList.__init__(self, nodes=nodes)
        
        
    def xform(self, **kargs):
        """
        Functions just like maya.cmds.xform
        
        **kargs**		all keyword args supported by maya.cmds.xform
        
        **RETURNS**		value based on a xform query or None
        """
        
        if self._node_list:
            
            return tuple([node.xform(**kargs) for node in self._node_list])
        
        return None
        
        
    def getAnimatedValues(self, start_frame=None, end_frame=None, step_size=1.0):
        
        if start_frame is None:
            start_frame = mc.playbackOptions(q=True, minTime=True)
            
        if end_frame is None:
            end_frame = mc.playbackOptions(q=True, maxTime=True)
          
        if start_frame < end_frame:
            cache_data = OrderedDict()
            orig_frame = mc.currentTime(q=True)
            
            cur_frame = start_frame
                
            while cur_frame <= end_frame:
                
                mc.currentTime(cur_frame)
                
                cache_data[cur_frame] = OrderedDict()
                
                for node in self._node_list:
                    
                    if not node in cache_data:
                        cache_data[cur_frame][node] = OrderedDict()
                        
                    cache_data[cur_frame][node]["translate"] = node.getWorldSpacePosition()
                    cache_data[cur_frame][node]["rotate"] = node.getRotationAsQuaternion()
                
                cur_frame += step_size
                
            mc.currentTime(orig_frame)
            
            return cache_data 
            
        else:
            raise RuntimeError("Given start frame is larger than the given end frame")
            
            
            
##---defered intializations----##    
MTrans.NODE_LIST_CLASS = MTransList