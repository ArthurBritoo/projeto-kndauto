#!/usr/bin/env python3
"""
validate_environment.py

Uso:
    python src/validate_environment.py <url_tweet_1> <url_tweet_2>
"""

import re
import sys
import shutil
import subprocess
from urllib.parse import urlparse

TWEET_RE = re.compile(
    r'^https?://(?:www\.)?(?:x\.com|twitter\.com)/[^/]+/(?:status|statuses)/(?P<id>\d+)', re.IGNORECASE
)

def extract_tweet_id(url: str):
    m = TWEET_RE.match(url.strip())
    if not m:
        return None
    return m.group('id')

def check_executable(name: str):
    # Primeiro tenta localizar no PATH
    path = shutil.which(name)
    if path:
        return path
    # Em alguns sistemas, o executável pode ser 'yt-dlp.exe' ou 'ffmpeg.exe' (Windows) — shutil.which já lida com isso.
    return None

def check_command_version(cmd:list):
    try:
        out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if out.returncode == 0:
            # Retornamos a primeira linha do stdout ou stderr como versão
            txt = (out.stdout + out.stderr).strip().splitlines()
            return txt[0] if txt else ""
        else:
            return None
    except Exception:
        return None

def validate(url1: str, url2: str):
    ids = []
    for idx, u in enumerate((url1, url2), start=1):
        tid = extract_tweet_id(u)
        if not tid:
            print(f"[ERRO] URL #{idx} inválida para tweet/X: {u}")
            return False, None
        ids.append(tid)
    # checar executáveis
    yt_path = check_executable('yt-dlp')
    ffmpeg_path = check_executable('ffmpeg')
    ffprobe_path = check_executable('ffprobe') or ffmpeg_path  # ffprobe pode estar junto do ffmpeg
    
    yt_ver = check_command_version(['yt-dlp', '--version']) if yt_path else None
    ffmpeg_ver = check_command_version(['ffmpeg', '-version']) if ffmpeg_path else None
    ffprobe_ver = check_command_version(['ffprobe', '-version']) if ffprobe_path else None

    print("URLs válidas. IDs extraídos:", ids)
    print("yt-dlp:", yt_path or "não encontrado", f"versão: {yt_ver or 'desconhecida'}")
    print("ffmpeg:", ffmpeg_path or "não encontrado", f"versão: {ffmpeg_ver or 'desconhecida'}")
    print("ffprobe:", ffprobe_path or "não encontrado", f"versão: {ffprobe_ver or 'desconhecida'}")

    ok = bool(yt_path and ffmpeg_path)
    if not ok:
        print("\n[ATENÇÃO] As ferramentas necessárias não foram encontradas no PATH.")
    return ok, {'ids': ids, 'paths': {'yt-dlp': yt_path, 'ffmpeg': ffmpeg_path, 'ffprobe': ffprobe_path}}

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Uso: python src/validate_environment.py <url_tweet_1> <url_tweet_2>")
        sys.exit(2)
    ok, info = validate(sys.argv[1], sys.argv[2])
    if ok:
        print("\nAmbiente OK — pode prosseguir para o download (PASSO 2).")
        sys.exit(0)
    else:
        print("\nAmbiente incompleto. Siga as instruções de instalação abaixo.")
        sys.exit(1)