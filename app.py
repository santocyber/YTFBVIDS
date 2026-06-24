import os, subprocess, json, threading, uuid
from pathlib import Path
from datetime import datetime
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
    send_file,
    jsonify,
)
import yt_dlp
from services import smart_shorts as ss

app = Flask(__name__)
app.config["SECRET_KEY"] = "ytfbvids-secret-key"
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024

BASE_DIR = Path(__file__).parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
CORTES_DIR = BASE_DIR / "cortes"
THUMBS_DIR = BASE_DIR / "static" / "thumbnails"

for d in [DOWNLOADS_DIR, CORTES_DIR, THUMBS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DOWNLOAD_JOBS = {}
DOWNLOAD_LOCK = threading.Lock()
SHORT_JOBS = {}
SHORT_LOCK = threading.Lock()
SHORT_MAX_DURATION = 30


def ffprobe_info(filepath):
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration,size",
                "-show_entries",
                "stream=width,height",
                "-of",
                "json",
                str(filepath),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(r.stdout)
        info = {"duration": 0.0, "size": 0, "width": 0, "height": 0}
        if "format" in data:
            info["duration"] = float(data["format"].get("duration", 0))
            info["size"] = int(data["format"].get("size", 0))
        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                info["width"] = int(s.get("width", 0))
                info["height"] = int(s.get("height", 0))
                break
        return info
    except Exception:
        return {"duration": 0.0, "size": 0, "width": 0, "height": 0}


def fmt_duration(sec):
    m, s = divmod(int(sec), 60)
    return f"{m}:{s:02d}"


def fmt_size(b):
    for u in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"


def make_thumbnail(video_path, thumb_path):
    if thumb_path.exists():
        return
    subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(video_path),
            "-ss",
            "00:00:01",
            "-vframes",
            "1",
            "-vf",
            "scale=320:-1",
            str(thumb_path),
            "-y",
        ],
        capture_output=True,
        timeout=30,
    )


def scan_dir(directory):
    items = []
    for f in directory.glob("*"):
        if f.suffix.lower() in (".mp4", ".mkv", ".avi", ".mov", ".webm"):
            thumb = THUMBS_DIR / (f.stem + ".jpg")
            make_thumbnail(f, thumb)
            info = ffprobe_info(f)
            mtime = f.stat().st_mtime
            items.append(
                {
                    "filename": f.name,
                    "size": info["size"],
                    "size_str": fmt_size(info["size"]),
                    "duration": info["duration"],
                    "duration_str": fmt_duration(info["duration"]),
                    "width": info["width"],
                    "height": info["height"],
                    "thumbnail": f"/static/thumbnails/{f.stem}.jpg",
                    "has_thumb": thumb.exists(),
                    "data": datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M"),
                    "mtime": mtime,
                }
            )
    return items


def ordenar(items, sort_by="data", order="desc"):
    reverse = order == "desc"
    chave = {"data": lambda x: x["mtime"], "tamanho": lambda x: x["size"], "duracao": lambda x: x["duration"]}
    key = chave.get(sort_by, chave["data"])
    items.sort(key=key, reverse=reverse)
    return items


def atualizar_job(job_id, **dados):
    with DOWNLOAD_LOCK:
        if job_id in DOWNLOAD_JOBS:
            DOWNLOAD_JOBS[job_id].update(dados)


def baixar_video_async(job_id, url):
    def hook(d):
        status = d.get("status")
        if status == "downloading":
            downloaded = d.get("downloaded_bytes") or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            percent = round((downloaded / total) * 100, 1) if total else 0
            atualizar_job(
                job_id,
                status="baixando",
                percent=percent,
                percent_text=d.get("_percent_str", f"{percent}%").strip(),
                speed=d.get("_speed_str", "").strip(),
                eta=d.get("_eta_str", "").strip(),
                filename=Path(d.get("filename", "")).name,
            )
        elif status == "finished":
            atualizar_job(
                job_id,
                status="processando",
                percent=99,
                percent_text="99%",
                speed="",
                eta="juntando audio e video",
                filename=Path(d.get("filename", "")).name,
            )

    try:
        atualizar_job(job_id, status="iniciando", percent=0, percent_text="0%")
        opts = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": str(DOWNLOADS_DIR / "%(title)s.%(ext)s"),
            "progress_hooks": [hook],
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        atualizar_job(
            job_id,
            status="concluido",
            percent=100,
            percent_text="100%",
            speed="",
            eta="",
            message="Download concluido",
        )
    except Exception as e:
        atualizar_job(
            job_id,
            status="erro",
            error=str(e),
            message="Erro ao baixar video",
        )


def cenas_para_shorts(video_path):
    scenes = ss.detect_scenes(video_path)
    return ss.split_long_scenes(scenes, max_duration=SHORT_MAX_DURATION)


def atualizar_short_job(job_id, **dados):
    with SHORT_LOCK:
        if job_id in SHORT_JOBS:
            SHORT_JOBS[job_id].update(dados)


def gerar_shorts_async_worker(job_id, filename, selected, smart_crop, mode):
    src = DOWNLOADS_DIR / filename
    try:
        if not src.exists():
            atualizar_short_job(job_id, status="erro", error="Video nao encontrado")
            return

        atualizar_short_job(job_id, status="preparando", percent=0, etapa="Detectando cenas e partes curtas")
        all_scenes = cenas_para_shorts(src)
        selected_set = {str(i) for i in selected}
        scenes = all_scenes if mode == "all" else [s for s in all_scenes if str(s["index"]) in selected_set]

        if not scenes:
            atualizar_short_job(job_id, status="erro", error="Nenhuma cena selecionada")
            return

        total = len(scenes)
        video_stem = Path(filename).stem
        success_count = 0

        for i, scene in enumerate(scenes):
            out_name = f"short_{video_stem}_cena{scene['index'] + 1}.mp4"
            out_path = CORTES_DIR / out_name
            percent = round((i / total) * 100, 1)
            atualizar_short_job(
                job_id,
                status="gerando",
                percent=percent,
                percent_text=f"{percent}%",
                etapa=f"Gerando short {i + 1} de {total}",
                arquivo=out_name,
            )

            def progresso_ffmpeg(percent_clip):
                total_percent = round(((i + (percent_clip / 100)) / total) * 100, 1)
                atualizar_short_job(
                    job_id,
                    percent=total_percent,
                    percent_text=f"{total_percent}%",
                    etapa=f"Gerando short {i + 1} de {total}",
                    arquivo=out_name,
                )

            ok = ss.generate_short(
                src,
                scene["start"],
                scene["end"],
                out_path,
                smart_crop,
                progress_callback=progresso_ffmpeg,
            )
            if ok:
                success_count += 1
                thumb = THUMBS_DIR / f"{out_path.stem}.jpg"
                if not thumb.exists():
                    ss.generate_scene_thumbnail(out_path, 0.5, thumb)
            else:
                atualizar_short_job(job_id, error=f"Falha ao gerar {out_name}")

            done = round(((i + 1) / total) * 100, 1)
            atualizar_short_job(job_id, percent=done, percent_text=f"{done}%")

        status = "concluido" if success_count else "erro"
        atualizar_short_job(
            job_id,
            status=status,
            percent=100 if success_count else 0,
            percent_text="100%" if success_count else "0%",
            etapa=f"{success_count} de {total} shorts gerados",
            message="Shorts gerados com sucesso" if success_count else "Nenhum short foi gerado",
        )
    except Exception as e:
        atualizar_short_job(job_id, status="erro", error=str(e), message="Erro ao gerar shorts")


@app.route("/")
def index():
    return render_template("index.html", videos=scan_dir(DOWNLOADS_DIR)[:8])


@app.route("/videos")
def videos():
    sort_by = request.args.get("sort", "data")
    order = request.args.get("order", "desc")
    return render_template("videos.html", videos=ordenar(scan_dir(DOWNLOADS_DIR), sort_by, order), sort_by=sort_by, order=order)


@app.route("/videos/tv")
def videos_tv():
    sort_by = request.args.get("sort", "data")
    order = request.args.get("order", "desc")
    start = request.args.get("start")
    videos_lista = ordenar(scan_dir(DOWNLOADS_DIR), sort_by, order)

    if start:
        nomes = [v["filename"] for v in videos_lista]
        if start in nomes:
            idx = nomes.index(start)
            videos_lista = videos_lista[idx:] + videos_lista[:idx]

    return render_template(
        "tv.html",
        videos=videos_lista,
        sort_by=sort_by,
        order=order,
        start=start,
    )


@app.route("/videos/<path:filename>")
def serve_video(filename):
    return send_from_directory(DOWNLOADS_DIR, filename)


@app.route("/videos/<path:filename>/audio")
def baixar_audio(filename):
    import tempfile
    src = DOWNLOADS_DIR / filename
    if not src.exists():
        return "Vídeo não encontrado", 404
    stem = Path(filename).stem
    out = Path(tempfile.gettempdir()) / f"{stem}.mp3"
    if not out.exists():
        try:
            subprocess.run([
                "ffmpeg", "-i", str(src),
                "-q:a", "0", "-map", "a",
                "-y", str(out)
            ], check=True, capture_output=True, timeout=300)
        except subprocess.CalledProcessError:
            return "Erro ao extrair áudio", 500
    return send_file(str(out), as_attachment=True, download_name=f"{stem}.mp3")


@app.route("/videos/<path:filename>/preview")
def video_preview(filename):
    p = DOWNLOADS_DIR / filename
    if not p.exists():
        return "Vídeo não encontrado", 404
    return render_template(
        "preview.html", filename=filename, info=ffprobe_info(p), tipo="video"
    )


@app.route("/videos/<path:filename>/cortar", methods=["POST"])
def cortar_video(filename):
    src = DOWNLOADS_DIR / filename
    if not src.exists():
        return "Vídeo não encontrado", 404
    stem = Path(filename).stem
    out = CORTES_DIR / f"short_{stem}.mp4"
    inicio = request.form.get("inicio", "0")
    duracao = request.form.get("duracao", "30")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(src),
                "-ss",
                inicio,
                "-t",
                duracao,
                "-vf",
                "crop=ih*(9/16):ih,scale=1080:1920",
                "-c:a",
                "aac",
                str(out),
                "-y",
            ],
            check=True,
            capture_output=True,
            timeout=300,
        )
        return redirect(url_for("shorts"))
    except subprocess.CalledProcessError as e:
        return f"Erro: {e.stderr.decode()}", 500


@app.route("/videos/<path:filename>/cenas")
def detectar_cenas(filename):
    src = DOWNLOADS_DIR / filename
    if not src.exists():
        return "Vídeo não encontrado", 404
    try:
        scenes = cenas_para_shorts(src)
    except Exception as e:
        return f"Erro ao detectar cenas: {e}", 500

    thumb_dir = THUMBS_DIR / "cenas" / Path(filename).stem
    thumb_dir.mkdir(parents=True, exist_ok=True)

    for scene in scenes:
        thumb_path = thumb_dir / f"cena{scene['index']+1}.jpg"
        if not thumb_path.exists():
            ss.generate_scene_thumbnail(src, scene["start"] + 0.5, thumb_path)
        scene["thumb"] = (
            f"/static/thumbnails/cenas/{Path(filename).stem}/cena{scene['index']+1}.jpg"
            if thumb_path.exists()
            else None
        )

    return render_template("cenas.html", filename=filename, scenes=scenes, info=ffprobe_info(src))


@app.route("/videos/<path:filename>/gerar-shorts", methods=["POST"])
def gerar_shorts(filename):
    src = DOWNLOADS_DIR / filename
    if not src.exists():
        return "Vídeo não encontrado", 404

    selected = request.form.getlist("cenas")
    use_smart = request.form.get("smart_crop") == "on"

    all_scenes = cenas_para_shorts(src)

    scenes = [s for s in all_scenes if str(s["index"]) in selected]
    if not scenes:
        return redirect(url_for("detectar_cenas", filename=filename))

    results = ss.generate_all_shorts(src, CORTES_DIR, scenes, smart_crop=use_smart)

    for r in results:
        short_path = CORTES_DIR / r["file"]
        if short_path.exists():
            thumb = THUMBS_DIR / (r["file"] + ".jpg")
            if not thumb.exists():
                ss.generate_scene_thumbnail(short_path, 0.5, thumb)

    return redirect(url_for("shorts"))


@app.route("/videos/<path:filename>/gerar-tudo", methods=["POST"])
def gerar_tudo(filename):
    src = DOWNLOADS_DIR / filename
    if not src.exists():
        return "Vídeo não encontrado", 404

    use_smart = request.form.get("smart_crop") == "on"

    scenes = cenas_para_shorts(src)

    if not scenes:
        return "Nenhuma cena detectada no vídeo.", 200

    results = ss.generate_all_shorts(src, CORTES_DIR, scenes, smart_crop=use_smart)

    for r in results:
        short_path = CORTES_DIR / r["file"]
        if short_path.exists():
            thumb = THUMBS_DIR / (r["file"] + ".jpg")
            if not thumb.exists():
                ss.generate_scene_thumbnail(short_path, 0.5, thumb)

    return redirect(url_for("shorts"))


@app.route("/videos/<path:filename>/gerar-shorts-async", methods=["POST"])
def gerar_shorts_async(filename):
    src = DOWNLOADS_DIR / filename
    if not src.exists():
        return jsonify({"error": "Video nao encontrado"}), 404

    selected = request.form.getlist("cenas")
    mode = request.form.get("modo", "selected")
    smart_crop = request.form.get("smart_crop") == "on"

    if mode != "all" and not selected:
        return jsonify({"error": "Nenhuma cena selecionada"}), 400

    job_id = uuid.uuid4().hex
    with SHORT_LOCK:
        SHORT_JOBS[job_id] = {
            "status": "aguardando",
            "percent": 0,
            "percent_text": "0%",
            "etapa": "Aguardando inicio",
            "arquivo": "",
            "error": "",
            "message": "",
        }

    thread = threading.Thread(
        target=gerar_shorts_async_worker,
        args=(job_id, filename, selected, smart_crop, mode),
        daemon=True,
    )
    thread.start()
    return jsonify({"job_id": job_id})


@app.route("/progresso-short/<job_id>")
def progresso_short(job_id):
    with SHORT_LOCK:
        job = SHORT_JOBS.get(job_id)
        if not job:
            return jsonify({"status": "nao_encontrado", "error": "Job nao encontrado"}), 404
        return jsonify(job)


@app.route("/shorts")
def shorts():
    sort_by = request.args.get("sort", "data")
    order = request.args.get("order", "desc")
    return render_template("shorts.html", shorts=ordenar(scan_dir(CORTES_DIR), sort_by, order), sort_by=sort_by, order=order)


@app.route("/shorts/feed")
def shorts_feed():
    sort_by = request.args.get("sort", "data")
    order = request.args.get("order", "desc")
    start = request.args.get("start")
    shorts_lista = ordenar(scan_dir(CORTES_DIR), sort_by, order)

    if start:
        nomes = [s["filename"] for s in shorts_lista]
        if start in nomes:
            idx = nomes.index(start)
            shorts_lista = shorts_lista[idx:] + shorts_lista[:idx]

    return render_template(
        "feed.html",
        shorts=shorts_lista,
        sort_by=sort_by,
        order=order,
        start=start,
    )


@app.route("/shorts/<path:filename>")
def serve_short(filename):
    return send_from_directory(CORTES_DIR, filename)


@app.route("/shorts/<path:filename>/preview")
def short_preview(filename):
    p = CORTES_DIR / filename
    if not p.exists():
        return "Short não encontrado", 404

    todos = sorted(CORTES_DIR.glob("*.mp4"), key=os.path.getmtime, reverse=True)
    nomes = [f.name for f in todos]
    prev_short = next_short = None
    if filename in nomes:
        idx = nomes.index(filename)
        if idx > 0:
            next_short = nomes[idx - 1]
        if idx < len(nomes) - 1:
            prev_short = nomes[idx + 1]

    return render_template(
        "preview.html", filename=filename, info=ffprobe_info(p),
        tipo="short", prev_short=prev_short, next_short=next_short
    )


@app.route("/baixar-async", methods=["POST"])
def baixar_async():
    url = request.form.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL vazia"}), 400

    job_id = uuid.uuid4().hex
    with DOWNLOAD_LOCK:
        DOWNLOAD_JOBS[job_id] = {
            "status": "aguardando",
            "percent": 0,
            "percent_text": "0%",
            "speed": "",
            "eta": "",
            "filename": "",
            "error": "",
            "message": "Aguardando inicio",
        }

    thread = threading.Thread(target=baixar_video_async, args=(job_id, url), daemon=True)
    thread.start()
    return jsonify({"job_id": job_id})


@app.route("/progresso/<job_id>")
def progresso(job_id):
    with DOWNLOAD_LOCK:
        job = DOWNLOAD_JOBS.get(job_id)
        if not job:
            return jsonify({"status": "nao_encontrado", "error": "Job nao encontrado"}), 404
        return jsonify(job)


@app.route("/baixar", methods=["POST"])
def baixar():
    url = request.form.get("url", "").strip()
    if not url:
        return redirect(url_for("index"))
    try:
        subprocess.run(
            [
                "yt-dlp",
                "-f",
                "bestvideo+bestaudio",
                "--merge-output-format",
                "mp4",
                "-o",
                str(DOWNLOADS_DIR / "%(title)s.%(ext)s"),
                url,
            ],
            check=True,
            timeout=600,
        )
    except subprocess.CalledProcessError:
        try:
            subprocess.run(
                [
                    "yt-dlp",
                    "-o",
                    str(DOWNLOADS_DIR / "%(title)s.%(ext)s"),
                    url,
                ],
                check=True,
                timeout=600,
            )
        except subprocess.CalledProcessError:
            return "Erro ao baixar vídeo. URL inválida?", 500
    return redirect(url_for("videos"))


@app.route("/deletar/<path:filename>", methods=["POST"])
def deletar(filename):
    for d in [DOWNLOADS_DIR, CORTES_DIR]:
        p = d / filename
        if p.exists():
            p.unlink()
    thumb = THUMBS_DIR / (Path(filename).stem + ".jpg")
    if thumb.exists():
        thumb.unlink()
    return redirect(request.referrer or url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5080, debug=True)
