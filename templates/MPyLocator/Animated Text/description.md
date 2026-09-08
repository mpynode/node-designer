# Animated Text

A text gizmo (`mPyLocator`) that puts a message in the viewport: the letters ride a travelling sine wave with a scrolling rainbow, trailed by sparkle points, a line ribbon and a pulsing halo. Good for a rig banner or a state readout. Selecting it flashes it white.

The motion runs off the timeline plus a slow wall-clock drift, so it keeps moving whether you scrub, play, or sit still.

## Inputs

* `displayText` -- your message. Blank shows `MPyNode!`.
* `loopFrames` -- one full cycle, in frames (default 60).
* `spacing` -- how far apart the letters sit.
* `waveHeight` -- how far the letters rise and fall. 0 keeps the text flat.

## Outputs

* The viewport drawing. Nothing is connected onward -- this is a gizmo, not a value.

## Create + Run demo

Sets the playback range to one loop and frames it.
