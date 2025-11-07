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


@app.post('/split_youtube')
def split_youtube(background_tasks: BackgroundTasks, url: str = Form(...), parts: int = Form(...), title: str = Form(''), subtitle: str = Form('')):
  """Endpoint que dispara o processo de dividir/convertir YouTube em background.

  Retorna imediatamente um status e escreve resultados em `youtube_output`.
  """
  from split_youtube import run_split

  out_dir = 'youtube_output'

  def job():
    try:
      run_split(url, parts=int(parts), title=title or '', subtitle=subtitle or '', out_dir=out_dir)
    except Exception as e:
      # escrevemos um arquivo de erro simples para diagnóstico
      Path(out_dir).mkdir(parents=True, exist_ok=True)
      with open(Path(out_dir) / 'error.txt', 'w', encoding='utf-8') as f:
        f.write(str(e))

  background_tasks.add_task(job)
  return {'status': 'started', 'out_dir': out_dir}


@app.get('/health')
def health():
    return {'status': 'ok'}
