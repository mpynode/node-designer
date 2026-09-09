# ouch -- compile report

**Source node:** `ouch`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 20:45

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- 2 region(s) still marked incomplete |
| 3 AI optimize | **1.20x** over 2 round(s) -- re-measured: unmeasurable under the gate |

## The Python this was generated from

```python
# Name: Ouch!!!!  (port)
# When the arm bends the wrong way, play the audio clip on Qt's media player
# (async -- does NOT pause Maya) and paint the arm red. color = colour output.
#
# self.audioData is the SINGLE source of truth for playback. The async player is
# (re)built whenever the CONTENT of self.audioData changes -- so it always plays
# whatever is in the buffer, whether that came from the baked clip, a right-click
# "Load media" onto audioData, or a disk (re)load below. There is exactly ONE
# audio buffer: self.audioData (persistent).
#
# audioFile is an OPTIONAL loader: point it at a .wav / .mp3 / ... and that file
# is read INTO self.audioData. self.audioPath is a TEMPORARY session guard (never
# saved) that just remembers which path we have already loaded, so we do not
# re-read the same file from disk every frame.
#
# (Imports + the ouch_* helper functions live in the Init tab.)

# -- keep self.audioData in sync with an optional audioFile -------------------
# Guarded as a whole so a headless / Qt-less session -- or a not-yet-loaded Init
# namespace -- can never stop the colour output below from computing.
try:
    raw = self.audioFile or ""

    # First eval this session: a buffer we already carry (the baked clip, or a
    # right-click load that was saved) is authoritative -- adopt the current
    # audioFile as "already loaded" so a reopened scene never re-reads it from
    # disk and clobbers the buffer. Only a genuinely EMPTY buffer loads on open.
    if not hasattr(self, "audioPath"):
        self.audioPath = raw if getattr(self, "audioData", None) else None

    # Load from disk ONLY when audioFile names a path we have not already loaded
    # this session. Mark the guard even on failure so a bad path can't re-read
    # every frame.
    if raw != self.audioPath:
        self.audioPath = raw
        path = ouch_resolve_clip_path(raw)
        if path:
            data = ouch_load_bytes(path)
            if data is not None:
                self.audioData = data          # the ONE audio buffer (persistent)

    # (Re)build the async player whenever the BUFFER CONTENT changes -- covers a
    # disk reload AND a manual right-click "Load media" onto audioData. Latched
    # on a content hash so a Qt-less session doesn't retry it on every eval.
    data = getattr(self, "audioData", None)
    if data:
        sig = ouch_bytes_signature(data)
        if getattr(self, "_player_sig", None) != sig:
            self._player_sig = sig
            old = getattr(self, "_player", None)
            if old is not None:
                try:
                    old.stop()
                except Exception:
                    pass
            self._player = ouch_make_player(data, sig)
except Exception:
    pass

# -- colour + one-shot playback ----------------------------------------------
# Session-only latch so the bend audio plays once per bend (seeded here so a
# vanilla node -- or one whose Init namespace hasn't loaded -- never reads an
# unset self.pain in the red branch below).
if not hasattr(self, "pain"):
    self.pain = False

self.color = [0, 1, 0]
if self.angle < 0.165009870842:
    self.color = [1, 0, 0]
    if not self.pain:
        self.pain = True
        player = getattr(self, "_player", None)
        if player is not None:
            player.setPosition(0)
            player.play()
else:
    self.pain = False
    # Arm back in a safe position -- stop the clip if it is still playing.
    player = getattr(self, "_player", None)
    if player is not None:
        player.stop()
```

## Unfinished work in the generated C++

* **not translated:** the whole audio block (self.audioData / self.audioPath /
* **not translated:** player.setPosition(0)/play()/stop() have no C++ equivalent

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **0.001 ms** -> best **0.001 ms** (**1.20x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: **unmeasurable** -- baseline 0.003 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); nothing this small can be optimized against measurably. The speedup above was taken before the gate existed and cannot be reproduced under it. Moved per tick: `angle (angle)`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.001 ms | -- | -- |
| 01 | `drop_dead_string_read` | This node is neither elementwise nor query-shaped -- it is a two-branch scalar compare whose entire cost is per-call Maya API overhead, so the win is deleting the API calls that produce nothing: the unused audioFile MString read, the static-registry scan over `this`, and a dead zero-write to the colour output. | 1.30x | 1.20x | 9.1 min | ACCEPTED |
| 02 | `collapse_colour_branch` | This node has no array, geometry or query work at all -- compute() is one scalar read, one compare and a 3-float write -- so the only change worth making was collapsing the two set3Float call sites into one; the node was already at the harness's measurement floor. | 1.00x | 0.001 ms | 6.1 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `collapse_colour_branch` -- predicted 1.00x, **rejected: not faster**. The node is neither ELEMENTWISE nor QUERY shaped: its only inputs are a scalar angle and an unused string, and its only output is a 3-float colour. There is no N and no M, so no acceleration structure, no parallel map and no cross-evaluation cache can apply (the one input that matters, angle, is perturbed by the harness on every tick by design, so any cache would be a guaranteed miss and any output memo would be a parity failure). I predicted before measuring that nothing would move the number, and that the honest deliverable was a leaner-but-identical compute plus the evidence for why the floor is where it is.

### Rejected rounds

* `collapse_colour_branch` -- rejected: not faster. This node has no array, geometry or query work at all -- compute() is one scalar read, one compare and a 3-float write -- so the only change worth making was collapsing the two set3Float call sites into one; the node was already at the harness's measurement floor.

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0001)
* verified with 1 geo/string input(s) left at default (unwired, could not be synthesized): audioFile | authored @maya_test: 1/1 passed
* speed: compiled 0.006 ms vs interpreted 0.077 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/ouch/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/ouch/2_assisted.cpp       AI filled the unported region(s)
build/stages/ouch/3_optimized/00_baseline.cpp
build/stages/ouch/3_optimized/01_drop_dead_string_read.cpp
build/stages/ouch/3_optimized/02_collapse_colour_branch.cpp
build/source/ouch.cpp      SHIPPED
```
