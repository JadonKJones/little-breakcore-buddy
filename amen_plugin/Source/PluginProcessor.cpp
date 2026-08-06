#include "PluginProcessor.h"
#include "PluginEditor.h"
#include <cmath>

AmenDrummerProcessor::AmenDrummerProcessor()
    : AudioProcessor(BusesProperties()
                          .withInput("Input", juce::AudioChannelSet::stereo(), true)
                          .withOutput("Output", juce::AudioChannelSet::stereo(), true))
{
}

bool AmenDrummerProcessor::isBusesLayoutSupported(const BusesLayout& layout) const
{
    return layout.getMainOutputChannelSet() == juce::AudioChannelSet::stereo()
        || layout.getMainOutputChannelSet() == juce::AudioChannelSet::mono();
}

void AmenDrummerProcessor::prepareToPlay(double newSampleRate, int samplesPerBlock)
{
    sampleRate = newSampleRate;
    monoScratch.setSize(1, samplesPerBlock);

    kick.prepare(sampleRate, samplesPerBlock, BandDetector::Type::LowPass, 20.0f, 150.0f);
    snare.prepare(sampleRate, samplesPerBlock, BandDetector::Type::BandPass, 150.0f, 4000.0f);
    cymbal.prepare(sampleRate, samplesPerBlock, BandDetector::Type::HighPass, 4000.0f, 20000.0f);

    resetState();
}

void AmenDrummerProcessor::resetState()
{
    kick.reset();
    snare.reset();
    cymbal.reset();
}

void AmenDrummerProcessor::processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&)
{
    const int numChannels = buffer.getNumChannels();
    const int numSamples = buffer.getNumSamples();
    if (numSamples == 0)
        return;

    // Reset on transport start (stopped -> playing) and on loop-back
    // (position jumping backwards while still playing).
    if (auto* transport = getPlayHead())
    {
        if (auto position = transport->getPosition())
        {
            const bool isPlaying = position->getIsPlaying();
            const double posSeconds = position->getTimeInSeconds().orFallback(0.0);

            const bool justStartedPlaying = isPlaying && !wasPlaying;
            const bool loopedBack = isPlaying && wasPlaying && (posSeconds + 0.05 < lastKnownPositionSeconds);

            if (justStartedPlaying || loopedBack)
                resetState();

            wasPlaying = isPlaying;
            lastKnownPositionSeconds = posSeconds;
        }
    }

    debugBlockCount.fetch_add(1);
    debugNumChannels.store(numChannels);
    debugNumSamples.store(numSamples);

    // Downmix to mono, matching analyzer.py's mono analysis.
    if (monoScratch.getNumSamples() < numSamples)
        monoScratch.setSize(1, numSamples, false, false, true);

    auto* mono = monoScratch.getWritePointer(0);
    const float scale = 1.0f / (float)juce::jmax(1, numChannels);
    for (int i = 0; i < numSamples; ++i)
    {
        float sum = 0.0f;
        for (int ch = 0; ch < numChannels; ++ch)
            sum += buffer.getReadPointer(ch)[i];
        mono[i] = sum * scale;
    }

    const auto nowMs = juce::Time::getMillisecondCounter();

    kick.processBlock(mono, numSamples, nowMs);
    snare.processBlock(mono, numSamples, nowMs);
    cymbal.processBlock(mono, numSamples, nowMs);

    // Pass audio through unmodified -- this is an analysis/visualizer tap, not an effect.
    juce::ignoreUnused(buffer);
}

juce::AudioProcessorEditor* AmenDrummerProcessor::createEditor()
{
    return new AmenDrummerEditor(*this);
}

// This creates new instances of the plugin.
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new AmenDrummerProcessor();
}
