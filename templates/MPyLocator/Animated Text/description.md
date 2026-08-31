# Animated Text

A text gizmo (`mPyLocator`) that puts a message in the viewport: the letters ride a travelling sine wave with a scrolling rainbow, trailed by sparkle points, a line ribbon and a pulsing halo. Good for a rig banner or a state readout.

Type your message into `displayText`; blank shows `MPyNode!`. `loopFrames` (default 60) is one cycle in frames; `spacing` and `waveHeight` set the layout. Selecting the gizmo flashes it white.

The motion runs off the timeline plus a slow wall-clock drift, so `auto_refresh` keeps it going whether you scrub, play, or sit still. **Create + Run demo** sets the playback range to one loop and frames it.
