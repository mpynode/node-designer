# ouch -- compile report

**Source node:** `ouch`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- 2 region(s) still marked incomplete |
| 3 AI optimize | not run |

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
        path           = ouch_resolve_clip_path(raw)
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
            old              = getattr(self, "_player", None)
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
        player    = getattr(self, "_player", None)
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

* **not translated:** audioFile -> self.audioData sync needs open()/file I/O
* **not translated:** the async Qt media player (ouch_make_player /

## Files

```
build/stages/ouch/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/ouch/2_assisted.cpp       AI filled the unported region(s)
build/source/ouch.cpp      SHIPPED
```
