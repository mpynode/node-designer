# Mesh Regions

Highlight a named piece of a mesh -- a cheek, a brow, a shoulder -- as a coloured patch you can hover and click. Each gizmo (`mPyLocator`) binds one mesh and one component tag, and draws that tag's faces as an outlined patch, rebuilt every redraw so it tracks deformation. It floats just off the surface along the vertex normals (no Z-fighting) and shows only its outer silhouette.

Hovering lifts and recolours a patch (precise ray-versus-triangle test); selecting lifts it further. Because each region is its own gizmo, they highlight independently.

Connect a mesh into `inMesh` and name the region in `regionTag`. `offset`, `hoverOffset` and `selectOffset` are absolute world-unit lifts, so the pop is the same whether the tag covers three faces or three hundred. `defaultColor`, `hoverColor` and `selectColor` set the colours, and `alpha` the transparency.

**Create + Run demo** imports the bundled head model, resolves every component tag on it (the eight mouth regions -- `topLip`, `bottomLip`, their left/right halves, and `mouthLeft` / `mouthRight`), and builds one gizmo per tag, each wired to the mesh's `worldMesh[0]` and lit in its own colour.
