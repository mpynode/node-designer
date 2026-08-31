# Spring Chain

A spring-and-mass solver for secondary motion: tails, ropes, jiggle. The first point chases the `driver`, each one after chases the point in front, so motion ripples down the chain and settles. `tension`, `damping`, `gravity` and `mass` shape it; `minDistance` / `maxDistance` clamp how far a point drifts from the one ahead. Positions come out on the `driven` vector array, one per output. Drive it with `time`; `resetBuffer` clears the stored state.

**Create + Run demo** builds a keyframed driver locator and a 100-sphere chain wired to `driven`, gravity zeroed, tuning attributes on the driver's channel box.
