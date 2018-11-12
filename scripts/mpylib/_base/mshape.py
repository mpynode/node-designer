import maya.cmds as mc

from mnode import MNode, MNodeList


class MShape(MNode):
    """
    :purpose:	Base class for shape node related funtionality. Single instance of
    			MShape respresents a single shape node in the current scene.
    :extends:	MNode
    """
    
    NODE_TYPE = "shape"
    
    
    def __init__(self, shape):
        """
        :purpose:	Intialize a new instance of MShape base on an existing shape node
        :arg		shape: MNode or string name of an existing shape node
        :returns:	None
        """
        
        super(MShape, self).__init__(node=shape)
        
        if not self.NODE_TYPE in self.getInheritedNodeTypes():
            raise RuntimeError(str(shape) + " is not of type: " + self.NODE_TYPE)
        
        
    def getDagPath(self):
        """
        Utility method for working with the Maya API. Returns MDagPath object for this mesh node.
        
        **RETURNS**		MDagPath
        """
        
        return self._dag_path
    
    
    def duplicate(self, **kargs):
        
        """
        Duplicate the node with the given options. This overrides the default MNode version because Maya
        returns the Transform
        
        **kargs**	keywords arg supported by maya.cmds.duplicate
        
        **RETURNS** MNode of the new node
        
        >>> new_node = node.duplicate()
        
        """        

        result = mc.duplicate(self, **kargs)[0]

        if result:
            return MNode(result)
    
        
    def getParent(self):
        """
        :purpose: 	Returns the shape's parent node
        :returns: 	MTrans or None
        """         
        
        parent = mc.listRelatives(self, parent=True, fullPath=True)
        
        if parent:
            return MNode(parent[0])
        
        return None
    
    
    def parent(self, trans):
        """
        :purpose: 	Parents this shape to another transform. Functions just like
                    maya.cmds.parent(shape=True, relative=True). 
        :arg		trans: MNode or string name of a transform node
        :returns: 	None
        """   
        
        args = [self, trans]
        
        mc.parent(*args, shape=True, relative=True)
    
    
    
class MShapeList(MNodeList):
    """
    :purpose:	List type object, used for storing MShape type objects
    """    
    
    NODE_CLASS = MShape
    
    
    def __init__(self, nodes=None):
        
        super(MShapeList, self).__init__(nodes)
        
        
##---defered intializations----##    
MShape.NODE_LIST_CLASS = MShapeList