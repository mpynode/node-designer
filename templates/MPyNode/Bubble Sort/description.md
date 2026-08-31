# Bubble Sort

A visual sorting toy. It holds a list of random values and runs one bubble-sort pass per evaluation, so wire `time` in and press play to watch the list sort itself. The list length follows how many outputs you connect, and values are remapped live between `minVal` (default 1) and `maxVal` (default 100).

`reset` picks the behaviour: **False** sorts once and holds, **True** keeps reshuffling, **Auto** (the default) reshuffles the moment the list is sorted. The values come out on `sort`, with a `SORTED!!!` / `UNSORTED!!!` status string on `text`.

**Create + Run demo** builds a row of 100 cubes one unit apart in X, each cube's height driven by one sorted value.
