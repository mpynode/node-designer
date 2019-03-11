# Node Designer
A Universal Python node for Autodesk's Maya.

Node Designer simplifies the technical overhead required by MPxNode, allowing users to easily develop nodes with Maya's Python API.

[![Node Designer](https://i.imgur.com/zMVItXHh.png)](https://vimeo.com/322550713)


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
Or use the provided helper to create a shelf button:
```
import mpylib
mpylib.ui.initShelf()
```
You can also use the scripting API directly:
```
from mpylib.nodes import MPyNode
node = MPyNode()
node.addInputAttr('inFloat','float', is_array=False, keyable=True)
node.addOutputAttr('outFloat','float', is_array=False, keyable=True)
node.setExpression('outFloat = inFloat')
```
Or subclass MPyNode and customize it to fit your needs:
```
from mpylib.nodes import MPyNode
class NewNodeClass(MPyNode):
    INIT_INPUT_ATTRS    = {'inFloat': {'attr_type':'float', 'is_array':False}}
    INIT_OUTPUT_ATTRS   = {'outFloat':{'attr_type':'float', 'is_array':False}}
    INIT_EXPRESSION_STR = 'outFloat = inFloat'
                      
new_node = NewNodeClass()
all_new_nodes = NewNodeClass.ls()
```

## Documentation 
https://mpynode.bitbucket.io/

## Authors
* **Gene Hansen**  (gene.hansen@gmail.com)
* **Eric Vignola** (eric.vignola@gmail.com)

## License
BSD 3-Clause License:
Copyright (c)  2019, Gene Hansen, Eric Vignola 
All rights reserved. 

Redistribution and use in source and binary forms, with or without 
modification, are permitted provided that the following conditions are met:


1. Redistributions of source code must retain the above copyright notice, 
   this list of conditions and the following disclaimer.
   
2. Redistributions in binary form must reproduce the above copyright notice, 
   this list of conditions and the following disclaimer in the documentation 
   and/or other materials provided with the distribution.
   
3. Neither the name of copyright holders nor the names of its 
   contributors may be used to endorse or promote products derived from 
   this software without specific prior written permission.
   
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE 
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE 
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE 
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL 
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR 
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER 
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, 
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE 
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

