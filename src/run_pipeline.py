"""
run_pipeline.py

Orquestra todo o fluxo do projeto:
 1) valida as URLs e ferramentas
 2) baixa os vídeos com yt-dlp
 3) analisa codecs com ffprobe
 4) concatena (sem re-encode quando possível, com fallback para re-encode)

Uso:
  python src/run_pipeline.py <url1> <url2> --out-dir ./downloads --output ./output_final.mp4

Opções: --cookies, --force-reencode
"""

import os
import sys
import argparse

def _ensure_out_dir(path: str):
    os.makedirs(path, exist_ok=True)


def run_pipeline(url1: str, url2: str, out_dir: str, output: str, cookies: str = None, force_reencode: bool = False):
    # importar dinamicamente os módulos do diretório src (quando executado como python src/run_pipeline.py)
    try:
        import validate_environment as validator
        import download_videos as downloader
        import analyze_codecs as analyzer
        import concat_videos as concater
    except Exception as e:
        raise RuntimeError(f'Erro ao importar módulos do src: {e}')

    print('1) Validando URLs e ambiente...')
    ok, info = validator.validate(url1, url2)
    if not ok:
        raise RuntimeError('Validação falhou: verifique URLs e ferramentas (yt-dlp, ffmpeg)')

    _ensure_out_dir(out_dir)

    print('2) Baixando vídeos com yt-dlp...')
    p1, p2 = downloader.download_two_videos(url1, url2, out_dir=out_dir, cookies_file=cookies)
    print(' - baixado:', p1)
    print(' - baixado:', p2)

    print('3) Analisando codecs e decidindo método de concat...')
    method, reasons = analyzer.recommend_concat_method([p1, p2])
    print('Recomendação:', method)
    for r in reasons:
        print(' -', r)

    if force_reencode:
        print('Forçando re-encode por opção do usuário')

    print('4) Concatenando...')
    out_path = os.path.abspath(output)
    concater.concat_videos([p1, p2], out_path, force_reencode=force_reencode)

    print('\nPipeline concluído. Arquivo final em:', out_path)
    return out_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Executa todo o pipeline: validar->baixar->analisar->concat')
    parser.add_argument('url1')
    parser.add_argument('url2')
    parser.add_argument('--out-dir', default='./downloads')
    parser.add_argument('--output', default='./output_final.mp4')
    parser.add_argument('--cookies', default=None, help='Arquivo cookies.txt (Netscape) para tweets privados')
    parser.add_argument('--force-reencode', action='store_true')

    args = parser.parse_args()
    try:
        run_pipeline(args.url1, args.url2, args.out_dir, args.output, cookies=args.cookies, force_reencode=args.force_reencode)
    except Exception as e:
        print('Erro no pipeline:', e)
        sys.exit(1)
