import unittest
import os
import cPickle
from collections import OrderedDict

try:
    import maya.standalone
    maya.standalone.initialize()
except:
    pass

import maya.cmds as mc
import maya.api.OpenMaya as om

from mpylib import MNode, MNodeList


class TestMNode(unittest.TestCase):
    
    TEST_CLASS = MNode
    TEST_LIST_CLASS = MNodeList

    DAG_NODE_NAME = "dag_node"
    DAG_NODE_TYPE = "transform"
    DAG_GET_ATTR = "translateX"
    DAG_MAP_ATTRS = ("translateX", "rotateZ", "visibility")
    DAG_INHERITED_TYPES = ("containerBase", "entity", "dagNode", "transform")

    DG_NODE_NAME = "dg_node"
    DG_NODE_TYPE = "time"
    DG_GET_ATTR = "unwarpedTime"
    DG_INHERITED_TYPES = ("time",)
    DG_MAP_ATTRS = ("unwarpedTime",)

    STR_REPLACE = "_node"


    def setUp(self):

        mc.file(newFile=True, force=True)

        self._dag_node = self.TEST_CLASS.createNode("transform", name=self.DAG_NODE_NAME)
        self._dg_node = self.TEST_CLASS.createNode("time", name=self.DG_NODE_NAME)


    def tearDown(self):

        mc.file(newFile=True, force=True)
        
        
    def testLinkFnSets(self):
        
        for node in (self._dag_node, self._dg_node):
            
            if node:
                self.assertTrue(node._fn_set_funcs)
                for attr in node._fn_set_funcs:
                    self.assertTrue(hasattr(node, attr))
                    self.assertTrue(callable(getattr(node, attr)))
                    
        
    def testInit(self):
        
        for node in (self._dag_node, self._dg_node):
            
            m_node = self.TEST_CLASS(node)
            self.assertEqual(m_node, node)
            
            m_node = self.TEST_CLASS(node.getPath())
            self.assertEqual(m_node, node)
            
            m_node = self.TEST_CLASS(node.getMObject())
            self.assertEqual(m_node, node)
        
        self.assertRaises(RuntimeError, self.TEST_CLASS)
        
        new_node = self.TEST_CLASS(node_type="time")
        self.assertEqual(new_node.getObjectType(), "time")
        self.assertEqual(new_node.getName(), "time2")
        
        new_node = self.TEST_CLASS(node_type="time", name="new_node")
        self.assertEqual(new_node.getObjectType(), "time")
        self.assertEqual(new_node.getName(), "new_node")        


    def testCreateNode(self):

        node = self.TEST_CLASS.createNode("transform", n="transform1")
        self.assertEqual(mc.nodeType(node), "transform")
        self.assertEqual(node.getName(), "transform1")

        node = MNode.createNode("nurbsSurface", name="fooSurface1", parent="transform1")
        self.assertEqual(mc.nodeType(node), "nurbsSurface")
        self.assertEqual(node.getName(), "fooSurface1")
        self.assertEqual(mc.listRelatives(node, parent=True)[0], "transform1")

        node = MNode.createNode("camera", shared=True, n="top")
        self.assertTrue(node is None)

        # This transform will be selected when created
        node = self.TEST_CLASS.createNode("transform", n="selectedTransform")

        sel = mc.ls(sl=True)

        # This will create a new transform node, but "selectedTransform"
        # will still be selected.
        self.TEST_CLASS.createNode("transform", ss=True)

        # Create node under new namespace
        self.TEST_CLASS.createNode("transform", n="newNS:transform1")


    def testGetInheritedNodeTypes(self):

        for node, node_types in map(None, (self._dag_node, self._dg_node), (self.DAG_INHERITED_TYPES, self.DG_INHERITED_TYPES)):
            
            if node:
                result = node.getInheritedNodeTypes()
    
                self.assertEqual(type(result), tuple)
                self.assertEqual(len(result), len(node_types))
    
                for result_type, node_type in map(None, result, node_types):
    
                    self.assertEqual(type(result_type), type(node_type))
                    self.assertEqual(result_type, node_type)


    def testEquality(self):

        for node in (self._dag_node, self._dg_node):
            
            if node:
                self.assertEqual(node, node)
                self.assertTrue(node == self.TEST_CLASS(str(node)))
                
                new_node = self.TEST_CLASS.createNode(node.getObjectType(), name="new_node")
    
                self.assertNotEqual(node, new_node)
                self.assertTrue(node != MNode(str(new_node)))


    def testAddAttr(self):

        for node in (self._dag_node, self._dg_node):
            
            if node:
                
                if node:
                    node.addAttr("testAttr", "float")
        
                    self.assertTrue(node.hasAttr("testAttr"))
                    self.assertTrue(mc.attributeQuery("testAttr", node=node, exists=True))
        
                    self.assertEqual(mc.getAttr(str(node) + ".testAttr", type=True), "float")
                    self.assertEqual(node.getAttr("testAttr", type=True), "float")
        
                    ##----adding string attr----###
                    node.addAttr("testStringAttr", "string")
        
                    self.assertTrue(node.hasAttr("testStringAttr"))
                    self.assertTrue(mc.attributeQuery("testStringAttr", node=node, exists=True))
        
                    self.assertEqual(mc.getAttr(str(node) + ".testStringAttr", type=True), "string")
                    self.assertEqual(node.getAttr("testStringAttr", type=True), "string")            



    def testAttributeQuery(self):

        for node in (self._dag_node, self._dg_node):
            
            if node:
                #Determine the hidden status of the "selector" attribute on choice nodes
                self.assertFalse(node.attributeQuery("caching", hidden=True))
    
                mc.addAttr(str(node), ln="egRange", at="long", min=0, max=5, dv=2 )
                mc.setAttr(str(node) + ".egRange", e=True, keyable=False )
    
                # Determine if an attribute is keyable
                self.assertFalse(node.attributeQuery("egRange", keyable=True))
    
                # Determine the minimum and maximum values of the added attribute egRange. Result: [0.0, 5.0]
                result = node.attributeQuery("egRange", range=True)
                self.assertEqual(len(result), 2)
                self.assertEqual(result[0], 0.0)
                self.assertEqual(result[1], 5.0)
    
                # Determine if there is a minimum for the attribute.
                # Note, having a minimum or maximum value does not imply the attribute has a range.
                node.addAttr("egMin", "long", min=2)
                self.assertTrue(node.attributeQuery("egMin", minExists=True))
    
                self.assertFalse(node.attributeQuery("egMin", maxExists=True))
    
                result = node.attributeQuery("egMin", min=True) # Result: [2.0]
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0], 2.0)
    
                # Determine if an attribute is an enum
                # List the enum strings. This will use ":" as a separator like the attr is written in
                # an .ma file.
                node.addAttr("myEnum", "enum", en="chicken:turkey:duck:", ct="fowl")
    
                result = node.attributeQuery("myEnum", listEnum=True) # Result: [u"chicken:turkey:duck"] #
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0], u"chicken:turkey:duck")
    
                # Secondary way to find an attribute"s type directly
                result = node.attributeQuery("myEnum", attributeType=True) # Result: "enum" #
                self.assertEqual(result, "enum")        
    
                # See to which categories and attribute belongs
                result = node.attributeQuery("myEnum", categories=True) # Result: ["fowl"] #
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0], "fowl")


    def testAddMenuCmd(self):

        for node in (self._dag_node, self._dg_node):
            
            if node:
                node.addMenuCmd("Test Menu", "import maya.cmds as mc;mc.sphere()")


    def testAttachMenuItems(self):

        for node in (self._dag_node, self._dg_node):
            
            if node:
                node.addMenuCmd("Test Menu", "import maya.cmds as mc;mc.sphere()")


    def testDuplicate(self):

        for node in (self._dag_node, self._dg_node):
            
            if node:
                
                all_nodes = node.ls()
                num_nodes = len(all_nodes)
    
                new_node = node.duplicate()
    
                self.assertEqual(type(new_node), node.__class__)
    
                self.assertNotEqual(new_node, node)
    
                self.assertEqual(len(node.ls()), num_nodes + 1)


    def testGetMenuCmds(self):

        for node in (self._dag_node, self._dg_node):
            
            if node:
                menu_cmds = node.getMenuCmds()
    
                self.assertTrue(menu_cmds is None)
    
                node.addMenuCmd("ui_name", "cmd_str")
    
                cmds = node.getMenuCmds()
    
                self.assertEqual(type(cmds), OrderedDict)
    
                self.assertEqual(len(cmds), 1)
    
                self.assertEqual(cmds["ui_name"], "cmd_str")


    def testGetHashCode(self):

        for node in (self._dag_node, self._dg_node):

            if node:
                hash_code = node.getHashCode()
                node_hndl = node.getMObjectHandle()
    
                self.assertEqual(hash_code, node_hndl.hashCode())


    def testGetNextAttr(self):

        for node in (self._dag_node, self._dg_node):

            if node:
                node.addAttr("testAttr0", "float")
                node.addAttr("testAttr1", "float")
    
                next_attr = node.getNextAttr("testAttr")
                self.assertEqual(next_attr, "testAttr2")
    
                node.addAttr("testAttr3", "float")
                node.addAttr("testAttr4", "float")
    
                next_attr = node.getNextAttr("testAttr")
                self.assertEqual(next_attr, "testAttr2")
    
                next_attr = node.getNextAttr("testAttr", start_num=3)
                self.assertEqual(next_attr, "testAttr5")


    def testGetPath(self):

        for node in (self._dag_node, self._dg_node):
            
            if node:
                self.assertEqual(node.getPath(), str(node))


    def testGetPlugs(self):

        in_node = self.TEST_CLASS.createNode("transform")

        plugs = self._dag_node.getPlugs()

        self.assertTrue(plugs is None)

        in_node.connectAttr("tx", self._dag_node, "tz")

        plugs = self._dag_node.getPlugs()

        self.assertEqual(len(plugs), 1)
        self.assertEqual(plugs[0], "translateZ")   


    def testIsFromReferencedFile(self):

        node_names = []

        for node in (self._dag_node, self._dg_node):
            
            if node:
                self.assertFalse(node.isFromReferencedFile())
    
                node_names.append(node.getName())

        tmp_path = os.environ["TEMP"] + "/testIsFromReferencedFile.ma"
        mc.file(rename=tmp_path)
        mc.file(force=True, save=True, type="mayaAscii")

        mc.file(force=True, newFile=True)

        mc.file(tmp_path, reference=True, type="mayaAscii", mergeNamespacesOnClash=False, namespace="test", options="v=1")

        for node_name in node_names:

            node = MNode("test:" + node_name)

            self.assertTrue(node.isFromReferencedFile())

        os.remove(tmp_path)


    def testLs(self):

        nodes = self.TEST_CLASS.ls()

        self.assertEqual(type(nodes), self.TEST_LIST_CLASS)
        self.assertEqual(len(nodes), len(mc.ls()))

        nodes = self.TEST_CLASS.ls("*_node")
        self.assertEqual(len(nodes), 2)

        self.assertTrue(self._dag_node in nodes)
        self.assertTrue(self._dg_node in nodes)


    def testRemoveInputConnections(self):

        in_node = self.TEST_CLASS.createNode("transform")

        in_node.connectAttr("tx", self._dag_node, "tz")
        self._dag_node.connectAttr("tz", in_node, "sx")
        
        nodes, plugs = self._dag_node.listConnections("tz")
        self.assertEqual(len(nodes), 2)        

        nodes, plugs = self._dag_node.listConnections("tz", source=True, destination=False)
        self.assertEqual(len(nodes), 1)

        self._dag_node.removeInputConnections("tz")

        nodes, plugs = self._dag_node.listConnections("tz", source=True, destination=False)
        self.assertTrue(nodes is None)
        
        nodes, plugs = self._dag_node.listConnections("tz", source=False, destination=True)
        self.assertEqual(len(nodes), 1)        

        ##----array attrs----##
        self._dag_node.addAttr("testArray", "float", multi=True)
        in_node.connectAttr("tz", self._dag_node, "testArray[0]")
        nodes, plugs = self._dag_node.listConnections("testArray", source=True, destination=False)
        self.assertFalse(nodes is None)
        
        self._dag_node.removeInputConnections("testArray")

        nodes, plugs = self._dag_node.listConnections("testArray", source=True, destination=False)
        self.assertTrue(nodes is None)
        
        in_node.addAttr("testArray", "float", multi=True)
        in_node.connectAttr("testArray", self._dag_node, "testArray")
        nodes, plugs = self._dag_node.listConnections("testArray", source=True, destination=False)
        self.assertFalse(nodes is None)
        
        self._dag_node.removeInputConnections("testArray")
        nodes, plugs = self._dag_node.listConnections("testArray", source=True, destination=False)
        self.assertTrue(nodes is None)
        
        
    def testRemoveOutputConnections(self):

        out_node = self.TEST_CLASS.createNode("transform")
        
        self._dag_node.connectAttr("tz", out_node, "sx")
        out_node.connectAttr("tx", self._dag_node, "tz")
        
        nodes, plugs = self._dag_node.listConnections("tz")
        self.assertEqual(len(nodes), 2)        
    
        nodes, plugs = self._dag_node.listConnections("tz", source=False, destination=True)
        self.assertEqual(len(nodes), 1)
    
        self._dag_node.removeOutputConnections("tz")
    
        nodes, plugs = self._dag_node.listConnections("tz", source=False, destination=True)
        self.assertTrue(nodes is None)
    
        nodes, plugs = self._dag_node.listConnections("tz", source=True, destination=False)
        self.assertEqual(len(nodes), 1)        
    
        ##----array attrs----##
        self._dag_node.addAttr("testArray", "float", multi=True)
        self._dag_node.connectAttr("testArray[0]", out_node, "tz")
        nodes, plugs = self._dag_node.listConnections("testArray", source=False, destination=True)
        self.assertFalse(nodes is None)
    
        self._dag_node.removeOutputConnections("testArray")
        nodes, plugs = self._dag_node.listConnections("testArray", source=False, destination=True)
        self.assertTrue(nodes is None)
    
        out_node.addAttr("testArray", "float", multi=True)
        self._dag_node.connectAttr("testArray", out_node, "testArray")
        nodes, plugs = self._dag_node.listConnections("testArray", source=False, destination=True)
        self.assertFalse(nodes is None)
    
        self._dag_node.removeOutputConnections("testArray")
        nodes, plugs = self._dag_node.listConnections("testArray", source=False, destination=True)
        self.assertTrue(nodes is None)
        
        self._dag_node.connectAttr("testArray[0]", out_node, "tz")
        nodes, plugs = self._dag_node.listConnections("testArray[0]", source=False, destination=True)
        self.assertFalse(nodes is None)
        
        self._dag_node.removeOutputConnections("testArray[0]")
        nodes, plugs = self._dag_node.listConnections("testArray[0]", source=False, destination=True)
        self.assertTrue(nodes is None)        
        

    def testSetAttrsFromMap(self):

        attr_map = {"tx":1.0, "ry":2.0, "sz":3.0, "foo":1000.0}

        self._dag_node.setAttrsFromMap(attr_map)

        for attr, val in attr_map.items():

            if self._dag_node.hasAttr(attr):

                self.assertEqual(self._dag_node.getAttr(attr), val)

        self.assertRaises(RuntimeError, self._dag_node.setAttrsFromMap, attr_map, skip_missing=False)


    def testSetDrivenKeyframe(self):

        driver = self.TEST_CLASS.createNode("transform")

        self._dag_node.setDrivenKeyframe("tz", driver, "tx")
        self._dag_node.setDrivenKeyframe("tz", driver, "tx", value=10.0, driverValue=20.0)

        driver.setAttr("tx", 0.0)
        self.assertEqual(self._dag_node.getAttr("tz"), 0.0)

        driver.setAttr("tx", 20.0)
        self.assertEqual(self._dag_node.getAttr("tz"), 10.0)        


    def testBakeResults(self):

        for node, attr in map(None, (self._dag_node, self._dg_node), (self.DAG_GET_ATTR, self.DG_GET_ATTR)):
            
            if node and (attr is not None):
                
                in_nodes, plugs = node.listConnections(attr, source=True, destination=False, plugs=True)
                self.assertTrue(in_nodes is None)
                self.assertTrue(plugs is None)
    
                node.bakeResults(attr, simulation=True, t=(5,44), sb=2)
    
                in_nodes, plugs = node.listConnections(attr, source=True, destination=False, plugs=True)
    
                self.assertEqual(len(in_nodes), 1)
                self.assertTrue(in_nodes[0].getObjectType().startswith("animCurve"))


    def testConnectAttr(self):

        dag_b = self.TEST_CLASS.createNode("transform", name="dag_node_b")

        for node, attr in map(None, (self._dag_node, self._dg_node), (self.DAG_GET_ATTR, self.DG_GET_ATTR)):
            
            if node and (attr is not None):
                
                cons = mc.listConnections(node + "." + attr, destination=True, plugs=True, skipConversionNodes=True)
                self.assertTrue(cons is None)
    
                dag_b.connectAttr("tx", node, attr)
                cons = mc.listConnections(node + "." + attr, destination=True, plugs=True, skipConversionNodes=True)
    
                self.assertEqual(len(cons), 1)
                self.assertEqual(cons[0], "dag_node_b.translateX")


    def testDelete(self):

        for node in (self._dg_node, self._dag_node):

            if node:
                node_name = str(node)
    
                self.assertTrue(mc.objExists(node))
                self.assertTrue(node.isValid())
    
                node.delete()
    
                self.assertFalse(node) #deleted object has __nonzero__ of False
                self.assertFalse(node.isValid())
                self.assertRaises(RuntimeError, node.getAttr, "caching")
                self.assertFalse(mc.objExists(node_name))


    def testDeleteAttr(self):

        self.testAddAttr()

        for node in (self._dag_node, self._dg_node):
            
            if node:
                
                self.assertTrue(node.hasAttr("testAttr"))
    
                node.deleteAttr("testAttr")
    
                self.assertFalse(node.hasAttr("testAttr"))


    def testGetAttr(self):

        attrs = (self.DAG_GET_ATTR, self.DG_GET_ATTR)
        vals = (0.0, 0.0)

        for i, node in enumerate((self._dag_node, self._dg_node)):
            
            if node and (attrs[i] is not None):
                mc.setAttr(node + "." + attrs[i], vals[i])
    
                result = node.getAttr(attrs[i])
    
                self.assertEqual(result, vals[i])
            
            
    def testGetAddAttrMaps(self):
        
        attrs = ({"attr_type":"float", "long_name":"floatAttr", "shortName":"fltAttr"},)
        
        for node in (self._dag_node, self._dg_node):
            
            if node:
                for attr_map in attrs:
                    node.addAttr(**attr_map)
            
                test_attrs = node.getAddAttrMaps()
                self.assertEqual(type(test_attrs), tuple)
                
                for i, attr_map in enumerate(attrs):
                    for key, val in attr_map.items():
                        self.assertEqual(test_attrs[i][key], val)


    def testGetAttrMap(self):

        node_attrs = (self.DAG_MAP_ATTRS, self.DG_MAP_ATTRS)

        for i, node in enumerate((self._dag_node, self._dg_node)):
            
            if node and (node_attrs[i] is not None):
                attr_map = node.getAttrMap(skip_multi=True, keyable=True)
    
                attrs = mc.listAttr(node, keyable=True)
    
                if attrs:
                    self.assertEqual(type(attr_map), OrderedDict)
    
                    for attr in attr_map.keys():
    
                        self.assertTrue(attr in attrs)
    
                        attr_val = mc.getAttr(node + "." + attr)
                        self.assertEqual(attr_map[attr], attr_val)            
    
                else:
                    self.assertTrue(attr_map is None)
    
                attr_map = node.getAttrMap(*node_attrs[i])
                self.assertEqual(len(attr_map), len(node_attrs[i]))
    
                for attr in node_attrs[i]:
                    self.assertEqual(attr_map[attr], node.getAttr(attr))

        attr_map = self._dag_node.getAttrMap("translate?")
        self.assertEqual(len(attr_map), 3)
        attrs = ("translateX", "translateY", "translateZ")

        for attr in attr_map.keys():
            self.assertTrue(attr in attrs)

            attr_val = mc.getAttr(self._dag_node + "." + attr)
            self.assertEqual(attr_map[attr], attr_val)

        attr_map = self._dag_node.getAttrMap(skip_multi=True, scalar=True)


    def testAddMarkingMenuCmd(self):

        self.testGetMarkingMenuCmds()


    def testGetMarkingMenuCmds(self):

        for node in (self._dag_node, self._dg_node):
            
            if node:
                node.addMenuCmd("myLs", "import maya.cmds; maya.cmds.ls()")
                node.addMenuCmd("mySphere", "import maya.cmds; maya.cmds.sphere()")
    
                cmds = node.getMenuCmds()
    
                self.assertEqual(type(cmds), OrderedDict)
    
                self.assertEqual(cmds["myLs"], "import maya.cmds; maya.cmds.ls()")
                self.assertEqual(cmds["mySphere"], "import maya.cmds; maya.cmds.sphere()")


    def testGetMessageAttr(self):

        src_node = self.TEST_CLASS.createNode("transform")

        for node in (self._dag_node, self._dg_node):

            if node:
                node.setMessageAttr("testMsg", src_node)
    
                result = node.getMessageAttr("testMsg")
    
                self.assertTrue(result, src_node)


    def testGetMObject(self):

        for node in (self._dag_node, self._dg_node):

            if node:
                obj = node.getMObject()
    
                self.assertIsInstance(obj, om.MObject)


    def testGetMObjectHandle(self):

        for node in (self._dag_node, self._dg_node):

            if node:
                obj_hndl = node.getMObjectHandle()
    
                self.assertIsInstance(obj_hndl, om.MObjectHandle)


    def testGetNamespace(self):

        mc.namespace(add="test")
        mc.namespace(add="test:test1")      

        for node in (self._dag_node, self._dg_node):

            if node:
                namespace = node.getNamespace()
                self.assertTrue(namespace is None)
    
                node.rename("test:" + node.getBasename())
    
                namespace = node.getNamespace()
                self.assertEqual(namespace, ":test")
    
                node.rename("test:test1:" + node.getBasename())
                namespace = node.getNamespace()
                self.assertEqual(namespace, ":test:test1")  


    def testHash(self):

        dag_obj = self._dag_node
        dg_obj = self._dg_node

        test_dict = {}
        test_dict[dag_obj] = 0
        test_dict[dg_obj] = 1

        self.assertEqual(test_dict[dag_obj], 0)
        self.assertEqual(test_dict[dg_obj], 1)


    def testGetName(self):

        mc.namespace(add="test")
        mc.namespace(add="test:test1")

        basenames = (self.DAG_NODE_NAME, self.DG_NODE_NAME)

        for i, node in enumerate((self._dag_node, self._dg_node)):

            if node:
                name = node.getName()
                self.assertEqual(name, basenames[i])
    
                node.rename("test:" + basenames[i])
                name = node.getName()
                self.assertEqual(name, "test:" + basenames[i])


    def testGetBasename(self):

        mc.namespace(add="test")
        mc.namespace(add="test:test1")

        basenames = (self.DAG_NODE_NAME, self.DG_NODE_NAME)

        for i, node in enumerate((self._dag_node, self._dg_node)):
            
            if node:
                basename = node.getBasename()
                self.assertEqual(basename, basenames[i])
    
                node.rename("test:" + basenames[i])
                name = node.getName()
                self.assertEqual(name, "test:" + basenames[i])            
    
                basename = node.getBasename()
                self.assertEqual(basename, basenames[i])


    def testHasAttr(self):

        for node, attr in map(None, (self._dag_node, self._dg_node), (self.DAG_GET_ATTR, self.DG_GET_ATTR)):
            
            if node and (attr is not None):
                self.assertTrue(node.hasAttr(attr))
                self.assertFalse(node.hasAttr("fakeAttr"))


    def testHasUniqueName(self):

        node_a = self.TEST_CLASS(mc.createNode("transform", name="node_a"))

        mc.parent(self._dag_node, node_a)

        self.assertTrue(self._dag_node.hasUniqueName())

        node_b = self.TEST_CLASS(mc.createNode("transform", name=self.DAG_NODE_NAME))

        self.assertFalse(node_b.hasUniqueName())


    def testIsValid(self):

        for i, node in enumerate((self._dg_node, self._dag_node)):
            
            if node:
                self.assertTrue(node.isValid())
    
                node.delete()
    
                self.assertFalse(node.isValid())


    def testIsLocked(self):

        for node in (self._dag_node, self._dg_node):

            if node:
                self.assertFalse(node.isLocked())
    
                mc.lockNode(node, lock=True)
    
                self.assertTrue(node.isLocked())


    def testGetPluginName(self):

        for node in (self._dag_node, self._dg_node):

            if node:
                plug_name = node.getPluginName()
    
                self.assertTrue(plug_name is None)


    def testListAttr(self):

        for node in (self._dag_node, self._dg_node):

            if node:
                all_attrs = node.listAttr()
                mc_attrs = mc.listAttr(node)
    
                self.assertEqual(len(all_attrs), len(mc_attrs))
    
                for attr_a, attr_b in map(None, all_attrs, mc_attrs):
                    self.assertEqual(attr_a, attr_b)

        trans_attrs = self._dag_node.listAttr("translate*")

        self.assertEqual(len(trans_attrs), 4)

        for axis in ("X", "Y", "Z"):
            self.assertTrue("translate" + axis in trans_attrs)


    def testListConnections(self):

        dag_b = self.TEST_CLASS.createNode("transform", name="dag_node_b")

        for node, attr in map(None, (self._dag_node, self._dg_node), (self.DAG_GET_ATTR, self.DG_GET_ATTR)):
            
            if node:
                if attr is not None:
                    nodes, plugs = node.listConnections(attr)
        
                    self.assertTrue(nodes is None)
                    self.assertTrue(plugs is None)
        
                    dag_b.connectAttr("tx", node, attr)
                    nodes, plugs = node.listConnections(attr, destination=True, skipConversionNodes=True)
        
                    self.assertEqual(type(nodes), MNodeList)
                    self.assertEqual(len(nodes), 1)
                    self.assertEqual(nodes[0], dag_b)
                    self.assertTrue(plugs is None)
        
                    nodes, plugs = node.listConnections(attr, destination=True, plugs=True, skipConversionNodes=True)
                    self.assertEqual(type(nodes), MNodeList)
                    self.assertEqual(len(nodes), 1)
                    self.assertEqual(nodes[0], dag_b)
                    self.assertEqual(type(plugs), tuple)
                    self.assertEqual(len(plugs), 1)
                    self.assertEqual(plugs[0], "translateX")


    def testGetObjectType(self):

        for node, node_type in map(None, (self._dag_node, self._dg_node), (self.DAG_NODE_TYPE, self.DG_NODE_TYPE)):

            if node:
                self.assertEqual(node.getObjectType(), node_type)


    def testRename(self):

        mc.namespace(add="test")
        mc.namespace(add="test:test1")      

        for node, basename in map(None, (self._dag_node, self._dg_node), (self.DAG_NODE_NAME, self.DG_NODE_NAME)):

            if node:
                name = node.getName()
                self.assertEqual(name, basename)
    
                node.rename("fooo")
                name = node.getName()
                self.assertEqual(name, "fooo")
    
                node.rename("test:" + basename)
    
                name = node.getName()
                self.assertEqual(name, "test:" + basename)


    def testSelect(self):

        for node in (self._dag_node, self._dg_node):
            
            if node:
                new_node = self.TEST_CLASS.createNode(node.getObjectType(), name="new_node")
                mc.select(clear=True)
        
                sel = mc.ls(sl=True, long=True)
                self.assertEqual(len(sel), 0)
        
                node.select()        
        
                sel = mc.ls(sl=True, long=True)
                self.assertEqual(len(sel), 1)
        
                self.assertEqual(node, sel[0])
                
                ## test add flag##
                new_node.select(add=True)
        
                sel = mc.ls(sl=True, long=True)
                self.assertEqual(len(sel), 2)
                self.assertEqual(node, sel[0])
                self.assertEqual(new_node, sel[1])
        
                ## test deselect flag ##
                node.select(deselect=True)
                sel = mc.ls(sl=True, long=True)
                self.assertEqual(len(sel), 1)
                self.assertEqual(new_node, sel[0])


    def testSetAttr(self):

        val = 1234.5

        for node, attr in map(None, (self._dag_node, self._dg_node), (self.DAG_GET_ATTR, self.DG_GET_ATTR)):
            
            if node and (attr is not None):
                node.setAttr(attr, val)
    
                result = mc.getAttr(node + "." + attr)
    
                self.assertEqual(result, val)


    def testSetMessageAttr(self):

        src_node = self.TEST_CLASS.createNode("transform")

        for node in (self._dag_node, self._dg_node):

            if node:
                attr = "testMsg"
    
                self.assertFalse(mc.attributeQuery(attr, node=node, exists=True))
    
                node.setMessageAttr(attr, src_node)
    
                self.assertTrue(mc.attributeQuery(attr, node=node, exists=True))
    
                self.assertEqual(mc.getAttr(node + "." + attr, type=True), "message")
                self.assertEqual(node.getAttr(attr, type=True), "message")
    
                self.assertEqual(node.getMessageAttr(attr), src_node)


    def testSetStringAttr(self):

        attr = "testStringAttr"
        val = "string val"

        for node in (self._dag_node, self._dg_node):

            if node:
                self.assertFalse(mc.attributeQuery(attr, node=node, exists=True))
    
                node.setStringAttr(attr, val)
    
                self.assertTrue(mc.attributeQuery(attr, node=node, exists=True))
    
                result = node.getAttr(attr)
    
                self.assertEqual(val, result)


    def testApplyAttrMap(self):

        attr_map = {"translateX":100.0, "visibility":False}

        for attr, val in attr_map.items():

            self.assertNotEqual(self._dag_node.getAttr(attr), val)

        self._dag_node.applyAttrMap(attr_map)

        for attr, val in attr_map.items():

            self.assertEqual(self._dag_node.getAttr(attr), val)  

        attr_map["fakeAttr"] = 500.0

        self.assertRaises(RuntimeError, self._dag_node.applyAttrMap, attr_map)

        self._dag_node.applyAttrMap(attr_map, skip_missing=True)



    def testGetSetAttrCmds(self):

        node = self._dag_node

        node.setAttr("tx", 100.0)

        self.assertTrue(node.getSetAttrCmds("ty") is None)

        result = node.getSetAttrCmds("ty", non_defaults_only=False)

        self.assertEqual(type(result), tuple)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], u'\tsetAttr ".ty" 0;')

        result = node.getSetAttrCmds("tx")

        self.assertEqual(type(result), tuple)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], u'\tsetAttr ".tx" 100;')
        
        node.addAttr("testStringAttr", "string")
        node.setAttr("testStringAttr", "test", type="string")
        
        result = node.getSetAttrCmds("testStringAttr")
        
        self.assertEqual(result[0], u"\tsetAttr \".testStringAttr\" -type \"string\" \"test\";")

##-----------------------------------string operations below this line--------------------------------------------##
    
    
    def testReduce(self):
        
        pass
        
        #test_attr_map = {"testAttr_1":"float", "testAttr_2":"string"}
        
        #for node_name in (self._dag_node.getName(), self._dg_node.getName()):
            
            #self.setUp()
            #node = self.TEST_CLASS(node_name)
            #node_type = node.getObjectType()
            
            #for attr_name, attr_type in test_attr_map.items():
                #node.addAttr(attr_name, attr_type)
            
            #node_str = cPickle.dumps(node)
            
            #mc.file(newFile=True, force=True)
            
            #new_node = cPickle.loads(node_str)
            
            #self.assertEqual(new_node.getName(), node_name)
            #self.assertEqual(new_node.getObjectType(), node_type)
            
            #for attr_name, attr_type in test_attr_map.items():
                #self.assertTrue(new_node.hasAttr(attr_name))          
            

    def testAdd(self):

        mc.namespace(add="test")

        for node in (self._dag_node, self._dg_node):
            
            if node:
                
                node_str = node + "_string"
                self.assertEqual(node_str, node.getName() + "_string")
                
                new_node = MNode.createNode("transform", name="new_node")
                node_str = node + new_node
                self.assertEqual(node_str, node.getName() + new_node.getName())
    
                node.rename("test:" + node.getName())
                node_str = node + "_string"
                self.assertEqual(node_str, node.getName() + "_string")
                
                
    def testRAdd(self):

        mc.namespace(add="test")

        for node in (self._dag_node, self._dg_node):
            
            if node:
                
                node_str = "string_" + node
                self.assertEqual(node_str, "string_" + node.getName())
                
                new_node = MNode.createNode("transform", name="new_node")
                node_str = new_node + node 
                self.assertEqual(node_str, new_node.getName() + node.getName())
    
                node.rename("test:" + node.getName())
                node_str = "string_" + node
                self.assertEqual(node_str, "string_" + node.getName())    
                
                
    def testCount(self):

        mc.namespace(add="test")

        for node in (self._dag_node, self._dg_node):
            
            if node:
                name_count = node.count(self.STR_REPLACE) #count number of sub-string '_node'
    
                self.assertEqual(name_count, node.getName().count(self.STR_REPLACE))
    
                node.rename(node.getName() + "_foo_poo_foo_foo")
    
                name_count = node.count("_foo")
                self.assertEqual(name_count, node.getName().count("_foo"))
    
                node.rename("test:" + node.getName())
    
                name_count = node.count(":", include_namespaces=True)
    
                self.assertEqual(name_count, node.getName().count(":"))
    
                new_name = node.count(":", include_namespaces=False)
                self.assertEqual(new_name, node.getBasename().count(":"))


    def testFind(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):
            if node:
                self.assertEqual(node.find("_"), node.getBasename().find("_"))
    
                node.rename("test_ns:" + node.getName())
    
                self.assertEqual(node.find("_"), node.getBasename().find("_"))
    
                self.assertEqual(node.find("_", include_namespaces=True), node.getName().find("_"))


    def testIndex(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):
            
            if node:
                self.assertEqual(node.index("_"), node.getBasename().index("_"))
    
                node.rename("test_ns:" + node.getName())
    
                self.assertEqual(node.index("_"), node.getBasename().index("_"))
    
                self.assertEqual(node.index("_", include_namespaces=True), node.getName().index("_"))


    def testIsalnum(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):
            
            if node:
                include_namespaces = False
                orig_name = node.getBasename()
    
                for i in xrange(2):
    
                    if i == 1:
                        node.rename("test_ns:" + orig_name)
                        include_namespaces = True
    
                    self.assertFalse(node.isalnum(include_namespaces=include_namespaces))
    
                    node.rename(node.replace("_", ""))
    
                    self.assertTrue(node.isalnum(include_namespaces=include_namespaces))
    
                    node.rename(node.getName() + "1")
    
                    self.assertTrue(node.isalnum(include_namespaces=include_namespaces))


    def testIsalpha(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):

            if node:
                include_namespaces = False
                orig_name = node.getBasename()
    
                for i in xrange(2):
    
                    if i == 1:
                        node.rename("test_ns:" + orig_name)
                        include_namespaces = True            
    
                    self.assertFalse(node.isalpha(include_namespaces=include_namespaces))
    
                    node.rename(node.replace("_", ""))
    
                    self.assertTrue(node.isalpha(include_namespaces=include_namespaces))
    
                    node.rename(node.getName() + "1")
    
                    self.assertFalse(node.isalpha(include_namespaces=include_namespaces))


    def testIslower(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):

            if node:
                include_namespaces = False
                orig_name = node.getBasename()
    
                for i in xrange(2):
    
                    if i == 1:
                        node.rename("test_ns:" + orig_name)
                        include_namespaces = True             
    
                    self.assertTrue(node.islower(include_namespaces=include_namespaces))
    
                    if i == 1:
                        node.rename("test_ns:D" + node.getBasename()[1:])
    
                    else:
                        node.rename("D" + node.getName()[1:])
    
                    self.assertFalse(node.islower(include_namespaces=include_namespaces))


    def testIstitle(self):

        mc.namespace(add="test_ns")
        mc.namespace(add="Testns")

        for node in (self._dag_node, self._dg_node):

            if node:
                include_namespaces = False
                orig_name = node.getBasename()
    
                for i in xrange(2):
    
                    if i == 1:
                        node.rename("test_ns:" + orig_name)
                        include_namespaces = True              
    
                    self.assertFalse(node.istitle(include_namespaces=include_namespaces))
    
                    node.rename(node.replace("_", ""))
    
                    self.assertFalse(node.istitle(include_namespaces=include_namespaces))
    
                    if i == 1:
                        node.rename("Testns:" + node.getBasename())
    
                    else:
                        node.rename("D" + node.getName()[1:])
    
                    self.assertTrue(node.istitle(include_namespaces=include_namespaces))        


    def testIsupper(self):

        mc.namespace(add="test_ns")
        mc.namespace(add="TEST_NS")

        for node in (self._dag_node, self._dg_node):

            if node:
                include_namespaces = False
                orig_name = node.getBasename()
    
                for i in xrange(2):
    
                    if i == 1:
                        node.rename("test_ns:" + orig_name)
                        include_namespaces = True               
    
                    self.assertFalse(node.isupper(include_namespaces=include_namespaces))
    
                    if i == 1:
                        node.rename("TEST_NS:" + node.upper())
    
                    else:
                        node.rename(node.upper())
    
                    self.assertTrue(node.isupper(include_namespaces=include_namespaces))    


    def testJoin(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):

            if node:
                include_namespaces = False
    
                for i in xrange(2):
    
                    result = node.getBasename().join(("1", "2", "3"))
    
                    if i == 1:
                        node.rename("test_ns:" + node.getBasename())
                        include_namespaces = True
    
                        result = node.getName().join(("1", "2", "3"))
    
                    self.assertEqual(node.join(("1", "2", "3"), include_namespaces=include_namespaces), result)


    def testLower(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):

            if node:
                include_namespaces = False
    
                for i in xrange(2):
    
                    result = node.getBasename().lower()
    
                    if i == 1:
                        node.rename("test_ns:" + node.getBasename())
                        include_namespaces = True
    
                        result = node.getName().lower()
    
                    self.assertEqual(node.lower(include_namespaces=include_namespaces), result)        


    def testLstrip(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):

            if node:
                include_namespaces = False
    
                for i in xrange(2):
    
                    result = node.getBasename().lstrip("de")
    
                    if i == 1:
                        node.rename("test_ns:" + node.getBasename())
                        include_namespaces = True
    
                        result = node.getName().lstrip("te")
    
                        self.assertEqual(node.lstrip("te", include_namespaces=include_namespaces), result)
    
                    else:
                        self.assertEqual(node.lstrip("de", include_namespaces=include_namespaces), result)           


    def testPartition(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):

            if node:
                include_namespaces = False
    
                for i in xrange(2):
    
                    result = node.getBasename().partition("_")
    
                    if i == 1:
                        node.rename("test_ns:" + node.getBasename())
                        include_namespaces = True
    
                        result = node.getName().partition("_")
    
                    self.assertEqual(node.partition("_", include_namespaces=include_namespaces), result)


    def testRfind(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):

            if node:
                self.assertEqual(node.rfind("_"), node.getBasename().rfind("_"))
    
                node.rename("test_ns:" + node.getName())
    
                self.assertEqual(node.rfind("_"), node.getBasename().rfind("_"))
    
                self.assertEqual(node.rfind("_", include_namespaces=True), node.getName().rfind("_"))        


    def testRindex(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):

            if node:
                self.assertEqual(node.rindex("_"), node.getBasename().rindex("_"))
    
                node.rename("test_ns:" + node.getName())
    
                self.assertEqual(node.rindex("_"), node.getBasename().rindex("_"))
    
                self.assertEqual(node.rindex("_", include_namespaces=True), node.getName().rindex("_"))        


    def testRpartition(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):

            if node:
                include_namespaces = False
    
                for i in xrange(2):
    
                    result = node.getBasename().rpartition("_")
    
                    if i == 1:
                        node.rename("test_ns:" + node.getBasename())
                        include_namespaces = True
    
                        result = node.getName().rpartition("_")
    
                    self.assertEqual(node.rpartition("_", include_namespaces=include_namespaces), result)        


    def testRsplit(self):

        mc.namespace(add="test")

        for node in (self._dag_node, self._dg_node):

            if node:
                node.rename(node.getBasename() + "_node")
    
                self.assertSequenceEqual(node.rsplit("_"), node.getBasename().rsplit("_"))
    
                node.rename("test:" + node.getBasename())
    
                self.assertSequenceEqual(node.rsplit("_"), node.getBasename().rsplit("_"))
                self.assertSequenceEqual(node.rsplit("_", include_namespaces=True), node.getName().rsplit("_"))
    
                self.assertSequenceEqual(node.rsplit("_", 1), node.getBasename().rsplit("_", 1))
                self.assertSequenceEqual(node.rsplit("_", 1, include_namespaces=True), node.getName().rsplit("_", 1))        


    def testRstrip(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):

            if node:
                include_namespaces = False
    
                for i in xrange(2):
    
                    result = node.getBasename().rstrip("de")
    
                    if i == 1:
                        node.rename("test_ns:" + node.getBasename())
                        include_namespaces = True
    
                        result = node.getName().rstrip("te")
    
                        self.assertEqual(node.rstrip("te", include_namespaces=include_namespaces), result)
    
                    else:
                        self.assertEqual(node.rstrip("de", include_namespaces=include_namespaces), result)      


    def testStrip(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):

            if node:
                include_namespaces = False
    
                for i in xrange(2):
    
                    result = node.getBasename().strip("de")
    
                    if i == 1:
                        node.rename("test_ns:" + node.getBasename())
                        include_namespaces = True
    
                        result = node.getName().strip("te")
    
                        self.assertEqual(node.strip("te", include_namespaces=include_namespaces), result)
    
                    else:
                        self.assertEqual(node.strip("de", include_namespaces=include_namespaces), result)


    def testSwapcase(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):

            if node:
                include_namespaces = False
    
                for i in xrange(2):
    
                    result = node.getBasename().swapcase()
    
                    if i == 1:
                        node.rename("test_ns:" + node.getBasename())
                        include_namespaces = True
    
                        result = node.getName().swapcase()
    
                    self.assertEqual(node.swapcase(include_namespaces=include_namespaces), result)             


    def testUpper(self):

        mc.namespace(add="test_ns")

        for node in (self._dag_node, self._dg_node):

            if node:
                include_namespaces = False
    
                for i in xrange(2):
    
                    result = node.getBasename().upper()
    
                    if i == 1:
                        node.rename("test_ns:" + node.getBasename())
                        include_namespaces = True
    
                        result = node.getName().upper()
    
                    self.assertEqual(node.upper(include_namespaces=include_namespaces), result)           


    def testReplace(self):

        mc.namespace(add="test")

        for node in (self._dag_node, self._dg_node):

            if node:
                new_name = node.replace(self.STR_REPLACE, "_name")
    
                self.assertEqual(new_name, node.getName().replace(self.STR_REPLACE, "_name"))
    
                node.rename(node.getName() + "_foo_poo_foo_foo")
    
                new_name = node.replace("_foo", "_poo", 2)
                self.assertEqual(new_name, node.getName().replace("_foo", "_poo", 2))
    
                node.rename("test:" + node.getName())
    
                new_name = node.replace(self.STR_REPLACE, "_name", include_namespaces=True)
    
                self.assertEqual(new_name, node.getName().replace(self.STR_REPLACE, "_name"))
    
                new_name = node.replace(self.STR_REPLACE, "_name", include_namespaces=False)
                self.assertEqual(new_name, node.getBasename().replace(self.STR_REPLACE, "_name"))


    def testCapitalize(self):

        mc.namespace(add="test")

        for node in (self._dag_node, self._dg_node):

            if node:
                new_name = node.capitalize()
    
                self.assertEqual(new_name, node.getBasename().capitalize())
    
                node.rename("test:" + node.getName())
    
                new_name = node.capitalize()
    
                self.assertEqual(new_name, node.getBasename().capitalize())
    
                new_name = node.capitalize(include_namespaces=True)
    
                self.assertEqual(new_name, "Test:" + node.getBasename().lower())


    def testStartswith(self):

        mc.namespace(add="test")

        for node in (self._dag_node, self._dg_node):

            if node:
                node.rename("test_" + node.getBasename())
    
                self.assertTrue(node.startswith("test_"))
                self.assertFalse(node.startswith("_node"))
    
                node.rename("test:" + node.getBasename())
    
                self.assertTrue(node.startswith("test_"))
                self.assertFalse(node.startswith("test:"))
                self.assertTrue(node.startswith("test:", include_namespaces=True))
    
                self.assertTrue(node.startswith("test_", 0, 5))
                self.assertFalse(node.startswith("test_", 1, 3))


    def testEndswith(self):

        mc.namespace(add="test")

        for node in (self._dag_node, self._dg_node):
            
            if node:
                node.rename(node.getBasename() + "_node")
    
                self.assertTrue(node.endswith("_node"))
                self.assertFalse(node.endswith("test_"))
    
                node.rename("test:" + node.getBasename())
    
                self.assertTrue(node.endswith("_node"))
                self.assertFalse(node.endswith(":" + node.getBasename()))
                self.assertTrue(node.endswith("t:" + node.getBasename(), include_namespaces=True))
    
                self.assertTrue(node.endswith("_node", 4))
                self.assertFalse(node.endswith("_node", 4, 7))


    def testSplit(self):

        mc.namespace(add="test")

        for node in (self._dag_node, self._dg_node):

            if node:
                node.rename(node.getBasename() + "_node")
    
                self.assertSequenceEqual(node.split("_"), node.getBasename().split("_"))
    
                node.rename("test:" + node.getBasename())
    
                self.assertSequenceEqual(node.split("_"), node.getBasename().split("_"))
                self.assertSequenceEqual(node.split("_", include_namespaces=True), node.getName().split("_"))
    
                self.assertSequenceEqual(node.split("_", 1), node.getBasename().split("_", 1))
                self.assertSequenceEqual(node.split("_", 1, include_namespaces=True), node.getName().split("_", 1))


class TestMNodeList(unittest.TestCase):
    
    TEST_CLASS = MNode
    TEST_LIST_CLASS = MNodeList
    

    def setUp(self):

        mc.file(newFile=True, force=True)

        self._dag_node = self.TEST_CLASS.createNode("transform", name="dag_node")
        self._dg_node = self.TEST_CLASS.createNode("time", name="dg_node")


    def tearDown(self):

        mc.file(newFile=True, force=True)    


    def testInit(self):

        node_list = self.TEST_LIST_CLASS()
        self.assertEqual(len(node_list), 0)

        node_list = self.TEST_LIST_CLASS((self._dag_node,))
        self.assertEqual(len(node_list), 1)

        node_list.append(self._dg_node)
        self.assertEqual(len(node_list), 2)

        self.assertEqual(node_list[0], self._dag_node)
        self.assertEqual(node_list[1], self._dg_node)

        node_a = self.TEST_CLASS.createNode("transform")
        node_b = self.TEST_CLASS.createNode("transform")

        node_list.extend((node_a, node_b))
        self.assertEqual(len(node_list), 4)

        self.assertTrue(node_a in node_list)

        iter_obj = iter(node_list)

        for i, item in enumerate(iter_obj):
            self.assertEqual(node_list[i], item)

        del(node_list[2])
        self.assertEqual(len(node_list), 3)
        self.assertFalse(node_a in node_list)


    def testListCast(self):

        node_list = self.TEST_LIST_CLASS((self._dag_node, self._dg_node))

        result = list(node_list)

        self.assertEqual(type(result), list)
        self.assertEqual(len(result), 2)

        for node in result:
            self.assertEqual(type(node), self.TEST_CLASS)

        result = tuple(node_list)

        self.assertEqual(type(result), tuple)
        self.assertEqual(len(result), 2)

        for node in result:
            self.assertEqual(type(node), self.TEST_CLASS)


    def testCount(self):

        node_list = self.TEST_LIST_CLASS()

        self.assertEqual(node_list.count(self._dag_node), 0)

        node_list.append(self._dag_node)
        self.assertEqual(node_list.count(self._dag_node), 1)

        node_list.append(self._dg_node)
        self.assertEqual(node_list.count(self._dag_node), 1)

        node_list.append(self._dag_node)
        self.assertEqual(node_list.count(self._dag_node), 2)


    def testSetAttr(self):

        node_list = self.TEST_LIST_CLASS()

        node_a = self.TEST_CLASS.createNode("transform")
        node_b = self.TEST_CLASS.createNode("transform")

        self.assertEqual(node_a.getAttr("translateX"), 0.0)
        self.assertEqual(node_b.getAttr("translateX"), 0.0)

        node_list.extend((node_a, node_b))

        node_list.setAttr("tx", 100.0)

        self.assertEqual(node_a.getAttr("translateX"), 100.0)
        self.assertEqual(node_b.getAttr("translateX"), 100.0)

        node_list.append(self._dg_node)
        self.assertRaises(RuntimeError, node_list.setAttr, "tx", 1.0)

        node_list.setAttr("tx", 200.0, skip_missing=True)
        self.assertEqual(node_a.getAttr("translateX"), 200.0)
        self.assertEqual(node_b.getAttr("translateX"), 200.0)


    def testGetAttr(self):

        node_list = self.TEST_LIST_CLASS()

        self.assertTrue(node_list.getAttr("tx") is None)

        node_a = self.TEST_CLASS.createNode("transform")
        node_b = self.TEST_CLASS.createNode("transform")
        node_list.extend((node_a, node_b))

        result = node_list.getAttr("tx")
        self.assertEqual(type(result), tuple)
        self.assertEqual(len(result), 2)

        self.assertEqual(result[0], 0.0)
        self.assertEqual(result[1], 0.0)

        node_list.append(self._dg_node)
        self.assertRaises(ValueError, node_list.getAttr, "tx")

        result = node_list.getAttr("tx", skip_missing=True)

        self.assertEqual(type(result), tuple)
        self.assertEqual(len(result), 3)

        self.assertEqual(result[0], 0.0)
        self.assertEqual(result[1], 0.0)
        self.assertTrue(result[2] is None)


    def testGetAttrMap(self):

        node_list = self.TEST_LIST_CLASS()

        self.assertTrue(node_list.getAttrMap("tx") is None)

        node_a = self.TEST_CLASS.createNode("transform")
        node_b = self.TEST_CLASS.createNode("transform")
        node_list.extend((node_a, node_b))

        keyable_attrs = node_list.getAttrMap(keyable=True)
        self.assertEqual(len(keyable_attrs), 2)

        for node in keyable_attrs.keys():

            self.assertTrue(node in node_list)
            self.assertEqual(len(keyable_attrs[node]), 10)

            for attr in keyable_attrs[node].keys():

                self.assertEqual(keyable_attrs[node][attr], node.getAttr(attr))


        keyable_attrs = node_list.getAttrMap("translateX")
        self.assertEqual(len(keyable_attrs), 2)

        for node in keyable_attrs.keys():

            self.assertTrue(node in node_list)
            self.assertEqual(len(keyable_attrs[node]), 1)

            self.assertEqual(keyable_attrs[node]["translateX"], node.getAttr("translateX"))


    def testListNodesWithAttr(self):

        attr_name = "test"
        num_nodes = 100
        node_list = self.TEST_LIST_CLASS()

        for i in range(num_nodes):

            node = self.TEST_CLASS.createNode("time")
            node_list.append(node)

            if i % 2 == 0:
                node.addAttr(attr_name, "string")

        self.assertEqual(len(node_list), num_nodes)

        result = node_list.listNodesWithAttr(attr_name)
        self.assertEqual(type(result), self.TEST_LIST_CLASS)
        self.assertEqual(len(result), num_nodes / 2)

        for node in result:

            self.assertTrue(node.hasAttr(attr_name))



    def testListNodesOfType(self):

        node_type_1 = "time"
        node_type_2 = "plusMinusAverage"
        num_nodes = 100
        node_list = self.TEST_LIST_CLASS()

        for i in range(num_nodes):

            node_type = node_type_2 if i % 2 == 0 else node_type_1

            node_list.append(self.TEST_CLASS.createNode(node_type))

        self.assertEqual(len(node_list), num_nodes)

        result = node_list.listNodesOfType(node_type_1)
        self.assertEqual(type(result), self.TEST_LIST_CLASS)
        self.assertEqual(len(result), num_nodes / 2)

        for node in result:
            self.assertEqual(node.getObjectType(), node_type_1)