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

from youtube_utils import download_youtube, get_duration_seconds, split_durations
from video_processing import extract_segment, convert_to_vertical, add_text


def run_split(url: str, parts: int = 3, title: str = '', subtitle: str = '', out_dir: str | Path = 'youtube_output'):
    """Run the split pipeline programmatically.

    This function performs the same steps as the CLI: download, split, convert, add texts and export files.
    It is safe to call from other Python modules (e.g. FastAPI background task).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print('1) Baixando vídeo...')
    src_path = download_youtube(url, out_dir)
    print('Arquivo baixado em', src_path)

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
            convert_to_vertical(segment_tmp, vertical)

            # add texts if present
            final_name = out_dir / f'parte_{idx}.mp4'
            print('Adicionando textos (se houver)...')
            add_text(vertical, final_name, title=title if title else None, subtitle=subtitle if subtitle else None)
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
        parser.add_argument('--url', required=True, help='Link do vídeo do YouTube')
        parser.add_argument('--parts', type=int, default=3, help='Número de partes para dividir (>=1)')
        parser.add_argument('--title', default='', help='Título a adicionar (opcional)')
        parser.add_argument('--subtitle', default='', help='Legenda a adicionar (opcional)')
        parser.add_argument('--out-dir', default='youtube_output', help='Pasta de saída')
        args = parser.parse_args()
        run_split(args.url, parts=args.parts, title=args.title, subtitle=args.subtitle, out_dir=args.out_dir)

    main()
