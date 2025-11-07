Projeto KNDAuto — Merge de vídeos de tweets/X (básico)
README para seu amigo — instruções passo a passo (curtas e testáveis)
===================================================================

Objetivo rápido
---------------
Este projeto baixa dois vídeos de tweets/X e gera um único arquivo MP4 com os dois vídeos concatenados.
Este README foi escrito para que uma IA ou você possa explicar de forma clara ao seu amigo o que fazer.

O que confirmar antes de começar
--------------------------------
1) Sistema operacional: Windows (as instruções abaixo usam PowerShell). Se o amigo usar macOS/Linux, eu adapto.
2) Python 3.10+ instalado (verificar com `python --version`).
3) Conexão com a internet e permissão para instalar pacotes via pip.

Passo a passo (o que pedir que o amigo faça)
-------------------------------------------

1) Copiar a pasta do projeto para o PC
	- Exemplo: `C:\Users\Amigo\Desktop\projeto-kndauto`

2) Preparar o ambiente Python (criar e ativar venv)
	- No PowerShell, dentro da pasta do projeto execute:
```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

3) Garantir que o FFmpeg esteja disponível
	- Opção A (Chocolatey):
	  ```powershell
	  choco install ffmpeg -y
	  ```
	- Opção B (manual): baixe um build estático (ex.: https://www.gyan.dev/ffmpeg/builds/) e coloque a pasta `ffmpeg` na raiz do projeto (de modo que exista `ffmpeg\bin\ffmpeg.exe`).
	- Verificar com:
```powershell
ffmpeg -version
ffprobe -version
```

4) Rodar a web UI local
	- Iniciar o servidor:
```powershell
python -m uvicorn src.web_app:app --reload --host 127.0.0.1 --port 8000
```
	- Abrir no navegador: http://127.0.0.1:8000/
	- A interface é simples: cole as duas URLs de tweets, clique em "Gerar vídeo combinado". O arquivo resultante será servido em `/downloads`.

5) (Alternativa) Gerar um .exe para facilitar (opcional)
	- No venv:
```powershell
python -m pip install pyinstaller
pyinstaller --onefile --noconsole --name projeto-kndauto-launcher --add-data ".\\ffmpeg;ffmpeg" src\\launcher.py
```
	- Enviar `dist\\projeto-kndauto-launcher.exe` ao amigo. Ao clicar duas vezes, o navegador deverá abrir automaticamente em http://127.0.0.1:8000/.

Checklist simples que a IA pode seguir para guiar o amigo
---------------------------------------------------------
1) Confirmar SO e versão do Python.
2) Pedir para abrir PowerShell na pasta do projeto.
3) Copiar/colar os blocos de comando (venv, pip).
4) Verificar `ffmpeg -version`.
5) Rodar uvicorn e abrir o navegador.
6) Colar URLs e aguardar o processamento.

Resolução rápida de problemas
-----------------------------
- "Form data requires python-multipart": rode `python -m pip install python-multipart`.
- "ffmpeg não encontrado": instale via Chocolatey ou coloque `ffmpeg\bin` na pasta do projeto.
- Se o .exe não abrir nada: peça para abrir um terminal, executar o exe e verificar mensagens ou gerar o exe sem `--noconsole` para ver logs.

Boas práticas e notas legais
---------------------------
- Não comite grandes binários no Git (como `ffmpeg`); use GitHub Releases ou instruções para instalar.
- Respeite direitos autorais dos vídeos baixados.

Exemplo de texto que a IA pode falar ao amigo
--------------------------------------------
"Vou te guiar passo a passo. Primeiro abre o PowerShell na pasta que eu te mandei e roda: `python -m venv .venv` etc. Depois instala o FFmpeg se necessário e roda o servidor. Quando a página abrir, cole as duas URLs e clique em gerar. Se algo falhar, me diga a mensagem de erro e eu te ajudo." 

Próximos passos que posso fazer por você
---------------------------------------
- Gerar um `.bat` para facilitar o start no Windows (faço agora se quiser).
- Recriar o .exe sem `--noconsole` para facilitar a visualização de logs durante testes.
- Remover `ffmpeg` do repositório e adicionar instruções para baixar via Releases/Chocolatey.

Diga qual desses você prefere e eu faço agora.

---

Adicionando suporte a YouTube (splits verticais 9:16)
--------------------------------------------------
Se você quiser que a mesma interface web aceite URLs do YouTube e dispare o processo de dividir/transformar o vídeo, siga estas instruções.

1) Arquivo principal que eu adicionei: `src/split_youtube.py` — esse script faz todo o trabalho (download, dividir, converter para 9:16, adicionar textos e exportar `parte_1.mp4`, `parte_2.mp4`, ...).

2) Para expor uma rota no `src/web_app.py` que aceite URLs do YouTube, adicione um endpoint POST que receba `url`, `parts`, `title`, `subtitle` e chame internamente `src/split_youtube.py` (como subprocesso ou importando a função).

Exemplo resumido (insira no seu `src/web_app.py`):

```python
from fastapi import FastAPI, Form, BackgroundTasks
from pathlib import Path
import subprocess

app = FastAPI()

@app.post('/split_youtube')
async def split_youtube_endpoint(background_tasks: BackgroundTasks, url: str = Form(...), parts: int = Form(...), title: str = Form(''), subtitle: str = Form('')):
	# roda em background para não bloquear a resposta
	out_dir = Path('youtube_output')
	def job():
		# chama o script Python como subprocess para isolar erros e logs
		cmd = [
			'python', 'src/split_youtube.py', '--url', url, '--parts', str(parts), '--title', title, '--subtitle', subtitle, '--out-dir', str(out_dir)
		]
		subprocess.run(cmd)
	background_tasks.add_task(job)
	return {'status': 'started', 'out_dir': str(out_dir)}
```

3) Comando exato para executar o servidor UVicorn em uma porta (por exemplo 9000):

```powershell
python -m uvicorn src.web_app:app --reload --host 0.0.0.0 --port 9000
```

Isso fará com que a API esteja disponível em `http://<seu_ip>:9000/` e a rota `/split_youtube` aceite POSTs com form-data.

👉 Agora você precisa fazer isso manualmente: editar `src/web_app.py` e colar o trecho acima (ou me pedir para aplicar a modificação e eu incluo o endpoint por você).

Opções extras
-------------
- Posso transformar o `src/split_youtube.py` em uma API FastAPI completa (endpoint, validação e status de jobs).
- Posso também adicionar um CLI alternativo (ex.: `python src/split_youtube.py --url <link> --parts 3` — já implementado) e documentá-lo.

Se quiser que eu aplique o endpoint diretamente no `src/web_app.py`, me autorize e eu faço o commit.
