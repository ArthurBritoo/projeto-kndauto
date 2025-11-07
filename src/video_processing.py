"""Video processing helpers: split, convert to vertical 9:16, add texts, export and cleanup.

Uses ffmpeg CLI via subprocess. Designed for cross-platform use (Windows/macOS/Linux) as long as ffmpeg is in PATH.
"""
from __future__ import annotations
import shlex
import subprocess
from pathlib import Path
from typing import Optional, Tuple
import json


def ffmpeg_run(cmd: list[str]):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}")
    return proc


def extract_segment(input_path: Path, start: float, duration: float, out_path: Path) -> None:
    """Extract a segment using -ss (start) and -t (duration) without re-encoding (copy) when possible."""
    cmd = [
        'ffmpeg',
        '-y',
        '-ss', str(start),
        '-i', str(input_path),
        '-t', str(duration),
        '-c', 'copy',
        str(out_path),
    ]
    ffmpeg_run(cmd)


def convert_to_vertical(input_path: Path, out_path: Path, target_w: int = 1080, target_h: int = 1920) -> None:
    """Convert a source video to vertical 9:16 while keeping content centered.

    Strategy:
    - scale the input so the smaller dimension fits the target
    - crop (center) or pad if necessary to reach exact target
    """
    # Determine source size using ffprobe so we can compute the scaled size and overlay position
    probe_cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height', '-of', 'json', str(input_path)
    ]
    proc = subprocess.run(probe_cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr}")
    info = json.loads(proc.stdout)
    stream = info.get('streams', [])[0]
    iw = int(stream.get('width', 0))
    ih = int(stream.get('height', 0))

    # compute scale that fits inside target (keep aspect)
    scale = min(target_w / iw, target_h / ih)
    scaled_w = int(iw * scale)
    scaled_h = int(ih * scale)

    overlay_x = (target_w - scaled_w) // 2
    overlay_y = (target_h - scaled_h) // 2

    # Use scale filter to ensure the video covers the target area, then pad center
    vf = (
        f"scale={scaled_w}:{scaled_h},pad={target_w}:{target_h}:{overlay_x}:{overlay_y},setsar=1"
    )
    cmd = [
        'ffmpeg', '-y', '-i', str(input_path), '-vf', vf, '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '128k', str(out_path)
    ]
    ffmpeg_run(cmd)

    # return geometry so callers can position text relative to the video content
    return scaled_w, scaled_h, overlay_x, overlay_y


def add_text(input_path: Path, out_path: Path, title: Optional[str] = None, subtitle: Optional[str] = None,
             title_font: str = 'Arial', subtitle_font: str = 'Arial',
             video_geom: Optional[Tuple[int,int,int,int]] = None, target_w: int = 1080, target_h: int = 1920) -> None:
    """Add optional title (yellow, top) and subtitle (white, bottom) using drawtext.

    The function will skip a text if the string is empty or None.
    Requires ffmpeg built with libfreetype (most official builds include it).
    """
    filters = []

    # If video geometry provided (scaled_w, scaled_h, overlay_x, overlay_y), position text close to the video
    if video_geom:
        scaled_w, scaled_h, overlay_x, overlay_y = video_geom
        # font sizes relative to the video's visible height
        title_fs = max(12, int(scaled_h * 0.06))
        subtitle_fs = max(10, int(scaled_h * 0.045))
        margin = max(6, int(scaled_h * 0.02))

        if title:
            # try to place title right above the video; if there's not enough space, place it inside the top of the video
            title_y = overlay_y - title_fs - margin
            if title_y < 4:
                title_y = overlay_y + margin
            filters.append(
                f"drawtext=font='{title_font}':text='{escape_text(title)}':fontcolor=yellow:fontsize={title_fs}:x=(w-text_w)/2:y={title_y}:box=1:boxcolor=black@0.4:boxborderw=10"
            )

        if subtitle:
            # try to place subtitle right below the video; if not enough space, place it inside the bottom of the video
            subtitle_y = overlay_y + scaled_h + margin
            if subtitle_y + subtitle_fs + margin > target_h - 4:
                subtitle_y = overlay_y + scaled_h - subtitle_fs - margin
            filters.append(
                f"drawtext=font='{subtitle_font}':text='{escape_text(subtitle)}':fontcolor=white:fontsize={subtitle_fs}:x=(w-text_w)/2:y={subtitle_y}:box=1:boxcolor=black@0.4:boxborderw=8"
            )
    else:
        # fallback to previous behavior (positions relative to full canvas)
        # drawtext expressions: center horizontally, place title a pouco abaixo do topo do vídeo
        # and subtitle um pouco acima da borda inferior, usando tamanhos relativas à altura (responsivo)
        if title:
            filters.append(
                f"drawtext=font='{title_font}':text='{escape_text(title)}':fontcolor=yellow:fontsize=trunc(h*0.06):x=(w-text_w)/2:y=h*0.06:box=1:boxcolor=black@0.4:boxborderw=10"
            )
        if subtitle:
            filters.append(
                f"drawtext=font='{subtitle_font}':text='{escape_text(subtitle)}':fontcolor=white:fontsize=trunc(h*0.045):x=(w-text_w)/2:y=h-text_h-h*0.06:box=1:boxcolor=black@0.4:boxborderw=8"
            )
    if not filters:
        # nothing to do, copy
        cmd = ['ffmpeg', '-y', '-i', str(input_path), '-c', 'copy', str(out_path)]
        ffmpeg_run(cmd)
        return
    vf = ','.join(filters)
    cmd = ['ffmpeg', '-y', '-i', str(input_path), '-vf', vf, '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-c:a', 'aac', '-b:a', '128k', str(out_path)]
    ffmpeg_run(cmd)


def escape_text(text: str) -> str:
    # Minimal escaping for ffmpeg drawtext: escape single quotes by backslash
    return text.replace("'", "\\'")
