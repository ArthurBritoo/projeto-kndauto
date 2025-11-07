"""Utilities to download YouTube video and get metadata using yt-dlp and ffprobe.

Requirements:
- yt-dlp (python package)
- ffmpeg/ffprobe in PATH

This module exposes:
- download_youtube(url, out_dir) -> filepath
- get_duration_seconds(filepath) -> float
"""
from __future__ import annotations
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Optional

import yt_dlp


def download_youtube(url: str, out_dir: str | Path) -> Path:
    """Download best video+audio merged format via yt-dlp.

    Returns path to downloaded file.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
        'outtmpl': str(out_dir / '%(id)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # yt-dlp may produce merged file with .mp4 extension
        if not Path(filename).exists():
            # try mp4
            base = Path(filename).with_suffix('.mp4')
            if base.exists():
                filename = str(base)
    return Path(filename)


def get_duration_seconds(filepath: str | Path) -> float:
    """Use ffprobe to get duration in seconds (float)."""
    filepath = str(filepath)
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'json',
        filepath,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr}")
    data = json.loads(proc.stdout)
    duration = float(data['format']['duration'])
    return duration


def split_durations(total_seconds: float, parts: int) -> list[tuple[float, float]]:
    """Return list of (start, duration) tuples dividing total_seconds into parts as evenly as possible.

    The last part may include the remainder.
    """
    if parts <= 0:
        raise ValueError('parts must be >= 1')
    base = total_seconds / parts
    ranges = []
    for i in range(parts):
        start = i * base
        # last part: ensure end equals total_seconds
        if i == parts - 1:
            duration = total_seconds - start
        else:
            duration = base
        ranges.append((start, duration))
    # normalize tiny floating errors
    ranges = [(round(s, 3), round(d, 3)) for s, d in ranges]
    return ranges
