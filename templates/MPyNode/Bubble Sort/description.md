# Bubble Sort

A visual sorting toy. It holds a list of random values and runs one bubble-sort pass per evaluation, so wire `time` in and press play to watch the list sort itself. The list length follows how many `sort` outputs you connect.

## Inputs

* `time` -- drives one sort pass per frame. Connect it to scene time.
* `minVal` / `maxVal` -- the range the values are remapped into (defaults 1 and 100).
* `reset` -- what happens when the list finishes. **False** sorts once and holds, **True** keeps reshuffling, **Auto** (the default) reshuffles the moment the list is sorted.

## Outputs

* `sort` -- the current values, one per connected element. The array length sets the list length.
* `text` -- a status string, either sorted or unsorted.

## Create + Run demo

Builds a row of 100 cubes one unit apart in X, each cube's height driven by one sorted value.
