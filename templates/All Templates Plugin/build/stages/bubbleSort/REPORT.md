# bubbleSort -- compile report

**Source node:** `bubbleSort`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# Name: Bubble Sort!  (port)
# Author: Eric Vignola - eric.vignola@gmail.com
#
# One bubble-sort pass per evaluation over n normalized random floats, where
# n = len(self.sort) = the number of connected outputs. Each output is lerped
# LIVE between minVal and maxVal, so dragging min/max rescales every output
# instantly (no re-sort). self.data / self.sorted are session-only.
#
# reset enum:  0 = False (sort one pass per eval, then hold sorted)
#              1 = True  (held reshuffle: regenerate every eval, never sorts)
#              2 = Auto  (sort, then auto-regenerate on completion -> loops
#                         forever with fresh patterns)
#
# (Imports live in the Init tab.)

n     = len(self.sort)
reset = self.reset

# (re)generate normalized [0, 1] data: first eval, output-count change,
# True (held reshuffle), or Auto once the previous pass finished sorting.
regen = (not hasattr(self, 'data')) or len(self.data) != n
if reset == 1:
    regen = True
if reset == 2 and getattr(self, 'sorted', False):
    regen = True

if regen:
    self.data   = [random.random() for _ in range(n)]
    self.sorted = False

# one bubble pass (skipped while held in True so it keeps reshuffling)
if reset != 1 and not self.sorted:
    self.sorted = True
    for i in range(n - 1):
        if self.data[i] > self.data[i + 1]:
            self.sorted = False
            self.data[i], self.data[i + 1] = self.data[i + 1], self.data[i]

self.text = 'SORTED!!!' if self.sorted else 'UNSORTED!!!'

# lerp each (partially) sorted float between the LIVE min/max
lo, hi = self.minVal, self.maxVal
self.sort = [lo + t * (hi - lo) for t in self.data]
```

## Files

```
build/stages/bubbleSort/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/bubbleSort/2_assisted.cpp       AI filled the unported region(s)
build/source/bubbleSort.cpp      SHIPPED
```
