"""
analyze_codecs.py

Ferramentas para analisar arquivos de vídeo com ffprobe e decidir se é possível
concatenar sem re-encodificação.

Uso (CLI):
    python src/analyze_codecs.py <arquivo1> <arquivo2>

Funções principais:
- analyze_file(path) -> dict: retorna propriedades detectadas (video/audio codec, w/h, fps, duration)
- can_concat_without_reencode([paths]) -> (bool, reasons): decide se concat direto é seguro
- recommend_concat_method([paths]) -> 'concat' or 'reencode' e justificativa

Requisitos:
- ffprobe (parte do ffmpeg) disponível no PATH
"""

import json
import subprocess
import sys
from typing import Dict, List, Tuple, Any


def _ffprobe_json(path: str) -> Dict[str, Any]:
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", path]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe falhou para {path}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def _parse_r_frame_rate(r: str) -> float:
    # r_frame_rate pode ser "30000/1001" ou "30/1" ou "30"
    if not r:
        return 0.0
    if '/' in r:
        num, den = r.split('/')
        try:
            return float(num) / float(den)
        except Exception:
            return 0.0
    try:
        return float(r)
    except Exception:
        return 0.0


def analyze_file(path: str) -> Dict[str, Any]:
    data = _ffprobe_json(path)
    streams = data.get('streams', [])
    info = {
        'path': path,
        'duration': float(data.get('format', {}).get('duration') or 0.0),
        'format_name': data.get('format', {}).get('format_name'),
        'nb_streams': len(streams),
        'video': None,
        'audio': None,
    }
    for s in streams:
        if s.get('codec_type') == 'video' and info['video'] is None:
            fps = _parse_r_frame_rate(s.get('r_frame_rate') or s.get('avg_frame_rate') or '')
            info['video'] = {
                'codec_name': s.get('codec_name'),
                'codec_long_name': s.get('codec_long_name'),
                'width': int(s.get('width') or 0),
                'height': int(s.get('height') or 0),
                'pix_fmt': s.get('pix_fmt'),
                'fps': fps,
                'bits_per_raw_sample': s.get('bits_per_raw_sample'),
            }
        if s.get('codec_type') == 'audio' and info['audio'] is None:
            info['audio'] = {
                'codec_name': s.get('codec_name'),
                'sample_rate': int(s.get('sample_rate') or 0),
                'channels': int(s.get('channels') or 0),
            }
    return info


def _float_close(a: float, b: float, tol: float = 0.01) -> bool:
    return abs(a - b) <= tol


def can_concat_without_reencode(paths: List[str]) -> Tuple[bool, List[str]]:
    """Verifica se todos os arquivos possuem propriedades compatíveis para concat demuxer (sem re-encode).

    Critérios (simplificados):
    - codec de vídeo idêntico
    - codec de áudio idêntico (ou ambos sem áudio)
    - mesma resolução (width/height)
    - fps igual (com tolerância)
    - mesma pixel format idealmente

    Retorna (True, []) se pode concatenar; caso contrário, (False, [reasons...])
    """
    infos = [analyze_file(p) for p in paths]
    reasons: List[str] = []

    # verificar vídeo
    videos = [i['video'] for i in infos]
    if any(v is None for v in videos):
        reasons.append('Algum arquivo não tem stream de vídeo detectado')
        return False, reasons

    first = videos[0]
    for idx, v in enumerate(videos[1:], start=2):
        if v['codec_name'] != first['codec_name']:
            reasons.append(f"Codec de vídeo diferente entre 1 e {idx}: {first['codec_name']} != {v['codec_name']}")
        if v['width'] != first['width'] or v['height'] != first['height']:
            reasons.append(f"Resolução diferente entre 1 e {idx}: {first['width']}x{first['height']} != {v['width']}x{v['height']}")
        if not _float_close(v.get('fps', 0.0) or 0.0, first.get('fps', 0.0) or 0.0):
            reasons.append(f"FPS diferente entre 1 e {idx}: {first.get('fps')} != {v.get('fps')}")
        if v.get('pix_fmt') != first.get('pix_fmt'):
            # pix_fmt pode variar; marcar como aviso (pode ou não impedir concat dependendo do demuxer)
            reasons.append(f"Pix_fmt diferente entre 1 e {idx}: {first.get('pix_fmt')} != {v.get('pix_fmt')}")

    # verificar áudio
    audios = [i['audio'] for i in infos]
    # se todos None, ok
    if any(a is None for a in audios) and not all(a is None for a in audios):
        reasons.append('Alguns arquivos têm stream de áudio e outros não')
    else:
        # se ambos tem audio, comparar codec/sample/channels
        if audios[0] is not None:
            first_a = audios[0]
            for idx, a in enumerate(audios[1:], start=2):
                if a['codec_name'] != first_a['codec_name']:
                    reasons.append(f"Codec de áudio diferente entre 1 e {idx}: {first_a['codec_name']} != {a['codec_name']}")
                if a['sample_rate'] != first_a['sample_rate']:
                    reasons.append(f"Sample rate diferente entre 1 e {idx}: {first_a['sample_rate']} != {a['sample_rate']}")
                if a['channels'] != first_a['channels']:
                    reasons.append(f"Número de canais diferente entre 1 e {idx}: {first_a['channels']} != {a['channels']}")

    can = len(reasons) == 0
    return can, reasons


def recommend_concat_method(paths: List[str]) -> Tuple[str, List[str]]:
    can, reasons = can_concat_without_reencode(paths)
    if can:
        return 'concat', ['Arquivos compatíveis — usar concat demuxer (sem re-encode)']
    # caso contrário, sugerir re-encode para H.264/AAC com parâmetros seguros
    rec = [
        'Recomendado re-encodar: parâmetros alvo H.264 (libx264) para vídeo e AAC para áudio',
        'Razões: ' + '; '.join(reasons)
    ]
    return 'reencode', rec


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Uso: python src/analyze_codecs.py <arquivo1> <arquivo2> [<arquivoN> ...]')
        sys.exit(2)
    paths = sys.argv[1:]
    print('Analisando arquivos:')
    for p in paths:
        print(' -', p)
    try:
        results = [analyze_file(p) for p in paths]
        for r in results:
            print('\nArquivo:', r['path'])
            print('  formato:', r.get('format_name'))
            print('  duracao:', r.get('duration'))
            if r.get('video'):
                v = r['video']
                print('  video codec:', v.get('codec_name'), f"({v.get('codec_long_name')})")
                print('  resolucao:', f"{v.get('width')}x{v.get('height')}")
                print('  fps:', v.get('fps'))
                print('  pix_fmt:', v.get('pix_fmt'))
            if r.get('audio'):
                a = r['audio']
                print('  audio codec:', a.get('codec_name'))
                print('  sample_rate:', a.get('sample_rate'))
                print('  canais:', a.get('channels'))

        method, reasons = recommend_concat_method(paths)
        print('\nRecomendação:', method)
        for line in reasons:
            print(' -', line)
    except Exception as e:
        print('Erro durante análise:', e)
        sys.exit(1)
