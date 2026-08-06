import bisect
import shutil
import subprocess

import pygame

from sprite import DrummerSprite

FPS = 30
BG_COLOR = (30, 30, 40)


def export_video(audio_path, onsets, duration, output_path, size=(480, 480),
                  sprite_size=(400, 400), fps=FPS, progress_callback=None):
    """Renders the drummer animation for the full track and muxes it with the
    original audio via ffmpeg. Runs synchronously; call progress_callback(i, total)
    if you want to report progress (e.g. to update the window during export)."""
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"

    sprite = DrummerSprite(size=sprite_size)
    onset_times = [t for t, _ in onsets]

    total_frames = max(1, int(duration * fps) + 1)
    width, height = size

    cmd = [
        ffmpeg_bin, "-y",
        "-f", "rawvideo",
        "-pixel_format", "rgb24",
        "-video_size", f"{width}x{height}",
        "-framerate", str(fps),
        "-i", "pipe:0",
        "-i", audio_path,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        "-map", "0:v:0",
        "-map", "1:a:0",
        output_path,
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    frame_surface = pygame.Surface(size)
    last_triggered_index = -1
    center = (width // 2, height // 2)

    try:
        for frame_i in range(total_frames):
            t = frame_i / fps

            idx = bisect.bisect_right(onset_times, t) - 1
            if idx > last_triggered_index:
                for i in range(last_triggered_index + 1, idx + 1):
                    onset_time, label = onsets[i]
                    sprite.trigger(label, onset_time)
                last_triggered_index = idx

            frame_surface.fill(BG_COLOR)
            pose = sprite.get_frame(t)
            pose_rect = pose.get_rect(center=center)
            frame_surface.blit(pose, pose_rect)

            raw = pygame.image.tostring(frame_surface, "RGB")
            proc.stdin.write(raw)

            if progress_callback and frame_i % fps == 0:
                progress_callback(frame_i, total_frames)
    finally:
        proc.stdin.close()
        _, stderr = proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (code {proc.returncode}):\n{stderr.decode(errors='replace')[-2000:]}")

    return output_path
