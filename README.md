Projeto KNDAuto — Merge de vídeos de tweets/X (básico)
===============================================

Resumo
------
Este projeto é uma ferramenta local, gratuita e open-source para baixar dois vídeos de tweets/X e juntá-los em um único arquivo MP4.

Funcionalidades principais
- Recebe duas URLs de tweets/X
- Baixa os vídeos com `yt-dlp`
- Analisa codecs com `ffprobe` (parte do FFmpeg)
- Tenta concatenar sem re-encode (rápido) e faz fallback para re-encode em H.264/AAC caso necessário
- Fornece uma interface web mínima (FastAPI) e um launcher empacotável em .exe

Requisitos (Windows)
- Python 3.10+ (testado com 3.13)
- pip
- FFmpeg (ffmpeg e ffprobe) — ou deixá-lo empacotado ao lado do exe

Arquitetura básica
- `src/validate_environment.py` — valida URLs e checa ferramentas (yt-dlp, ffmpeg)
- `src/download_videos.py` — baixa vídeos usando `yt-dlp` (módulo Python)
- `src/analyze_codecs.py` — usa `ffprobe` para analisar codecs e decidir método de concat
- `src/concat_videos.py` — concatena (sem re-encode ou com fallback re-encode)
- `src/run_pipeline.py` — orquestra o fluxo completo (validate -> download -> analyze -> concat)
- `src/web_app.py` — interface web básica (FastAPI)
- `src/launcher.py` — launcher pensado para empacotar com PyInstaller (inicia servidor e abre navegador)

Instalação (rápido)
-------------------
Recomendo usar um virtualenv dentro do projeto:

PowerShell (na raiz do projeto):
```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Instalar FFmpeg (se ainda não tiver):

Opção A — Chocolatey (mais simples):
```powershell
choco install ffmpeg -y
```

Opção B — download manual (se não tiver Chocolatey):
1. Baixe um build estático (ex.: https://www.gyan.dev/ffmpeg/builds/)
2. Extraia e coloque a pasta `ffmpeg` na raiz do projeto (de forma que exista `ffmpeg\bin\ffmpeg.exe`)

Rodando em desenvolvimento (servidor web local)
---------------------------------------------
Após instalar dependências e FFmpeg:

```powershell
# iniciar o servidor (uvicorn)
python -m uvicorn src.web_app:app --reload --host 127.0.0.1 --port 8000
```

Acesse no navegador: http://127.0.0.1:8000/

Usando o launcher (.exe)
------------------------
Para criar um executável Windows “one-click”:

1) Instale PyInstaller no venv:
```powershell
python -m pip install pyinstaller
```

2) Se você deseja embutir o FFmpeg com o .exe (recomendado para usuários finais), coloque a pasta `ffmpeg` na raiz do projeto (com `bin\ffmpeg.exe` e `bin\ffprobe.exe`).

3) Execute (PowerShell):
```powershell
pyinstaller --onefile --noconsole --name projeto-kndauto-launcher --add-data ".\ffmpeg;ffmpeg" src\launcher.py
```

Obs. sobre o `--add-data` no Windows: a sintaxe é `"SRC;DEST"` e, no PowerShell, as barras invertidas e aspas devem ser escapadas como no exemplo acima.

O `.exe` será gerado em `dist\projeto-kndauto-launcher.exe`.

Se preferir não empacotar, você pode distribuir o projeto e pedir ao usuário que execute o `.bat` (ex.: ativar venv e iniciar uvicorn).

Exemplos de uso (linha de comando)
---------------------------------
- Baixar dois vídeos manualmente:
```powershell
python src\download_videos.py "https://x.com/user/status/ID1" "https://x.com/user/status/ID2" --out .\downloads
```

- Rodar pipeline completo (gera ./output_final.mp4):
```powershell
python src\run_pipeline.py "<url1>" "<url2>" --out-dir .\downloads --output .\output_final.mp4
```

Problemas comuns e soluções
---------------------------
- Form data requires "python-multipart": instale `python-multipart` (já incluído no `requirements.txt`).
- ffmpeg/ffprobe não encontrado: instale via Chocolatey ou coloque `ffmpeg\bin` na raiz do projeto (ou no PATH do sistema).
- SmartScreen / antivírus ao abrir o .exe: EXEs gerados por PyInstaller podem acionar avisos. Para distribuição ampla, assine digitalmente o arquivo.
- Tweets privados: gere um `cookies.txt` (formato Netscape) e passe a opção `--cookies C:\caminho\cookies.txt` nos comandos.

Dicas para entregar ao seu amigo (passo-a-passo simplificado)
-----------------------------------------------------------
1. Copie a pasta do projeto para o PC do seu amigo.
2. Peça para ele instalar Python 3.10+ e criar/ativar venv (ou forneça o .exe gerado).
3. Se usar o .exe gerado, apenas execute `dist\projeto-kndauto-launcher.exe` e abra o navegador quando for aberto automaticamente.
4. Se usar sem empacotar: ative o venv, rode `python -m pip install -r requirements.txt` e então `python -m uvicorn src.web_app:app --reload --host 127.0.0.1 --port 8000`.

Notas legais e licença
---------------------
- Este projeto usa `yt-dlp` e `ffmpeg`, ambos open-source. Respeite licenças e direitos autorais dos vídeos que baixar.
- Use para fins educativos/testes locais. Não recomendo uso para distribuição de conteúdos protegidos sem permissão.

Estrutura de arquivos (resumida)
-------------------------------
- `src/` — código fonte (validate, download, analyze, concat, web_app, launcher, run_pipeline)
- `requirements.txt` — dependências Python
- `ffmpeg/` — (opcional) pasta com binários ffmpeg (colocar antes de empacotar)
- `dist/` — saída do PyInstaller
- `downloads/` — arquivos baixados (ignorado pelo .gitignore)

Ajuda / Contribuições
---------------------
Se quiser, eu posso:
- Gerar um instalador (Inno Setup) para facilitar instalação no Windows;
- Mudar a UI para usar BackgroundTasks e mostrar status de job;
- Adicionar testes unitários básicos;
- Ajudar a assinar digitalmente o executável (requer conta de desenvolvedor).

Obrigado — se quiser eu já gero um README curto em inglês também, ou um `.bat` para facilitar o start no Windows.
# projeto-kndauto

Repositório local sincronizado com https://github.com/ArthurBritoo/projeto-kndauto

Conteúdo inicial criado automaticamente pelo assistente para permitir o primeiro commit.
