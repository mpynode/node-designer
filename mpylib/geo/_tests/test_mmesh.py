
try:
    import maya.standalone
    maya.standalone.initialize()
except:
    pass

import maya.cmds as mc
import maya.api.OpenMaya as om

from mpylib import MNode, MTrans, MShape
from mpylib.geo import MMesh

from mpylib._base._tests.test_mshape import TestMShape


class TestMMesh(TestMShape):
    
    DG_NODE_NAME = "dg_node"
    DG_NODE_TYPE = "mesh"
    DG_GET_ATTR = None
    DG_INHERITED_TYPES = ("containerBase", "entity", "dagNode", "shape", "geometryShape",
                          "deformableShape", "controlPoint", "surfaceShape", "mesh")
    DG_MAP_ATTRS = None

    STR_REPLACE = "_node"


    def setUp(self):

        mc.file(newFile=True, force=True)

        self._dag_node = MTrans(mc.polyCube(w=1, h=1, d=1, sx=1, sy=1, sz=1, ax=(0, 1, 0), ch=False, name=self.DAG_NODE_NAME)[0])
        self._shape = self._dag_node.getShapes()[0]
        self._shape.rename(self.DG_NODE_NAME)
        self._dg_node = self._shape
        
        
    def testInit(self):
        
        mesh = MMesh(self._shape)
        
        
    def testGetVertCount(self):
        
        mesh = MMesh(self._shape)
        
        num_verts = mesh.getVertCount()
        
        self.assertEqual(num_verts, 8)
        
        
    def testGetEdgeCount(self):
        
        mesh = MMesh(self._shape)
        
        num_edges = mesh.getEdgeCount()
        
        self.assertEqual(num_edges, 12)
        
        
    def testGetPolygonCount(self):
        
        mesh = MMesh(self._shape)
        
        num_polys = mesh.getPolygonCount()
        
        self.assertEqual(num_polys, 6)
        
        
    def testGetClosestPoint(self):
        
        pnt = om.MPoint(10.0, 20.0, 30.0)
        
        closest_pnt, face_index = MMesh(self._shape).getClosestPoint(pnt)
        closest_pnt_om, face_index_om = om.MFnMesh(self._shape).getClosestPoint(pnt)
        
        self.assertSequenceEqual(closest_pnt, closest_pnt_om)
        self.assertEqual(face_index, face_index_om)
        
        
    def testGetVertsConnectedToVerts(self):

        mesh = MMesh(self._shape)        
        
        ##-----query all verts on the cube----##
        results = ((2,1,6), (0,3,7), (3,0,4), (1,2,5), (5,2,6), (3,4,7), (7,4,0), (5,6,1))
        
        verts = mesh.getVertsConnectedToVerts()
        
        self.assertEqual(len(verts), 8)
        
        for vert, con_vrts in map(None, verts, results):
            self.assertEqual(len(vert), 3)
            
            for i, j in map(None, vert, con_vrts):
                self.assertEqual(type(i), int)
                self.assertEqual(i, j)
        
        ##---query specific verts----##
        results = ((0,3,7), (3,0,4), (1,2,5))
        verts = mesh.getVertsConnectedToVerts((1, 2, 3))
        
        self.assertEqual(len(verts), 3)
        
        for vert, con_vrts in map(None, verts, results):
            self.assertEqual(len(vert), 3)
            
            for i, j in map(None, vert, con_vrts):
                self.assertEqual(type(i), int)
                self.assertEqual(i, j)
                
                
    def testGetEdgesConnectedToVerts(self):
        
        mesh = MMesh(self._shape)      
        
        ##-----query all verts on the cube----##
        results = ((10,0,4), (11,5,0), (6,4,1), (7,1,5), (8,6,2), (9,2,7), (10,8,3), (11,3,9))
        
        edges = mesh.getEdgesConnectedToVerts()
        
        self.assertEqual(len(edges), 8)
        
        for vert, con_vrts in map(None, edges, results):
            self.assertEqual(len(vert), 3)
            
            for i, j in map(None, vert, con_vrts):
                self.assertEqual(i, j)
        
        ##---query specific verts----##
        results = ((11,5,0), (6,4,1), (7,1,5))
        edges = mesh.getEdgesConnectedToVerts((1, 2, 3))
        
        self.assertEqual(len(edges), 3)
        self.assertEqual(type(edges), list)
        
        for vert, con_vrts in map(None, edges, results):
            self.assertEqual(len(vert), 3)
            
            for i, j in map(None, vert, con_vrts):
                self.assertEqual(type(i), int)
                self.assertEqual(i, j)
                
                
    def testGetFacesConnectedToVerts(self):
        
        mesh = MMesh(self._shape)       
        
        ##-----query all verts on the cube----##
        results = ((5,0,3), (3,0,4), (1,0,5), (4,0,1), (2,1,5), (4,1,2), (3,2,5), (4,2,3))
        
        faces = mesh.getFacesConnectedToVerts()
        
        self.assertEqual(len(faces), 8)
        
        for vert, con_vrts in map(None, faces, results):
            self.assertEqual(len(vert), 3)
            
            for i, j in map(None, vert, con_vrts):
                self.assertEqual(type(i), int)
                self.assertEqual(i, j)
        
        ##---query specific verts----##
        results = ((3,0,4), (1,0,5), (4,0,1))
        faces = mesh.getFacesConnectedToVerts((1, 2, 3))
        
        self.assertEqual(len(faces), 3)
        
        for vert, con_vrts in map(None, faces, results):
            self.assertEqual(len(vert), 3)
            
            for i, j in map(None, vert, con_vrts):
                self.assertEqual(type(i), int)
                self.assertEqual(i, j)
        
        
    def testGetPoints(self):
        
        results = (	(-0.5, -0.5, 0.5),
					(0.5, -0.5, 0.5),
                    (-0.5, 0.5, 0.5),
                    (0.5, 0.5, 0.5),
                    (-0.5, 0.5, -0.5),
                    (0.5, 0.5, -0.5),
                    (-0.5, -0.5, -0.5),
                    (0.5, -0.5, -0.5))
        
        trans = self._dag_node
        mesh = MMesh(self._shape)
        
        trans.xform(ws=True, translation=(1.0, 1.0, 1.0))
        
        pnts = mesh.getPoints()
        
        self.assertEqual(len(pnts), 8)
        
        for i in range(len(pnts)):
            
            for j, elm in enumerate((pnts[i][0], pnts[i][1], pnts[i][2])):
                
                self.assertEqual(elm, results[i][j])
                
        pnts = mesh.getPoints(world_space=True)
    
        self.assertEqual(len(pnts), 8)

        for i in range(len(pnts)):

            for j, elm in enumerate((pnts[i][0], pnts[i][1], pnts[i][2])):

                self.assertEqual(elm, results[i][j] + 1.0)
                
                
    def testGetVertsConnectedToFaces(self):

        mesh = MMesh(self._shape)        
        
        ##-----query all faces on the cube----##
        results = ((0, 1, 3, 2),
                   (2, 3, 5, 4),
                   (4, 5, 7, 6),
                   (6, 7, 1, 0),
                   (1, 7, 5, 3),
                   (6, 0, 2, 4))
        
        faces = mesh.getVertsConnectedToFaces()
        
        self.assertEqual(len(faces), 6)
        
        for vert, con_vrts in map(None, faces, results):
            self.assertEqual(len(vert), 4)
            
            for i, j in map(None, vert, con_vrts):
                self.assertEqual(type(i), int)
                self.assertEqual(i, j)
                
                
        ##---query specific faces----##
        results = ((2, 3, 5, 4), (4, 5, 7, 6), (6, 7, 1, 0))
        faces = mesh.getVertsConnectedToFaces((1, 2, 3))
        
        self.assertEqual(len(faces), 3)
        
        for vert, con_vrts in map(None, faces, results):
            self.assertEqual(len(vert), 4)
            
            for i, j in map(None, vert, con_vrts):
                self.assertEqual(type(i), int)
                self.assertEqual(i, j)
                
                
    def testGetVertUVIndices(self):
        
        ##---create a cube with multiple uv sets to test----##
        mc.polyCopyUV(self._shape, uvSetNameInput="map1", uvSetName="map2", createNewMap=1, ch=0)
    
        mesh = MMesh(self._shape)
    
        ##-----query all uvs on the cube----##
        results = ((0, 0, 8),
                   (9, 1, 1),
                   (2, 2, 2),
                   (3, 3, 3),
                   (4, 4, 13),
                   (11, 5, 5),
                   (6, 6, 12),
                   (10, 7, 7))
    
        uvs = mesh.getVertUVIndices(uv_set="map1")
        
        self.assertEqual(len(uvs), 8)
        
        for uv, con_uvs in map(None, uvs, results):
            self.assertEqual(len(uv), 3)
            
            for i, j in map(None, uv, con_uvs):
                self.assertEqual(type(i), int)
                self.assertEqual(i, j)
        
        ##---query specific verts----##
        results = ((9, 1, 1),
                   (2, 2, 2),
                   (3, 3, 3))
        
        uvs = mesh.getVertUVIndices((1, 2, 3), uv_set="map1")
        
        self.assertEqual(len(uvs), 3)
        
        for uv, con_uvs in map(None, uvs, results):
            self.assertEqual(len(uv), 3)
            
            for i, j in map(None, uv, con_uvs):
                self.assertEqual(type(i), int)
                self.assertEqual(i, j)
                
                
        ##---test what happens when an empty uv set is queried---##
        
        mc.polyUVSet(mesh, create=True, uvSet="map3")
        
        uvs = mesh.getVertUVIndices((1, 2, 3), uv_set="map3")
        
        self.assertEqual(len(uvs), 3)
        
        for uv in uvs:
            self.assertEqual(len(uv), 3)
            
            for i in uv:
                self.assertEqual(i, -1)
                
                
                
    def testGetNumUVSets(self):
        
        mesh = MMesh(self._shape)
        
        num_sets = mesh.getNumUVSets()
        
        self.assertEqual(num_sets, 1)
        
        mc.polyCopyUV(mesh, uvSetNameInput="map1", uvSetName="map2", createNewMap=1, ch=0)
        
        num_sets = mesh.getNumUVSets()
        
        self.assertEqual(num_sets, 2)
        
        
    def testGetUVSetNames(self):
        
        mesh = MMesh(self._shape)
        
        set_names = mesh.getUVSetNames()
        
        self.assertEqual(type(set_names), tuple)
        self.assertEqual(len(set_names), 1)
        self.assertEquals(set_names[0], "map1")
        
        mc.polyCopyUV(mesh, uvSetNameInput="map1", uvSetName="map2", createNewMap=1, ch=0)
        
        set_names = mesh.getUVSetNames()
        
        self.assertEqual(type(set_names), tuple)
        self.assertEqual(len(set_names), 2)
        self.assertEquals(set_names[0], "map1")
        self.assertEquals(set_names[1], "map2")
        
        
        
    def testGetUVCoords(self):
        
        mesh = MMesh(self._shape)
        
        u_coords, v_coords = mesh.getUVCoords()
        
        self.assertEqual(len(u_coords), 14)
        self.assertEqual(len(v_coords), 14)
        
        for coord_seq in (u_coords, v_coords):
            
            for item in coord_seq:
                self.assertEqual(type(item), float)