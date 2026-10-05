# Virtual Computer Control v8

Windows desktop controller using MediaPipe hand tracking, SpeechRecognition/PyAudio voice input, PyAutoGUI, web search, and YouTube result resolution.

## Setup
1. Windows 10/11, Python 3.13 64-bit.
2. Run `setup.bat`.
3. Run `run.bat`.
4. Allow Camera and Microphone permissions.

## Gesture controls
- Index finger: move cursor
- Thumb/index pinch: left click
- 3 fingers: right click
- Open hand: scroll
- Fist: click

## Voice examples
- Search latest Java tutorials in Google
- Search YouTube for relaxing music
- Play Believer
- Play Believer on YouTube
- Play Believer on Spotify
- Open Chrome
- Open Calculator
- Type hello world
- Click / right click / double click
- Minimize / maximize / close window
- Copy / paste / select all
- New tab / close tab / refresh
- Volume up / volume down / mute
- Screenshot

`play <song>` uses yt-dlp only to resolve the first YouTube result and then opens the actual YouTube watch URL; it does not download the media.


### MediaPipe note
This version uses the MediaPipe Hand Landmarker Tasks API and downloads the official hand landmark model during setup. This avoids the removed legacy `mp.solutions` API in current MediaPipe releases.
