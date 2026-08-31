# hexAttribute -- compile report

**Source node:** `hexAttribute`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- 1 region(s) still marked incomplete |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# Name: Text Mesh Generator  (numpy-first port)
# Author: Eric Vignola - eric.vignola@gmail.com
# The `output` attribute is typed `hex`: assign plain text and the attr
# auto-encodes it to the space-separated UTF-8 hex a Maya `type` node
# consumes as mesh text -- no manual unicode -> hex step needed.

# Convert XYZ input (a numpy 3-vector) to rounded strings.
self.output = 'DRAG ME AROUND!\n'
self.output += 'X: %s\n' % round(float(self.inPosition[0]), self.decimals)
self.output += 'Y: %s\n' % round(float(self.inPosition[1]), self.decimals)
self.output += 'Z: %s\n' % round(float(self.inPosition[2]), self.decimals)
```

## Unfinished work in the generated C++

* **not translated:** CPython's str(float) switches to scientific notation

## Files

```
build/stages/hexAttribute/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/hexAttribute/2_assisted.cpp       AI filled the unported region(s)
build/source/hexAttribute.cpp      SHIPPED
```
