# Mesh Regions

Highlight a named piece of a mesh -- a cheek, a brow, a shoulder -- as a coloured patch you can hover and click. Each gizmo (`mPyLocator`) binds one mesh and one component tag, and draws that tag's faces as an outlined patch, rebuilt every redraw so it tracks deformation. It floats just off the surface along the vertex normals, so there is no Z-fighting, and shows only its outer silhouette.

Hovering lifts and recolours a patch; selecting lifts it further. Each region is its own gizmo, so they highlight independently.

## Inputs

* `inMesh` -- the mesh to read. Connect its `worldMesh[0]`.
* `regionTag` -- the name of the component tag to draw. This is what picks the patch.
* `offset` -- how far off the surface the patch floats at rest, in world units.
* `hoverOffset` / `selectOffset` -- the lift when hovered and when selected. Absolute, so the pop is the same whether the tag covers three faces or three hundred.
* `hoverDur` -- how long the hover lift takes.
* `defaultColor` / `hoverColor` / `selectColor` -- the patch fill in each state.
* `outlineColor` / `outlineHoverColor` / `outlineSelectColor` -- the silhouette colour in each state.
* `alpha` -- patch transparency.

## Outputs

* The viewport drawing, plus the hover and selection response. Nothing is connected onward -- this is a gizmo, not a value.

## Commands

* `setup` -- binds the gizmo to a mesh and a tag from your selection. Offered as **Run setup on selection**.

## Create + Run demo

Imports the bundled head model, resolves every component tag on it -- the eight mouth regions `topLip`, `bottomLip`, their left and right halves, and `mouthLeft` / `mouthRight` -- and builds one gizmo per tag, each lit in its own colour.
