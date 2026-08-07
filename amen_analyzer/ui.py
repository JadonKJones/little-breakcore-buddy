import pygame
import numpy as np


class WaveformDisplay:
    COLORS = {
        "kick": (255, 100, 100),
        "snare": (100, 255, 100),
        "cymbal": (100, 150, 255),
    }

    MIN_VIEW_DURATION = 0.2

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.onsets = []
        self.duration = 1.0
        self.selected_index = None

        self.audio_data = None
        self.sr = None

        self.view_start = 0.0
        self.view_duration = 1.0

        self.base_surface = pygame.Surface((width, height))
        self._dirty = True

    def set_audio(self, audio_data, sr, duration):
        self.audio_data = audio_data
        self.sr = sr
        self.duration = max(duration, 1e-6)
        self.view_start = 0.0
        self.view_duration = self.duration
        self._dirty = True

    def set_onsets(self, onsets, duration=None):
        """onsets: list of (time_in_seconds, label_string)"""
        self.onsets = onsets
        if duration is not None:
            self.duration = max(duration, 1e-6)
        self._dirty = True

    def set_view(self, view_start, view_duration):
        view_duration = max(self.MIN_VIEW_DURATION, min(view_duration, self.duration))
        view_start = max(0.0, min(view_start, self.duration - view_duration))
        if view_start != self.view_start or view_duration != self.view_duration:
            self.view_start = view_start
            self.view_duration = view_duration
            self._dirty = True

    def scroll(self, delta_seconds):
        self.set_view(self.view_start + delta_seconds, self.view_duration)

    def zoom(self, factor, anchor_time=None):
        """factor < 1 zooms in, factor > 1 zooms out. anchor_time keeps that
        point under the same relative position while zooming."""
        if anchor_time is None:
            anchor_time = self.view_start + self.view_duration / 2

        anchor_frac = (anchor_time - self.view_start) / self.view_duration
        new_duration = self.view_duration * factor
        new_start = anchor_time - anchor_frac * new_duration
        self.set_view(new_start, new_duration)

    def zoom_to_fit(self):
        self.set_view(0.0, self.duration)

    def _render(self):
        self.base_surface.fill((20, 20, 30))

        if self.audio_data is not None and self.sr:
            start_sample = int(self.view_start * self.sr)
            end_sample = int((self.view_start + self.view_duration) * self.sr)
            start_sample = max(0, start_sample)
            end_sample = min(len(self.audio_data), end_sample)
            segment = self.audio_data[start_sample:end_sample]

            if len(segment) > 0:
                samples_per_pixel = max(1, len(segment) // self.width)
                usable = samples_per_pixel * self.width
                if usable > 0:
                    trimmed = segment[:usable]
                    chunks = trimmed.reshape(self.width, samples_per_pixel)
                    waveform = np.max(np.abs(chunks), axis=1)
                else:
                    waveform = np.abs(segment)
                    waveform = np.pad(waveform, (0, self.width - len(waveform)))

                peak = np.max(waveform)
                if peak > 1e-8:
                    waveform = waveform / peak

                y_center = self.height // 2
                for x, amp in enumerate(waveform):
                    y_top = y_center - int(amp * self.height / 2)
                    y_bot = y_center + int(amp * self.height / 2)
                    pygame.draw.line(self.base_surface, (90, 100, 130), (x, y_top), (x, y_bot))

        for i, (onset_time, label) in enumerate(self.onsets):
            if self.view_start <= onset_time <= self.view_start + self.view_duration:
                ox = self.time_to_x(onset_time)
                onset_color = self.COLORS.get(label, (200, 200, 200))
                line_width = 3 if i == self.selected_index else 1
                # A dark outline keeps markers visible against a loud, solidly-filled
                # waveform -- otherwise a dense run of same-colored markers (e.g. a
                # snare roll against the waveform's own green fill) visually vanishes
                # right where it matters most.
                pygame.draw.line(self.base_surface, (10, 10, 15), (ox, 0), (ox, self.height), line_width + 2)
                pygame.draw.line(self.base_surface, onset_color, (ox, 0), (ox, self.height), line_width)

        self._dirty = False

    def get_surface_with_playhead(self, playhead_time=None, color=(255, 0, 0)):
        if self._dirty:
            self._render()

        surface = self.base_surface.copy()
        if playhead_time is not None and self.view_start <= playhead_time <= self.view_start + self.view_duration:
            x = self.time_to_x(playhead_time)
            pygame.draw.line(surface, color, (x, 0), (x, self.height), 2)
        return surface

    def time_to_x(self, t):
        return int(((t - self.view_start) / self.view_duration) * self.width)

    def x_to_time(self, x):
        return self.view_start + (x / self.width) * self.view_duration

    def find_nearest_onset(self, t, max_dist=0.05):
        nearest = None
        min_dist = max_dist
        for i, (onset_time, _) in enumerate(self.onsets):
            dist = abs(onset_time - t)
            if dist < min_dist:
                min_dist = dist
                nearest = i
        return nearest

    def find_nearest_onset_px(self, x, max_px=10):
        """Like find_nearest_onset, but tolerance is in screen pixels
        (converted to seconds using the current zoom level)."""
        max_dist = (max_px / self.width) * self.view_duration
        return self.find_nearest_onset(self.x_to_time(x), max_dist=max_dist)

    def set_selected(self, index):
        if index != self.selected_index:
            self.selected_index = index
            self._dirty = True

    def mark_dirty(self):
        self._dirty = True
