#!/usr/bin/env python3
"""Extract metadata, subtitles, audio, and keyframes from YouTube videos.

Usage:
    python3 tools/media_tools/youtube_tool.py --url URL
    python3 tools/media_tools/youtube_tool.py --url URL --lang ru
    python3 tools/media_tools/youtube_tool.py --url URL --transcribe
    python3 tools/media_tools/youtube_tool.py --url URL --frames 5
    python3 tools/media_tools/youtube_tool.py --url URL --audio
    python3 tools/media_tools/youtube_tool.py --url URL --metadata-only
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


def _check_tool(name: str) -> str | None:
    return shutil.which(name)


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300, **kwargs)


def _fail(msg: str) -> None:
    json.dump({"error": msg}, sys.stdout, ensure_ascii=False)
    sys.exit(1)


def fetch_metadata(url: str) -> dict:
    if not _check_tool("yt-dlp"):
        _fail("yt-dlp is not installed")

    r = _run([
        "yt-dlp", "--dump-json", "--no-download",
        "--no-warnings", "--no-playlist", url,
    ])
    if r.returncode != 0:
        _fail(f"yt-dlp metadata error: {r.stderr.strip()}")

    info = json.loads(r.stdout)
    return {
        "title": info.get("title"),
        "author": info.get("uploader") or info.get("channel"),
        "duration": info.get("duration"),
        "description": info.get("description"),
        "publish_date": info.get("upload_date"),
        "tags": info.get("tags") or [],
        "views": info.get("view_count"),
        "thumbnail": info.get("thumbnail"),
        "_info": info,
    }


def fetch_subtitles(url: str, lang: str | None, info: dict) -> tuple[str | None, str | None]:
    tmpdir = tempfile.mkdtemp(prefix="yt_subs_")
    try:
        available_subs = info.get("subtitles") or {}
        available_auto = info.get("automatic_captions") or {}

        target_lang = _pick_lang(lang, available_subs, available_auto)
        if not target_lang:
            return None, None

        use_auto = target_lang not in available_subs
        sub_args = ["--write-auto-sub"] if use_auto else ["--write-sub"]

        out_template = os.path.join(tmpdir, "subs")
        r = _run([
            "yt-dlp", "--skip-download", "--no-warnings", "--no-playlist",
            *sub_args, "--sub-lang", target_lang, "--sub-format", "vtt",
            "--convert-subs", "srt",
            "-o", out_template, url,
        ])
        if r.returncode != 0:
            return None, None

        srt_files = glob.glob(os.path.join(tmpdir, "*.srt"))
        if not srt_files:
            vtt_files = glob.glob(os.path.join(tmpdir, "*.vtt"))
            if not vtt_files:
                return None, None
            srt_files = vtt_files

        text = Path(srt_files[0]).read_text(encoding="utf-8", errors="replace")
        clean = _clean_srt(text)
        return clean, target_lang
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _pick_lang(
    requested: str | None,
    manual: dict,
    auto: dict,
) -> str | None:
    if requested:
        if requested in manual or requested in auto:
            return requested
        for key in list(manual) + list(auto):
            if key.startswith(requested):
                return key
        return requested

    for preferred in ("en", "ru", "de", "es", "fr", "ja", "ko", "zh"):
        if preferred in manual:
            return preferred
    if manual:
        return next(iter(manual))
    for preferred in ("en", "ru", "de", "es", "fr", "ja", "ko", "zh"):
        if preferred in auto:
            return preferred
    if auto:
        return next(iter(auto))
    return None


def _clean_srt(text: str) -> str:
    lines: list[str] = []
    prev = ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.isdigit():
            continue
        if "-->" in line:
            continue
        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        cleaned = line.replace("<i>", "").replace("</i>", "")
        cleaned = cleaned.replace("<b>", "").replace("</b>", "")
        import re
        cleaned = re.sub(r"<[^>]+>", "", cleaned)
        cleaned = cleaned.strip()
        if cleaned and cleaned != prev:
            lines.append(cleaned)
            prev = cleaned
    return "\n".join(lines)


def download_audio(url: str) -> str:
    if not _check_tool("yt-dlp"):
        _fail("yt-dlp is not installed")

    out_dir = "/tmp"
    filename = f"yt_audio_{uuid.uuid4().hex[:8]}"
    out_path = os.path.join(out_dir, filename)

    r = _run([
        "yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "4",
        "--no-playlist", "--no-warnings",
        "-o", f"{out_path}.%(ext)s", url,
    ], timeout=600)
    if r.returncode != 0:
        _fail(f"yt-dlp audio download error: {r.stderr.strip()}")

    candidates = glob.glob(f"{out_path}.*")
    if not candidates:
        _fail("Audio download produced no file")
    return candidates[0]


def transcribe_audio(audio_path: str) -> str:
    script = Path(__file__).parent / "transcribe_audio.py"
    if not script.exists():
        _fail(f"transcribe_audio.py not found at {script}")

    r = _run([sys.executable, str(script), "--file", audio_path], timeout=600)
    if r.returncode != 0:
        _fail(f"Transcription error: {r.stderr.strip()}")

    try:
        result = json.loads(r.stdout)
        return result.get("text") or result.get("transcript", "")
    except json.JSONDecodeError:
        return r.stdout.strip()


def extract_frames(url: str, n: int) -> list[str]:
    if not _check_tool("ffmpeg"):
        _fail("ffmpeg is not installed")
    if not _check_tool("yt-dlp"):
        _fail("yt-dlp is not installed")

    r = _run(["yt-dlp", "-g", "--no-playlist", "--no-warnings", url])
    if r.returncode != 0:
        _fail(f"yt-dlp stream URL error: {r.stderr.strip()}")

    stream_url = r.stdout.strip().splitlines()[0]
    out_dir = tempfile.mkdtemp(prefix="yt_frames_")
    out_pattern = os.path.join(out_dir, "frame_%03d.jpg")

    r = _run([
        "ffmpeg", "-i", stream_url,
        "-vf", r"select=eq(pict_type\,I)",
        "-vsync", "vfr",
        "-frames:v", str(n),
        "-q:v", "2",
        out_pattern,
    ], timeout=120)

    frames = sorted(glob.glob(os.path.join(out_dir, "*.jpg")))
    if not frames:
        shutil.rmtree(out_dir, ignore_errors=True)
        out_dir = tempfile.mkdtemp(prefix="yt_frames_")
        out_pattern = os.path.join(out_dir, "frame_%03d.jpg")
        r2 = _run(["yt-dlp", "--dump-json", "--no-download", "--no-warnings", "--no-playlist", url])
        if r2.returncode == 0:
            info = json.loads(r2.stdout)
            duration = info.get("duration", 60)
            interval = max(1, duration // (n + 1))
            r = _run([
                "ffmpeg", "-i", stream_url,
                "-vf", f"fps=1/{interval}",
                "-frames:v", str(n),
                "-q:v", "2",
                out_pattern,
            ], timeout=120)
            frames = sorted(glob.glob(os.path.join(out_dir, "*.jpg")))

    return frames


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube metadata/subtitles/media extraction")
    parser.add_argument("--url", required=True, help="YouTube video URL")
    parser.add_argument("--lang", default=None, help="Subtitle language code (default: auto-detect)")
    parser.add_argument("--transcribe", action="store_true", help="Transcribe audio if no subtitles")
    parser.add_argument("--frames", type=int, default=0, help="Extract N keyframes")
    parser.add_argument("--audio", action="store_true", help="Download audio only (mp3)")
    parser.add_argument("--metadata-only", action="store_true", help="Only metadata, skip subtitles")
    args = parser.parse_args()

    meta = fetch_metadata(args.url)
    info = meta.pop("_info")

    result = {
        "title": meta["title"],
        "author": meta["author"],
        "duration": meta["duration"],
        "description": meta["description"],
        "publish_date": meta["publish_date"],
        "tags": meta["tags"],
        "views": meta["views"],
        "thumbnail": meta["thumbnail"],
    }

    if not args.metadata_only:
        subs_text, subs_lang = fetch_subtitles(args.url, args.lang, info)
        result["subtitles"] = subs_text
        result["subtitle_lang"] = subs_lang

        if not subs_text and args.transcribe:
            audio_path = download_audio(args.url)
            try:
                result["transcript"] = transcribe_audio(audio_path)
            finally:
                if os.path.exists(audio_path):
                    os.remove(audio_path)

    if args.frames > 0:
        result["frames"] = extract_frames(args.url, args.frames)

    if args.audio:
        result["audio_path"] = download_audio(args.url)

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
