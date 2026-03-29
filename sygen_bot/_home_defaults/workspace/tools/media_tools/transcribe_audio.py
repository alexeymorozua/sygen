#!/usr/bin/env python3
"""Transcribe audio/voice files to text.

Strategies (tried in order):
0. Custom external command (if ``transcription.command`` is configured)
1. OpenAI Whisper API (requires OPENAI_API_KEY)
2. Local ``whisper`` CLI (Python whisper package)
3. Local ``whisper-cli`` (whisper.cpp)

Language and model are read from ``~/.sygen/config/config.json``
(section ``transcription``).  Defaults: language=auto, model=small.

Usage:
    python tools/media_tools/transcribe_audio.py --file /path/to/audio.ogg
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_SYGEN_HOME = Path(
    os.environ.get("SYGEN_HOME", str(Path.home() / ".sygen"))
).expanduser()

_TELEGRAM_FILES = _SYGEN_HOME / "workspace" / "telegram_files"
_MATRIX_FILES = _SYGEN_HOME / "workspace" / "matrix_files"
_API_FILES = _SYGEN_HOME / "workspace" / "api_files"

_ALLOWED_ROOTS = (_TELEGRAM_FILES, _MATRIX_FILES, _API_FILES)


def _load_transcription_config() -> dict:
    """Load transcription settings from config.json."""
    config_path = _SYGEN_HOME / "config" / "config.json"
    defaults = {"language": "auto", "model": "small", "command": None}
    if not config_path.exists():
        return defaults
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        section = data.get("transcription", {})
        return {
            "language": section.get("language", defaults["language"]),
            "model": section.get("model", defaults["model"]),
            "command": section.get("command", defaults["command"]),
        }
    except (json.JSONDecodeError, OSError):
        return defaults


def _transcribe_custom(path: Path, cfg: dict) -> dict:
    """Transcribe using a user-configured external command."""
    command = cfg.get("command")
    if not command:
        return {"error": "no custom command configured"}

    try:
        result = subprocess.run(
            [command, str(path)],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            env={
                **os.environ,
                "TRANSCRIPTION_LANGUAGE": cfg["language"],
                "TRANSCRIPTION_MODEL": cfg["model"],
            },
        )
    except FileNotFoundError:
        return {"error": f"custom transcription command not found: {command}"}
    except subprocess.TimeoutExpired:
        return {"error": f"custom command timed out after 300s: {command}"}

    if result.returncode != 0:
        return {"error": f"custom command failed (exit {result.returncode}): {result.stderr[:500]}"}

    transcript = result.stdout.strip()
    if not transcript:
        return {"error": "custom command returned empty output"}

    return {"transcript": transcript, "method": "custom_command"}


def _transcribe_openai(path: Path, cfg: dict) -> dict:
    """Transcribe using OpenAI Whisper API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not set"}

    try:
        from openai import OpenAI  # type: ignore[import-untyped]
    except ImportError:
        return {"error": "openai package not installed (pip install openai)"}

    client = OpenAI(api_key=api_key)
    try:
        with path.open("rb") as f:
            kwargs: dict = {
                "model": "whisper-1",
                "file": f,
                "response_format": "verbose_json",
            }
            lang = cfg["language"]
            if lang and lang != "auto":
                kwargs["language"] = lang
            result = client.audio.transcriptions.create(**kwargs)
    except Exception as exc:
        return {"error": f"OpenAI API error: {exc}"}

    return {
        "transcript": result.text,
        "language": getattr(result, "language", None),
        "duration_seconds": getattr(result, "duration", None),
        "method": "openai_whisper_api",
    }


def _transcribe_local_whisper(path: Path, cfg: dict) -> dict:
    """Transcribe using local whisper CLI (Python package)."""
    whisper_bin = shutil.which("whisper")
    if not whisper_bin:
        return {"error": "whisper CLI not found"}

    out_dir = path.parent
    cmd = [whisper_bin, str(path), "--model", cfg["model"], "--output_format", "json", "--output_dir", str(out_dir)]
    lang = cfg["language"]
    if lang and lang != "auto":
        cmd += ["--language", lang]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    except subprocess.TimeoutExpired:
        return {"error": "whisper timed out after 300s"}

    if result.returncode != 0:
        return {"error": f"whisper failed: {result.stderr[:500]}"}

    json_out = out_dir / f"{path.stem}.json"
    if json_out.exists():
        try:
            data = json.loads(json_out.read_text())
        except (json.JSONDecodeError, OSError):
            json_out.unlink(missing_ok=True)
            return {"error": "Failed to parse whisper JSON output"}
        json_out.unlink(missing_ok=True)
        return {
            "transcript": data.get("text", ""),
            "language": data.get("language"),
            "method": "local_whisper",
        }

    return {"transcript": result.stdout.strip(), "method": "local_whisper"}


def _transcribe_whisper_cpp(path: Path, cfg: dict) -> dict:
    """Transcribe using whisper.cpp CLI."""
    whisper_cli = shutil.which("whisper-cli")
    if not whisper_cli:
        return {"error": "whisper-cli not found"}

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"error": "ffmpeg not found"}

    model_name = f"ggml-{cfg['model']}.bin"
    model_path = Path.home() / ".local/share/whisper-cpp/models" / model_name

    if not model_path.exists():
        return {"error": f"whisper-cpp model not found: {model_path}"}

    wav_path = path.with_suffix(".temp.wav")
    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", str(path), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav_path)],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        return {"error": f"ffmpeg conversion failed: {exc.stderr[:500] if exc.stderr else ''}"}

    cmd = [whisper_cli, "-m", str(model_path), "-f", str(wav_path), "--no-timestamps"]
    lang = cfg["language"]
    if lang and lang != "auto":
        cmd += ["-l", lang]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    except subprocess.TimeoutExpired:
        wav_path.unlink(missing_ok=True)
        return {"error": "whisper-cli timed out after 300s"}

    wav_path.unlink(missing_ok=True)

    if result.returncode != 0:
        return {"error": f"whisper-cli failed: {result.stderr[:500]}"}

    return {"transcript": result.stdout.strip(), "method": "whisper_cpp"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe audio/voice to text")
    parser.add_argument("--file", required=True, help="Path to audio file")
    args = parser.parse_args()

    path = Path(args.file).resolve()
    allowed = any(path.is_relative_to(root.resolve()) for root in _ALLOWED_ROOTS)
    if not allowed:
        print(json.dumps({"error": f"Path outside allowed directories: {path}"}))
        sys.exit(1)
    if not path.exists():
        print(json.dumps({"error": f"File not found: {path}"}))
        sys.exit(1)

    cfg = _load_transcription_config()

    strategies = []
    if cfg.get("command"):
        strategies.append(_transcribe_custom)
    strategies += [_transcribe_openai, _transcribe_local_whisper, _transcribe_whisper_cpp]

    errors: list[str] = []

    for strategy in strategies:
        result = strategy(path, cfg)
        if "transcript" in result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        errors.append(result.get("error", "unknown error"))

    print(json.dumps({
        "error": "All transcription methods failed",
        "details": errors,
        "hint": "Install openai (pip install openai) and set OPENAI_API_KEY, "
        "or install whisper locally (pip install openai-whisper), "
        "or set transcription.command in config.json for a custom backend",
    }, ensure_ascii=False, indent=2))
    sys.exit(1)


if __name__ == "__main__":
    main()
