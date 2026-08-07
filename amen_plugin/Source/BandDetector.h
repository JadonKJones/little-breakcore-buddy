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

    // Kept short deliberately: with kHopSize=1024 (~23ms/frame), a 24-frame
    // history would span ~550ms. During a fast roll several genuine hits land
    // inside that single window, so the rolling average rises to match the
    // roll itself and individual hits stop clearing threshold*ratio -- the
    // same failure mode as librosa's default ~1.16s pre_avg/post_avg window
    // (see analyzer.py). A ~140ms window stays local enough to still resolve
    // hits within a roll instead of averaging them away.
    static constexpr int kFluxHistorySize = 6;
    static constexpr float kMinFlux = 0.0025f;      // ignore near-silence
    static constexpr int kMinGapMs = 20;            // debounce -- real hits can land ~23ms apart

    // Two-tier detection, adapted for real time: analyzer.py's offline
    // version can scan the *whole* track to find gaps and retroactively fill
    // them with a looser threshold -- a plugin can't look into the future.
    // The causal equivalent: STRICT is the normal/primary threshold (fewer
    // false positives in ordinary passages). If nothing has cleared it for
    // longer than GAP_FILL, that's exactly what an unresolved roll looks
    // like in real time too, so LOOSE gets a chance to catch it until
    // *something* fires again (which immediately puts us back in strict
    // mode -- no need to wait out a fixed cooldown).
    static constexpr float kStrictRatio = 2.2f;
    static constexpr float kLooseRatio = 1.6f;
    static constexpr juce::uint32 kGapFillMs = 350;

    // A relative ratio-over-local-average can still fire in genuine silence:
    // in a near-silent stretch, even a tiny stray blip is trivially "many
    // times" its own near-zero local neighborhood. This is an absolute floor
    // on the RAW audio's own level (matches analyzer.py's ABSOLUTE_SILENCE_RMS),
    // so it stays meaningful regardless of how the relative math shakes out.
    static constexpr float kAbsoluteSilenceRms = 0.02f;

    void analyseFrame(juce::uint32 nowMs)
    {
        // Unwrap the ring buffer into chronological order for the FFT.
        for (int i = 0; i < kFftSize; ++i)
            fftData[(size_t)i] = ringBuffer[(size_t)((ringWritePos + i) % kFftSize)];
        std::fill(fftData.begin() + kFftSize, fftData.end(), 0.0f);

        // Raw-sample RMS, computed before windowing/FFT overwrite fftData in place.
        float sumSquares = 0.0f;
        for (int i = 0; i < kFftSize; ++i)
            sumSquares += fftData[(size_t)i] * fftData[(size_t)i];
        const float rawRms = std::sqrt(sumSquares / (float)kFftSize);
        const bool notSilent = rawRms >= kAbsoluteSilenceRms;

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

        const bool gapTooLong = (nowMs - lastTriggerMs) > kGapFillMs;
        const float ratio = gapTooLong ? kLooseRatio : kStrictRatio;
        debugEnvelope.store(adaptiveFloor * ratio);

        if (flux > kMinFlux
            && flux > adaptiveFloor * ratio
            && notSilent
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
