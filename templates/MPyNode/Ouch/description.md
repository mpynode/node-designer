# Ouch

Watches a joint angle and complains when the joint straightens or bends the wrong way. Wire a joint's rotation into `angle`: `color` stays green while the joint is bent, and flips to red with an audio clip when `angle` drops below a small threshold. Playback is non-blocking.

The sound lives in the persistent `audioData` buffer -- the single source of truth for playback -- so it travels with the scene and the player always plays whatever the buffer holds. Swap it two ways: point `audioFile` at another `.wav` / `.mp3`, or right-click `audioData` in the Variables tab and choose **Load media**. Audio needs an interactive Maya session.

**Create + Run demo** builds a skinned 3-joint arm, drives `angle` from the elbow and shades the mesh with `color`. It starts bent and green -- play the timeline and the arm turns red as the elbow straightens past the threshold.
