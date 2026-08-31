# springChain -- compile report

**Source node:** `springChain`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# Name: Simple spring solver  (numpy-first port)
# Author: Eric Vignola - eric.vignola@gmail.com
# self.initialized (session-only) avoids an integration on the first eval after
# load. self.position / self.velocity persist. driven = vector array output.
#
# (Imports + helper functions live in the Init tab.)

# ---------------------------- Main ----------------------------#

# Fresh (vanilla) node, or one whose buffers were never restored: seed the
# spring buffers so the first integration has state. The original relied on
# restored stored vars; gallery templates ship vanilla (no stored vars).
if not hasattr(self, 'velocity'):
    self.velocity = [np.zeros(3) for _ in range(len(self.driven))]
    self.position = [np.zeros(3) for _ in range(len(self.driven))]

# First eval after a load: just mark initialized + push the stored buffer out
# (self.initialized is session-only -> absent again on the next load).
if not hasattr(self, 'initialized'):
    self.initialized = True

else:
    n = len(self.driven)

    if self.resetBuffer:
        self.velocity = [np.zeros(3) for _ in range(n)]
        self.position = [np.zeros(3) for _ in range(n)]

    elif len(self.velocity) < n:
        for _ in range(len(self.velocity), n):
            self.velocity.append(np.zeros(3))
            self.position.append(np.zeros(3))

    elif len(self.velocity) > n:
        self.velocity = self.velocity[:n]
        self.position = self.position[:n]

    else:
        # Initial drag
        self.position[0], self.velocity[0] = spring(
            self.driver, self.position[0], self.velocity[0],
            self.gravity, self.tension, self.mass, self.damping, self.minDistance, self.maxDistance)

        # Spring forces down the chain
        for i in range(1, n):
            self.position[i], self.velocity[i] = spring(
                self.position[i - 1], self.position[i], self.velocity[i],
                self.gravity, self.tension, self.mass, self.damping, self.minDistance, self.maxDistance)


# Output positions from the stored buffer
self.driven[:] = np.asarray(self.position, dtype=float)
```

## Files

```
build/stages/springChain/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/springChain/2_assisted.cpp       AI filled the unported region(s)
build/source/springChain.cpp      SHIPPED
```
