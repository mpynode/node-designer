# DNET Spring-Network Solver

A mass-spring network for rigging. Knots carry goal transforms (`matrices[]`);
links (`index0`/`index1`) are springs with rest lengths (`restLengths`). Each
frame the solver settles the net, so free knots trail and jiggle behind whatever
drives them -- soft secondary motion for lips, fleshy pads and membranes.
Anchored knots (`anchors[i] > 0`) snap to their live goal. Solved parent-space
positions come out on `positions[]`.

Every scene here is built from just two authoring commands -- **create_knot** and
**create_link** -- so the demos are exactly what you would assemble by hand. A
knot is a GOAL transform (its `worldMatrix` drives `matrices[i]`, an `anchored`
float drives `anchors[i]`) plus a RESULT child riding `positions[i]`; a link is a
transform carrying its own per-link `tension`/`push`/`pull` (wired to the matching
solver slots) with `inheritsTransform` off. With `draw_icon=True` a knot also gets
an icosahedron: a hidden PROXY shape on the result child worldspace-blendShaped
onto a visible DUPLICATE on the goal (sized by a `radius` attr), so the visible
icon deforms onto the solved knot; a link gets a degree-1 line whose two CVs track
the knots' result children (a `decomposeMatrix` per CV).

**Create + Run demo** offers three showcases (right-click the template for the
submenu).

*Grid Net* anchors the four corners of a 6x8 grid and animates one of them, so
the net swings between the fixed corners and settles -- play the timeline. It is
built lightweight (`draw_icon=False`): a goal, a result child and a tiny marker
sphere, no icosahedron.

*Layout Net (JSON)* rebuilds a 30-knot / 38-link mouth membrane from a captured
layout with the full shape scheme (`draw_icon=True`), then rigs it to a skull.
`skull.ma` is imported and its **jaw** and **cranium** drive the net: a `midway`
transform, positioned from the jaw and rotated halfway between the two, carries
the mouth corners; the upper-lip knots follow the cranium and the lower-lip knots
the jaw, so opening the jaw splits each coincident lip-seam pair.

*Two Knots (Shapes)* is the minimal net: TWO FREE knots, each tethered to a pair
of anchors and linked to each other -- six knots, five links, the same shape
scheme end to end. Drag any anchor and the free knots follow springily, their
icosahedra deforming onto the solved positions.

**Build your own** (Methods tab): run **create_knot** a few times to drop knots
(each is a goal with an `anchored` weight wired into `matrices[]`/`anchors[]` plus
a result child on `positions[]`; pass `draw_icon=True` for the icosahedron icon,
sized by a `radius` attr that defaults to 0.1), then select some spoke knots,
shift-select a hub last, and run **create_link** to spring them together (each link
seeds `index0`/`index1`/`restLengths` and carries its own per-link `tension`,
`push` and `pull` -- the only channels left editable, since the link transform's
translate/rotate/scale + visibility are locked and hidden; `draw_icon=True` adds
the line).

Tuning: `iterations` (relaxation cap), `damping` (under-relaxation step),
`tolerance` (convergence threshold), `tension` (per-link contraction),
`push`/`pull` (per-link compression / stretch resistance -- one slot per link,
neutral 1.0), `resetBuffer` (defaults True: re-seed free knots from their live
goals each eval; set False to carry state and let free knots continue).
