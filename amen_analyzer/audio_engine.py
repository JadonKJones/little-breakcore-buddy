import soundfile as sf
import librosa as lr
import numpy as np
import pygame


class AudioEngine:
    def __init__(self):
        pygame.mixer.init()
        self.audio_data = None
        self.sr = None
        self.duration = 0.0
        self.sound = None

    def load_audio(self, filepath):
        self.audio_data, self.sr = lr.load(filepath, sr=None, mono=True)
        self.duration = lr.get_duration(y=self.audio_data, sr=self.sr)
        self.sound = pygame.mixer.Sound(filepath)
        return self.duration

    def play(self, start_time=0.0):
        if self.sound is None:
            return
        self.sound.stop()
        self.sound.play()

    def stop(self):
        if self.sound is not None:
            self.sound.stop()

    def is_playing(self):
        return self.sound is not None and pygame.mixer.get_busy()
