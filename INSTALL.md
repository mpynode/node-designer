#INSTALLATION INSTRUCTIONS
#-------------------------

1) Clone/Download https://bitbucket.org/mpynode/node-designer/src/release/ 

2) Copy the following to a location listed under MAYA_PLUGIN_PATH
* ./node-designer/plug-ins/_mpynode
* ./node-designer/plug-ins/mpynode_plugin.py
```
MAYA_PLUGIN_PATH default locations

Windows
<user’s directory>/Documents/Maya/<version>/plug-ins
<user’s directory>/Documents/Maya/plug-ins

macOS
~/Library/Preferences/Autodesk/Maya/<version>/plug-ins
~/Library/Preferences/Autodesk/Maya/plug-ins

Linux
$MAYA_APP_DIR/Maya/<version>/plug-ins
$MAYA_APP_DIR/Maya/plug-ins
```

3) Copy the following to a location listed under PYTHONPATH
* ./node-designer/scripts/mpylib
```
PYTHONPATH default locations
Windows
<user’s directory>/My Documents/Maya/projects/default/mel
<user’s directory>/My Documents/Maya/<version>/scripts
<user’s directory>/My Documents/Maya/scripts
<user’s directory>/My Documents/Maya/<version>/presets
<user’s directory>/My Documents/Maya/<version>/prefs/shelves
<user’s directory>/My Documents/Maya/<version>/prefs/markingMenus

macOS
~/Library/Preferences/Autodesk/Maya/<version>
~/Library/Preferences/Autodesk/Maya

Linux
/usr/autodesk/userconfig/Maya/<version>/scripts
/usr/autodesk/userconfig/Maya/scripts
$MAYA_APP_DIR/Maya/<version>/scripts
$MAYA_APP_DIR/Maya/scripts
$MAYA_APP_DIR/Maya/<version>/prefs/shelves
```

4) Launch Node Designer directly
```
from mpylib.ui import NDMainWindow
win = NDMainWindow()
win.show()
```

5) Optionally, create a shelf button with this helper
```
import mpylib
mpylib.ui.initShelf()
```

6) Use the API directly to create nodes, or subclass for full integration into your pipeline.
```
# Direct API calls
from mpylib.nodes import MPyNode
node = MPyNode()
node.addInputAttr('inFloat','float', is_array=False, keyable=True)
node.addOutputAttr('outFloat','float', is_array=False, keyable=True)
node.setExpression('outFloat = inFloat')


# Subclass
from mpylib.nodes import MPyNode
class NewNodeClass(MPyNode):
    INIT_INPUT_ATTRS    = {'inFloat': {'attr_type':'float', 'is_array':False}}
    INIT_OUTPUT_ATTRS   = {'outFloat':{'attr_type':'float', 'is_array':False}}
    INIT_EXPRESSION_STR = 'outFloat = inFloat'
                      
new_node = NewNodeClass()
all_new_nodes = NewNodeClass.ls()
```

