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
- **Corte Manual** — escolha início e duração para criar um short
- **Detecção Automática de Cenas** — divide o vídeo usando o filtro `scene` do FFmpeg
- **Smart Crop** — detecta rostos com OpenCV Haar Cascade e centraliza o crop
- **Geração em Massa** — crie shorts de todas as cenas de uma só vez
- **Extrair Áudio** — via CLI com `--audio-only`
- **Modo TV** *(em breve)* — player sequencial com playlist lateral
- **Feed de Shorts** *(em breve)* — navegação vertical estilo TikTok com autoplay

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3, Flask |
| Frontend | Jinja2, Bootstrap 5, Bootstrap Icons |
| Vídeo | FFmpeg / FFprobe |
| Download | yt-dlp |
| Visão Computacional | OpenCV (opcional) |

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
git clone https://github.com/seu-usuario/YTFBVIDS.git
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
| `/baixar` | POST | Baixar vídeo de uma URL |
| `/videos` | GET | Lista de vídeos baixados |
| `/videos/<filename>/preview` | GET | Preview do vídeo |
| `/videos/<filename>/cortar` | POST | Corte manual (início + duração) |
| `/videos/<filename>/cenas` | GET | Detecção automática de cenas |
| `/videos/<filename>/gerar-shorts` | POST | Gerar shorts das cenas selecionadas |
| `/videos/<filename>/gerar-tudo` | POST | Gerar shorts de todas as cenas |
| `/shorts` | GET | Lista de shorts gerados |
| `/shorts/<filename>/preview` | GET | Preview do short |
| `/deletar/<filename>` | POST | Deletar vídeo ou short |

## Estrutura do Projeto

```
YTFBVIDS/
  app.py                      # Servidor Flask (porta 5080)
  services/
    smart_shorts.py           # Detecção de cenas, crop, geração de shorts
  scripts/
    baixar_editar.py          # CLI para download + áudio + corte
  templates/
    base.html                 # Layout base (Bootstrap 5, tema escuro)
    index.html                # Página inicial com formulário de download
    videos.html               # Lista de vídeos baixados
    preview.html              # Preview do vídeo/short
    cenas.html                # Cenas detectadas
    shorts.html               # Lista de shorts gerados
    feed.html                 # Feed vertical estilo TikTok (planejado)
    tv.html                   # Modo TV com playlist (planejado)
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
| `max_segment` | `120` | Tamanho máximo do fallback uniforme (segundos) |

Se nenhuma cena for detectada, o vídeo é dividido em segmentos uniformes de até 120s.

## Roadmap

- [ ] Implementar rotas para Modo TV (`/tv`)
- [ ] Implementar rota para Feed de Shorts (`/feed`)
- [ ] Modo escuro / light toggle
- [ ] Suporte a playlist de URLs

## Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues e pull requests.

1. Faça um fork do projeto
2. Crie uma branch: `git checkout -b minha-feature`
3. Commit suas mudanças: `git commit -m 'Adiciona nova funcionalidade'`
4. Push: `git push origin minha-feature`
5. Abra um Pull Request

## Licença

Distribuído sob a licença MIT. Veja `LICENSE` para mais informações.
