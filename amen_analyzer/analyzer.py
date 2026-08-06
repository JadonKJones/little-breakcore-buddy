import librosa as lr
import numpy as np


class DrumAnalyzer:
    """Detects drum hits using per-frequency-band onset detection.

    A single shared onset envelope is dominated by cymbal/hi-hat transients,
    which drown out kick and snare hits. Detecting onsets separately in the
    low/mid/high bands catches all three instead.
    """

    BANDS = {
        "kick": (20, 150),
        "snare": (150, 4000),
        "cymbal": (4000, None),
    }

    def __init__(self, sr):
        self.sr = sr
        self.onsets = []  # list of (time, label), sorted, deduped

    def detect_onsets(self, audio_data):
        """Runs per-band onset detection and returns a single chronological
        list of (time, label). Kick/snare/cymbal are independent channels --
        a kick and a cymbal landing at the same instant are both kept (not
        collapsed to one winner), since the sprite treats kick as an overlay
        on top of whatever snare/cymbal pose is active, not a competing pose."""
        band_hits = []
        for label, (fmin, fmax) in self.BANDS.items():
            fmax = fmax or (self.sr // 2)
            onset_env = lr.onset.onset_strength(y=audio_data, sr=self.sr, fmin=fmin, fmax=fmax)
            frames = lr.onset.onset_detect(
                onset_envelope=onset_env,
                sr=self.sr,
                units="frames",
                backtrack=True,
            )
            times = lr.frames_to_time(frames, sr=self.sr)
            for t in times:
                band_hits.append((float(t), label))

        band_hits.sort(key=lambda h: h[0])
        self.onsets = band_hits
        return self.onsets
