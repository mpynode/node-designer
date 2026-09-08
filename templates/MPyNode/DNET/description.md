# DNET Spring-Network Solver

A mass-spring network for rigging. Knots are points with goal transforms; links are springs between them. Each frame the solver settles the net, so free knots trail and jiggle behind whatever drives them -- soft secondary motion for lips, fleshy pads and membranes.

A knot is either anchored, meaning it snaps to its goal transform, or free, meaning the springs decide where it goes. You build a net entirely from the two commands below, so what the demos ship is exactly what you would assemble by hand.

## Inputs

* `matrices` -- one goal transform per knot. Driven by each knot's goal `worldMatrix`.
* `anchors` -- one weight per knot. Above 0 pins that knot to its goal; 0 lets the springs move it.
* `index0` / `index1` -- the two knots each link connects, one entry per link.
* `restLengths` -- the length each link wants to be, one per link. This is what the net settles toward.
* `tension` -- per-link stiffness. Higher is tighter and snappier.
* `push` / `pull` -- per-link asymmetry: how hard a link resists being compressed versus stretched. Use them to make a membrane that resists opening but folds easily, or the reverse.
* `iterations` -- how many solver passes per frame. More is more settled and slower.
* `tolerance` -- how close is close enough. The solver stops early once the net is moving less than this.
* `damping` -- how quickly motion bleeds off. Low keeps wobbling, high settles fast.
* `inverseMatrix` -- the space the results come back in. Wire the parent's `worldInverseMatrix` so the outputs land in that parent's space.
* `resetBuffer` -- set it to **True** to clear the stored state, after moving the rig or if the net has blown up.
* `evaluate` -- set it to **False** to freeze the solver where it is, without unhooking anything.
* `time` -- steps the simulation. Connect it to scene time.

## Outputs

* `positions` -- the solved knot positions, one per knot, in the space set by `inverseMatrix`. Connect each to its result transform.
* `lengths` -- each link's current length, one per link. Useful for driving a stretch value off how far a spring is from rest.
* `maxIterations` -- how many passes the last frame actually needed. Watch it to see whether `iterations` is set higher than necessary.
* `maxForce` -- the largest spring force on the last frame. A spike here is the warning sign before a net blows up.

## Commands

* `create_knot` -- creates one knot: a GOAL transform you place or drive, plus a RESULT child that rides the solved position, wired into the next free slot. Pass `draw_icon=True` and it also gets a visible icosahedron sized by its own `radius` attribute, so you can see the solved point.
* `create_link` -- springs every selected knot to the LAST-selected one. Select the spokes, shift-select the hub last, then run. Each link gets its own transform carrying its `tension`, `push` and `pull`, so you can tune springs individually.

**Build your own:** run `create_knot` a few times to drop knots, then select some spokes, shift-select a hub last, and run `create_link` to spring them together.

## Create + Run demo

Offers three showcases -- right-click the template for the submenu.

* **Grid Net** anchors the four corners of a 6x8 grid and animates one of them, so the net swings between the fixed corners and settles. Press play.
* **Layout Net (JSON)** rebuilds a 30-knot, 38-link mouth membrane from a captured layout and rigs it to a skull. The jaw and cranium drive the net: upper-lip knots follow the cranium, lower-lip knots the jaw, so opening the jaw splits each lip-seam pair.
* **Two Knots (Shapes)** is the minimal net -- two free knots, each tethered to a pair of anchors and linked to each other. Drag any anchor and the free knots follow springily.
