# little breakcore buddy

A drum-break onset analyzer and a little animated drummer that reacts to kick/snare/cymbal hits in real time — as a desktop app, and as a VST3 plugin that sits on an FL Studio channel.

Two pieces sharing the same core idea:

- **[amen_analyzer](amen_analyzer/)** — a Python/Pygame desktop app. Load a WAV, get automatic kick/snare/cymbal onset detection, scrub/zoom the waveform, manually correct mislabeled hits, and export JSON/CSV/an animated MP4.
- **[amen_plugin](amen_plugin/)** — a JUCE/C++ VST3 ("Drummer") that does the same detection live on whatever audio passes through the channel it's on.

## How it works

Both share the same three-layer approach:

1. **Detection** — incoming audio is split into three frequency bands (kick ~20-150Hz, snare ~150-4000Hz, cymbal 4000Hz+), each with its own onset detector, so a loud hi-hat doesn't drown out a quiet kick.
2. **State machine** — each detected hit feeds a small state machine tracking the current pose and idle timeout:
   - Snare cycles through its full 6-frame sequence; a fresh crash run picks its starting frame (crash1/2 vs crash3/4) based on whichever snare frame preceded it, and vice versa — the arm position carries over between the two instead of resetting.
   - A single kick briefly overlays a `_k` frame variant on top of whatever pose is already active. A **kick roll** (2+ rapid kicks in a row) instead takes over as its own pose, alternating snare3/snare4, same as snare/cymbal would.
3. **Render** — the desktop app draws this to a Pygame window (or bakes it into an MP4 with ffmpeg); the plugin draws it live into its JUCE editor.

## Desktop app

Prebuilt `AmenAnalyzer.exe` (no Python needed) is on the [Releases page](https://github.com/JadonKJones/little-breakcore-buddy/releases). To run from source:

```bash
cd amen_analyzer
pip install -r requirements.txt
python main.py <drums_only.wav> [full_song.wav]
```

Passing a second file lets onset detection run on an isolated drum stem (cleaner detection) while playback/waveform/video export use the full mix.

Controls: `SPACE` play/pause · click a marker to select, `K`/`S`/`C` to relabel, `Delete` to remove · `Ctrl+Z`/`Ctrl+Y` undo/redo · `Ctrl+S`/`Ctrl+O` save/load JSON · `Ctrl+E` export CSV · `Ctrl+V` export animated video.

## VST3 plugin

Prebuilt `Drummer.vst3` is also on the [Releases page](https://github.com/JadonKJones/little-breakcore-buddy/releases) — copy it into `C:\Program Files\Common Files\VST3\`, rescan plugins in FL Studio, and drop it on a channel like Fruity Dance.

To build from source (JUCE 7 + CMake, auto-fetched):

```bash
cd amen_plugin
cmake -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
```

The built plugin lands at `build/AmenDrummer_artefacts/Release/VST3/Drummer.vst3`.

## Known issues

- **Drum rolls** (rapid repeated hits, especially kicks) don't always animate correctly yet — actively being worked on.

## Project page

Up and running at [jadonkjones.github.io/little-breakcore-buddy](https://jadonkjones.github.io/little-breakcore-buddy/).
