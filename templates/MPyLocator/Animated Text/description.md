# Animated Text

A text gizmo (`mPyLocator`) that puts a message in the viewport: the letters ride a travelling sine wave with a scrolling rainbow, trailed by sparkle points, a line ribbon and a pulsing halo. Good for a rig banner or a state readout.

Type your message into `displayText`; blank shows `MPyNode!`. `loopDuration` is wall-clock seconds per loop (default 1; 2 is slower, -1 runs in reverse, 0 freezes); `spacing` and `waveHeight` set the layout. Selecting the gizmo flashes it white.

The motion runs off the wall clock (`self.wallclock`), never the timeline: it looks the same at idle, while scrubbing and in every playback mode, and the compiled node matches it exactly. **Create + Run demo** frames it.
