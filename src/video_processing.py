"""Video processing helpers: split, convert to vertical 9:16, add texts, export and cleanup.

Uses ffmpeg CLI via subprocess. Designed for cross-platform use (Windows/macOS/Linux) as long as ffmpeg is in PATH.
"""
from __future__ import annotations
import shlex
import subprocess
from pathlib import Path
from typing import Optional


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
    # Use scale filter to ensure the video covers the target area, then crop center
    vf = (
        f"scale=w=iw*min({target_w}/iw\,{target_h}/ih):h=ih*min({target_w}/iw\,{target_h}/ih),"
        f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    )
    cmd = [
        'ffmpeg', '-y', '-i', str(input_path), '-vf', vf, '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '128k', str(out_path)
    ]
    ffmpeg_run(cmd)


def add_text(input_path: Path, out_path: Path, title: Optional[str] = None, subtitle: Optional[str] = None,
             title_font: str = 'Arial', subtitle_font: str = 'Arial') -> None:
    """Add optional title (yellow, top) and subtitle (white, bottom) using drawtext.

    The function will skip a text if the string is empty or None.
    Requires ffmpeg built with libfreetype (most official builds include it).
    """
    filters = []
    # drawtext expressions: center horizontally, place title a pouco abaixo do topo do vídeo
    # and subtitle um pouco acima da borda inferior, usando tamanhos relativos à altura (responsivo)
    # fontsize uses an expression based on video height: trunc(h*0.06) para título e trunc(h*0.045) para legenda
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
