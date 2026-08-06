#pragma once

#include <juce_audio_processors/juce_audio_processors.h>
#include "PluginProcessor.h"
#include "DrummerSprite.h"

class AmenDrummerEditor : public juce::AudioProcessorEditor,
                           private juce::Timer
{
public:
    explicit AmenDrummerEditor(AmenDrummerProcessor&);
    ~AmenDrummerEditor() override = default;

    void paint(juce::Graphics&) override;
    void resized() override {}

private:
    void timerCallback() override;
    void pollForNewOnsets();

    AmenDrummerProcessor& processor;
    DrummerSprite sprite;

    juce::uint32 lastSeenKickMs = 0;
    juce::uint32 lastSeenSnareMs = 0;
    juce::uint32 lastSeenCymbalMs = 0;

    // A snare and a cymbal firing within this many ms of each other are
    // almost always spectral leakage from one physical hit into both bands,
    // not two real hits -- both compete for the sprite's base pose, so
    // letting both through causes a pose switch immediately followed by
    // another, reading as noise. Kick is exempt: it only overlays.
    static constexpr juce::uint32 kSnareCymbalDedupeMs = 15;
    juce::uint32 lastPercOnsetMs = 0;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AmenDrummerEditor)
};
