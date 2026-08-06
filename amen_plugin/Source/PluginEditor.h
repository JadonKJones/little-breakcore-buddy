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

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AmenDrummerEditor)
};
