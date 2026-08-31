import ast, unittest
from mpynode._common.methods.maya_command import detect_commands, detect_demos
SRC = (
    "from mpynode._common.methods.maya_command import maya_command, maya_demo\n"
    "@maya_command(name='doThing')\n"
    "def do_thing(self, x=1):\n"
    "    return x\n"
    "@maya_demo(label='Demo')\n"
    "def demo_it(self):\n"
    "    return 1\n"
)
class TestTreeParam(unittest.TestCase):
    def test_commands_tree_matches_source(self):
        tree = ast.parse(SRC)
        self.assertEqual(detect_commands(SRC), detect_commands(SRC, tree=tree))
        self.assertEqual([c['name'] for c in detect_commands(SRC, tree=tree)], ['doThing'])
    def test_demos_tree_matches_source(self):
        tree = ast.parse(SRC)
        self.assertEqual(detect_demos(SRC), detect_demos(SRC, tree=tree))
if __name__ == "__main__":
    unittest.main()
