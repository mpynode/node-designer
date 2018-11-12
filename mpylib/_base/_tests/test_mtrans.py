import unittest
from collections import OrderedDict

try:
    import maya.standalone
    maya.standalone.initialize()
except:
    pass

import maya.cmds as mc
from mpylib import MNode, MNodeList, MTrans, MTransList, MShapeList


from test_mnode import TestMNode


class TestMTrans(TestMNode):
    
    TEST_CLASS = MTrans
    TEST_LIST_CLASS = MTransList
    TEST_SHAPE_LIST_CLASS = MShapeList
    
    
    def setUp(self):
        
        mc.file(newFile=True, force=True)
        
        self._dag_node = self.TEST_CLASS(name=self.DAG_NODE_NAME)
        self._dg_node = None
        
        
    def testLs(self):
        
        self._dag_node.delete()
        
        trans_nodes = MTrans.ls("test_*")
        self.assertTrue(trans_nodes is None)
        
        node_a = self.TEST_CLASS()
        node_a.rename("test_node_a")
        node_b = self.TEST_CLASS()
        node_b.rename("test_node_b")
        
        trans_nodes = MTrans.ls("test_*")
        
        self.assertEqual(type(trans_nodes), MTransList)
        self.assertEqual(len(trans_nodes), 2)
        self.assertEqual(trans_nodes[0], node_a)
        self.assertEqual(trans_nodes[1], node_b)
        
        
    def testInit(self):
        
        ##---init new---##
        new_node = self.TEST_CLASS()
        new_node.rename("test_node")
        self.assertEqual(new_node.getObjectType(), "transform")
        
        ##---init existing---##
        node = self.TEST_CLASS("test_node")
        self.assertEqual(node.getName(), "test_node")
        
        ##---should take a joint as well---##
        jnt = MNode.createNode("joint")
        jnt.rename("jnt_1")
        node = self.TEST_CLASS(jnt)
        self.assertEqual(node.getName(), "jnt_1")
        
        
    def testConvertLocalVectToWorld(self):
        
        self._dag_node.rotate((90.0, 90.0, 90.0))
        local_vect = (1.0, 0.0, 0.0)
        
        world_vect = self._dag_node.convertLocalVectToWorld(local_vect)
        result = (0.0, 0.0, -1.0)
        
        for a, b in map(None, world_vect, result):
            self.assertAlmostEqual(a, b)
        
        
    def testFreeze(self):
        
        self._dag_node.rotate((90.0, 90.0, 90.0))
        self._dag_node.move((100.0, 100.0, 100.0))
        
        for axis in ("x", "y", "z"):
            self.assertEqual(self._dag_node.getAttr("r" + axis), 90.0)
            
        for axis in ("x", "y", "z"):
            self.assertEqual(self._dag_node.getAttr("t" + axis), 100.0)
            
        self._dag_node.freeze()
        
        for axis in ("x", "y", "z"):
            for attr in ("r", "t"):
                self.assertEqual(self._dag_node.getAttr(attr + axis), 0.0)
                
        
        
    def testGetBaseParent(self):
        
        b = self.TEST_CLASS()
        c = self.TEST_CLASS()
        
        self._dag_node.parent(b)
        b.parent(c)
        
        base_parent = self._dag_node.getBaseParent()
        
        self.assertEqual(base_parent, c)
        
        
        
    def testGetChildren(self):
        
        b = self.TEST_CLASS()
        c = self.TEST_CLASS()
        
        self.assertTrue(self._dag_node.getChildren() is None)
        
        b.parent(self._dag_node)
        c.parent(self._dag_node)
        
        children = self._dag_node.getChildren()
        result = (b, c)
        
        self.assertEqual(type(children), MTransList)
        self.assertEqual(len(children), 2)
        
        for item in result:
            self.assertTrue(item in children)
            
        
        loc_trans = self.TEST_CLASS(mc.spaceLocator()[0])
        
        self.assertTrue(loc_trans.getChildren() is None)
        
        jnt = self.TEST_CLASS(MNode.createNode("joint"))
        
        jnt.parent(loc_trans)
        
        children = loc_trans.getChildren()
        
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0], jnt)
        
        
    def testGetRotationAsQuaternion(self):
        
        rot = self._dag_node.getRotationAsQuaternion()
        
        
    def testSetRotationAsQuaternion(self):
        
        b = self.TEST_CLASS(name="b")
        
        rot_quat = self._dag_node.getRotationAsQuaternion()
        b.setRotationFromQuaternion(rot_quat)
        
        
    def testGetDescendents(self):
        
        b = self.TEST_CLASS()
        c = self.TEST_CLASS()
        
        self.assertTrue(self._dag_node.getDescendents() is None)
        
        self._dag_node.parent(b)
        b.parent(c)
        
        children = c.getDescendents()
        result = (self._dag_node, b)
        
        self.assertEqual(type(children), MTransList)
        self.assertEqual(len(children), 2)
        
        for item in result:
            self.assertTrue(item in children)
            
        children = c.getDescendents(include_root=True)
        result = (self._dag_node, b, c)
                
        self.assertEqual(type(children), MTransList)
        self.assertEqual(len(children), 3)
        
        for item in result:
            self.assertTrue(item in children)        
        
    
    def testGetDistance(self):
        
        self._dag_node = self.TEST_CLASS()
        b = self.TEST_CLASS()
        
        b.setAttr("tx", 153.0)
        
        dis = self._dag_node.getDistance(b)
        
        self.assertEqual(dis, 153.0)
        
        
    def testGetParent(self):
        
        b = self.TEST_CLASS()
        
        self.assertTrue(self._dag_node.getParent() is None)
        
        self._dag_node.parent(b)
        
        self.assertEqual(self._dag_node.getParent(), b)
        
        
    def testGetPath(self):
        
        a = self.TEST_CLASS()
        a.rename("a")
        b = self.TEST_CLASS()
        b.rename("b")
        
        self.assertEqual(a.getPath(), "|a")
        
        a.parent(b)
        
        self.assertEqual(a.getPath(), "|b|a")
        self.assertEqual(str(a), "|b|a") #casting as string calls getPath
        
    
    def testGetShapes(self):
        
        loc = mc.spaceLocator()
        trans = self.TEST_CLASS(loc[0])
        shape = MNode("locatorShape1")
        
        shapes = trans.getShapes()
        
        self.assertEqual(len(shapes), 1)
        self.assertEqual(type(shapes), self.TEST_SHAPE_LIST_CLASS)
        self.assertEqual(shapes[0], shape)
        
        ##----cube mesh test----##
        trans = self.TEST_CLASS(mc.polyCube(w=1, h=1, d=1, sx=1, sy=1, sz=1, ax=(0, 1, 0), ch=False)[0])
        
        shapes = trans.getShapes()
        
        self.assertEqual(len(shapes), 1)
        self.assertEqual(type(shapes), self.TEST_SHAPE_LIST_CLASS)
        
        shapes = trans.getShapes(shape_type="locator")
        
        self.assertTrue(shapes is None)
    
    
    def testListRelatives(self):
        
        a = self.TEST_CLASS()
        a.rename("a")
        b = self.TEST_CLASS()
        b.rename("b")
        
        a.parent(b)
        
        self.assertEqual(a.listRelatives(children=True), None)
        
        
    def testMatch(self):
        
        a = self.TEST_CLASS()
        b = self.TEST_CLASS()
        
        b.move((100, 200, 300))
        b.rotate((90, 180, 270))
        b.setAttr("rotateOrder", 3)
        
        a.match(b)
        
        for attr in ("rotateOrder", "tx", "ty", "tz"):
            self.assertEqual(a.getAttr(attr), b.getAttr(attr))
            
        for local_axis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
            
            a_axis = a.convertLocalVectToWorld(local_axis)
            b_axis = b.convertLocalVectToWorld(local_axis)
            
            for a_val, b_val in map(None, a_axis, b_axis):
                self.assertAlmostEqual(a_val, b_val)
        
        
    def testMove(self):
        
        a = self.TEST_CLASS()

        a.move((100, 200, 300))
        
        pos = a.xform(q=True, ws=True, t=True)
        
        self.assertEqual(pos[0], 100.0)
        self.assertEqual(pos[1], 200.0)
        self.assertEqual(pos[2], 300.0)
        
    
    def testParent(self):
        
        a = self.TEST_CLASS()
        b = self.TEST_CLASS()
        
        b.parent(a)
        
        self.assertEqual(b.getParent(), a)
        self.assertEqual(a.getChildren()[0], b)
        
        
    def testAimConstraint(self):
            
        a = self.TEST_CLASS()
        b = self.TEST_CLASS()
        c = self.TEST_CLASS()
        
        aim_con = a.aimConstraint(b, c, aimVector=(1.0, 0.0, 0.0), upVector=(0.0, 1.0, 0.0), worldUpType="scene")
        self.assertEqual(type(aim_con), MTrans)
        self.assertEqual(aim_con.getObjectType(), "aimConstraint")
        
        for attr in ("rx", "ry", "rz"):
            
            con, plugs = a.listConnections(attr, destination=True)
            self.assertEqual(con[0], aim_con)
            
            
    def testScaleConstraint(self):

        a = self.TEST_CLASS()
        b = self.TEST_CLASS()
        c = self.TEST_CLASS()

        scale_con = a.scaleConstraint(b, c)
        self.assertEqual(type(scale_con), MTrans)
        self.assertEqual(scale_con.getObjectType(), "scaleConstraint")

        for attr in ("sx", "sy", "sz"):

            con, plugs = a.listConnections(attr, destination=True)
            self.assertEqual(con[0], scale_con)       
        
        
    def testOrientConstraint(self):
        
        a = self.TEST_CLASS()
        b = self.TEST_CLASS()
        c = self.TEST_CLASS()
        
        ori_con = a.orientConstraint(b, c)
        self.assertEqual(type(ori_con), MTrans)
        self.assertEqual(ori_con.getObjectType(), "orientConstraint")
        
        for attr in ("rx", "ry", "rz"):
            
            con, plugs = a.listConnections(attr, destination=True)
            self.assertEqual(con[0].getName(), ori_con.getName())
        
        
    
    def testParentConstraint(self):
        
        a = self.TEST_CLASS()
        b = self.TEST_CLASS()
        c = self.TEST_CLASS()
        
        par_con = a.parentConstraint(b, c)
        self.assertEqual(type(par_con), MTrans)
        self.assertEqual(par_con.getObjectType(), "parentConstraint")
        
        for attr in ("tx", "ty", "tz", "rx", "ry", "rz"):
            
            con, plugs = a.listConnections(attr, destination=True)
            self.assertEqual(con[0].getName(), par_con.getName())
        
        
    def testPointConstraint(self):
        
        a = self.TEST_CLASS()
        b = self.TEST_CLASS()
        c = self.TEST_CLASS()
        
        point_con = a.pointConstraint(b, c)
        self.assertEqual(type(point_con), MTrans)
        self.assertEqual(point_con.getObjectType(), "pointConstraint")
        
        for attr in ("tx", "ty", "tz"):
            
            con, plugs = a.listConnections(attr, destination=True)
            self.assertEqual(con[0].getName(), point_con.getName())
        
        
    def testRotate(self):
        
        node = self.TEST_CLASS()
        node.rotate((90, 180, 270))
        
        results = ((0.0, 1.0, 0.0), (0.0, 0.0, -1.0), (-1.0, 0.0, 0.0))
        local_axes =((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        
        for local_axis, result in map(None, local_axes, results):
            a_axis = node.convertLocalVectToWorld(local_axis)
            
            for a, b in map(None, a_axis, result):
                self.assertAlmostEqual(a, b)
        

    def testScale(self):
        
        a = self.TEST_CLASS()
        a.scale((2.0, 3.0, 1.0))
        
        for attr, value in map(None, ("sx", "sy", "sz"), (2.0, 3.0, 1.0)):
            self.assertEqual(a.getAttr(attr), value)
        
        
    def testXform(self):
        
        a = self.TEST_CLASS()
        pos = a.xform(q=True, ws=True, t=True)
        
        for val in pos:
            self.assertEqual(val, 0.0)
            
        a.xform( ws=True, t=(1.0, 1.0, 1.0))
        pos = a.xform(q=True, ws=True, t=True)
        
        for val in pos:
            self.assertEqual(val, 1.0)
            
            
    def testGetHierarchyAttrMap(self):
        
        a = self.TEST_CLASS(name="a")
        b = self.TEST_CLASS(name="b")
        c = self.TEST_CLASS(name="c")
        
        b.parent(a)
        c.parent(b)
        
        node_order = (a, b, c)
        
        node_map = a.getHierarchyAttrMap(attr_strs=("rotate?", "translate?"), keyable=True)
    
        self.assertEqual(type(node_map), OrderedDict)
        
        for i, node in enumerate(node_map.keys()):
            
            self.assertEqual(node, node_order[i])
            
            attr_map = node_map[node]
            attrs = node.listAttr("rotate?", "translate?", keyable=True)
            
            self.assertEqual(len(attrs), len(attr_map.keys()))
    
            for attr in attr_map.keys():
        
                self.assertTrue(attr in attrs)
        
                attr_val = node.getAttr(attr)
                self.assertEqual(attr_map[attr], attr_val)
                
                
    def testWalkChildren(self):
        
        a = self.TEST_CLASS(name="a")
        b = self.TEST_CLASS(name="b")
        c = self.TEST_CLASS(MNode.createNode("joint", name="c"))
        d = self.TEST_CLASS(name="d")
        e = self.TEST_CLASS(name="e")
        f = self.TEST_CLASS(name="f")
    
        b.parent(a)
        c.parent(b)
        e.parent(c)
        f.parent(e)
        d.parent(c)
        
        parent_first_order = (b, c, e, f, d)
        child_first_order = (f, e, d, c, b)
        
        walker = a.walkChildren()
        
        for child in parent_first_order:
            
            next_child = next(walker)
            
            self.assertEqual(next_child, child)
            
            
        walker = a.walkChildren(child_first=True)
    
        for child in child_first_order:
    
            next_child = next(walker)
    
            self.assertEqual(next_child, child)
            
            
        ##----test object type functinality----##
        parent_first_order = (b, e, f, d) ## missing joint
        child_first_order = (f, e, d, b) ## missing joint
        
        walker = a.walkChildren(obj_type="transform")
        
        for child in parent_first_order:
    
            next_child = next(walker)
    
            self.assertEqual(next_child, child)
            
            
        walker = a.walkChildren(child_first=True, obj_type="transform")
    
        for child in child_first_order:
    
            next_child = next(walker)
    
            self.assertEqual(next_child, child)
            

        ##---test return root---##
        parent_first_order = (a, b, c, e, f, d)
        child_first_order = (f, e, d, c, b, a)
    
        walker = a.walkChildren(include_root=True)
    
        for child in parent_first_order:
    
            next_child = next(walker)
    
            self.assertEqual(next_child, child)
    
    
        walker = a.walkChildren(include_root=True, child_first=True)
    
        for child in child_first_order:
    
            next_child = next(walker)
    
            self.assertEqual(next_child, child)              
            
            
        ##----test object type functinality with stop_on_type----##
        parent_first_order = (a, b) ## joint stop recursion
        child_first_order = (b, a) ## joint stop recursion
    
        walker = a.walkChildren(include_root=True, obj_type="transform", stop_on_type=True)
    
        for child in parent_first_order:
    
            next_child = next(walker)
    
            self.assertEqual(next_child, child)
    
    
        walker = a.walkChildren(include_root=True, child_first=True, obj_type="transform", stop_on_type=True)
    
        for child in child_first_order:
    
            next_child = next(walker)
    
            self.assertEqual(next_child, child)  

            
    def testGoToInitialPose(self):
        
        self.testSetInitialPose()
        self.testSetCurrentPoseToInitial()
            
            
    def testSetInitialPose(self):
        
        a = self.TEST_CLASS()
        
        a.setInitialPose("translateX", 100.0)
        a.setInitialPose("rx", 90.0)
        a.setInitialPose("translateX", 200.0)
        
        self.assertEqual(a.getAttr("tx"), 0.0)
        self.assertEqual(a.getAttr("rx"), 0.0) 
        
        a.goToInitialPose()
        
        self.assertEqual(a.getAttr("tx"), 200.0)
        self.assertEqual(a.getAttr("rx"), 90.0)        
        
        
    def testSetCurrentPoseToInitial(self):
        
        pose = {"tx":100.0, "ty":200.0, "tz":300.0, "rx":10.0, "ry":20.0, "rz":30.0,
                "sx":3.0, "sy":4.0, "sz":0.5}
        
        a = self.TEST_CLASS()
        
        for attr, attr_val in pose.items():
            
            a.setAttr(attr, attr_val)
        
        a.setCurrentPoseToInitial()
        
        for attr in pose.keys():
            a.setAttr(attr, 1.0)
            self.assertEqual(a.getAttr(attr), 1.0)
            
        a.goToInitialPose()
        
        for attr, attr_val in pose.items():
            
            self.assertAlmostEqual(a.getAttr(attr), attr_val)
            
    def testIsChildOf(self):
        
        a = self.TEST_CLASS()
        b = self.TEST_CLASS()
        c = self.TEST_CLASS()
        
        self.assertFalse(c.isChildOf(a))
        
        c.parent(a)
        self.assertTrue(c.isChildOf(a))
        
        c.parent(b)
        self.assertFalse(c.isChildOf(a))
        
        b.parent(a)
        self.assertFalse(c.isChildOf(a))
        self.assertTrue(c.isChildOf(a, recursive=True))
        
        
    def testGetParentOfType(self):
        
        a = self.TEST_CLASS(name="a")
        b = self.TEST_CLASS(MNode.createNode("joint", name="b"))
        c = self.TEST_CLASS(name="c")
        d = self.TEST_CLASS(name="d")
        
        e = self.TEST_CLASS(name="e")
        e.parent(c)
        
        b.parent(a)
        c.parent(b)
        d.parent(c)
        
        par = d.getParentOfType("transform")
        self.assertEqual(par, c)
        
        par = par.getParentOfType("joint")
        self.assertEqual(par, b)
        
        par = d.getParentOfType("parentConstraint")
        self.assertTrue(par is None)
        
        par = b.getParentOfType("joint")
        self.assertTrue(par is None)