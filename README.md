# little breakcore buddy

A drum-break onset analyzer and a little animated drummer that reacts to kick/snare/cymbal hits in real time — as a desktop app, and as a VST3 plugin that sits on an FL Studio channel.

Two pieces sharing the same core idea:

- **[amen_analyzer](amen_analyzer/)** — a Python/Pygame desktop app. Load a WAV, get automatic kick/snare/cymbal onset detection, scrub/zoom the waveform, manually correct mislabeled hits, and export JSON/CSV/an animated MP4.
- **[amen_plugin](amen_plugin/)** — a JUCE/C++ VST3 ("Drummer") that does the same detection live on whatever audio passes through the channel it's on.

## What's new in v1.1

- **Rolls actually get detected now.** The old analyzer's time resolution was too coarse to see individual hits in a fast roll at all — they blurred into one smooth curve before detection even ran. Fixed by analyzing at ~2.9ms resolution instead of ~11.6ms.
- **Way fewer false hits.** A single global sensitivity couldn't tell a real quiet hit from background noise in one section while also catching every hit in a loud roll in another. Now runs a confident "strict" pass everywhere, and only falls back to a more sensitive pass to fill in a genuinely long gap — which is what an unresolved roll looks like.
- **No more phantom hits in silence.** Added an absolute floor on the audio's actual level, so a stray blip during true silence can't get flagged just because it's "loud" relative to near-zero background.
- **Kick/snare band swap.** Testing showed the low band consistently reads snares better and the mid band reads kicks better on real material — flipped which band drives which label.
- **Kick rolls animate properly.** A rapid kick roll now takes over the sprite's pose entirely (alternating snare5/snare6) instead of just flickering a brief overlay on whatever was already showing.
- **Snare/crash arm continuity.** The drummer's arm position now carries naturally between a snare hit and the crash that follows it (and back), instead of resetting.
- **Waveform shows the drums track, not the full mix** — matches what the onset markers are actually timed against.
- **Onset markers stay visible** even against a loud, densely-filled waveform (they used to blend into a same-colored fill during dense rolls).
- **Plugin gets the same treatment**, adapted for real time: a causal two-tier strict/loose detector and the same absolute silence floor, since it can't scan the whole track ahead of time like the desktop app can.

## How it works

Both share the same three-layer approach:

1. **Detection** — incoming audio is split into three frequency bands (kick ~150-4000Hz, snare ~20-150Hz, cymbal 4000Hz+), each with its own onset detector, so a loud hi-hat doesn't drown out a quiet kick. A two-tier strict/loose threshold (with the loose pass only kicking in to fill a genuinely long gap) keeps normal passages clean while still catching fast rolls.
2. **State machine** — each detected hit feeds a small state machine tracking the current pose and idle timeout:
   - Snare cycles through its full 6-frame sequence; a fresh crash run picks its starting frame (crash1/2 vs crash3/4) based on whichever snare frame preceded it, and vice versa — the arm position carries over between the two instead of resetting.
   - A single kick briefly overlays a `_k` frame variant on top of whatever pose is already active. A **kick roll** (2+ rapid kicks in a row) instead takes over as its own pose, alternating snare5/snare6, same as snare/cymbal would.
3. **Render** — the desktop app draws this to a Pygame window (or bakes it into an MP4 with ffmpeg); the plugin draws it live into its JUCE editor.

## Desktop app

Prebuilt `AmenAnalyzer.exe` (no Python needed) is on the [Releases page](https://github.com/JadonKJones/little-breakcore-buddy/releases). To run from source:

```bash
cd amen_analyzer
pip install -r requirements.txt
python main.py <drums_only.wav> [full_song.wav]
```

Passing a second file lets onset detection run on an isolated drum stem (cleaner detection) while playback/waveform/video export use the full mix. The waveform shown is always the drums-only track, since that's what the onset markers are timed against.

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

## Known limitations

- The plugin runs in real time and can't scan ahead the way the offline analyzer can, so its detection — while much closer than before — still won't quite match the desktop app's accuracy in every case.

## Project page

Up and running at [jadonkjones.github.io/little-breakcore-buddy](https://jadonkjones.github.io/little-breakcore-buddy/).
