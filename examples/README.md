#PROVIDED EXAMPLES

###./node-designer/examples/bubbleSort.ma
* Scrub the timeline to see bubblre sort in action.
* Select the node and change some variables to see the effects.


###./node-designer/examples/gameOfLifeNode.ma
* Scrub the timeline to see Conway's game of life in action.
* Select the node and change some variables to see the effects.


###./node-designer/examples/ouchNode.ma
* !!! requires the pyaudio module !!!
* Sound data is stored on self.
* "Breaking" the arm causes the arm to color red and the computer will play an "ouch!" sample.


###./node-designer/examples/quaternionSpineNode.ma
* Scrub the timeline to see the spine in action.
* Select the node and change some variables to see the effects.


###./node-designer/examples/splineNode.ma
* Implementation of DeBoor's algorithm to draw a spline.
* Select the node and change some variables to see the effects.
* Append more controllers/point samples to the node to see the effects.


###./node-designer/examples/springChainNode.ma
* A simple physics chain
* Drag the head controller around to see the chain in action.
* Append more chain elements to the node to make the chain longer.
* Select the node and change some variables to see the effects.


###./node-designer/examples/textMeshGeneratorNode.ma
* Move the text around to see the position get pushed to text in real time.
* Mesh is generated with Maya's "type" node. Text comes from MPyNode's string output.


###./node-designer/examples/unitSphereCollisionNode.ma
* Move/Rotate/Scale the sphere into the grid to see result.
* Data in self stored the grid's positions.
* Select the node and change some variables to see the effects.


###./node-designer/examples/numpy_examples/autoFrame.ma
* !!! requires numpy !!!
* Autoframes a given mesh to a camera's with/height.
* On init, the node will automatically open an "autoFramed" viewport.
* Orient the perspective camera to see the result on the autoFramed viewport.
* Select the autoFramed camera, changed the width/height values to see the result.
* Scrub the timeline to see the camera autoFrame as the mesh deforms.


###./node-designer/examples/numpy_examples/boids.ma
* !!! requires numpy !!!
* Craig Reynolds's Boid algorithm.
* Scrub the timeline to see the spine in action.
* Select the node and change some variables to see the effects.


###./node-designer/examples/other_examples/textureSwitchNode/textureSwitchNode.ma
* On init node will query the current scene location and set a local texture path.
* Node will look for all textures under local path.
* Select the grid, and change textureIndex to switch which texture is displayed.
* Add pictures to the texture path, select the grid and toggle "refreshList" to add pictures to the list.


