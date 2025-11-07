"""Main script: download a YouTube video, split into N parts, convert to vertical, add optional texts, export parts.

Usage (CLI):
    python src/split_youtube.py --url <youtube_url> --parts 3 --title "Meu título" --subtitle "Legenda"

This script is cross-platform (requires Python 3.11+, yt-dlp and ffmpeg installed).
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import tempfile
import sys

# Ensure the module's directory is on sys.path so local imports (youtube_utils, video_processing)
# resolve whether the module is imported as a script, as a package, or loaded by spec.
sys.path.insert(0, str(Path(__file__).parent))

from youtube_utils import download_youtube, get_duration_seconds, split_durations
from video_processing import extract_segment, convert_to_vertical, add_text
import re


def safe_filename(s: str) -> str:
    # remove unsafe chars, replace spaces with underscore
    s = s.strip()
    s = re.sub(r'[\\/:*?"<>|]', '', s)
    s = re.sub(r'\s+', '_', s)
    return s or 'video'


def unique_path(directory: Path, base: str, ext: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / f"{base}{ext}"
    i = 1
    while candidate.exists():
        candidate = directory / f"{base}_{i}{ext}"
        i += 1
    return candidate


def run_split(url: str, parts: int = 3, title: str = '', subtitle: str = '', out_dir: str | Path = 'downloads',
              force_reprocess: bool = False, force_redownload: bool = False, download_archive: str | None = None,
              cookies: str | None = None, cookies_from_browser: str | None = None):
    """Run the split pipeline programmatically.

    This function performs the same steps as the CLI: download, split, convert, add texts and export files.
    It is safe to call from other Python modules (e.g. FastAPI background task).
    """
    base_out = Path(out_dir)
    raw_dir = base_out / 'youtube' / 'raw_videos'
    output_dir = base_out / 'youtube' / 'output_videos'
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    import time
    print('1) Baixando vídeo...')
    t0 = time.monotonic()
    # choose whether to skip download based on force_redownload
    skip_if_exists = not bool(force_redownload)
    # default archive file under downloads/youtube/download_archive.txt unless provided
    if download_archive is None:
        download_archive = str(base_out / 'youtube' / 'download_archive.txt')
    src_path = download_youtube(url, raw_dir, skip_if_exists=skip_if_exists, max_height=720,
                              download_archive=download_archive, cookies=cookies, cookies_from_browser=cookies_from_browser)
    t1 = time.monotonic()
    print(f'Arquivo baixado em {src_path} (download time: {t1-t0:.1f}s)')

    print('2) Obtendo duração...')
    total = get_duration_seconds(src_path)
    print(f'Duração total: {total:.2f} s')

    ranges = split_durations(total, parts)

    tmpdir = Path(tempfile.mkdtemp(prefix='split_youtube_'))
    print('Usando pasta temporária', tmpdir)

    produced = []
    try:
        for idx, (start, duration) in enumerate(ranges, start=1):
            segment_tmp = tmpdir / f'segment_{idx}.mp4'
            print(f'Extraindo parte {idx}: start={start} duration={duration}')
            seg_t0 = time.monotonic()
            # Try to extract with copy first; if it fails re-encode the segment
            try:
                extract_segment(src_path, start, duration, segment_tmp)
            except Exception as e:
                print('extract_segment falhou, tentando re-encode para segment_tmp:', e)
                # re-encode fallback
                extract_segment_reencode(src_path, start, duration, segment_tmp)
            # convert to vertical 9:16
            vertical = tmpdir / f'vertical_{idx}.mp4'
            print('Convertendo para 9:16...')
            # convert_to_vertical now returns geometry (scaled_w, scaled_h, overlay_x, overlay_y)
            v_t0 = time.monotonic()
            video_geom = convert_to_vertical(segment_tmp, vertical)
            v_t1 = time.monotonic()

            # add texts if present
            # use title (if provided) or source stem to name output files (deterministic name for caching)
            stem = safe_filename(title) if title else safe_filename(src_path.stem)
            final_base = f"{stem}_parte_{idx}"
            final_name = output_dir / f"{final_base}.mp4"

            # If final exists and we are not forcing reprocess, skip processing this part
            if final_name.exists() and not force_reprocess:
                print(f'Parte {idx}: arquivo final já existe, pulando (use --force-reprocess para regenerar): {final_name}')
                produced.append(final_name)
                continue

            # if forcing reprocess and file exists, remove it so we overwrite cleanly
            if final_name.exists() and force_reprocess:
                try:
                    final_name.unlink()
                except Exception:
                    pass

            print('Adicionando textos (se houver)...')
            add_t0 = time.monotonic()
            # pass returned geometry so texts are placed close to the video rather than at canvas extremes
            add_text(vertical, final_name, title=title if title else None, subtitle=subtitle if subtitle else None,
                     video_geom=video_geom, target_w=1080, target_h=1920)
            add_t1 = time.monotonic()

            seg_t1 = time.monotonic()
            print(f'Parte {idx} tempos: extract={(seg_t1-seg_t0):.1f}s, convert={(v_t1-v_t0):.1f}s, add_text={(add_t1-add_t0):.1f}s')
            produced.append(final_name)

        print('Arquivos gerados:')
        for p in produced:
            print(' -', p)
    finally:
        # cleanup
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


def extract_segment_reencode(input_path, start, duration, out_path):
    cmd = [
        'ffmpeg', '-y', '-ss', str(start), '-i', str(input_path), '-t', str(duration),
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-c:a', 'aac', '-b:a', '128k', str(out_path)
    ]
    import subprocess
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)


if __name__ == '__main__':
    def main():
        parser = argparse.ArgumentParser(description='Baixa um vídeo do YouTube e divide em partes verticais 9:16')
        parser.add_argument('--url', required=True, nargs='+', help='One or more YouTube links to process')
        parser.add_argument('--parts', type=int, default=3, help='Número de partes para dividir (>=1)')
        parser.add_argument('--title', default='', help='Título a adicionar (opcional)')
        parser.add_argument('--subtitle', default='', help='Legenda a adicionar (opcional)')
        parser.add_argument('--out-dir', default='youtube_output', help='Pasta de saída')
        parser.add_argument('--force-reprocess', action='store_true', help='Forçar reprocessamento das partes mesmo se existirem arquivos finais')
        parser.add_argument('--force-redownload', action='store_true', help='Forçar re-download mesmo se o vídeo já foi baixado')
        parser.add_argument('--download-archive', default=None, help='Arquivo de archive para yt-dlp (download-archive)')
        parser.add_argument('--cookies', default=None, help='Caminho para cookies.txt (Netscape)')
        parser.add_argument('--cookies-from-browser', default=None, help='Extrair cookies do navegador (e.g. chrome, firefox)')
        args = parser.parse_args()
        for u in args.url:
            print('\n==== Processando URL:', u)
            run_split(u, parts=args.parts, title=args.title, subtitle=args.subtitle, out_dir=args.out_dir,
                      force_reprocess=args.force_reprocess, force_redownload=args.force_redownload,
                      download_archive=args.download_archive, cookies=args.cookies, cookies_from_browser=args.cookies_from_browser)

    main()
