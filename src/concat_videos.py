"""
concat_videos.py

Concatena dois ou mais vídeos em um único MP4.

Estratégia:
- Tenta concatenação sem re-encodificação usando o concat demuxer do ffmpeg
- Se não for possível (incompatibilidade de codecs/resolução/fps), re-encoda cada
  arquivo para um MPEG-TS com H.264/AAC e concatena os .ts (fallback seguro)

Uso (CLI):
    python src/concat_videos.py out.mp4 input1.mp4 input2.mp4 [...]

O script usa `analyze_codecs.can_concat_without_reencode` para decidir automaticamente.
"""

import os
import subprocess
import tempfile
from typing import List, Tuple

try:
    # importar função de análise (o arquivo analyze_codecs.py foi criado anteriormente)
    from analyze_codecs import can_concat_without_reencode, recommend_concat_method
except Exception:
    # caso a importação falhe (contexto), definir stubs conservadores
    def can_concat_without_reencode(paths: List[str]) -> Tuple[bool, List[str]]:
        return False, ['analyze_codecs não disponível']
    def recommend_concat_method(paths: List[str]):
        return 'reencode', ['analyze_codecs não disponível']


def _run(cmd: List[str]):
    print('>',' '.join(cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Comando falhou: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    return proc


def concat_without_reencode(paths: List[str], output: str):
    """Concat usando concat demuxer (-f concat -i list.txt -c copy).

    Requer que todos os arquivos tenham codecs/resolução/fps compatíveis.
    """
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt', encoding='utf-8') as f:
        for p in paths:
            # ffmpeg espera caminhos com quotes se tiverem espaços
            f.write(f"file '{os.path.abspath(p).replace("'", "'\\''")}" + "'\n")
        list_path = f.name
    try:
        cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_path, '-c', 'copy', output]
        _run(cmd)
    finally:
        try:
            os.remove(list_path)
        except Exception:
            pass


def concat_with_reencode(paths: List[str], output: str, crf: int = 20, preset: str = 'veryfast'):
    """Re-encoda cada entrada para MPEG-TS com H.264/AAC e concatena os .ts resultantes.

    Fluxo:
    - para cada input: ffmpeg -i in -c:v libx264 -preset <preset> -crf <crf> -pix_fmt yuv420p -c:a aac -b:a 128k -f mpegts tmpN.ts
    - depois: ffmpeg -y -i "concat:tmp1.ts|tmp2.ts|..." -c copy -bsf:a aac_adtstoasc output
    """
    tmp_files = []
    try:
        for i, p in enumerate(paths, start=1):
            tmp = os.path.join(tempfile.gettempdir(), f'kndconcat_{os.getpid()}_{i}.ts')
            cmd = [
                'ffmpeg', '-y', '-i', p,
                '-c:v', 'libx264', '-preset', preset, '-crf', str(crf), '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '128k', '-f', 'mpegts', tmp
            ]
            _run(cmd)
            tmp_files.append(tmp)

        concat_input = 'concat:' + '|'.join(tmp_files)
        cmd2 = ['ffmpeg', '-y', '-i', concat_input, '-c', 'copy', '-bsf:a', 'aac_adtstoasc', output]
        _run(cmd2)
    finally:
        for t in tmp_files:
            try:
                os.remove(t)
            except Exception:
                pass


def concat_videos(paths: List[str], output: str, force_reencode: bool = False) -> str:
    """Concatena videos. Retorna o caminho do arquivo final (output).

    Se force_reencode=True, pula análise e usa re-encode.
    """
    if not paths or len(paths) < 2:
        raise ValueError('É necessário pelo menos 2 arquivos de entrada para concatenar')

    if force_reencode:
        method = 'reencode'
        reasons = ['Usuário forçou re-encode']
    else:
        method, reasons = recommend_concat_method(paths)

    print('Método escolhido:', method)
    for r in reasons:
        print(' -', r)

    if method == 'concat':
        try:
            concat_without_reencode(paths, output)
            return output
        except Exception as e:
            print('Concat sem re-encode falhou, faremos fallback para re-encode:', e)

    # fallback para re-encode
    concat_with_reencode(paths, output)
    return output


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Concatena vídeos com fallback para re-encode (H.264/AAC)')
    parser.add_argument('output')
    parser.add_argument('inputs', nargs='+')
    parser.add_argument('--force-reencode', action='store_true')
    parser.add_argument('--crf', type=int, default=20)
    parser.add_argument('--preset', default='veryfast')

    args = parser.parse_args()
    out = args.output
    inputs = args.inputs
    try:
        result = concat_videos(inputs, out, force_reencode=args.force_reencode)
        print('Arquivo final gerado em:', result)
    except Exception as e:
        print('Erro:', e)
        raise
