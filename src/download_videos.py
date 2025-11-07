"""
download_videos.py

Funções para baixar vídeos de tweets/X usando yt-dlp.

Uso:
    from download_videos import download_tweet_video, download_two_videos

    path1 = download_tweet_video(url1, out_dir="./downloads")
    path2 = download_tweet_video(url2, out_dir="./downloads")

    # ou baixar dois de uma vez
    p1, p2 = download_two_videos(url1, url2, out_dir="./downloads")

Observações:
- Requer `yt-dlp` instalado (pip install yt-dlp) e acesso de rede.
- Para tweets privados, passe um arquivo de cookies em formato Netscape (cookies.txt) via
  opção cookies or via `yt-dlp` args.
"""

import os
import re
import time
from typing import Optional, Tuple

try:
    # Import do módulo Python do yt-dlp (recomendado para uso programático)
    import yt_dlp as ytdlp
except Exception as e:
    ytdlp = None
    # Não falhar aqui; o script irá avisar ao usuário para instalar.

TWEET_RE = re.compile(
    r'^https?://(?:www\.)?(?:x\.com|twitter\.com)/[^/]+/(?:status|statuses)/(?P<id>\d+)', re.IGNORECASE
)


def extract_tweet_id(url: str) -> Optional[str]:
    m = TWEET_RE.match(url.strip())
    return m.group('id') if m else None


def _ensure_out_dir(path: str):
    os.makedirs(path, exist_ok=True)


def download_tweet_video(url: str, out_dir: str = './downloads', cookies_file: Optional[str] = None, max_retries: int = 3, timeout: int = 300) -> str:
    """
    Baixa o vídeo principal do tweet usando yt-dlp.

    Retorna o caminho completo do arquivo baixado.

    Parâmetros:
    - url: URL do tweet (string)
    - out_dir: pasta onde salvar o arquivo
    - cookies_file: caminho opcional para cookies (Netscape cookies.txt) para acessar conteúdo privado
    - max_retries: número de tentativas em caso de falha
    - timeout: timeout (segundos) para a operação de download (passada ao yt-dlp como --socket-timeout)
    """
    if ytdlp is None:
        raise RuntimeError('yt-dlp não está instalado como módulo Python. Rode: python -m pip install yt-dlp')

    tid = extract_tweet_id(url)
    if not tid:
        raise ValueError(f'URL inválida de tweet/X: {url}')

    _ensure_out_dir(out_dir)

    # Template de saída: usar id do video como nome (garante unicidade)
    outtmpl = os.path.join(out_dir, f"{tid}.%(ext)s")

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': outtmpl,
        'noplaylist': True,
        'quiet': True,
        'socket_timeout': timeout,
        # 'retries': 3, # não existe diretamente aqui; tratamos por aplicação
        # evitar limpar arquivos parcialmente baixados automaticamente -- yt-dlp lida com isso
    }

    if cookies_file:
        ydl_opts['cookiefile'] = cookies_file

    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            with ytdlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                # O yt-dlp retornará um dict com 'ext' e 'requested_downloads' info.
                # Precisamos localizar o arquivo salvo: a saída tem pattern outtmpl com ext.
                ext = info.get('ext') or info.get('requested_formats', [{}])[-1].get('ext')
                if not ext:
                    # fallback: procurar nos arquivos da pasta por prefixo id
                    for f in os.listdir(out_dir):
                        if f.startswith(tid + '.'):
                            return os.path.join(out_dir, f)
                    raise RuntimeError('Não foi possível determinar a extensão do arquivo baixado')
                out_path = os.path.join(out_dir, f"{tid}.{ext}")
                if os.path.exists(out_path):
                    return out_path
                # se não existe, talvez o yt-dlp salvou com outro nome; tentar localizar
                for f in os.listdir(out_dir):
                    if f.startswith(tid + '.'):
                        return os.path.join(out_dir, f)
                raise RuntimeError('Download aparentemente concluído mas arquivo não encontrado')
        except Exception as e:
            last_exc = e
            # backoff exponencial simples
            wait = min(5 * attempt, 60)
            time.sleep(wait)
    # se chegou aqui, falhou todas as tentativas
    raise RuntimeError(f'Falha ao baixar {url} após {max_retries} tentativas: {last_exc}')


def download_two_videos(url1: str, url2: str, out_dir: str = './downloads', cookies_file: Optional[str] = None) -> Tuple[str, str]:
    """Baixa os dois vídeos e retorna os dois caminhos (path1, path2)."""
    p1 = download_tweet_video(url1, out_dir=out_dir, cookies_file=cookies_file)
    p2 = download_tweet_video(url2, out_dir=out_dir, cookies_file=cookies_file)
    return p1, p2


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Baixar vídeo de dois tweets/X usando yt-dlp')
    parser.add_argument('url1')
    parser.add_argument('url2')
    parser.add_argument('--out', default='./downloads')
    parser.add_argument('--cookies', default=None, help='Arquivo cookies.txt (Netscape) para tweets privados')

    args = parser.parse_args()
    print('Iniciando downloads...')
    try:
        p1, p2 = download_two_videos(args.url1, args.url2, out_dir=args.out, cookies_file=args.cookies)
        print('Download concluído:')
        print(' -', p1)
        print(' -', p2)
    except Exception as e:
        print('Erro:', e)
        raise
