import os
import pygame

ANIMATION_DIR = os.path.join(os.path.dirname(__file__), "..", "animation frames")

IDLE_TIMEOUT = 0.12  # seconds since last hit before returning to idle (also resets cycle/pattern)

# Pairs of snare-frame indices (0-based) used depending on the recent hit pattern.
PAIRS = {
    "snare": (0, 1),       # consecutive snares: snare1, snare2
    "kick": (2, 3),        # consecutive kicks: snare3, snare4
    "alternate": (4, 5),   # kick/snare alternating: snare5, snare6
}

# Which crash pair to start on, based on the note that preceded the crash.
CRASH_PAIRS = {
    "snare": (0, 1),  # crash1, crash2
    "kick": (2, 3),   # crash3, crash4
}


class DrummerSprite:
    def __init__(self, size=None):
        self.frames = {
            "idle": self._load("idle.png", size),
            "snare": [self._load(f"snare{i}.png", size) for i in range(1, 7)],
            "crash": [self._load(f"crash{i}.png", size) for i in range(1, 5)],
        }

        self.last_label = None  # "kick", "snare", or "cymbal"
        self.last_time = -999.0
        self.cycle_index = 0
        self.category = None  # "kick", "snare", or "alternate" -- only meaningful for kick/snare hits
        self.crash_pair = CRASH_PAIRS["snare"]
        self.last_perc_label = None  # most recent kick/snare label, survives through crash hits

    def _load(self, filename, size):
        path = os.path.join(ANIMATION_DIR, filename)
        image = pygame.image.load(path).convert_alpha()
        if size is not None:
            image = pygame.transform.smoothscale(image, size)
        return image

    def trigger(self, label, onset_time):
        """Call once, in onset-time order, each time playback crosses an onset."""
        gap = onset_time - self.last_time
        fresh = self.last_label is None or gap >= IDLE_TIMEOUT

        if label == "cymbal":
            same = (not fresh) and self.last_label == "cymbal"
            if same:
                self.cycle_index += 1
            else:
                self.cycle_index = 0
                self.crash_pair = CRASH_PAIRS.get(self.last_perc_label, CRASH_PAIRS["snare"])
            self.category = None
        elif label in ("kick", "snare"):
            if fresh or self.last_label not in ("kick", "snare"):
                new_category = label
            elif self.last_label == label:
                new_category = label
            else:
                new_category = "alternate"

            self.cycle_index = self.cycle_index + 1 if new_category == self.category else 0
            self.category = new_category
            self.last_perc_label = label
        else:
            return

        self.last_label = label
        self.last_time = onset_time

    def reset(self):
        self.last_label = None
        self.last_time = -999.0
        self.cycle_index = 0
        self.category = None
        self.crash_pair = CRASH_PAIRS["snare"]
        self.last_perc_label = None

    def get_frame(self, playhead_time):
        if playhead_time is None:
            return self.frames["idle"]

        elapsed = playhead_time - self.last_time
        if self.last_label is None or elapsed > IDLE_TIMEOUT or elapsed < 0:
            return self.frames["idle"]

        if self.last_label == "cymbal":
            a, b = self.crash_pair
            frames = self.frames["crash"]
            return frames[a] if self.cycle_index % 2 == 0 else frames[b]

        if self.last_label in ("kick", "snare"):
            a, b = PAIRS[self.category]
            frames = self.frames["snare"]
            return frames[a] if self.cycle_index % 2 == 0 else frames[b]

        return self.frames["idle"]
