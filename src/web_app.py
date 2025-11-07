"""
web_app.py

Aplicação web mínima (FastAPI) para enviar duas URLs de tweets/X e gerar o MP4 combinado.

Uso:
  python -m uvicorn src.web_app:app --reload --host 127.0.0.1 --port 8000

Observações:
- Este é um exemplo síncrono e bem básico: submeter o formulário bloqueará a requisição até
  o processamento terminar. Para produção, mover o processamento para background (Celery, tasks)
  ou usar BackgroundTasks do FastAPI.
"""

import os
import time
from pathlib import Path
from fastapi import FastAPI, Form, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title='projeto-kndauto - basic web UI')

# Servir a pasta downloads para permitir o download do arquivo final
os.makedirs('downloads', exist_ok=True)
app.mount('/downloads', StaticFiles(directory='downloads'), name='downloads')


@app.get('/', response_class=HTMLResponse)
def index():
    html = '''
    <html>
      <head>
        <title>Merge Tweets Vídeo - Básico</title>
      </head>
      <body>
        <h2>Opções</h2>
        <h3>1) Merge de 2 vídeos de tweets/X</h3>
        <form action="/merge" method="post">
          <label>URL do Tweet 1:</label><br>
          <input type="text" name="url1" size="80" required><br><br>
          <label>URL do Tweet 2:</label><br>
          <input type="text" name="url2" size="80" required><br><br>
            <label>Cookies (opcional, path para cookies.txt):</label><br>
            <input type="text" name="cookies" size="80" placeholder="C:\\caminho\\cookies.txt"><br><br>
            <label>Título do vídeo final (opcional):</label><br>
            <input type="text" name="title" size="80" placeholder="Ex: Meu merge"><br><br>
            <input type="checkbox" name="force_reencode"> Forçar re-encode (slower, mais compatível)<br><br>
            <button type="submit">Gerar vídeo combinado</button>
        </form>

        <hr>
        <h3>2) Split e converter vídeo do YouTube (9:16)</h3>
        <form action="/split_youtube" method="post">
          <label>URL do YouTube:</label><br>
          <input type="text" name="url" size="80" required><br><br>
          <label>Número de partes:</label><br>
          <input type="number" name="parts" value="3" min="1"><br><br>
          <label>Título (amarelo, opcional):</label><br>
          <input type="text" name="title" size="80" placeholder="Ex: Meu vídeo"><br><br>
          <label>Legenda (branca, opcional):</label><br>
          <input type="text" name="subtitle" size="80" placeholder="Ex: @meu_usuario"><br><br>
          <button type="submit">Gerar partes 9:16</button>
        </form>
      </body>
    </html>
    '''
    return HTMLResponse(content=html)


@app.post('/merge')
def merge(url1: str = Form(...), url2: str = Form(...), cookies: str = Form(None), title: str = Form(''), force_reencode: str = Form(None)):
    """Endpoint simples que executa o pipeline e redireciona para o arquivo final na pasta downloads."""
    # Importar localmente para evitar circular imports quando a app é importada
    from run_pipeline import run_pipeline
    # converter checkbox para boolean
    force = bool(force_reencode)

    try:
        # run_pipeline will place outputs under downloads/twitter/output_videos and return the chosen output path
        out_path = run_pipeline(url1, url2, out_dir='downloads', output=None, title=title or '', cookies=cookies or None, force_reencode=force)
    except Exception as e:
        # Retornar uma página de erro simples
        return HTMLResponse(f'<h3>Erro durante o processamento:</h3><pre>{e}</pre>', status_code=500)

    # Render a small result page with download link and a button to process another
    rel = os.path.relpath(out_path, start=os.path.abspath('downloads'))
    download_url = f'/downloads/{rel}'
    html = f"""
    <html>
      <head><title>Processamento concluído</title></head>
      <body>
        <h3>Processamento concluído</h3>
        <p>Arquivo gerado: <a href="{download_url}">{os.path.basename(out_path)}</a></p>
        <p><a href="/">&larr; Processar outro</a></p>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.post('/split_youtube')
def split_youtube(background_tasks: BackgroundTasks, url: str = Form(...), parts: int = Form(...), title: str = Form(''), subtitle: str = Form('')):
    """Endpoint que dispara o processo de dividir/convertir YouTube em background.

    Retorna imediatamente um status e escreve resultados em `downloads/youtube/output_videos`.
    """

    # import run_split robustly: try relative, absolute, then load by path as fallback
    def _get_run_split():
        try:
            # when module is imported as package (e.g. src.web_app)
            from .split_youtube import run_split
            return run_split
        except Exception:
            try:
                # when running as script or different import layout
                from src.split_youtube import run_split
                return run_split
            except Exception:
                # fallback: load the file directly by path
                import importlib.util
                mod_path = Path(__file__).parent / 'split_youtube.py'
                spec = importlib.util.spec_from_file_location('split_youtube', str(mod_path))
                mod = importlib.util.module_from_spec(spec)
                # ensure the src folder is on sys.path so local imports inside the module work
                import sys
                src_dir = str(Path(__file__).parent)
                if src_dir not in sys.path:
                    sys.path.insert(0, src_dir)
                spec.loader.exec_module(mod)
                return getattr(mod, 'run_split')

    run_split = _get_run_split()
    out_dir = 'downloads'

    def job():
        try:
            run_split(url, parts=int(parts), title=title or '', subtitle=subtitle or '', out_dir=out_dir)
        except Exception as e:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            with open(Path(out_dir) / 'error.txt', 'w', encoding='utf-8') as f:
                f.write(str(e))

    background_tasks.add_task(job)
    # Return a small HTML page informing the job started and provide a button to process another
    html = f"""
    <html>
      <head><title>Processamento em segundo plano</title></head>
      <body>
        <h3>Processamento iniciado</h3>
        <p>As partes serão escritas em: <code>{out_dir}/youtube/output_videos</code></p>
        <p><a href="/">&larr; Processar outro</a></p>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get('/health')
def health():
    return {'status': 'ok'}
