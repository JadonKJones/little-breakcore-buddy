import librosa as lr
import numpy as np
from scipy.ndimage import maximum_filter1d, uniform_filter1d


class DrumAnalyzer:
    """Detects drum hits using per-frequency-band onset detection.

    A single shared onset envelope is dominated by cymbal/hi-hat transients,
    which drown out kick and snare hits. Detecting onsets separately in the
    low/mid/high bands catches all three instead.
    """

    BANDS = {
        "snare": (20, 150),
        "kick": (150, 4000),
        "cymbal": (4000, None),
    }

    # librosa's default hop_length (512, ~11.6ms/frame at 44.1kHz) is too
    # coarse to resolve a fast roll at all -- hits ~20-25ms apart just blur
    # into one smooth rising plateau in the envelope, invisible to any
    # peak-picker no matter how it's tuned. This hop gives ~2.9ms/frame,
    # fine enough to see individual hits as distinct spikes again.
    HOP_LENGTH = 128

    PEAK_WINDOW_SECONDS = 0.010  # local-max window (each side) -- how close two hits can be and still both register
    AVG_WINDOW_SECONDS = 0.090   # local-average window -- how "local" the adaptive floor is
    WAIT_SECONDS = 0.015         # minimum spacing between accepted hits (debounce)

    # Two-tier detection: a single global sensitivity can't serve both a
    # normal passage and a fast roll at once. A ratio/floor loose enough to
    # resolve every hit in a roll also fires on trivial texture (hi-hat
    # decay, room tone, minor dynamics) everywhere else; a ratio/floor tight
    # enough to stay quiet in normal passages misses real hits packed into
    # a roll. So: the STRICT pass is the primary result (confident, sparse,
    # low false-positive rate). The LOOSE pass only gets used to fill in
    # spans where STRICT left a genuinely long gap (> GAP_FILL_THRESHOLD) --
    # which is exactly what an unresolved roll looks like -- rather than
    # applying loose detection everywhere.
    STRICT_RATIO = 3.2
    STRICT_MIN_LEVEL_FRACTION = 0.3
    LOOSE_RATIO = 2.3
    LOOSE_MIN_LEVEL_FRACTION = 0.2
    GAP_FILL_THRESHOLD_SECONDS = 0.35

    # A relative ratio-over-local-average can still fire in genuine silence:
    # in a near-silent stretch, even a tiny stray blip (bleed, room tone, a
    # single loud non-drum transient) is trivially "many times" its own
    # near-zero local neighborhood. This is an absolute floor on the RAW
    # audio's own level (not the onset envelope), so it stays meaningful
    # regardless of how the relative math shakes out.
    ABSOLUTE_SILENCE_RMS = 0.02

    # A snare and a cymbal landing within this many seconds of each other are
    # almost always spectral leakage from one physical hit into both bands,
    # not two real hits -- both compete for the sprite's "base pose", so
    # letting both through causes a pose switch immediately followed by
    # another one, which reads as noise rather than a real roll. Kick is
    # exempt: it only overlays the current pose, so a kick landing alongside
    # a snare/cymbal is harmless and worth keeping.
    SNARE_CYMBAL_DEDUPE_WINDOW = 0.015

    def __init__(self, sr):
        self.sr = sr
        self.onsets = []  # list of (time, label), sorted, deduped

    def detect_onsets(self, audio_data):
        """Runs per-band onset detection and returns a single chronological
        list of (time, label). Kick/snare/cymbal are independent channels --
        a kick and a cymbal landing at the same instant are both kept (not
        collapsed to one winner), since the sprite treats kick as an overlay
        on top of whatever snare/cymbal pose is active, not a competing pose."""
        raw_rms = lr.feature.rms(y=audio_data, hop_length=self.HOP_LENGTH, frame_length=2048)[0]

        band_hits = []
        for label, (fmin, fmax) in self.BANDS.items():
            fmax = fmax or (self.sr // 2)
            onset_env = lr.onset.onset_strength(
                y=audio_data, sr=self.sr, fmin=fmin, fmax=fmax, hop_length=self.HOP_LENGTH
            )
            times = self._detect_band(onset_env, raw_rms)
            for t in times:
                band_hits.append((float(t), label))

        band_hits.sort(key=lambda h: h[0])

        deduped = []
        last_perc_time = None
        for t, label in band_hits:
            if label in ("snare", "cymbal"):
                if last_perc_time is not None and t - last_perc_time < self.SNARE_CYMBAL_DEDUPE_WINDOW:
                    continue
                last_perc_time = t
            deduped.append((t, label))

        self.onsets = deduped
        return self.onsets

    def _detect_band(self, envelope, raw_rms):
        strict_frames = self._pick_peaks(envelope, raw_rms, self.STRICT_RATIO, self.STRICT_MIN_LEVEL_FRACTION)
        strict_times = lr.frames_to_time(strict_frames, sr=self.sr, hop_length=self.HOP_LENGTH)

        loose_frames = self._pick_peaks(envelope, raw_rms, self.LOOSE_RATIO, self.LOOSE_MIN_LEVEL_FRACTION)
        loose_times = lr.frames_to_time(loose_frames, sr=self.sr, hop_length=self.HOP_LENGTH)

        final = list(strict_times)
        for i in range(len(strict_times) - 1):
            if strict_times[i + 1] - strict_times[i] > self.GAP_FILL_THRESHOLD_SECONDS:
                final.extend(
                    t for t in loose_times if strict_times[i] < t < strict_times[i + 1]
                )

        return sorted(final)

    def _pick_peaks(self, envelope, raw_rms, ratio, min_level_fraction):
        """librosa.onset.onset_detect's peak-picking (via its `delta`
        parameter) is fundamentally additive: a frame counts as an onset if
        it exceeds a *local average + fixed amount*. That shape can't win
        both ways at once -- a delta small enough to catch quiet-ish real
        hits also fires on trivial noise in loud sections, and a delta big
        enough to stay quiet in loud sections misses real hits in anything
        that isn't the single loudest passage in the whole track (made worse
        by onset_detect's default normalize=True, which rescales by one
        global max before applying delta at all).

        What a drum hit actually looks like regardless of the section's
        overall loudness is *relative*: a spike that's some multiple of its
        own recent local average, not a fixed additive amount above it. So
        this picks local maxima and keeps ones that are `ratio` times their
        local average, which stays consistent whether the passage is quiet
        or a wall of noise.
        """
        frame_seconds = self.HOP_LENGTH / self.sr
        peak_window_frames = max(1, round(self.PEAK_WINDOW_SECONDS / frame_seconds))
        avg_window_frames = max(1, round(self.AVG_WINDOW_SECONDS / frame_seconds))
        wait_frames = max(1, round(self.WAIT_SECONDS / frame_seconds))

        local_max = maximum_filter1d(
            envelope, size=2 * peak_window_frames + 1, mode="nearest"
        )
        local_avg = uniform_filter1d(
            envelope, size=avg_window_frames, mode="nearest"
        )
        min_level = min_level_fraction * np.mean(envelope)

        n = min(len(envelope), len(raw_rms))
        not_silent = raw_rms[:n] >= self.ABSOLUTE_SILENCE_RMS

        is_peak = (envelope >= local_max) & (envelope >= local_avg * ratio) & (envelope >= min_level)
        is_peak = is_peak[:n] & not_silent
        candidates = np.nonzero(is_peak)[0]

        picks = []
        last_pick = -10 ** 9
        for i in candidates:
            if i - last_pick >= wait_frames:
                picks.append(i)
                last_pick = i

        return np.array(picks, dtype=int)
