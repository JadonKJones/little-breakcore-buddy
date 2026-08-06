# Amen Drummer — PoC VST3

Minimal JUCE plugin: drop it on a channel in FL Studio, and it flashes a red
box whenever it detects a transient in the incoming audio (broadband energy
onset detection — no kick/snare/cymbal classification yet, that's the next
step once this works end-to-end).

## What's here

- `CMakeLists.txt` — pulls JUCE 7.0.12 automatically via CMake FetchContent
  (no manual JUCE download needed; the VST3 SDK ships inside JUCE).
- `Source/PluginProcessor.{h,cpp}` — audio thread: tracks a fast-attack/
  slow-release envelope and fires an onset whenever a block's RMS jumps
  above `envelope * 1.8`, debounced to 80ms.
- `Source/PluginEditor.{h,cpp}` — GUI: a 60fps timer repaints a box that
  lights up for 150ms after each detected onset.

## One-time setup

You have Visual Studio 2022 Community (with the MSVC compiler) already.
You're missing CMake:

```bash
winget install Kitware.CMake
```

Restart your terminal after installing so `cmake` is on PATH.

## Build

From this directory:

```bash
cmake -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
```

First configure will take a few minutes — it clones JUCE from GitHub.

The built VST3 will land at:

```
build/AmenDrummer_artefacts/Release/VST3/Amen Drummer.vst3
```

## Install into FL Studio

Copy (or symlink) that `.vst3` folder into your VST3 plugin directory,
typically:

```
C:\Program Files\Common Files\VST3\
```

Then in FL Studio: rescan plugins (Options > Manage Plugins > Find
Plugins), drop "Amen Drummer" on your drum channel like you would Fruity
Dance, and play the track.

## Next steps (not in this PoC)

- Port the 3-band onset split + kick/snare/cymbal heuristics from
  `analyzer.py` into `processBlock` (bandpass filters + separate envelope
  followers per band).
- Port the `DrummerSprite` state machine from `sprite.py` and load the PNG
  frames via JUCE's `juce::ImageCache`/binary resources instead of a
  colored box.
- Swap the flashing box for the actual sprite once classification works.
