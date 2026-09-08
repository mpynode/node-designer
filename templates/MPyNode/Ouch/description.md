# Ouch

Watches a joint angle and complains when the joint straightens or bends the wrong way. Wire a joint's rotation into `angle`: the colour stays green while the joint is bent, and flips to red with an audio clip when the angle drops below a small threshold. Playback does not block the scene.

The sound lives in the node's persistent `audioData` variable, so it travels with the scene and the player always plays whatever that buffer holds. Swap it two ways: point `audioFile` at another `.wav` or `.mp3`, or right-click `audioData` on the Variables tab and choose **Load media**. Audio needs an interactive Maya session.

## Inputs

* `angle` -- the joint angle to watch. Wire the joint's rotation here.
* `audioFile` -- a `.wav` or `.mp3` to load into the buffer, replacing the shipped clip.

## Outputs

* `color` -- green while the joint is bent, red once it straightens past the threshold. Connect it to a shader.

## Create + Run demo

Builds a skinned three-joint arm, drives `angle` from the elbow and shades the mesh with `color`. It starts bent and green -- play the timeline and the arm turns red as the elbow straightens.
