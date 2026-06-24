#!/usr/bin/env python3
"""
Baixa vídeo de Facebook/YouTube/TikTok, extrai áudio e gera cortes para
Instagram Reels, TikTok, YouTube Shorts (9:16 vertical).
"""

import subprocess, sys, os, argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
AUDIO_DIR = BASE_DIR / "audio"
CORTES_DIR = BASE_DIR / "cortes"


def baixar(url, output_dir=None):
    output_dir = output_dir or DOWNLOADS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    nome = "%(title)s.%(ext)s"
    cmd = [
        "yt-dlp",
        "-f",
        "bestvideo+bestaudio",
        "--merge-output-format",
        "mp4",
        "-o",
        str(output_dir / nome),
        url,
    ]
    print(f"\n>>> Baixando: {url}")
    subprocess.run(cmd, check=True)
    return list(output_dir.glob("*.mp4"))[-1]


def extrair_audio(video_path, output_path=None):
    if output_path is None:
        output_path = AUDIO_DIR / (video_path.stem + ".mp3")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f">>> Extraindo áudio: {output_path}")
    subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(video_path),
            "-q:a",
            "0",
            "-map",
            "a",
            str(output_path),
            "-y",
        ],
        check=True,
        capture_output=True,
    )
    return output_path


def cortar_para_shorts(video_path, duracao=30, output_path=None):
    """
    Corta e redimensiona para 1080x1920 (9:16 vertical).
    """
    if output_path is None:
        output_path = CORTES_DIR / f"shorts_{video_path.stem}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f">>> Gerando Short/Reel: {output_path} (max {duracao}s)")
    subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vf",
            "crop=ih*(9/16):ih,scale=1080:1920",
            "-t",
            str(duracao),
            "-c:a",
            "aac",
            str(output_path),
            "-y",
        ],
        check=True,
        capture_output=True,
    )
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Baixar, extrair áudio e cortar vídeos para Shorts/Reels"
    )
    parser.add_argument("url", help="URL do vídeo (Facebook, YouTube, TikTok, etc.)")
    parser.add_argument("--audio-only", action="store_true", help="Apenas baixar áudio")
    parser.add_argument(
        "--cortar",
        type=int,
        metavar="SEGUNDOS",
        nargs="?",
        const=30,
        default=0,
        help="Cortar e redimensionar para 9:16 (padrão: 30s)",
    )
    parser.add_argument("--output-dir", help="Diretório de saída do vídeo baixado")

    args = parser.parse_args()

    if args.audio_only:
        cmd = [
            "yt-dlp",
            "-x",
            "--audio-format",
            "mp3",
            "-o",
            str(AUDIO_DIR / "%(title)s.%(ext)s"),
            args.url,
        ]
        print(f">>> Baixando apenas áudio: {args.url}")
        subprocess.run(cmd, check=True)
        print(">>> Áudio salvo em:", AUDIO_DIR)
        return

    video = baixar(args.url, args.output_dir)
    print(f">>> Vídeo salvo: {video}")

    extrair_audio(video)
    print(f">>> Áudio salvo em: {AUDIO_DIR}")

    if args.cortar > 0:
        shorts = cortar_para_shorts(video, duracao=args.cortar)
        print(f">>> Short/Reel salvo: {shorts}")


if __name__ == "__main__":
    main()
