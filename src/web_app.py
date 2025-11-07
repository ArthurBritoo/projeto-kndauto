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
from fastapi import FastAPI, Form, Request
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
        <h2>Merge de 2 vídeos de tweets (básico)</h2>
        <form action="/merge" method="post">
          <label>URL do Tweet 1:</label><br>
          <input type="text" name="url1" size="80" required><br><br>
          <label>URL do Tweet 2:</label><br>
          <input type="text" name="url2" size="80" required><br><br>
          <label>Cookies (opcional, path para cookies.txt):</label><br>
          <input type="text" name="cookies" size="80" placeholder="C:\\caminho\\cookies.txt"><br><br>
          <input type="checkbox" name="force_reencode"> Forçar re-encode (slower, mais compatível)<br><br>
          <button type="submit">Gerar vídeo combinado</button>
        </form>
      </body>
    </html>
    '''
    return HTMLResponse(content=html)


@app.post('/merge')
def merge(url1: str = Form(...), url2: str = Form(...), cookies: str = Form(None), force_reencode: str = Form(None)):
    """Endpoint simples que executa o pipeline e redireciona para o arquivo final na pasta downloads."""
    # Importar localmente para evitar circular imports quando a app é importada
    from run_pipeline import run_pipeline

    timestamp = int(time.time())
    output_name = f'output_{timestamp}.mp4'
    output_path = os.path.join('downloads', output_name)

    # converter checkbox para boolean
    force = bool(force_reencode)

    try:
        run_pipeline(url1, url2, out_dir='downloads', output=output_path, cookies=cookies or None, force_reencode=force)
    except Exception as e:
        # Retornar uma página de erro simples
        return HTMLResponse(f'<h3>Erro durante o processamento:</h3><pre>{e}</pre>', status_code=500)

    # Redirecionar para o arquivo estático gerado
    return RedirectResponse(url=f'/downloads/{output_name}', status_code=303)


@app.get('/health')
def health():
    return {'status': 'ok'}
