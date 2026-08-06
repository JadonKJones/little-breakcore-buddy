import os
import sys
import pygame

if getattr(sys, "frozen", False):
    # PyInstaller bundle: --add-data placed "animation frames" at the bundle root.
    ANIMATION_DIR = os.path.join(sys._MEIPASS, "animation frames")
else:
    ANIMATION_DIR = os.path.join(os.path.dirname(__file__), "..", "animation frames")

IDLE_TIMEOUT = 0.12       # seconds since last snare/crash hit before returning to idle (also resets cycle)
KICK_OVERLAY_DURATION = 0.12  # how long the "k" variant of the current pose shows after a kick
KICK_ROLL_THRESHOLD = 1   # kick_cycle_index at/above this means "2nd+ rapid kick" -- a roll, not a single hit

# Which crash pair to start on, based on the note that preceded the crash.
CRASH_PAIRS = {
    "snare": (0, 1),  # crash1, crash2
    "kick": (2, 3),   # crash3, crash4
}

# The sprite's arm position has to continue naturally: whichever snare-look
# frame (1-4) was last shown decides which crash frame the swing starts on
# (and the pair alternates back to the other one on repeats). snare5/6 don't
# have a matching crash frame, so they fall back to CRASH_PAIRS above.
SNARE_FRAME_TO_CRASH_PAIR = {
    1: (1, 0),  # snare1 -> crash2, then crash1
    2: (0, 1),  # snare2 -> crash1, then crash2
    3: (3, 2),  # snare3 -> crash4, then crash3
    4: (2, 3),  # snare4 -> crash3, then crash4
}

# The reverse: whichever crash frame (1-4) was last shown decides which
# snare frame a fresh snare run starts on (0-based index into "snare").
CRASH_FRAME_TO_SNARE_START = {
    1: 1,  # crash1 -> snare2
    2: 0,  # crash2 -> snare1
    3: 3,  # crash3 -> snare4
    4: 2,  # crash4 -> snare3
}


class DrummerSprite:
    def __init__(self, size=None):
        self.frames = {
            "idle": self._load("idle.png", size),
            "idle_k": self._load("idlek.png", size),
            "snare": [self._load(f"snare{i}.png", size) for i in range(1, 7)],
            "snare_k": [self._load(f"snare{i}k.png", size) for i in range(1, 7)],
            "crash": [self._load(f"crash{i}.png", size) for i in range(1, 5)],
            "crash_k": [self._load(f"crash{i}k.png", size) for i in range(1, 5)],
        }

        self.last_pose_label = None  # "snare" or "cymbal" -- kick never becomes the base pose
        self.last_pose_time = -999.0
        self.cycle_index = 0
        self.crash_pair = CRASH_PAIRS["snare"]
        self.last_perc_type = None  # most recent of "kick"/"snare", used to pick crash_pair
        self.last_kick_time = -999.0
        self.kick_cycle_index = 0  # alternates snare3/snare4 when a kick lands with nothing else active
        self.last_snare_frame = None  # 1-6, whichever snare-look frame was most recently shown
        self.last_crash_frame = None  # 1-4, whichever crash frame was most recently shown
        self.snare_start_index = 0  # 0-based, which snare frame a fresh snare run starts on

    def _load(self, filename, size):
        path = os.path.join(ANIMATION_DIR, filename)
        image = pygame.image.load(path).convert_alpha()
        if size is not None:
            image = pygame.transform.smoothscale(image, size)
        return image

    def trigger(self, label, onset_time):
        """Call once, in onset-time order, each time playback crosses an onset."""
        if label == "kick":
            kick_gap = onset_time - self.last_kick_time
            self.kick_cycle_index = self.kick_cycle_index + 1 if kick_gap < KICK_OVERLAY_DURATION else 0
            self.last_kick_time = onset_time
            self.last_perc_type = "kick"
            if self.kick_cycle_index >= KICK_ROLL_THRESHOLD:
                # A roll (2nd+ rapid kick): kick takes over as the active pose,
                # same as snare/cymbal would, instead of just a brief overlay.
                self.last_snare_frame = 3 if self.kick_cycle_index % 2 == 0 else 4
                self.last_pose_label = "kick"
                self.last_pose_time = onset_time
            return

        if label not in ("snare", "cymbal"):
            return

        gap = onset_time - self.last_pose_time
        fresh = self.last_pose_label is None or gap >= IDLE_TIMEOUT
        same = (not fresh) and self.last_pose_label == label

        if label == "cymbal":
            if same:
                self.cycle_index += 1
            else:
                self.cycle_index = 0
                if self.last_snare_frame in SNARE_FRAME_TO_CRASH_PAIR:
                    self.crash_pair = SNARE_FRAME_TO_CRASH_PAIR[self.last_snare_frame]
                else:
                    self.crash_pair = CRASH_PAIRS.get(self.last_perc_type, CRASH_PAIRS["snare"])
            a, b = self.crash_pair
            self.last_crash_frame = (a if self.cycle_index % 2 == 0 else b) + 1
        else:  # snare
            if same:
                self.cycle_index += 1
            else:
                self.cycle_index = 0
                self.snare_start_index = CRASH_FRAME_TO_SNARE_START.get(self.last_crash_frame, 0)
            self.last_perc_type = "snare"
            self.last_snare_frame = (self.snare_start_index + self.cycle_index) % 6 + 1

        self.last_pose_label = label
        self.last_pose_time = onset_time

    def reset(self):
        self.last_pose_label = None
        self.last_pose_time = -999.0
        self.cycle_index = 0
        self.crash_pair = CRASH_PAIRS["snare"]
        self.last_perc_type = None
        self.last_kick_time = -999.0
        self.kick_cycle_index = 0
        self.last_snare_frame = None
        self.last_crash_frame = None
        self.snare_start_index = 0

    def get_frame(self, playhead_time):
        if playhead_time is None:
            return self.frames["idle"]

        overlay_elapsed = playhead_time - self.last_kick_time
        overlay_active = 0 <= overlay_elapsed <= KICK_OVERLAY_DURATION

        pose_elapsed = playhead_time - self.last_pose_time
        is_idle = self.last_pose_label is None or pose_elapsed > IDLE_TIMEOUT or pose_elapsed < 0

        if is_idle:
            return self.frames["idle_k"] if overlay_active else self.frames["idle"]

        if self.last_pose_label == "kick":
            # Mid-roll: behaves just like a snare pose, alternating snare3/snare4.
            frames = self.frames["snare"]
            return frames[2] if self.kick_cycle_index % 2 == 0 else frames[3]

        if self.last_pose_label == "snare":
            frames = self.frames["snare_k"] if overlay_active else self.frames["snare"]
            return frames[(self.snare_start_index + self.cycle_index) % len(frames)]

        if self.last_pose_label == "cymbal":
            a, b = self.crash_pair
            frames = self.frames["crash_k"] if overlay_active else self.frames["crash"]
            return frames[a] if self.cycle_index % 2 == 0 else frames[b]

        return self.frames["idle"]
