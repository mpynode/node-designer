import unittest
import tempfile
import os
import string
import codecs

try:
    import maya.standalone
    maya.standalone.initialize()
except:
    pass


        
try:
    import cPickle as pickle # python2
except:
    import pickle # python3
    unicode = str
    
    


import maya.api.OpenMaya as om
import maya.cmds as mc

from .mpylib import MNode
from .mpylib.nodes import MPyNode


class TestMPyNode(unittest.TestCase):

    TEST_CLASS = MPyNode


    def setUp(self):

        mc.file(newFile=True, force=True)


    def testInit(self):

        node = self.TEST_CLASS()
        name = self.TEST_CLASS.__name__[0].lower() + self.TEST_CLASS.__name__[1:] + "1"
        self.assertEqual(node.getName(), name)

        same_node = self.TEST_CLASS(node)
        self.assertEqual(same_node, node)

        new_node = self.TEST_CLASS(name="test_py_node")
        self.assertEqual(new_node.getName(), "test_py_node")


    def testDelete(self):

        self.testInit()

        node = self.TEST_CLASS("test_py_node")

        node.delete()


    def testLs(self):

        new_nodes = []

        for i in range(10):
            new_nodes.append(self.TEST_CLASS(name="new_node_" + str(i)))

        results = self.TEST_CLASS.ls()
        self.assertEqual(len(results), 10)

        for node in results:
            self.assertTrue(node in results)
            self.assertEqual(type(node), self.TEST_CLASS)

        new_nodes = []

        for i in range(10):
            new_nodes.append(TestChildClass(name="new_child_" + str(i)))

        results = TestChildClass.ls()
        self.assertEqual(len(results), 10)

        for node in results:
            self.assertTrue(node in results)
            self.assertEqual(type(node), TestChildClass)


    def testExportToFile(self):

        for use_binary in (True, False):
            mc.file(newFile=True, force=True)

            file_ext = MPyNode.BINARY_FILE_EXT if use_binary else MPyNode.ASCII_FILE_EXT

            self.testInit()
            node = self.TEST_CLASS("test_py_node")

            temp_file = os.environ["TEMP"] + "\\testExportToFile." + file_ext
            if os.path.exists(temp_file):
                os.remove(temp_file)

            self.assertFalse(os.path.exists(temp_file))
            node.exportToFile(temp_file, use_binary=use_binary)
            self.assertTrue(os.path.exists(temp_file))

            mc.file(newFile=True, force=True)
            fh = open(temp_file)

            try:
                node = pickle.load(fh)

            except Exception as err:
                fh.close()
                raise

            else:
                fh.close()

            self.assertTrue(node.isValid())
            os.remove(temp_file)


    def testImportFromFile(self):

        for use_binary in (True, False):
            mc.file(newFile=True, force=True)

            file_ext = MPyNode.BINARY_FILE_EXT if use_binary else MPyNode.ASCII_FILE_EXT

            self.testInit()
            node = self.TEST_CLASS("test_py_node")

            temp_file = os.environ["TEMP"] + "\\testExportToFile." + file_ext
            if os.path.exists(temp_file):
                os.remove(temp_file)

            self.assertFalse(os.path.exists(temp_file))
            node.exportToFile(temp_file, use_binary=use_binary)
            self.assertTrue(os.path.exists(temp_file))

            mc.file(newFile=True, force=True)

            node = MPyNode.importFromFile(temp_file)
            self.assertTrue(node.isValid())

            os.remove(temp_file)


    def testSetExpression(self):

        node = self.TEST_CLASS()

        exp_str = "i = 1 + 1"

        node.setExpression(exp_str)

        self.assertEqual(node.getExpression(), exp_str)

        exp_str = "self.test_init = 0.0"
        node.setExpression(exp_str)


    def testGetExpression(self):

        self.testSetExpression()


    def testAddInputAttr(self):

        node = self.TEST_CLASS(name="test_node")
        data_check_dict = {}
        i = 1

        for is_array in (False, True):

            for attr_type in MPyNode._NEW_INPUT_TYPES.keys():

                name_suffix = "" if not is_array else "_array"
                attr_name = "test_" + attr_type + name_suffix

                node.addInputAttr(attr_name, attr_type, is_array=is_array)

                self.assertTrue(node.hasAttr(attr_name))

                if is_array:
                    self.assertEqual(node.getAttr(attr_name, size=True), 0)

                else:
                    self.assertEqual(node.getAttr(attr_name, size=True), 1)

                ##---test internal data---##
                data_check_dict[attr_name] = [attr_type]
                internal_str = node._getInternalInputString()

                self.assertTrue(internal_str is not None)

                interal_dict = pickle.loads(codecs.decode(internal_str.encode(), "base64"))

                self.assertEqual(type(interal_dict), dict)
                self.assertEqual(len(interal_dict), i)
                i += 1

                for internal_attr, internal_type in interal_dict.items():
                    self.assertSequenceEqual(interal_dict[internal_attr], data_check_dict[internal_attr])

        return data_check_dict


    def testRenameInputAttr(self):

        return self._testRenameAttr()


    def testRenameOutputAttr(self):

        return self._testRenameAttr(is_input=False)


    def _testRenameAttr(self, is_input=True):

        node = self.TEST_CLASS(name="test_node")
        data_check_dict = {}
        i = 1
        in_node = self.TEST_CLASS(name="in_node")


        for is_array in (False, True):

            attr_types = MPyNode._NEW_INPUT_TYPES.keys() if is_input else MPyNode._NEW_OUTPUT_TYPES.keys()

            for attr_type in attr_types:

                name_suffix = "" if not is_array else "_array"
                attr_name = "test_" + attr_type + name_suffix
                attr_renamed = "testRenamed_" + attr_type + name_suffix

                add_func =  getattr(node, "addInputAttr") if is_input else getattr(node, "addOutputAttr")
                rename_func = getattr(node, "renameInputAttr") if is_input else getattr(node, "renameOutputAttr")

                add_func(attr_name, attr_type, is_array=is_array)
                rename_func(attr_name, attr_renamed)

                self.assertFalse(node.hasAttr(attr_name))
                self.assertTrue(node.hasAttr(attr_renamed))

                if is_array:
                    self.assertEqual(node.getAttr(attr_renamed, size=True), 0)

                else:
                    self.assertEqual(node.getAttr(attr_renamed, size=True), 1)

                ##---test internal data---##
                data_check_dict[attr_renamed] = [attr_type]
                internal_str = node._getInternalInputString() if is_input else node._getInternalOutputString()

                self.assertTrue(internal_str is not None)

                interal_dict = pickle.loads(codecs.decode(internal_str.encode(), "base64"))

                self.assertEqual(type(interal_dict), dict)
                self.assertEqual(len(interal_dict), i)
                #self.assertFalse(interal_dict.has_key(attr_name))
                self.assertFalse(attr_name in interal_dict)
                i += 1

                for internal_attr, internal_type in interal_dict.items():

                    self.assertSequenceEqual(interal_dict[internal_attr], data_check_dict[internal_attr])

        return data_check_dict


    def testDeleteInputAttr(self):

        data_check_dict = self.testAddInputAttr()
        i = len(data_check_dict)

        node = self.TEST_CLASS("test_node")

        for is_array in (False, True):

            for attr_type in MPyNode._NEW_INPUT_TYPES.keys():

                name_suffix = "" if not is_array else "_array"
                attr_name = "test_" + attr_type + name_suffix

                self.assertTrue(node.hasAttr(attr_name))

                node.deleteInputAttr(attr_name)

                self.assertFalse(node.hasAttr(attr_name))

                ##---test internal data---##
                internal_str = node._getInternalInputString()

                del(data_check_dict[attr_name])

                self.assertTrue(internal_str is not None)

                interal_dict = pickle.loads(codecs.decode(internal_str.encode(), "base64"))

                i -= 1

                if i > 0:
                    self.assertEqual(type(interal_dict), dict)
                    self.assertEqual(len(interal_dict), i)

                    for internal_attr, internal_type in interal_dict.items():

                        self.assertSequenceEqual(interal_dict[internal_attr], data_check_dict[internal_attr])

                else:
                    self.assertTrue(interal_dict is None)


    def testDeleteOutputAttr(self):

        data_check_dict = self.testAddOutputAttr()
        i = len(data_check_dict)

        node = self.TEST_CLASS("test_node")

        for is_array in (False, True):

            for attr_type in MPyNode._NEW_OUTPUT_TYPES.keys():

                name_suffix = "" if not is_array else "_array"
                attr_name = "test_" + attr_type + name_suffix

                self.assertTrue(node.hasAttr(attr_name))

                node.deleteOutputAttr(attr_name)

                self.assertFalse(node.hasAttr(attr_name))

                ##---test internal data---##
                internal_str = node._getInternalOutputString()

                del(data_check_dict[attr_name])

                self.assertTrue(internal_str is not None)

                interal_dict = pickle.loads(codecs.decode(internal_str.encode(), "base64"))

                i -= 1

                if i > 0:
                    self.assertEqual(type(interal_dict), dict)
                    self.assertEqual(len(interal_dict), i)

                    for internal_attr, internal_type in interal_dict.items():

                        self.assertSequenceEqual(interal_dict[internal_attr], data_check_dict[internal_attr])

                else:
                    self.assertTrue(interal_dict is None)


    def testAddOutputAttr(self):

        node = self.TEST_CLASS(name="test_node")
        data_check_dict = {}
        i = 1

        for is_array in (False, True):

            for attr_type in MPyNode._NEW_OUTPUT_TYPES.keys():

                name_suffix = "" if not is_array else "_array"
                attr_name = "test_" + attr_type + name_suffix

                node.addOutputAttr(attr_name, attr_type, is_array=is_array)

                self.assertTrue(node.hasAttr(attr_name))

                if is_array:
                    self.assertEqual(node.getAttr(attr_name, size=True), 0)

                else:
                    self.assertEqual(node.getAttr(attr_name, size=True), 1)

                ##---test internal data---##
                data_check_dict[attr_name] = [attr_type]
                internal_str = node._getInternalOutputString()

                self.assertTrue(internal_str is not None)

                interal_dict = pickle.loads(codecs.decode(internal_str.encode(), "base64"))

                self.assertEqual(type(interal_dict), dict)
                self.assertEqual(len(interal_dict), i)
                i += 1

                for internal_attr, internal_type in interal_dict.items():

                    self.assertSequenceEqual(interal_dict[internal_attr], data_check_dict[internal_attr])

        return data_check_dict


    def testListInputAttrs(self):

        self.testAddInputAttr()

        node = self.TEST_CLASS("test_node")
        attr_list = []

        for is_array in (False, True):

            for attr_type in MPyNode._NEW_INPUT_TYPES.keys():

                name_suffix = "" if not is_array else "_array"
                attr_name = "test_" + attr_type + name_suffix

                attr_list.append(attr_name)

        results = node.listInputAttrs()

        for attr in results:
            self.assertTrue(attr in attr_list)


    def testAddStoredVariable(self):

        self.testInit()

        node = self.TEST_CLASS("test_py_node")

        for var_name in string.ascii_lowercase:
            node.addStoredVariable(var_name)


    def testListStoredVariables(self):

        self.testAddStoredVariable()

        node = self.TEST_CLASS("test_py_node")

        stored_vars = node.listStoredVariables()

        #for var_name, letter in map(None, stored_vars, string.ascii_lowercase):
        for var_name, letter in zip(stored_vars, string.ascii_lowercase):
            self.assertEqual(var_name, letter)


    def testHasStoredVariable(self):

        self.testAddStoredVariable()

        node = self.TEST_CLASS("test_py_node")

        self.assertFalse(node.hasStoredVariable("foo"))

        for var_name in string.ascii_lowercase:

            self.assertTrue(node.hasStoredVariable(var_name))


    def testSetStoredVariable(self):

        self.testInit()

        node = self.TEST_CLASS("test_py_node")

        for i, var_name in enumerate(string.ascii_lowercase):

            node.setStoredVariable(var_name, {var_name:{unicode(var_name):1}})


    def testGetStoredVariables(self):

        self.testSetStoredVariable()

        node = self.TEST_CLASS("test_py_node")

        var_map = node.getStoredVariables()

        for i, var_name in enumerate(string.ascii_lowercase):

            self.assertTrue(var_name in var_map)
            self.assertEqual(type(var_map[var_name]), dict)
            self.assertEqual(var_map[var_name][var_name], {unicode(var_name):1})


    def testRemoveStoredVariable(self):

        self.testAddStoredVariable()

        node = self.TEST_CLASS("test_py_node")

        removed_var = "f"

        var_names = node.listStoredVariables()

        self.assertTrue(removed_var in var_names)

        node.removeStoredVariable(removed_var)

        var_names = node.listStoredVariables()

        self.assertFalse(removed_var in var_names)


    def testFunctionalStoredVariables(self):

        in_node = MNode.createNode("transform", name="in_node")
        out_node = MNode.createNode("transform", name="out_node")

        node = self.TEST_CLASS(name="test_py_node")
        node.addStoredVariable("testVar")

        node.addInputAttr("inAttr", "float", keyable=True, defaultValue=-1.0)
        node.addOutputAttr("outAttr", "float")

        node.setExpression("if not hasattr(self, 'testVar'):\n\tself.testVar = 1.0\nelse:\n\tself.testVar += 1.0\noutAttr = self.testVar\n")

        in_node.connectAttr("translateX", node, "inAttr")
        node.connectAttr("outAttr", out_node, "translateX")

        in_node.setAttr("translateX", 1.0)

        out_value = out_node.getAttr("translateX")

        self.assertEqual(out_value, 1.0)

        out_file_name = os.environ["TEMP"].replace("\\", "/") + "/test_mpynode.ma"

        mc.file(rename=out_file_name)
        mc.file(save=True, force=True, type="mayaAscii")

        for i in range(2, 100):
            mc.file(out_file_name, open=True, force=True)

            in_node = MNode("in_node")
            out_node = MNode("out_node")
            in_node.setAttr("translateX", float(i) + 1.0)
            out_value = out_node.getAttr("translateX")

            self.assertEqual(out_value, float(i))

            mc.file(save=True, force=True, type="mayaAscii")


    def testListOutputAttrs(self):

        self.testAddOutputAttr()

        node = self.TEST_CLASS("test_node")
        attr_list = []

        for is_array in (False, True):

            for attr_type in MPyNode._NEW_OUTPUT_TYPES.keys():

                name_suffix = "" if not is_array else "_array"
                attr_name = "test_" + attr_type + name_suffix

                attr_list.append(attr_name)

        results = node.listOutputAttrs()

        for attr in results:
            self.assertTrue(attr in attr_list)


    def testGetInputAttrMap(self):

        self.testAddInputAttr()

        node = self.TEST_CLASS("test_node")
        attr_map = node.getInputAttrMap()

        for attr_name, attr_data in attr_map.items():

            attr_tokens = attr_name.split("_")

            self.assertTrue(len(attr_tokens) in (2, 3))
            self.assertEqual(attr_tokens[1], attr_data[MPyNode._ATTR_MAP_TYPE_KEY])

            if len(attr_tokens) == 2:
                #self.assertFalse(attr_data.has_key(MPyNode.ATTR_MAP_ARRAY_KEY))
                self.assertFalse(MPyNode.ATTR_MAP_ARRAY_KEY in attr_data)

            else:
                self.assertTrue(attr_data[MPyNode.ATTR_MAP_ARRAY_KEY])


    def testGetOutputAttrMap(self):

        self.testAddOutputAttr()

        node = self.TEST_CLASS("test_node")
        attr_map = node.getOutputAttrMap()

        for attr_name, attr_data in attr_map.items():

            attr_tokens = attr_name.split("_")

            self.assertTrue(len(attr_tokens) in (2, 3))
            self.assertEqual(attr_tokens[1], attr_data[MPyNode._ATTR_MAP_TYPE_KEY])

            if len(attr_tokens) == 2:
                #self.assertFalse(attr_data.has_key(MPyNode.ATTR_MAP_ARRAY_KEY))
                self.assertFalse(MPyNode.ATTR_MAP_ARRAY_KEY in attr_data)

            else:
                self.assertTrue(attr_data[MPyNode.ATTR_MAP_ARRAY_KEY])


    def testListValidInputTypes(self):

        attr_types = MPyNode.listValidInputTypes()

        self.assertEqual(type(attr_types), tuple)
        self.assertEqual(len(attr_types), len(MPyNode._NEW_INPUT_TYPES))

        attr_keys = MPyNode._NEW_INPUT_TYPES.keys()
        attr_keys.sort()

        self.assertSequenceEqual(attr_types, attr_keys)


    def testListValidOutputTypes(self):

        attr_types = MPyNode.listValidOutputTypes()

        self.assertEqual(type(attr_types), tuple)
        self.assertEqual(len(attr_types), len(MPyNode._NEW_OUTPUT_TYPES))

        attr_keys = MPyNode._NEW_OUTPUT_TYPES.keys()
        attr_keys.sort()

        self.assertSequenceEqual(attr_types, attr_keys)


    def testFunctionalFloat(self):

        for is_array in (False, True):

            mc.file(newFile=True, force=True)

            mc.playbackOptions(e=True, minTime=1, maxTime=100)

            in_node = MNode(mc.spaceLocator(name="in_node")[0])
            out_node = MNode(mc.spaceLocator(name="out_node")[0])

            attr_type = "float"
            input_attr = "translateX"
            output_attr = "translateX"
            output_attr_2 = "translateY"
            anim_values = (1.0, 100.0)

            self._runFunctionalTest(in_node, out_node, attr_type, input_attr, output_attr, input_attr, anim_values, is_array, output_attr_2=output_attr_2)


    def testFunctionalEnum(self):

        for is_array in (False, True):

            mc.file(newFile=True, force=True)

            mc.playbackOptions(e=True, minTime=1, maxTime=100)

            in_node = MNode(mc.spaceLocator(name="in_node")[0])
            out_node = MNode(mc.spaceLocator(name="out_node")[0])

            attr_type = "enum"
            input_attr = "testEnum"
            output_attr = "testEnum"
            output_attr_2 = "testEnum2"
            enum_names = ":".join(["enum" + str(i) for i in range(100)])
            attr_kargs={"enumName":enum_names}
            anim_values = (1, 100)

            self._runFunctionalTest(in_node, out_node, attr_type, input_attr, output_attr, input_attr, anim_values, is_array, output_attr_2=output_attr_2, attr_kargs=attr_kargs)


    def testFunctionalInt(self):

        for is_array in (False, True):

            mc.file(newFile=True, force=True)

            mc.playbackOptions(e=True, minTime=1, maxTime=100)

            in_node = MNode(mc.spaceLocator(name="in_node")[0])
            out_node = MNode(mc.spaceLocator(name="out_node")[0])

            attr_type = "int"
            input_attr = "testInt"
            output_attr = "testInt"
            output_attr_2 = "testInt2"
            anim_values = (1, 100)

            self._runFunctionalTest(in_node, out_node, attr_type, input_attr, output_attr, input_attr, anim_values, is_array, output_attr_2=output_attr_2)


    def testFunctionalBool(self):

        for is_array in (False, True):

            mc.file(newFile=True, force=True)

            mc.playbackOptions(e=True, minTime=1, maxTime=100)

            in_node = MNode(mc.spaceLocator(name="in_node")[0])
            out_node = MNode(mc.spaceLocator(name="out_node")[0])

            attr_type = "bool"
            input_attr = "testBool"
            output_attr = "testBool"
            out_attr_2 = "testBool2"
            anim_values = (True, False)

            self._runFunctionalTest(in_node, out_node, attr_type, input_attr, output_attr, input_attr, anim_values, is_array, output_attr_2=out_attr_2)


    def testFunctionalVector(self):

        for is_array in (False, True):
            for use_comp_names in (False, True):
                mc.file(newFile=True, force=True)

                mc.playbackOptions(e=True, minTime=1, maxTime=100)

                in_node = MNode(mc.spaceLocator(name="in_node")[0])
                out_node = MNode(mc.spaceLocator(name="out_node")[0])

                attr_type = "vector"
                input_attr = "translate"
                output_attr = "scale"
                output_attr_2 = "translate"
                anim_values = ((1.0, 1.0, 1.0), (100.0, 200.0, 300.0))

                self._runFunctionalTest(in_node, out_node, attr_type, input_attr, output_attr, input_attr, anim_values, is_array, output_attr_2=output_attr_2, use_comp_names=use_comp_names)


    def testFunctionalMatrix(self):

        for is_array in (False, True):

            mc.file(newFile=True, force=True)

            mc.playbackOptions(e=True, minTime=1, maxTime=100)

            in_node = MNode(mc.spaceLocator(name="in_node")[0])
            out_node = MNode.createNode("multMatrix", name="matrix_out_node")

            attr_type = "matrix"
            input_attr = "matrix"
            output_attr = "matrixIn[0]"
            output_attr_2 = "matrixIn[1]"
            anim_attr = "translate"
            anim_values = ((1.0, 1.0, 1.0), (100.0, 200.0, 300.0))

            self._runFunctionalTest(in_node, out_node, attr_type, input_attr, output_attr, anim_attr, anim_values, is_array, output_attr_2=output_attr_2)


    def testFunctionalColor(self):

        for is_array in (False, True):
            for use_comp_names in (False, True):
                mc.file(newFile=True, force=True)

                mc.playbackOptions(e=True, minTime=1, maxTime=100)

                in_node = MNode(mc.spaceLocator(name="in_node")[0])
                out_node = MNode(mc.spaceLocator(name="out_node")[0])

                attr_type = "color"
                input_attr = "translate"
                output_attr = "scale"
                output_attr_2 = "translate"
                anim_values = ((1.0, 1.0, 1.0), (100.0, 200.0, 300.0))

                self._runFunctionalTest(in_node, out_node, attr_type, input_attr, output_attr, input_attr, anim_values, is_array, output_attr_2=output_attr_2, use_comp_names=use_comp_names)


    def testFunctionalAngle(self):

        for is_array in (False, True):

            mc.file(newFile=True, force=True)

            mc.playbackOptions(e=True, minTime=1, maxTime=100)

            in_node = MNode(mc.spaceLocator(name="in_node")[0])
            out_node = MNode(mc.spaceLocator(name="out_node")[0])

            attr_type = "angle"
            input_attr = "rotateX"
            output_attr = "rotateX"
            out_attr_2 = "rotateY"
            anim_values = (1.0, 100.0)

            self._runFunctionalTest(in_node, out_node, attr_type, input_attr, output_attr, input_attr, anim_values, is_array, output_attr_2=out_attr_2)


    def testFunctionalEuler(self):

        for is_array in (False, True):
            for use_comp_names in (False, True):
                mc.file(newFile=True, force=True)

                mc.playbackOptions(e=True, minTime=1, maxTime=100)

                in_node = MNode(mc.spaceLocator(name="in_node")[0])
                out_node = MNode(mc.spaceLocator(name="out_node")[0])

                attr_type = MPyNode.ATTR_TYPE_EULER
                input_attr = "rotate"
                output_attr = "rotate"
                output_attr_2 = "scale"
                anim_values = ((1.0, 1.0, 1.0), (100.0, 200.0, 300.0))

                self._runFunctionalTest(in_node, out_node, attr_type, input_attr, output_attr, input_attr, anim_values, is_array, output_attr_2=output_attr_2, use_comp_names=use_comp_names)


    def testFunctionalString(self):

        for is_array in (False, True):

            mc.file(newFile=True, force=True)

            mc.playbackOptions(e=True, minTime=1, maxTime=100)

            in_node = MNode(mc.spaceLocator(name="in_node")[0])
            out_node = MNode(mc.spaceLocator(name="out_node")[0])

            attr_type = "string"
            input_attr = "string_test"
            input_value = "test_string_value"
            output_attr = "string_test"
            output_attr_2 = "string_test2"
            anim_values = None

            self._runFunctionalTest(in_node, out_node, attr_type, input_attr, output_attr, input_attr, anim_values, is_array, input_value=input_value, output_attr_2=output_attr_2)


    def testFunctionalPy(self):

        for is_array in (False, True):

            mc.file(newFile=True, force=True)

            mc.playbackOptions(e=True, minTime=1, maxTime=100)

            in_node = MNode(mc.spaceLocator(name="in_node")[0])
            out_node = MNode(mc.spaceLocator(name="out_node")[0])

            in_py_node = MPyNode(name="in_py_node")
            out_py_node = MPyNode(name="out_py_node")

            in_py_node.addInputAttr("inFloat", MPyNode.ATTR_TYPE_FLOAT)
            in_py_node.addOutputAttr("outPy", MPyNode.ATTR_TYPE_PY, is_array=is_array)

            out_py_node.addInputAttr("inPy", MPyNode.ATTR_TYPE_PY, is_array=is_array)
            out_py_node.addOutputAttr("outFloat", MPyNode.ATTR_TYPE_FLOAT)

            if not is_array:
                in_py_node.setExpression("outPy = {'test':inFloat}")
                out_py_node.setExpression("outFloat = inPy['test'] + inPy['test']")

                in_node.connectAttr("tx", in_py_node, "inFloat")
                in_py_node.connectAttr("outPy", out_py_node, "inPy")
                out_py_node.connectAttr("outFloat", out_node, "tx")

            else:
                in_py_node.setExpression("outPy = [{'test':inFloat}, {'test':inFloat}]")
                out_py_node.setExpression("outFloat = inPy[0]['test'] + inPy[1]['test']")

                in_node.connectAttr("tx", in_py_node, "inFloat")
                in_py_node.connectAttr("outPy[0]", out_py_node, "inPy[0]")
                in_py_node.connectAttr("outPy[1]", out_py_node, "inPy[1]")
                out_py_node.connectAttr("outFloat", out_node, "tx")

            for f in range(101):

                mc.currentTime(f, update=True)

                in_node.setAttr("tx", float(f))
                out_val = out_node.getAttr("tx")

                self.assertEqual(float(f) + float(f), out_val)


    def testFunctionalTime(self):

        for is_array in (False, True):

            mc.file(newFile=True, force=True)

            mc.playbackOptions(e=True, minTime=1, maxTime=100)

            in_node = MNode("time1")
            out_node = MNode.createNode("animBlendNodeTime", name="out_node")

            attr_type = "time"
            input_attr = "outTime"
            output_attr = "inputA"
            output_attr_2 = "inputB"
            anim_values = None

            self._runFunctionalTest(in_node, out_node, attr_type, input_attr, output_attr, input_attr, anim_values, is_array)


    def testFunctionalMesh(self):

        for is_array in (False, True):

            mc.file(newFile=True, force=True)

            mc.playbackOptions(e=True, minTime=1, maxTime=100)

            num_meshes = 1 if not is_array else 4
            in_nodes = []
            geo_points = []

            for i in range(num_meshes):

                cube_trans = mc.polyCube(name="in_node_" + str(i), ch=False)[0]
                new_mesh = MNode(mc.listRelatives(cube_trans, shapes=True, fullPath=True)[0])
                in_nodes.append(new_mesh)

                fn_set = om.MFnMesh(new_mesh)
                geo_points.append(fn_set.getPoints(om.MSpace.kObject))

            attr_type = "mesh"
            input_attr = "worldMesh[0]"
            expr_str = "outAttr = inGeo.getPoints()" if not is_array else "outAttr = inGeo[0].getPoints()"
            anim_values = None

            self._runFunctionalGeoTest(in_nodes, input_attr, attr_type, is_array, expr_str, geo_points)


    def testChildClass(self):

        mc.playbackOptions(e=True, minTime=1, maxTime=100)

        in_node = MNode(mc.spaceLocator(name="in_node")[0])
        out_node = MNode(mc.spaceLocator(name="out_node")[0])

        py_node = TestChildClass()

        for i, attr_name in enumerate(TestChildClass.INIT_INPUT_ATTRS):
            self.assertTrue(py_node.hasAttr(attr_name))

        for i, attr_name in enumerate(TestChildClass.INIT_OUTPUT_ATTRS):
            self.assertTrue(py_node.hasAttr(attr_name))

        for i, attr_name in enumerate(TestChildClass.INIT_ATTRS):
            self.assertTrue(py_node.hasAttr(attr_name))

        attr_type = "float"
        input_attr = "translateX"
        output_attr = "translateX"
        anim_values = (1.0, 100.0)

        self._runFunctionalTest(in_node, out_node, attr_type, input_attr, output_attr, input_attr, anim_values, False, py_node=py_node)


    def testReduce(self):

        exp = "floatOutput = floatInput * 2.0\nintOutput = intInput + enumInput"

        node = MPyNode()
        node.rename("test_mpynode")

        input_maps = {"floatInput":{"attr_type":"float", "keyable":True, "defaultValue":100.0},
                      "intInput":{"attr_type":"int","min":1, "max":3, "channelBox":True, "defaultValue":3},
                      "enumInput":{"attr_type":"enum", "enumName":"one=1:three=3:five=5", "defaultValue":1},
                      "stringInput":{"attr_type":"string"},
                      "arrayInput":{"attr_type":"float", "is_array":True},
                      "boolInput":{"attr_type":"bool", "defaultValue":True}}

        output_maps = {"floatOutput":{"attr_type":"float", "defaultValue":1.0},
                       "intOutput":{"attr_type":"int", "defaultValue":0}}

        stored_vars = {"var_1":1.0, "var_2":2.0}

        for attr_name, attr_map in input_maps.items():
            node.addInputAttr(attr_name, **attr_map)

        for attr_name, attr_map in output_maps.items():
            node.addOutputAttr(attr_name, **attr_map)

        node.setExpression(exp)

        for var_name, var_val in stored_vars.items():
            node.setStoredVariable(var_name, var_val)

        node_str = pickle.dumps(node)
        new_node = pickle.loads(node_str)

        ##----test inputs----##
        result_inputs = new_node.getInputAttrMap()
        self.assertEqual(len(result_inputs), len(input_maps))

        for attr_name, attr_data in result_inputs.items():
            #self.assertTrue(input_maps.has_key(attr_name))
            self.assertTrue(attr_name in input_maps)
            test_data = input_maps[attr_name]
            self.assertEqual(len(attr_data), len(test_data))

            for key, val in attr_data.items():
                #self.assertTrue(test_data.has_key(key))
                self.assertTrue(key in test_data)
                self.assertEqual(val, test_data[key])

        ##----test output----##
        result_outputs = new_node.getOutputAttrMap()
        self.assertEqual(len(result_outputs), len(output_maps))

        for attr_name, attr_data in result_outputs.items():
            #self.assertTrue(output_maps.has_key(attr_name))
            self.assertTrue(attr_name in output_maps)
            test_data = output_maps[attr_name]
            self.assertEqual(len(attr_data), len(test_data))

            for key, val in attr_data.items():
                #self.assertTrue(test_data.has_key(key))
                self.assertTrue(key in test_data)
                self.assertEqual(val, test_data[key])

        ##----test stored variables----##
        result_stored_vars = new_node.getStoredVariables()
        self.assertEqual(len(result_stored_vars), len(stored_vars))

        for var_name, var_val in stored_vars.items():
            self.assertTrue(var_name in result_stored_vars)
            self.assertEqual(var_val, result_stored_vars[var_name])

        ##----test expression----##
        result_exp = new_node.getExpression()
        self.assertEqual(result_exp, exp)


    def _runFunctionalGeoTest(self, in_nodes, input_attr, attr_type, is_array, expr_str, geo_points,
                              attr_kargs=None):

        if attr_kargs is None:
            attr_kargs = {}

        out_node = MNode(mc.spaceLocator(name="out_node")[0])

        py_node = self.TEST_CLASS(name="test_py_node")
        py_node.setExpression(expr_str)

        py_node.addInputAttr("inGeo", attr_type, is_array=is_array, **attr_kargs)
        py_node.addOutputAttr("outAttr", "vector", is_array=True, **attr_kargs)

        py_node.addInputAttr("inTime", "time")
        py_node.addOutputAttr("computeCount", "int")

        if not is_array:
            in_nodes[0].connectAttr(input_attr, py_node, "inGeo")

        else:
            for i, in_node in enumerate(in_nodes):
                in_node.connectAttr(input_attr, py_node, "inGeo[" + str(i) + "]")


        for i in range(len(in_nodes)):
            print (py_node.getAttr("outAttr[" + str(i) + "]"))


    def _runFunctionalTest(self, in_node, out_node, attr_type, input_attr, output_attr, anim_attr, anim_values, is_array, py_node=None,
                           out_attr_type=None, input_value=None, expr_str=None, output_attr_2=None, attr_kargs=None, use_comp_names=False):

        in_node_name = str(in_node)
        out_node_name = str(out_node)
        in_attr_name = "inAttr"
        out_attr_name = "outAttr"
        comp_count_attr = "computeCount"
        attr_mel_type = MPyNode._NEW_INPUT_TYPES[attr_type]
        out_mel_type = MPyNode._NEW_OUTPUT_TYPES[attr_type] if not out_attr_type else MPyNode._NEW_OUTPUT_TYPES[out_attr_type]

        if attr_kargs is None:
            attr_kargs = {}

        if expr_str is None:
            expr_str = "outAttr = inAttr\nif not hasattr(self, '_comp_count'):\n    self._comp_count = 0\nelse:    self._comp_count += 1\ncomputeCount=self._comp_count"

        if not out_attr_type:
            out_attr_type = attr_type

        if not py_node:
            py_node = self.TEST_CLASS(name="test_py_node")
            py_node.setExpression(expr_str)

            py_node.addInputAttr(in_attr_name, attr_type, is_array=is_array, **attr_kargs)
            py_node.addOutputAttr(out_attr_name, out_attr_type, is_array=is_array, **attr_kargs)

            py_node.addInputAttr("dummyInput", "float", is_array=True) ##adding to make sure it doesn't cause multiple calls to compute()
            py_node.setAttr("dummyInput", size=10)
            py_node.addOutputAttr(comp_count_attr, "int")

        if not in_node.hasAttr(input_attr):
            in_node.addAttr(input_attr, attr_mel_type, keyable=True, **attr_kargs)

        if not out_node.hasAttr(output_attr.split("[")[0]):
            out_node.addAttr(output_attr, out_mel_type, keyable=True, **attr_kargs)

        pynode_in_attr = in_attr_name if not is_array else in_attr_name + "[0]"
        pynode_out_attr = out_attr_name if not is_array else out_attr_name + "[0]"
        py_node.connectAttr(pynode_out_attr, out_node, output_attr)

        if not use_comp_names:
            in_node.connectAttr(input_attr, py_node, pynode_in_attr)

        else:
            for i, axis in enumerate(("X", "Y", "Z")):
                comp_name = MPyNode._VECTOR_COMP_NAMES[attr_type][i]

                if is_array:
                    in_node.connectAttr(input_attr + axis, py_node, pynode_in_attr + "." + in_attr_name + comp_name)

                else:
                    in_node.connectAttr(input_attr + axis, py_node, in_attr_name + comp_name)

        if is_array and output_attr_2:
            py_node.setAttr(out_attr_name, size=2)

            if not out_node.hasAttr(output_attr_2.split("[")[0]):
                out_node.addAttr(output_attr_2, attr_mel_type, **attr_kargs)

            py_node.connectAttr(out_attr_name + "[1]", out_node, output_attr_2)


        child_in_attrs = in_node.attributeQuery(anim_attr, listChildren=True)

        if input_value is not None:
            in_node.setAttr(anim_attr, input_value, type=attr_mel_type)

        if anim_values is not None:
            ##---not a compound attr---##
            if not child_in_attrs:
                mc.setKeyframe(in_node, attribute=anim_attr, time=1, value=anim_values[0])
                mc.setKeyframe(in_node, attribute=anim_attr, time=100, value=anim_values[1])

            ##---compound attr---##
            else:
                for i, child_attr in enumerate(child_in_attrs):
                    mc.setKeyframe(in_node, attribute=anim_attr, time=1, value=anim_values[0][i])
                    mc.setKeyframe(in_node, attribute=anim_attr, time=100, value=anim_values[1][i])

        out_file_name = os.environ["TEMP"].replace("\\", "/") + "/test_mpynode.ma"

        py_node_name = str(py_node)

        mc.file(rename=out_file_name)
        mc.file(save=True, force=True, type="mayaAscii")

        for i in range(2):

            ##--reopen scene second time around---##
            if i:
                mc.file(out_file_name, open=True, force=True)
                in_node = MNode(in_node_name)
                out_node = MNode(out_node_name)
                py_node = self.TEST_CLASS(py_node_name)

                if not anim_values and attr_mel_type != "time":
                    in_node.setAttr(input_attr, input_value, type=attr_mel_type)

            for f in range(101):

                mc.currentTime(f, update=True)

                in_val = in_node.getAttr(input_attr)
                out_val = out_node.getAttr(output_attr)

                self.assertEqual(in_val, out_val)

            if attr_type != "string":
                self.assertTrue(py_node.getAttr("computeCount") in (99, 100))

        if os.path.exists(out_file_name):
            os.remove(out_file_name)


class TestChildClass(MPyNode):

    INIT_EXPRESSION_STR = "outAttr = inAttr\nif not hasattr(self, '_comp_count'):\n    self._comp_count = 0\nelse:    self._comp_count += 1\ncomputeCount=self._comp_count"

    INIT_INPUT_ATTRS = {"inAttr":{"attr_type":"float", "is_array":False}}

    INIT_OUTPUT_ATTRS = {"outAttr":{"attr_type":"float", "is_array":False},
                         "computeCount":{"attr_type":"int", "is_array":False}}

    INIT_ATTRS = {"testAttr1":{"attr_type":"message"}}



#class TestMPyShape(TestMPyNode):

    #TEST_CLASS = MPyShape


    #def testShapeAttrs(self):

        #node = self.TEST_CLASS(name="testShape")

        #for attr_name in (self.TEST_CLASS.COMPUTE_SHAPE_ATTR_NAME, self.TEST_CLASS.VERT_POS_ATTR_NAME):
            #self.assertTrue(node.hasAttr(attr_name))


    #def testFunctionalShapeAttrs(self):

        #pass
