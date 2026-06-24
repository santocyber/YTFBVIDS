<div align="center">
  <h1>YTFBVIDS</h1>
  <p>
    <strong>YouTube / Facebook / TikTok Video Downloader & Shorts Creator</strong>
  </p>
  <p>
    <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License MIT">
    <img src="https://img.shields.io/badge/ffmpeg-required-red?logo=ffmpeg" alt="FFmpeg">
  </p>
  <p>
    Web app em Flask para baixar vídeos e criar Shorts/Reels no formato 9:16 (1080×1920).
    <br>
    Interface em português com tema escuro.
  </p>
</div>

---

## Funcionalidades

- **Download** de vídeos via `yt-dlp` (YouTube, Facebook, Instagram, TikTok, Twitter, etc.)
- **Download Assíncrono** — progresso em tempo real com barra de progresso e ETA
- **Corte Manual** — escolha início e duração para criar um short
- **Detecção Automática de Cenas** — divide o vídeo usando o filtro `scene` do FFmpeg, com fallback uniforme
- **Divisão de Cenas Longas** — cenas com mais de 30s são divididas em partes para Shorts
- **Smart Crop** — detecta rostos com OpenCV Haar Cascade e centraliza o crop
- **Geração em Massa** — crie shorts de todas as cenas de uma só vez (síncrono ou assíncrono com progresso)
- **Modo TV** — player sequencial com playlist lateral e navegação
- **Feed de Shorts** — navegação vertical estilo TikTok com autoplay e scroll infinito
- **Extrair Áudio** — via CLI ou diretamente pela interface web
- **Preview com Navegação** — preview de shorts com links para anterior/próximo

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3, Flask |
| Frontend | Jinja2, Bootstrap 5, Bootstrap Icons |
| Vídeo | FFmpeg / FFprobe (subprocess + pipe) |
| Download | yt-dlp (CLI e Python API) |
| Visão Computacional | OpenCV (opcional, para smart crop) |

## Requisitos

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) (com `ffprobe`)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

```bash
# Instalar dependências Python
pip install -r requirements.txt

# Verificar ferramentas de sistema
ffmpeg -version
yt-dlp --version
```

## Instalação

```bash
git clone https://github.com/santocyber/YTFBVIDS.git
cd YTFBVIDS
pip install -r requirements.txt
```

## Como Usar

### Servidor Web

```bash
python3 app.py
# Acesse http://localhost:5080
```

Ou em background:

```bash
./start.sh   # inicia na porta 5080, PID salvo em .server.pid
./stop.sh    # para o servidor
```

### CLI

```bash
python3 scripts/baixar_editar.py <URL>              # baixar + extrair áudio
python3 scripts/baixar_editar.py <URL> --audio-only  # apenas áudio
python3 scripts/baixar_editar.py <URL> --cortar 30   # baixar + cortar short de 30s
```

## Rotas da API

| Rota | Método | Descrição |
|------|--------|-----------|
| `/` | GET | Página inicial com formulário de download |
| `/baixar` | POST | Download síncrono (subprocess `yt-dlp`) |
| `/baixar-async` | POST | Download assíncrono com progresso (yt-dlp Python API) |
| `/progresso/<job_id>` | GET | Status do download assíncrono (JSON) |
| `/videos` | GET | Lista de vídeos baixados (suporta `?sort=` e `?order=`) |
| `/videos/tv` | GET | Modo TV com player sequencial e playlist |
| `/videos/<filename>` | GET | Servir arquivo de vídeo |
| `/videos/<filename>/preview` | GET | Preview do vídeo |
| `/videos/<filename>/audio` | GET | Download do áudio em MP3 |
| `/videos/<filename>/cortar` | POST | Corte manual (início + duração) |
| `/videos/<filename>/cenas` | GET | Detecção automática de cenas |
| `/videos/<filename>/gerar-shorts` | POST | Gerar shorts síncrono (cenas selecionadas) |
| `/videos/<filename>/gerar-tudo` | POST | Gerar shorts síncrono (todas as cenas) |
| `/videos/<filename>/gerar-shorts-async` | POST | Gerar shorts assíncrono com progresso |
| `/progresso-short/<job_id>` | GET | Status da geração de shorts (JSON) |
| `/shorts` | GET | Lista de shorts gerados (suporta `?sort=` e `?order=`) |
| `/shorts/feed` | GET | Feed vertical estilo TikTok |
| `/shorts/<filename>` | GET | Servir arquivo de short |
| `/shorts/<filename>/preview` | GET | Preview do short (com navegação anterior/próximo) |
| `/deletar/<filename>` | POST | Deletar vídeo ou short |

## Estrutura do Projeto

```
YTFBVIDS/
  app.py                      # Servidor Flask (porta 5080)
  services/
    smart_shorts.py           # Detecção de cenas, split, crop, geração de shorts
  scripts/
    baixar_editar.py          # CLI para download + áudio + corte
  templates/
    base.html                 # Layout base (Bootstrap 5, tema escuro)
    index.html                # Página inicial com formulário de download
    videos.html               # Lista de vídeos baixados
    preview.html              # Preview do vídeo/short (com navegação)
    cenas.html                # Cenas detectadas para seleção
    shorts.html               # Lista de shorts gerados
    feed.html                 # Feed vertical estilo TikTok
    tv.html                   # Modo TV com playlist
  downloads/                  # Vídeos baixados (gitignorado)
  cortes/                     # Shorts gerados (gitignorado)
  audio/                      # Áudio extraído (gitignorado)
  static/thumbnails/          # Thumbnails (gitignorado)
```

## Parâmetros da Detecção de Cenas

Em `services/smart_shorts.py`:

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `threshold` | `0.3` | Sensibilidade do filtro `scene` do FFmpeg |
| `min_duration` | `3` | Duração mínima de uma cena (segundos) |
| `max_segment` | `120` | Acima disso, retorna uma única cena (sem detecção) |

Se nenhuma cena for detectada, o vídeo é dividido em segmentos uniformes.

Cenas longas são automaticamente divididas em partes de no máximo `SHORT_MAX_DURATION` (30s) por `split_long_scenes()`.

## Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues e pull requests.

1. Faça um fork do projeto
2. Crie uma branch: `git checkout -b minha-feature`
3. Commit suas mudanças: `git commit -m 'Adiciona nova funcionalidade'`
4. Push: `git push origin minha-feature`
5. Abra um Pull Request

## Licença

Distribuído sob a licença MIT. Veja `LICENSE` para mais informações.
