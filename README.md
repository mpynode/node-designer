# MPyNode
A Universal Python node for Autodesk's Maya.

MPyNode simplifies all the technical overhead required by MPxNode, allowing users to easily develop nodes with Maya's Python API.

### Feature Highlights
* Fully scriptable Python API.
* UI interface for rapid MPyNode prototyping.
* Dynamically created input/output attributes.
* Pickelable import/export formats to save node templates to disk.
* Data stored on `self` can be marked to remain in the scene between sessions.
* Built-in profiler.

### Usage
Open the Node Designer to create your first node:
```
from mpylib.ui import NDMainWindow
win = NDMainWindow()
win.show()
```
Or use the scripting API directly:
```
from mpylib.nodes import MPyNode
node = MPyNode()
node.addInputAttr('inFloat','float', is_array=False, keyable=True)
node.addOutputAttr('outFloat','float', is_array=False, keyable=True)
node.setExpression('outFloat = inFloat')
```
Or by subclassing:
```
from mpylib.nodes import MPyNode
class NewNodeClass(MPyNode):
    INIT_INPUT_ATTRS    = {'inFloat':{'attr_type':'float', 'is_array':False}}
    INIT_OUTPUT_ATTRS   = {'outFloat':{'attr_type':'float', 'is_array':False}}
    INIT_EXPRESSION_STR = 'outFloat = inFloat'
                      
new_node = NewNodeClass()
all_new_nodes = NewNodeClass.ls()
```

## Documentation
**coming soon**

## Authors
* **Gene Hansen**  (gene.hansen@gmail.com)
* **Eric Vignola** (eric.vignola@gmail.com)

## License
All Rights Reserved
