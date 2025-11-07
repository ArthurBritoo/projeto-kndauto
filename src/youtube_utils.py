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
import tempfile
from http.cookiejar import CookieJar


def _export_cookies_from_browser_to_file(browser: str, out_path: Path) -> Path:
    """Try to extract cookies from the user's browser using browser_cookie3 and
    write them in Netscape cookie file format to out_path. Returns out_path on success.
    Raises RuntimeError on failure.
    """
    try:
        import browser_cookie3
    except Exception as e:
        raise RuntimeError(f'browser_cookie3 not available: {e}')

    # choose loader
    try:
        if browser and browser.lower() in ('chrome', 'edge', 'chromium'):
            cj = browser_cookie3.chrome()
        elif browser and browser.lower() in ('firefox', 'ff'):
            cj = browser_cookie3.firefox()
        else:
            # generic loader attempts several browsers
            cj = browser_cookie3.load()
    except Exception as e:
        raise RuntimeError(f'failed to load cookies from browser "{browser}": {e}')

    # write Netscape format
    try:
        with open(out_path, 'w', encoding='utf-8') as fh:
            fh.write('# Netscape HTTP Cookie File\n')
            for c in cj:
                # cookie attributes: domain, flag, path, secure, expires, name, value
                domain = c.domain
                flag = 'TRUE' if domain.startswith('.') else 'FALSE'
                path_c = c.path
                secure = 'TRUE' if getattr(c, 'secure', False) else 'FALSE'
                expires = str(int(getattr(c, 'expires', 0) or 0))
                name = c.name
                value = c.value
                fh.write('\t'.join([domain, flag, path_c, secure, expires, name, value]) + '\n')
    except Exception as e:
        raise RuntimeError(f'failed to write cookies file: {e}')

    return out_path


def download_youtube(url: str, out_dir: str | Path, skip_if_exists: bool = True, max_height: Optional[int] = None,
                     download_archive: Optional[str] = None, cookies: Optional[str] = None,
                     cookies_from_browser: Optional[str] = None) -> Path:
    """Download best video+audio merged format via yt-dlp.

    If skip_if_exists is True the function will attempt to detect an existing
    downloaded file for the video id and return it without re-downloading.

    max_height: if provided (e.g. 720) will restrict the downloaded video
    resolution to at most that height to speed up downloads and reduce size.

    Returns path to downloaded file.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # choose format string, optionally limit height
    if max_height:
        fmt = f"best[height<={max_height}]+bestaudio/best[height<={max_height}]"
    else:
        fmt = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'

    ydl_opts = {
        'format': fmt,
        'outtmpl': str(out_dir / '%(id)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'noplaylist': True,
        # do not overwrite by default; we'll control via skip_if_exists
        'nooverwrites': False,
    }
    if download_archive:
        # ensure archive directory exists
        try:
            Path(download_archive).parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        ydl_opts['download_archive'] = str(download_archive)
    # cookies handling: either a cookiefile path or extract from browser (chrome/firefox/edge)
    # If user asked for cookies-from-browser, try to extract cookies ourselves into a temp file
    # and pass cookiefile to yt-dlp. This avoids some incompatibilities inside yt-dlp's
    # internal cookies-from-browser handling.
    if cookies_from_browser and not cookies:
        try:
            tf = Path(tempfile.mktemp(prefix='yt_cookies_', suffix='.txt'))
            _export_cookies_from_browser_to_file(cookies_from_browser, tf)
            cookies = str(tf)
            # prefer cookiefile path
            ydl_opts['cookiefile'] = cookies
        except Exception as e:
            # if extraction failed, fall back to letting yt-dlp try its own cookies-from-browser
            print(f'youtube_utils: failed to extract cookies from browser: {e}; will fallback to yt-dlp internal extraction')
            ydl_opts['cookiesfrombrowser'] = str(cookies_from_browser)
    else:
        if cookies:
            # explicit cookie file (Netscape format)
            ydl_opts['cookiefile'] = str(cookies)

    # Try to inspect info to get video id and expected filename without forcing a download
    with yt_dlp.YoutubeDL({'noplaylist': True, 'quiet': True}) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception:
            info = None

    if info and skip_if_exists:
        vid = info.get('id')
        # check common extensions (.mp4, .mkv, .webm, original ext)
        candidates = [out_dir / f"{vid}.mp4", out_dir / f"{vid}.mkv", out_dir / f"{vid}.webm", out_dir / f"{vid}.{info.get('ext', 'mp4')}" ]
        for c in candidates:
            if c.exists():
                print('download_youtube: arquivo já existe, pulando download ->', c)
                return c

    # perform download using the Python API; if it fails (often due to cookies-from-browser
    # extraction issues) fallback to calling the yt-dlp CLI which sometimes behaves more
    # robustly in environments where the API extraction raises internal errors.
    ydl_opts['nooverwrites'] = True if skip_if_exists else False
    try:
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
    except Exception as e:
        # Fallback: call yt-dlp CLI with similar options
        print('youtube_utils: Python API download failed, falling back to yt-dlp CLI:', e)
        cli_cmd = ['yt-dlp', '--no-playlist', '-f', fmt, '-o', str(out_dir / '%(id)s.%(ext)s'), '--merge-output-format', 'mp4']
        if download_archive:
            cli_cmd += ['--download-archive', str(download_archive)]
        if skip_if_exists:
            cli_cmd += ['--no-overwrites']
        if cookies:
            cli_cmd += ['--cookies', str(cookies)]
        if cookies_from_browser:
            cli_cmd += ['--cookies-from-browser', str(cookies_from_browser)]
        # run CLI and capture output
        import subprocess
        proc = subprocess.run(cli_cmd + [url], capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"yt-dlp CLI failed:\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}")

        # pick the newest file in out_dir as the downloaded file (best-effort)
        candidates = list(out_dir.glob('*'))
        if not candidates:
            raise RuntimeError('yt-dlp CLI reported success but no file found in out_dir')
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]


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
