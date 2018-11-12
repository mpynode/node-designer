import unittest

try:
    import maya.standalone
    maya.standalone.initialize()
except:
    pass

import maya.cmds as mc
import maya.api.OpenMaya as om
from mpylib import MShape, MNode, MTrans

from test_mnode import TestMNode


class TestMShape(TestMNode):

    DAG_NODE_NAME = "dag_node"
    DAG_NODE_TYPE = "transform"
    DAG_GET_ATTR = "translateX"
    DAG_MAP_ATTRS = ("translateX", "rotateZ", "visibility")
    DAG_INHERITED_TYPES = ("containerBase", "entity", "dagNode", "transform")

    DG_NODE_NAME = "dg_node"
    DG_NODE_TYPE = "locator"
    DG_GET_ATTR = "localPositionX"
    DG_INHERITED_TYPES = ('containerBase', 'entity', 'dagNode', 'shape', 'geometryShape', 'locator')
    DG_MAP_ATTRS = ("localPositionX",)

    STR_REPLACE = "_node"


    def setUp(self):

        mc.file(newFile=True, force=True)

        self._dag_node = MTrans(mc.spaceLocator(name=self.DAG_NODE_NAME)[0])

        self._shape = MShape(mc.listRelatives(self._dag_node, shapes=True)[0])
        self._shape.rename(self.DG_NODE_NAME)
        self._dg_node = self._shape


    def testInit(self):

        shape = MShape(self._shape)
        self.assertEqual(shape.apiTypeStr, "kLocator")


    def testGetParent(self):

        par_node = self._shape.getParent()

        self.assertEqual(par_node, self._dag_node)


    def testDuplicate(self):
        
        num_nodes = len(MShape.ls())

        new_node = self._shape.duplicate()

        self.assertEqual(type(new_node), MNode)
        
        new_node = MTrans(new_node)
        new_shape = new_node.getShapes()[0]

        self.assertNotEqual(new_shape, self._shape)