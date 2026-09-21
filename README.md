# Node Designer
A Universal Python node for Autodesk's Maya. 

Node Designer simplifies the technical overhead required by MPxNode, allowing users to easily develop nodes with Maya's Python API. As a Python node, it exposes the plugin's compute block in the form of an expression, with input/output plugs dynamically populated.

New in version 2.0: 
- 12 genuine Maya node types to achieve complex tasks such as custom deformers and geometry generators.
- AI Assistance to write and compile C++ plugins! 

**Coming from 1.x?** Scenes built with Node Designer 1.x open directly: each node is upgraded in place when the scene loads, and the Script Editor lists what changed. Code that imported `mpylib` has to be ported to numpy or `mpynode.api`. Take the 1.x plug-in and `mpylib` off Maya's paths first, since both versions register the `mPyNode` node type and only one can load per session.

## Authors
* **Gene Hansen**  (gene.hansen@gmail.com)
* **Eric Vignola** (eric.vignola@gmail.com)

Found this useful? [Buy us a coffee :)](https://buymeacoffee.com/ericvignola) ☕


## Install

1. **Put the repo anywhere on disk.** All paths below are relative to the repo root.

2. **Set the two paths** before launching Maya:


   ```bash
   # macos
   export MAYA_PLUG_IN_PATH="$PWD/plug-ins:$MAYA_PLUG_IN_PATH"
   export PYTHONPATH="$PWD/scripts:$PYTHONPATH"
   ```
   ```bat
   rem windows
   set MAYA_PLUG_IN_PATH=%cd%\plug-ins;%MAYA_PLUG_IN_PATH%
   set PYTHONPATH=%cd%\scripts;%PYTHONPATH%
   ```

3. **Or copy the repo's `userSetup.py` into your Maya user scripts folder**, then point it
   back at the repo with `MPYNODE_PROJECT_DIR`:

   ```bash
   # macos
   cp userSetup.py ~/Library/Preferences/Autodesk/maya/2026/scripts/   # macOS
   cp userSetup.py ~/maya/2026/scripts/                                # Linux
   export MPYNODE_PROJECT_DIR="$PWD"
   ```

   ```bat
   rem windows
   copy userSetup.py "%USERPROFILE%\Documents\maya\2026\scripts\"
   set MPYNODE_PROJECT_DIR=%CD%
   ```

   Already have a `userSetup.py`? Append this repo's contents to it instead.

4. **Optional — add a shelf button:**

   ```python
   from mpynode.ui import shelf
   shelf.install_shelf_button()
   ```

## Quick start

**Launch Node Designer**

```python
from mpynode.ui.mpynode_designer import show_designer
show_designer()
```
And start building new nodes, or browse any of the provided templates.

**Or use the API**

```python
from mpynode import MPyNode

n = MPyNode.create(name="myCalc")
n.add_input_attr("a", "double")
n.add_input_attr("b", "double")
n.add_output_attr("sum", "double")
n.set_compute_expression("""
self.sum = self.a + self.b
""")
```


## How it works

Each node stores its Python as text on a plug, so the source travels with the scene and
there is nothing to import or deploy. Attributes you add at runtime cannot use Maya's
`attributeAffects` (that is class-init-time only), so MPyNode installs DG callbacks that
reproduce the same dirty propagation automatically. 

Compiling walks the node's Python AST
and lowers it directly to C++, falling back to an LLM only for constructs it cannot
translate deterministically. You can then opt-in for further LLM assisted optimization passes,
which adaptively attempt to optimize the C++ code's performance. 

Full detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Templates

37 templates in `templates/`, at least one for every node type, each with a runnable demo.
Browse them in the Designer's **Templates** tab.

Source code for each template is provided. To compile them yourself — see [INSTALL.md](INSTALL.md).

## Documentation

| Document | What it covers |
|---|---|
| [docs/index.md](docs/index.md) | The full API — every node type, attribute types, worked recipes |
| [docs/CHEATSHEET.md](docs/CHEATSHEET.md) | Quick reference for the Python API: create, attributes, expressions, stored vars, compile |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the framework and the compiler are built |
| [INSTALL.md](INSTALL.md) | Install variants, environment variables, troubleshooting |
| [docs/PORTING.md](docs/PORTING.md) | Per-platform build status and the Windows / Linux recipes |
| [docs/node_types/](docs/node_types/) | One design note per node type |
| [docs/notes/](docs/notes/) | Contributor design notes for work that is scoped but not built |


## License
BSD 3-Clause License:
Copyright (c)  2019-2026, Gene Hansen, Eric Vignola 
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