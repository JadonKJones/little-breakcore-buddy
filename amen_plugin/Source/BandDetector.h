#pragma once

#include <juce_dsp/juce_dsp.h>
#include <atomic>
#include <cmath>

/** Runs one frequency band (low/mid/high, matching analyzer.py's kick/snare/
    cymbal split) through a fixed filter, tracks a fast-attack/fast-release
    envelope on the filtered signal, and fires an onset when the current
    block jumps sufficiently above that envelope. */
class BandDetector
{
public:
    enum class Type { LowPass, BandPass, HighPass };

    void prepare(double newSampleRate, int maxBlockSize, Type type, float freqLowHz, float freqHighHz)
    {
        sampleRate = newSampleRate;
        scratch.setSize(1, maxBlockSize);

        if (type == Type::LowPass)
        {
            stage1.coefficients = juce::dsp::IIR::Coefficients<float>::makeLowPass(sampleRate, freqHighHz);
            twoStage = false;
        }
        else if (type == Type::HighPass)
        {
            stage1.coefficients = juce::dsp::IIR::Coefficients<float>::makeHighPass(sampleRate, freqLowHz);
            twoStage = false;
        }
        else // BandPass, implemented as cascaded high-pass + low-pass (wide bands don't
             // behave well as a single biquad bandpass with a low Q)
        {
            stage1.coefficients = juce::dsp::IIR::Coefficients<float>::makeHighPass(sampleRate, freqLowHz);
            stage2.coefficients = juce::dsp::IIR::Coefficients<float>::makeLowPass(sampleRate, freqHighHz);
            twoStage = true;
        }

        juce::dsp::ProcessSpec spec { sampleRate, (juce::uint32)maxBlockSize, 1 };
        stage1.prepare(spec);
        stage2.prepare(spec);

        reset();
    }

    void reset()
    {
        stage1.reset();
        stage2.reset();
        envelope = 0.0f;
        lastTriggerMs = 0;
    }

    /** mono: single-channel input for this block. Returns true if this call triggered an onset. */
    bool processBlock(const float* mono, int numSamples, juce::uint32 nowMs)
    {
        auto* work = scratch.getWritePointer(0);
        std::copy(mono, mono + numSamples, work);

        juce::dsp::AudioBlock<float> block(scratch.getArrayOfWritePointers(), 1, (size_t)numSamples);
        juce::dsp::ProcessContextReplacing<float> context(block);
        stage1.process(context);
        if (twoStage)
            stage2.process(context);

        float sumSquares = 0.0f;
        for (int i = 0; i < numSamples; ++i)
            sumSquares += work[i] * work[i];
        const float blockRms = std::sqrt(sumSquares / (float)juce::jmax(1, numSamples));

        debugRms.store(blockRms);

        bool triggered = false;
        if (blockRms > kMinLevel
            && blockRms > envelope * kThresholdRatio
            && (nowMs - lastTriggerMs) > (juce::uint32)kMinGapMs)
        {
            lastTriggerMs = nowMs;
            lastOnsetMs.store(nowMs);
            triggered = true;
        }

        if (blockRms > envelope)
        {
            envelope = blockRms;
        }
        else
        {
            const float blockSeconds = (float)numSamples / (float)sampleRate;
            const float releaseCoeff = std::exp(-blockSeconds / kReleaseSeconds);
            envelope = envelope * releaseCoeff + blockRms * (1.0f - releaseCoeff);
        }
        debugEnvelope.store(envelope);

        return triggered;
    }

    std::atomic<juce::uint32> lastOnsetMs { 0 };
    std::atomic<float> debugRms { 0.0f };
    std::atomic<float> debugEnvelope { 0.0f };

private:
    double sampleRate = 44100.0;
    bool twoStage = false;
    juce::dsp::IIR::Filter<float> stage1, stage2;
    juce::AudioBuffer<float> scratch;

    float envelope = 0.0f;
    juce::uint32 lastTriggerMs = 0;

    static constexpr float kThresholdRatio = 1.5f;
    static constexpr float kMinLevel = 0.008f; // filtered bands carry less energy than broadband
    static constexpr int kMinGapMs = 50;
    static constexpr float kReleaseSeconds = 0.05f;
};
