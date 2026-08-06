#pragma once

#include <juce_dsp/juce_dsp.h>
#include <atomic>
#include <cmath>
#include <vector>

/** Real-time spectral-flux onset detector for one frequency band (matching
    analyzer.py's kick/snare/cymbal band split). Unlike a simple RMS-vs-
    envelope threshold, this compares the magnitude spectrum frame-to-frame
    (restricted to the band's frequency bins) and fires when that spectral
    change rises well above its own recent rolling average -- much closer to
    what librosa's onset_strength actually computes offline. */
class BandDetector
{
public:
    void prepare(double newSampleRate, int /*maxBlockSize*/, float freqLowHz, float freqHighHz)
    {
        sampleRate = newSampleRate;

        // Bin 0 (DC) and the Nyquist bin are packed specially by JUCE's real-only
        // FFT (not as a normal [2*bin, 2*bin+1] pair), so both are avoided here.
        const double binHz = sampleRate / (double)kFftSize;
        binLow = juce::jlimit(1, kNumBins - 2, (int)std::round(freqLowHz / binHz));
        binHigh = juce::jlimit(binLow, kNumBins - 2, (int)std::round(freqHighHz / binHz));

        reset();
    }

    void reset()
    {
        std::fill(ringBuffer.begin(), ringBuffer.end(), 0.0f);
        std::fill(prevMagnitude.begin(), prevMagnitude.end(), 0.0f);
        std::fill(fluxHistory.begin(), fluxHistory.end(), 0.0f);
        ringWritePos = 0;
        samplesSinceHop = 0;
        fluxHistoryPos = 0;
        fluxHistorySum = 0.0f;
        lastTriggerMs = 0;
    }

    /** mono: single-channel input for this block, in host block order. */
    void processBlock(const float* mono, int numSamples, juce::uint32 nowMs)
    {
        for (int i = 0; i < numSamples; ++i)
        {
            ringBuffer[(size_t)ringWritePos] = mono[i];
            ringWritePos = (ringWritePos + 1) % kFftSize;

            if (++samplesSinceHop >= kHopSize)
            {
                samplesSinceHop = 0;
                analyseFrame(nowMs);
            }
        }
    }

    std::atomic<juce::uint32> lastOnsetMs { 0 };
    std::atomic<float> debugRms { 0.0f };      // repurposed: current flux
    std::atomic<float> debugEnvelope { 0.0f }; // repurposed: adaptive threshold

private:
    static constexpr int kFftOrder = 11;
    static constexpr int kFftSize = 1 << kFftOrder; // 2048
    static constexpr int kHopSize = kFftSize / 2;   // 1024 (~50% overlap)
    static constexpr int kNumBins = kFftSize / 2 + 1;

    static constexpr int kFluxHistorySize = 24; // rolling window for the adaptive floor
    static constexpr float kThresholdRatio = 1.6f; // flux must exceed rolling-average floor * this
    static constexpr float kMinFlux = 0.0025f;      // ignore near-silence
    static constexpr int kMinGapMs = 40;            // debounce

    void analyseFrame(juce::uint32 nowMs)
    {
        // Unwrap the ring buffer into chronological order for the FFT.
        for (int i = 0; i < kFftSize; ++i)
            fftData[(size_t)i] = ringBuffer[(size_t)((ringWritePos + i) % kFftSize)];
        std::fill(fftData.begin() + kFftSize, fftData.end(), 0.0f);

        window.multiplyWithWindowingTable(fftData.data(), (size_t)kFftSize);
        fft.performRealOnlyForwardTransform(fftData.data());

        float flux = 0.0f;
        for (int bin = binLow; bin <= binHigh; ++bin)
        {
            const float re = fftData[(size_t)(2 * bin)];
            const float im = fftData[(size_t)(2 * bin + 1)];
            const float mag = std::sqrt(re * re + im * im);

            const float diff = mag - prevMagnitude[(size_t)bin];
            if (diff > 0.0f)
                flux += diff;

            prevMagnitude[(size_t)bin] = mag;
        }
        flux /= (float)(binHigh - binLow + 1);

        debugRms.store(flux);

        const float adaptiveFloor = fluxHistorySum / (float)kFluxHistorySize;
        debugEnvelope.store(adaptiveFloor * kThresholdRatio);

        if (flux > kMinFlux
            && flux > adaptiveFloor * kThresholdRatio
            && (nowMs - lastTriggerMs) > (juce::uint32)kMinGapMs)
        {
            lastTriggerMs = nowMs;
            lastOnsetMs.store(nowMs);
        }

        fluxHistorySum += flux - fluxHistory[(size_t)fluxHistoryPos];
        fluxHistory[(size_t)fluxHistoryPos] = flux;
        fluxHistoryPos = (fluxHistoryPos + 1) % kFluxHistorySize;
    }

    double sampleRate = 44100.0;
    int binLow = 0, binHigh = 0;

    juce::dsp::FFT fft { kFftOrder };
    juce::dsp::WindowingFunction<float> window { (size_t)kFftSize, juce::dsp::WindowingFunction<float>::hann };

    std::array<float, kFftSize> ringBuffer {};
    int ringWritePos = 0;
    int samplesSinceHop = 0;

    std::array<float, kFftSize * 2> fftData {};
    std::array<float, kNumBins> prevMagnitude {};

    std::array<float, kFluxHistorySize> fluxHistory {};
    int fluxHistoryPos = 0;
    float fluxHistorySum = 0.0f;

    juce::uint32 lastTriggerMs = 0;
};
