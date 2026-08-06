#pragma once

#include <juce_audio_processors/juce_audio_processors.h>
#include <atomic>
#include "BandDetector.h"

class AmenDrummerProcessor : public juce::AudioProcessor
{
public:
    AmenDrummerProcessor();
    ~AmenDrummerProcessor() override = default;

    void prepareToPlay(double sampleRate, int samplesPerBlock) override;
    void releaseResources() override {}
    void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;

    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }

    const juce::String getName() const override { return "Drummer"; }
    bool acceptsMidi() const override { return false; }
    bool producesMidi() const override { return false; }
    double getTailLengthSeconds() const override { return 0.0; }

    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram(int) override {}
    const juce::String getProgramName(int) override { return {}; }
    void changeProgramName(int, const juce::String&) override {}

    void getStateInformation(juce::MemoryBlock&) override {}
    void setStateInformation(const void*, int) override {}

    bool isBusesLayoutSupported(const BusesLayout& layout) const override;

    // Matches analyzer.py's kick/snare/cymbal frequency-band split.
    BandDetector kick;   // 20-150 Hz, low-pass
    BandDetector snare;  // 150-4000 Hz, band-pass
    BandDetector cymbal; // 4000 Hz+, high-pass

    std::atomic<juce::int64> debugBlockCount { 0 };
    std::atomic<int> debugNumChannels { 0 };
    std::atomic<int> debugNumSamples { 0 };

private:
    double sampleRate = 44100.0;
    juce::AudioBuffer<float> monoScratch;

    bool wasPlaying = false;
    double lastKnownPositionSeconds = 0.0;
    void resetState();

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AmenDrummerProcessor)
};
