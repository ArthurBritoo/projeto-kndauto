"""
launcher.py

Launcher simples para Windows: inicia o servidor FastAPI (uvicorn) e abre o navegador
no endereço local. Projetado para ser empacotado com PyInstaller em um único .exe.

Comportamento:
- Se houver uma pasta "ffmpeg" ao lado do executável (ou no projeto durante desenvolvimento),
  adiciona seu subdiretório "bin" ao PATH para que ffmpeg/ffprobe sejam encontrados.
- Inicia uvicorn numa thread em background e aguarda a porta ficar disponível antes de
  abrir o navegador padrão em http://127.0.0.1:8000/

Uso para empacotar:
  1) Coloque a pasta "ffmpeg" (contendo bin\ffmpeg.exe e bin\ffprobe.exe) na raiz do projeto.
  2) Ative seu venv com as dependências instaladas (uvicorn, fastapi, etc.).
  3) Instale o PyInstaller: python -m pip install pyinstaller
  4) Execute o PyInstaller (exemplo):
     pyinstaller --onefile --noconsole --name projeto-kndauto-launcher --add-data "ffmpeg;ffmpeg" src\launcher.py

Ao executar o .exe gerado, o servidor será iniciado e o navegador será aberto automaticamente.
"""

import os
import sys
import threading
import time
import webbrowser
import socket


def ensure_ffmpeg_in_path():
    """Se existir uma pasta 'ffmpeg/bin' próxima ao executável, adiciona ao PATH."""
    # Quando empacotado com PyInstaller, os arquivos são extraídos para _MEIPASS
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__))
    ff_bin = os.path.join(base_path, 'ffmpeg', 'bin')
    if os.path.isdir(ff_bin):
        os.environ['PATH'] = ff_bin + os.pathsep + os.environ.get('PATH', '')


def run_server():
    # Importar localmente para reduzir custo na inicialização
    import uvicorn
    from web_app import app
    # uvicorn.run bloqueia; rodamos em uma thread separada
    uvicorn.run(app, host='127.0.0.1', port=8000)


def wait_for_port(host='127.0.0.1', port=8000, timeout=30.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except Exception:
            time.sleep(0.2)
    return False


def main():
    ensure_ffmpeg_in_path()

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    ready = wait_for_port('127.0.0.1', 8000, timeout=30.0)
    url = 'http://127.0.0.1:8000/'
    if ready:
        try:
            webbrowser.open(url)
        except Exception:
            print(f'Abra no navegador manualmente: {url}')
    else:
        print('Servidor não ficou pronto no tempo esperado. Verifique logs.')

    # Manter o processo principal vivo enquanto a thread do servidor roda
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
