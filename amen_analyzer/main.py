import bisect
import os
import sys
import pygame
import librosa as lr

from audio_engine import AudioEngine
from ui import WaveformDisplay
from analyzer import DrumAnalyzer
from utils import History
from sprite import DrummerSprite
from data_manager import DataManager
from video_export import export_video

WIDTH, HEIGHT = 1200, 600
WAVEFORM_X, WAVEFORM_Y = 25, 50
WAVEFORM_W, WAVEFORM_H = WIDTH - 50, 200

ZOOM_FACTOR = 1.25
SCROLL_FRACTION = 0.1
CLICK_TOLERANCE_PX = 10
SPRITE_SIZE = (200, 200)

LABEL_KEYS = {
    pygame.K_k: "kick",
    pygame.K_s: "snare",
    pygame.K_c: "cymbal",
}


def main():
    # Usage: main.py <drums_only.wav> [full_song.wav]
    # If a second file is given, onsets are detected from the drums-only
    # track (cleaner detection), but playback/waveform/video export use the
    # full song -- so the video plays the whole mix while the sprite reacts
    # to hits timed off the isolated drums.
    drums_path = sys.argv[1] if len(sys.argv) > 1 else "i know it hurts only drums.wav"
    song_path = sys.argv[2] if len(sys.argv) > 2 else drums_path

    base_path, _ = os.path.splitext(song_path)
    json_path = base_path + ".json"
    csv_path = base_path + ".csv"
    video_path = base_path + "_animated.mp4"

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Amen Break Analyzer")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 24)

    audio_engine = AudioEngine()
    waveform_ui = WaveformDisplay(WAVEFORM_W, WAVEFORM_H)
    sprite = DrummerSprite(size=SPRITE_SIZE)

    try:
        audio_engine.load_audio(song_path)
        waveform_ui.set_audio(audio_engine.audio_data, audio_engine.sr, audio_engine.duration)

        if drums_path == song_path:
            drums_audio, drums_sr = audio_engine.audio_data, audio_engine.sr
        else:
            drums_audio, drums_sr = lr.load(drums_path, sr=None, mono=True)

        analyzer = DrumAnalyzer(sr=drums_sr)
        onset_labels = analyzer.detect_onsets(drums_audio)
        onsets = list(onset_labels)
        waveform_ui.set_onsets(onsets)
        history = History(onsets)

        load_error = None
    except Exception as e:
        load_error = str(e)
        onsets = []
        history = None

    def commit(new_onsets):
        nonlocal onsets
        onsets = new_onsets
        history.push(onsets)
        waveform_ui.set_onsets(onsets)

    def relabel_selected(label):
        idx = waveform_ui.selected_index
        if idx is None:
            return
        t, _ = onsets[idx]
        new_onsets = list(onsets)
        new_onsets[idx] = (t, label)
        commit(new_onsets)

    def delete_selected():
        idx = waveform_ui.selected_index
        if idx is None:
            return
        new_onsets = list(onsets)
        del new_onsets[idx]
        commit(new_onsets)
        waveform_ui.set_selected(None)

    def add_onset_at(t, label="kick"):
        new_onsets = list(onsets)
        bisect.insort(new_onsets, (t, label))
        commit(new_onsets)
        waveform_ui.set_selected(new_onsets.index((t, label)))

    playing = False
    playback_start_time = 0.0
    last_triggered_index = -1
    status_message = ""

    def set_status(msg):
        nonlocal status_message
        status_message = msg

    def save_json():
        DataManager.save_analysis(onsets, json_path)
        set_status(f"Saved analysis to {json_path}")

    def load_json():
        if not os.path.exists(json_path):
            set_status(f"No saved analysis found at {json_path}")
            return
        loaded = DataManager.load_analysis(json_path)
        commit(list(loaded))
        waveform_ui.set_selected(None)
        set_status(f"Loaded analysis from {json_path}")

    def export_csv_file():
        DataManager.export_csv(onsets, csv_path)
        set_status(f"Exported CSV to {csv_path}")

    def do_export_video():
        nonlocal playing
        if playing:
            audio_engine.stop()
            playing = False

        screen.fill((30, 30, 40))
        msg = font.render("Exporting video... this may take a moment", True, (255, 220, 100))
        screen.blit(msg, (25, HEIGHT // 2))
        pygame.display.flip()

        try:
            export_video(song_path, onsets, audio_engine.duration, video_path)
            set_status(f"Exported video to {video_path}")
        except Exception as e:
            set_status(f"Video export failed: {e}")

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_SPACE and load_error is None:
                    if playing:
                        audio_engine.stop()
                        playing = False
                    else:
                        audio_engine.play()
                        playback_start_time = pygame.time.get_ticks() / 1000.0
                        playing = True
                        last_triggered_index = -1
                        sprite.reset()
                if load_error is None:
                    if event.key in (pygame.K_LEFT,):
                        waveform_ui.scroll(-waveform_ui.view_duration * SCROLL_FRACTION)
                    if event.key in (pygame.K_RIGHT,):
                        waveform_ui.scroll(waveform_ui.view_duration * SCROLL_FRACTION)
                    if event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                        waveform_ui.zoom(1 / ZOOM_FACTOR)
                    if event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        waveform_ui.zoom(ZOOM_FACTOR)
                    if event.key == pygame.K_HOME:
                        waveform_ui.zoom_to_fit()

                    mods = pygame.key.get_mods()

                    if event.key in LABEL_KEYS and not (mods & pygame.KMOD_CTRL):
                        relabel_selected(LABEL_KEYS[event.key])
                    if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                        delete_selected()

                    if event.key == pygame.K_z and (mods & pygame.KMOD_CTRL):
                        state = history.undo()
                        if state is not None:
                            onsets = state
                            waveform_ui.set_onsets(onsets)
                            waveform_ui.set_selected(None)
                    if event.key == pygame.K_y and (mods & pygame.KMOD_CTRL):
                        state = history.redo()
                        if state is not None:
                            onsets = state
                            waveform_ui.set_onsets(onsets)
                            waveform_ui.set_selected(None)

                    if event.key == pygame.K_s and (mods & pygame.KMOD_CTRL):
                        save_json()
                    if event.key == pygame.K_o and (mods & pygame.KMOD_CTRL):
                        load_json()
                    if event.key == pygame.K_e and (mods & pygame.KMOD_CTRL):
                        export_csv_file()
                    if event.key == pygame.K_v and (mods & pygame.KMOD_CTRL):
                        do_export_video()
            if event.type == pygame.MOUSEWHEEL and load_error is None:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                if WAVEFORM_Y <= mouse_y <= WAVEFORM_Y + WAVEFORM_H:
                    anchor_time = waveform_ui.x_to_time(mouse_x - WAVEFORM_X)
                    if event.y > 0:
                        waveform_ui.zoom(1 / ZOOM_FACTOR, anchor_time)
                    elif event.y < 0:
                        waveform_ui.zoom(ZOOM_FACTOR, anchor_time)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and load_error is None:
                mouse_x, mouse_y = event.pos
                if WAVEFORM_Y <= mouse_y <= WAVEFORM_Y + WAVEFORM_H and WAVEFORM_X <= mouse_x <= WAVEFORM_X + WAVEFORM_W:
                    local_x = mouse_x - WAVEFORM_X
                    nearest = waveform_ui.find_nearest_onset_px(local_x, max_px=CLICK_TOLERANCE_PX)
                    if nearest is not None:
                        waveform_ui.set_selected(nearest)
                    else:
                        add_onset_at(waveform_ui.x_to_time(local_x))

        screen.fill((30, 30, 40))

        if load_error:
            text = font.render(f"Failed to load audio: {load_error}", True, (255, 80, 80))
            screen.blit(text, (25, 25))
        else:
            playhead_time = None
            if playing:
                elapsed = (pygame.time.get_ticks() / 1000.0) - playback_start_time
                if elapsed >= audio_engine.duration or not audio_engine.is_playing():
                    playing = False
                else:
                    playhead_time = elapsed
                    view_end = waveform_ui.view_start + waveform_ui.view_duration
                    if not (waveform_ui.view_start <= playhead_time <= view_end):
                        waveform_ui.set_view(playhead_time, waveform_ui.view_duration)

                    onset_times = [t for t, _ in onsets]
                    idx = bisect.bisect_right(onset_times, playhead_time) - 1
                    if idx > last_triggered_index:
                        for i in range(last_triggered_index + 1, idx + 1):
                            t, label = onsets[i]
                            sprite.trigger(label, t)
                        last_triggered_index = idx

            waveform_surface = waveform_ui.get_surface_with_playhead(playhead_time)
            screen.blit(waveform_surface, (WAVEFORM_X, WAVEFORM_Y))

            source_label = song_path if drums_path == song_path else f"{song_path}  (onsets from {drums_path})"
            hint = font.render(
                f"{source_label}  |  SPACE: play/pause  |  ESC: quit  |  "
                f"duration: {audio_engine.duration:.2f}s  |  onsets: {len(onsets)}",
                True, (200, 200, 200)
            )
            screen.blit(hint, (25, 20))

            selected_note = ""
            if waveform_ui.selected_index is not None:
                sel_t, sel_label = onsets[waveform_ui.selected_index]
                selected_note = f"  |  selected: {sel_label} @ {sel_t:.3f}s (K/S/C relabel, Del remove)"

            zoom_hint = font.render(
                f"view: {waveform_ui.view_start:.2f}s - {waveform_ui.view_start + waveform_ui.view_duration:.2f}s  |  "
                f"wheel/+- zoom, arrows pan, Home fit  |  click: select/add onset  |  Ctrl+Z/Y undo/redo"
                f"{selected_note}",
                True, (150, 150, 150)
            )
            screen.blit(zoom_hint, (25, WAVEFORM_Y - 22))

            export_hint = font.render(
                "Ctrl+S save JSON  |  Ctrl+O load JSON  |  Ctrl+E export CSV  |  Ctrl+V export video",
                True, (150, 150, 150)
            )
            screen.blit(export_hint, (25, HEIGHT - 45))

            if status_message:
                status_text = font.render(status_message, True, (120, 220, 140))
                screen.blit(status_text, (25, HEIGHT - 25))

            legend_x = 25
            for label, color in WaveformDisplay.COLORS.items():
                pygame.draw.rect(screen, color, (legend_x, WAVEFORM_Y + WAVEFORM_H + 15, 14, 14))
                text = font.render(label, True, (220, 220, 220))
                screen.blit(text, (legend_x + 20, WAVEFORM_Y + WAVEFORM_H + 13))
                legend_x += 100

            sprite_y = WAVEFORM_Y + WAVEFORM_H + 50
            frame = sprite.get_frame(playhead_time)
            frame_rect = frame.get_rect(center=(WAVEFORM_X + WAVEFORM_W // 2, sprite_y + SPRITE_SIZE[1] // 2))
            screen.blit(frame, frame_rect)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
