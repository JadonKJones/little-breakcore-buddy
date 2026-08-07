#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <array>
#include <utility>
#include "BinaryData.h"

/** Direct port of sprite.py's DrummerSprite state machine: kick is a brief
    overlay (using the "k" frame variants) on top of whatever snare/cymbal
    pose is currently active, rather than a pose of its own. Snare cycles
    its full 6-frame sequence; crash starts on the crash1/2 or crash3/4 pair
    depending on whichever of kick/snare preceded it. Runs on the message
    thread (the editor's timer), driven by onset timestamps from the processor. */
class DrummerSprite
{
public:
    DrummerSprite()
    {
        idleImage = loadImage(BinaryData::idle_png, BinaryData::idle_pngSize);
        idleKImage = loadImage(BinaryData::idlek_png, BinaryData::idlek_pngSize);

        snareImages = {
            loadImage(BinaryData::snare1_png, BinaryData::snare1_pngSize),
            loadImage(BinaryData::snare2_png, BinaryData::snare2_pngSize),
            loadImage(BinaryData::snare3_png, BinaryData::snare3_pngSize),
            loadImage(BinaryData::snare4_png, BinaryData::snare4_pngSize),
            loadImage(BinaryData::snare5_png, BinaryData::snare5_pngSize),
            loadImage(BinaryData::snare6_png, BinaryData::snare6_pngSize),
        };
        snareKImages = {
            loadImage(BinaryData::snare1k_png, BinaryData::snare1k_pngSize),
            loadImage(BinaryData::snare2k_png, BinaryData::snare2k_pngSize),
            loadImage(BinaryData::snare3k_png, BinaryData::snare3k_pngSize),
            loadImage(BinaryData::snare4k_png, BinaryData::snare4k_pngSize),
            loadImage(BinaryData::snare5k_png, BinaryData::snare5k_pngSize),
            loadImage(BinaryData::snare6k_png, BinaryData::snare6k_pngSize),
        };

        crashImages = {
            loadImage(BinaryData::crash1_png, BinaryData::crash1_pngSize),
            loadImage(BinaryData::crash2_png, BinaryData::crash2_pngSize),
            loadImage(BinaryData::crash3_png, BinaryData::crash3_pngSize),
            loadImage(BinaryData::crash4_png, BinaryData::crash4_pngSize),
        };
        crashKImages = {
            loadImage(BinaryData::crash1k_png, BinaryData::crash1k_pngSize),
            loadImage(BinaryData::crash2k_png, BinaryData::crash2k_pngSize),
            loadImage(BinaryData::crash3k_png, BinaryData::crash3k_pngSize),
            loadImage(BinaryData::crash4k_png, BinaryData::crash4k_pngSize),
        };
    }

    /** label: "kick", "snare", or "cymbal". Call once per onset, in time order. */
    void trigger(const juce::String& label, juce::uint32 onsetMs)
    {
        if (label == "kick")
        {
            const juce::uint32 kickGap = onsetMs - lastKickMs;
            kickCycleIndex = (kickGap < kKickRollGapMs) ? kickCycleIndex + 1 : 0;
            lastKickMs = onsetMs;
            lastPercType = "kick";
            if (kickCycleIndex >= kKickRollThreshold)
            {
                // A roll (2nd+ rapid kick): kick takes over as the active pose,
                // same as snare/cymbal would, instead of just a brief overlay.
                lastSnareFrame = (kickCycleIndex % 2 == 0) ? 5 : 6;
                lastPoseLabel = "kick";
                lastPoseTimeMs = onsetMs;
            }
            return;
        }

        if (label != "snare" && label != "cymbal")
            return;

        const juce::uint32 gap = onsetMs - lastPoseTimeMs;
        const bool fresh = lastPoseLabel.isEmpty() || gap >= kIdleTimeoutMs;
        const bool same = !fresh && lastPoseLabel == label;

        if (label == "cymbal")
        {
            if (same)
                cycleIndex++;
            else
            {
                cycleIndex = 0;
                crashPair = crashPairFor(lastSnareFrame, lastPercType);
            }
            lastCrashFrame = (cycleIndex % 2 == 0 ? crashPair.first : crashPair.second) + 1;
        }
        else // snare
        {
            if (same)
                cycleIndex++;
            else
            {
                cycleIndex = 0;
                snareStartIndex = snareStartFor(lastCrashFrame);
            }
            lastPercType = "snare";
            lastSnareFrame = (snareStartIndex + cycleIndex) % 6 + 1;
        }

        lastPoseLabel = label;
        lastPoseTimeMs = onsetMs;
    }

    void reset()
    {
        lastPoseLabel.clear();
        lastPoseTimeMs = 0;
        cycleIndex = 0;
        crashPair = { 0, 1 };
        lastPercType.clear();
        lastKickMs = 0;
        kickCycleIndex = 0;
        lastSnareFrame = 0;
        lastCrashFrame = 0;
        snareStartIndex = 0;
    }

    const juce::Image& getFrame(juce::uint32 nowMs) const
    {
        const bool overlayActive = (nowMs - lastKickMs) <= kKickOverlayMs;

        const bool isIdle = lastPoseLabel.isEmpty() || (nowMs - lastPoseTimeMs) > kIdleTimeoutMs;
        if (isIdle)
            return overlayActive ? idleKImage : idleImage;

        if (lastPoseLabel == "kick")
        {
            // Mid-roll: behaves just like a snare pose, alternating snare5/snare6.
            return snareImages[(size_t)(kickCycleIndex % 2 == 0 ? 4 : 5)];
        }

        if (lastPoseLabel == "snare")
        {
            const auto& frames = overlayActive ? snareKImages : snareImages;
            return frames[(size_t)((snareStartIndex + cycleIndex) % (int)frames.size())];
        }

        if (lastPoseLabel == "cymbal")
        {
            const auto& frames = overlayActive ? crashKImages : crashImages;
            return frames[(size_t)(cycleIndex % 2 == 0 ? crashPair.first : crashPair.second)];
        }

        return idleImage;
    }

private:
    static constexpr juce::uint32 kIdleTimeoutMs = 120;   // matches sprite.py IDLE_TIMEOUT = 0.12s
    static constexpr juce::uint32 kKickOverlayMs = 60;    // matches sprite.py KICK_OVERLAY_DURATION = 0.06s
    static constexpr juce::uint32 kKickRollGapMs = 120;   // matches sprite.py KICK_ROLL_GAP = 0.12s
    static constexpr int kKickRollThreshold = 1;           // matches sprite.py KICK_ROLL_THRESHOLD

    /** The sprite's arm position has to continue naturally: whichever
        snare-look frame (1-4) was last shown decides which crash frame the
        swing starts on. snare5/6 (lastSnareFrame not in 1-4) fall back to
        the old kick/snare default. */
    static std::pair<int, int> crashPairFor(int precedingSnareFrame, const juce::String& precedingPercType)
    {
        switch (precedingSnareFrame)
        {
            case 1: return { 1, 0 }; // snare1 -> crash2, then crash1
            case 2: return { 0, 1 }; // snare2 -> crash1, then crash2
            case 3: return { 3, 2 }; // snare3 -> crash4, then crash3
            case 4: return { 2, 3 }; // snare4 -> crash3, then crash4
            default: break;
        }
        if (precedingPercType == "kick") return { 2, 3 };
        return { 0, 1 }; // default / "snare"
    }

    /** Reverse of crashPairFor: whichever crash frame (1-4) was last shown
        decides which snare frame (0-based index) a fresh snare run starts
        on. Anything else (no crash yet) starts at snare1. */
    static int snareStartFor(int precedingCrashFrame)
    {
        switch (precedingCrashFrame)
        {
            case 1: return 1; // crash1 -> snare2
            case 2: return 0; // crash2 -> snare1
            case 3: return 3; // crash3 -> snare4
            case 4: return 2; // crash4 -> snare3
            default: return 0;
        }
    }

    static juce::Image loadImage(const void* data, int size)
    {
        return juce::ImageCache::getFromMemory(data, size);
    }

    juce::Image idleImage, idleKImage;
    std::array<juce::Image, 6> snareImages, snareKImages;
    std::array<juce::Image, 4> crashImages, crashKImages;

    juce::String lastPoseLabel;   // "snare" or "cymbal" -- kick never becomes the base pose
    juce::uint32 lastPoseTimeMs = 0;
    int cycleIndex = 0;
    std::pair<int, int> crashPair { 0, 1 };
    juce::String lastPercType;    // most recent of "kick"/"snare", used to pick crashPair
    juce::uint32 lastKickMs = 0;
    int kickCycleIndex = 0;       // consecutive rapid kicks -- alternates snare5/snare6 during a kick roll
    int lastSnareFrame = 0;       // 1-6, whichever snare-look frame was most recently shown (0 = none yet)
    int lastCrashFrame = 0;       // 1-4, whichever crash frame was most recently shown (0 = none yet)
    int snareStartIndex = 0;      // 0-based, which snare frame a fresh snare run starts on
};
