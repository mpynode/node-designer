import maya.cmds as mc
import maya.api.OpenMaya as om

from .._base import MNode, MShape


class MMesh(MShape):
    """
    Provides object oriented interface for querying/editing poly mesh shape nodes.
    """    

    NODE_TYPE = "mesh"

    DAG_FN_CLASS = om.MFnMesh
    
    DAG_FN_FUNCS = MShape.DAG_FN_FUNCS + ("setCurrentUVSetName", "getBinaryBlindData", "onBoundary",
                                          "getInvisibleFaces", "setVertexColors", "copyInPlace", "isColorClamped",
                                          "getTangents", "unlockVertexNormals", "getUVSetFamilyNames",
                                          "setCreaseVertices", "numUVs", "getFaceVertexTangents", "currentUVSetName",
                                          "getPolygonVertices", "addPolygon", "collapseEdges", "getEdgeVertices",
                                          "getStringBlindData", "cachedIntersectionAcceleratorInfo",
                                          "getConnectedShaders", "getBlindDataAttrNames", "getFaceNormalIds",
                                          "getBlindDataTypes", "getVertexNormals", "numColors", "assignColor",
                                          "setNormals", "clearBlindData", "getClosestUVs", "booleanOp", "updateSurface",
                                          "setFloatBlindData", "getTriangleOffsets", "assignColors",
                                          "setStringBlindData", "deleteVertex", "lockVertexNormals",
                                          "getFaceVertexTangent", "assignUVs", "setColors", "removeFaceColors",
                                          "isEdgeSmooth", "getFloatBlindData", "getColorRepresentation",
                                          "closestIntersection", "getFaceVertexNormal", "getPointAtUV", "setUVs",
                                          "setEdgeSmoothing", "sortIntersectionFaceTriIds", "getNormals", "clearColors",
                                          "getPolygonUVid", "getFaceVertexBinormals", "setFaceColor",
                                          "getAssociatedUVSetTextures", "freeCachedIntersectionAccelerator",
                                          "createInPlace", "getNormalIds", "getVertices", "setInvisibleFaces",
                                          "getBoolBlindData", "getUVSetsInFamily", "addHoles", "createColorSet",
                                          "anyIntersection", "getFaceUVSetNames", "copyUVSet", "removeVertexColors",
                                          "isNormalLocked", "deleteFace", "getClosestNormal", "extrudeFaces",
                                          "setColor", "setFaceVertexNormal", "deleteEdge", "currentColorSetName",
                                          "getPolygonNormal", "setUV", "assignUV", "getTriangles",
                                          "clearGlobalIntersectionAcceleratorInfo", "getColorSetFamilyNames",
                                          "isColorSetPerInstance", "getClosestPointAndNormal", "booleanOps",
                                          "getTangentId", "getVertexColors", "getPolygonTriangleVertices",
                                          "cleanupEdgeSmoothing", "createBlindDataType", "getPoint", "deleteColorSet",
                                          "setFaceVertexColor", "subdivideFaces", "getColorIndex", "deleteUVSet",
                                          "getUVs", "setIntBlindData", "isRightHandedTangent", "setCreaseEdges",
                                          "getVertexNormal", "getFaceVertexColors", "getAssociatedUVSetInstances",
                                          "getPointsAtUV", "getColorSetNames", "getDoubleBlindData", "getIntBlindData",
                                          "getFloatPoints", "getUVAtPoint", "isUVSetPerInstance", "duplicateFaces",
                                          "getBinormals", "setSomeUVs", "createUVSet", "generateSmoothMesh",
                                          "isBlindDataTypeUsed", "getUV", "copy", "collapseFaces", "clearUVs",
                                          "getFaceAndVertexIndices", "getFaceVertexIndex", "getSmoothMeshDisplayOptions",
                                          "extrudeEdges", "setEdgeSmoothings", "hasAlphaChannels", "allIntersections",
                                          "hasColorChannels", "isPolygonUVReversed", "getUvShellsIds", "getColors",
                                          "setFaceColors", "uniformGridParams", "unlockFaceVertexNormals",
                                          "setBoolBlindData", "setSomeColors", "getAssignedUVs", "getHoles",
                                          "setCurrentColorSetName", "getCreaseVertices", "intersectFaceAtUV",
                                          "setSmoothMeshDisplayOptions", "setFaceVertexColors", "getFaceVertexNormals",
                                          "setDoubleBlindData", "getFaceVertexBinormal", "getColor", "setPoint",
                                          "hasBlindData", "setFaceVertexNormals", "autoUniformGridParams", "syncObject",
                                          "removeFaceVertexColors", "subdivideEdges", "lockFaceVertexNormals",
                                          "isPolygonConvex", "setVertexNormals", "getAssociatedColorSetInstances",
                                          "setPoints", "getPolygonUV", "globalIntersectionAcceleratorsInfo",
                                          "polygonVertexCount", "extractFaces", "setIsColorClamped", "setVertexNormal",
                                          "getColorSetsInFamily", "setBinaryBlindData", "renameUVSet", "getCreaseEdges")
    


    def __init__(self, node):
        """
        Initialize a new MMesh object

        **node**		string name or MNode to intialize from

        **RETURNS**		*None*
        """

        if type(node) == om.MObject and node.apiType() == om.MFn.kMeshData:
            node = om.MFnMeshData(node).object()

        super(MMesh, self).__init__(node)

        if self.getObjectType() != self.NODE_TYPE:
            raise RuntimeError("Object must be " + self.NODE_TYPE + " type.")


    def _findSkinCluster(self, node):
        """
        Private recursive function that walks the dg in search of any incoming skin clusters nodes
        """

        if node.getObjectType() == "skinCluster":
            return node

        elif node.getObjectType() == "groupParts":

            nodes, plugs = node.listConnections("inputGeometry", source=True,
                                                destination=False, skipConversionNodes=True)

            if nodes:
                return self._findSkinCluster(nodes[0])

        return None


    def _getConnectedVerts(self, func_name, indices, **kargs):
        """
        Private generic method that handles use of MItMesh methods that query connected components
        """

        comp_indices = []
        mesh_iter = om.MItMeshVertex(self._dag_path)

        ##---find the proper MItMeshVertex get method by name----##
        get_func = getattr(mesh_iter, func_name)

        ##---loop all verts----##
        if not indices:
            while not mesh_iter.isDone():
                comp_indices.append(get_func(*kargs.values()))
                mesh_iter.next()    

        ##---loop given verts----##
        else:
            for i in indices:
                mesh_iter.setIndex(i)
                comp_indices.append(get_func(*kargs.values()))

        if comp_indices:
            return comp_indices

        return None


    def getVertCount(self):
        """
        Returns the number of vertices for this mesh.

        **RETURNS**		int number of verts
        """

        return self._fn_set.numVertices


    def getEdgeCount(self):
        """
        Returns the number of edges for this mesh.

        **RETURNS**		int number of edges
        """

        return self._fn_set.numEdges


    def getPolygonCount(self):
        """
        Returns the number of polygons for this mesh.

        **RETURNS**		int number of polygons
        """

        return self._fn_set.numPolygons
    
    
    def setPoints(self, points, world_space=False):
        """
        Sets the positions of the mesh's vertices. The positions may be 
        given as a sequence of MFloatPoint's or a sequence of MPoint's, but
        not a mix of the two.
        
        **points**
        	sequence of MPoint or MFloatPoint positions to set.

        **world_space**
        	Optional *bool* - whether to return the positions as world space values. default=False

        **RETURNS**
        	MPointArray representing the x,y,z positions of the verts on the mesh

        """

        space = om.MSpace.kObject if not world_space else om.MSpace.kWorld

        return self._fn_set.setPoints(points, space)    


    def getPoints(self, world_space=False):
        """
        Return the positions of all verts on this mesh

        **world_space**
        	Optional *bool* - whether to return the positions as world space values. default=False

        **RETURNS**
        	MPointArray representing the x,y,z positions of the verts on the mesh

        >>> mesh = MMesh(shape)
        >>> vrt_pos = mesh.getPoints(world_space=True)
        >>>
        >>> vert_0_x = vrt_pos[0][0]
        >>> vert_0_y = vrt_pos[0][1]
        >>> vert_0_z = vrt_pos[0][2]

        """

        space = om.MSpace.kObject if not world_space else om.MSpace.kWorld

        return self._fn_set.getPoints(space)


    def getClosestPoint(self, point, space=om.MSpace.kObject):
        """
        Returns a tuple containing the closest point on the mesh to the
        given point and the ID of the face in which that closest point lies.

        **point**		MPoint - point to be compared

        **space**		MSpace constant - Coordinate space to use. Default = OpenMaya.MSpace.kObject

        **RETURNS**		Tuple (MPoint, int)
        """

        closest_point, face_index = self._fn_set.getClosestPoint(point, space) 

        return closest_point, face_index


    def getVertsConnectedToVerts(self, verts=None):
        """
        Returns a tuple containing vert indices of all connected verts for all verts on a mesh or specific verts on a mesh.
        If all verts a queried, the indices of the returned tuple will equal the vert indices of the mesh. If specific
        verts are queried, indices of the returned tuple will match the indices of the provided vert list.

        **verts**		Optional sequence of *int* mesh indices to query. Default=None, which queries ALL verts on the mesh

        **RETURNS**		Tuple of sequences of connected vert indices

        >>> ##--connected verts for all verts on a cube
        >>> mesh = MMesh(shape)
        >>> verts = mesh.getVertsConnectedToVerts()
        >>> ##RESULTS -- ((2,1,6), (0,3,7), (3,0,4), (1,2,5), (5,2,6), (3,4,7), (7,4,0), (5,6,1))
        >>>
        >>> ##--connected verts for vert 1, 2 and 3
        >>> mesh = MMesh(shape)
        >>> verts = mesh.getVertsConnectedToVerts((1,2,3))
        >>> ##RESULTS -- ((0,3,7), (3,0,4), (1,2,5))

        """

        return self._getConnectedVerts("getConnectedVertices", verts)


    def getFacesConnectedToVerts(self, verts=None):
        """
        Returns a tuple containing face indices of all connected faces for all verts on a mesh or specific verts on a mesh.
        If all verts a queried, the indices of the returned tuple will equal the indices of the mesh. If specific
        verts are queried, indices of the returned tuple will match the indices of the provided vert list.

        **verts**		Optional sequence of *int* mesh indices to query. Default=None, which queries ALL verts on the mesh

        **RETURNS**		Tuple of sequences of connected face indices

        >>> ##--connected faces for all verts on a cube
        >>> mesh = MMesh(shape)
        >>> verts = mesh.getFacesConnectedToVerts()
        >>> ##RESULTS -- ((5,0,3), (3,0,4), (1,0,5), (4,0,1), (2,1,5), (4,1,2), (3,2,5), (4,2,3))
        >>>
        >>> ##--connected faces for vert 1, 2 and 3
        >>> mesh = MMesh(shape)
        >>> verts = mesh.getFacesConnectedToVerts((1,2,3))
        >>> ##RESULTS -- ((3,0,4), (1,0,5), (4,0,1))

        """        

        return self._getConnectedVerts("getConnectedFaces", verts)


    def getEdgesConnectedToVerts(self, verts=None):
        """
        Returns a tuple containing edge indices of all connected edges for all verts on a mesh or specific verts on a mesh.
        If all verts a queried, the indices of the returned tuple will equal the indices of the mesh. If specific
        verts are queried, indices of the returned tuple will match the indices of the prvided vert list.

        **verts**		Optional sequence of *int* mesh indices to query. Default=None, which queries ALL verts on the mesh

        **RETURNS**		Tuple of sequences of connected edge indices

        >>> ##--connected verts for all edges on a cube
        >>> mesh = MMesh(shape)
        >>> verts = mesh.getEdgesConnectedToVerts()
        >>> ##RESULTS -- ((10,0,4), (11,5,0), (6,4,1), (7,1,5), (8,6,2), (9,2,7), (10,8,3), (11,3,9))
        >>>
        >>> ##--connected edges for vert 1, 2 and 3
        >>> mesh = MMesh(shape)
        >>> verts = mesh.getEdgesConnectedToVerts((1, 2, 3))
        >>> ##RESULTS -- ((11,5,0), (6,4,1), (7,1,5))

        """

        return self._getConnectedVerts("getConnectedEdges", verts)


    def getVertsConnectedToFaces(self, faces=None):
        """
        Returns a tuple containing vert indices of all connected verts for all faces on a mesh or specific faces on a mesh.
        If all faces a queried, the indices of the returned tuple will equal the face indices of the mesh. If specific
        faces are queried, indices of the returned tuple will match the face indices of the provided faces list.

        **faces**		Optional sequence of *int* mesh face indices to query. Default=None, which queries ALL faces on the mesh

        **RETURNS**		Tuple of sequences of connected vert indices

        >>> ##--connected verts for all faces on a cube
        >>> mesh = MMesh(shape)
        >>> verts = mesh.getVertsConnectedToFaces()
        >>> ##RESULTS -- results = ((0, 1, 3, 2),(2, 3, 5, 4),(4, 5, 7, 6),(6, 7, 1, 0),(1, 7, 5, 3),(6, 0, 2, 4))
        >>> 
        >>> ##----get verts connected to face 0------##
        >>> face_0_verts = verts[0]
        >>>
        >>> ##--connected verts for face 1, 2 and 3
        >>> mesh = MMesh(shape)
        >>> verts = mesh.getVertsConnectedToFaces((1, 2, 3))
        >>> ##RESULTS -- ((2, 3, 5, 4), (4, 5, 7, 6), (6, 7, 1, 0))
        >>>
        >>> ##----get verts connected to face 1 which is at index 0 in the returned sequence------##
        >>> face_1_verts = verts[0]

        """ 

        comp_indices = []
        mesh_iter = om.MItMeshPolygon(self._dag_path)

        ##---loop all faces----##
        if not faces:
            while not mesh_iter.isDone():
                comp_indices.append(mesh_iter.getVertices())
                mesh_iter.next(None) ##- api 2.0 bug... function requires one arg even though docs say next() takes no args

        ##---loop given faces----##
        else:
            for i in faces:
                mesh_iter.setIndex(i)
                comp_indices.append(mesh_iter.getVertices())

        if comp_indices:
            return comp_indices
        return None



    def getUVsConnectedToFaces(self, faces=None, uv_set=None):
        """
        Returns a tuple containing uv indices of all connected face vertices for all faces on a mesh or specific faces on a mesh.
        If all faces a queried, the indices of the returned tuple will equal the face indices of the mesh. If specific
        faces are queried, indices of the returned tuple will match the face indices of the provided faces list.

        **faces**		Optional sequence of *int* mesh face indices to query. Default=None, which queries ALL faces on the mesh
        **uv_set**      Optional uv_set name, if none given code will return current uvSet

        **RETURNS**		Tuple of sequences of connected uv indices

        >>> ##--connected uvs for all faces on a cube
        >>> mesh = MMesh(shape)
        >>> uvs = mesh.getUVsConnectedToFaces()
        >>> ##RESULTS -- results = ((0, 1, 3, 2),(2, 3, 5, 4),(4, 5, 7, 6),(6, 7, 1, 0),(1, 7, 5, 3),(6, 0, 2, 4))
        >>> 
        >>> ##----get uvs connected to face 0------##
        >>> face_0_uvs = mesh.getUVsConnectedToFaces(faces=[0])
        >>>
        >>> ##--connected uvs for face 1, 2 and 3
        >>> mesh = MMesh(shape)
        >>> uvs = mesh.getUVsConnectedToFaces((1, 2, 3))
        >>> ##RESULTS -- ((2, 3, 5, 4), (4, 5, 7, 6), (6, 7, 1, 0))
        >>>
        >>> ##----get uvs connected to face 1 which is at index 0 in the returned sequence------##
        >>> face_1_uvs = uvs[0]
        """

        comp_indices = []
        face_index = None
        mesh_iter = om.MItMeshFaceVertex(self._dag_path)

        if uv_set is None:
            uv_set = '' # uvSet seems to require a string input

        ##---loop all faces----##
        if not faces:

            while not mesh_iter.isDone():

                # If this is a new face, begin a new sublist
                index = mesh_iter.faceId()
                if face_index != index:
                    comp_indices.append([])
                    face_index = index

                # Append uv indices to the last sublist
                if mesh_iter.hasUVs(uvSet=uv_set):
                    comp_indices[-1].append(mesh_iter.getUVIndex(uvSet=uv_set))

                mesh_iter.next()

        ##---loop given faces----##
        else:
            for i in faces:
                mesh_iter.setIndex(i)

                # If this is a new face, begin a new sublist
                if face_index != i:
                    comp_indices.append([])
                    face_index = i

                if mesh_iter.hasUVs(uvSet=uv_set):
                    comp_indices[-1].append(mesh_iter.getUVIndex(uvSet=uv_set))


        if comp_indices:
            return comp_indices


        return None



    def getVertUVIndices(self, verts=None, uv_set=None):
        """
        Returns a tuple containing UV indices of associated with all verts on a mesh or specific verts on a mesh.
        If all verts a queried, the indices of the returned tuple will equal the indices of the mesh verts. If specific
        verts are queried, indices of the returned tuple will match the indices of the provided vert list.
        Any invalid or missing UVs will be returned as -1.

        **verts**		Optional sequence of *int* vert indices to query. Default=None, which queries ALL verts on the mesh
        **uv_set**		Optional string name of a uvset to query. If None, the 'current' uvset will be queried.

        **RETURNS**		Tuple of sequences of UV int indices. Invalid or missing UVs will return an index of -1.

        >>> ##--connected verts for all edges on a cube
        >>> mesh = MMesh(shape)
        >>> uvs = mesh.getVertUVIndices(uv_set="map1")
        >>> ##RESULTS -- results = ((0, 0, 8),(9, 1, 1),(2, 2, 2),(3, 3, 3),(4, 4, 13),(11, 5, 5),(6, 6, 12),(10, 7, 7))
        >>>
        >>> ##--connected edges for vert 1, 2 and 3
        >>> mesh = MMesh(shape)
        >>> verts = mesh.getVertUVIndices((1, 2, 3))
        >>> ##RESULTS -- ((9, 1, 1),(2, 2, 2),(3, 3, 3))

        """        

        return self._getConnectedVerts("getUVIndices", verts, uv_set=uv_set)



    def getUVCoords(self, uv_set=None):
        """
        """

        return self._fn_set.getUVs(uvSet=uv_set) if uv_set else self._fn_set.getUVs(uvSet="")


    def getUVSetNames(self):
        """
        Return the string names of this mesh's uv sets

        **RETURNS**		tuple of string names

        >>> mesh = MMesh(shape)
        >>> uv_sets = mesh.getUVSetNames()
        >>> ##RESULTS -- ('map1', 'map2')

        """

        return self._fn_set.getUVSetNames()


    def getNumUVSets(self):
        """
        Return the number of uv sets within this mesh

        **RETURNS**		int

        >>> mesh = MMesh(shape)
        >>> uv_sets = mesh.getUVSetNames()
        >>> ##RESULTS -- 1

        """        

        return self._fn_set.numUVSets


    def getSkinCluster(self):
        """
        Returns skin cluster node feeding this mesh

        **RETURNS**		*MNode* of skinCluster or None
        """

        nodes, plugs = self.listConnections("inMesh", source=True, destination=False,
                                            skipConversionNodes=True)

        if nodes:
            return self._findSkinCluster(nodes[0])

        return None 


    def getVertCount(self):
        """
        Returns the number of verts

        **RETURNS**		*int*
        """

        return mc.polyEvaluate(self, vertex=True)


    def setVertexColor(self, vert_indices, **kargs):
        """
        Colors the given verts

        **vert_indices**		list/tuple of ints
        **kargs**				any keyword argument supported by mc.polyColorPerVertex

        **RETURNS**				None
        """

        args = [str(self) + ".vtx[" + str(i) + "]" for i in vert_indices]
        mc.polyColorPerVertex(*args, **kargs)


    def getVertsAsMObject(self, indices=None):
        """
        Utility method for working with the Maya API. Returns a single MObject that represents multiple verts on this mesh.

        **indices**
        optional list/tuple of ints of mesh vert indices to get. If not given, method returns an MObject that represents ALL verts on the mesh

        **RETURNS**
        MObject
        """

        sel = om.MSelectionList()
        shape_path = self._dag_path.fullPathName()

        ##----get ALL verts as a single MObject----##
        if indices is None:
            sel.add(shape_path + ".vtx[:]")

        ##----get specific verts----##
        else:
            for i in indices:
                sel.add(shape_path + ".vtx[" + str(i) + "]")

        dag_path, vert_mobj = sel.getComponent(0)

        return vert_mobj	




