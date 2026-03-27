#!/usr/bin/env python3
"""Send any file to Telegram; for large files use local fileshare or 0x0.st.

Usage:
    python send_large_file.py --file /path/to/output.mp3
    python send_large_file.py --file /path/to/app.apk

Env vars (optional):
    FILESHARE_URL       - base URL of local fileshare (e.g. http://100.106.179.13:8080)
    FILESHARE_DOWNLOADS - path to fileshare downloads/ dir (auto-detected from ~/.sygen/fileshare/downloads)

Prints JSON: {"action": "telegram"|"upload", "path"|"url": "..."}
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

MAX_TG_BYTES = 45 * 1024 * 1024  # 45 MB
UPLOAD_URL = "https://0x0.st"
UPLOAD_TIMEOUT = 45


def detect_fileshare():
    base_url = os.environ.get("FILESHARE_URL", "").rstrip("/")
    downloads_dir = os.environ.get("FILESHARE_DOWNLOADS", "")

    if not downloads_dir:
        candidate = os.path.expanduser("~/.sygen/fileshare/downloads")
        if os.path.isdir(candidate):
            downloads_dir = candidate

    if base_url and downloads_dir and os.path.isdir(downloads_dir):
        return base_url, downloads_dir
    return None, None


def upload_local(file_path: str, base_url: str, downloads_dir: str) -> str | None:
    filename = os.path.basename(file_path)
    dest = os.path.join(downloads_dir, filename)
    if os.path.exists(dest):
        name, ext = os.path.splitext(filename)
        from datetime import datetime
        suffix = datetime.now().strftime("%H%M%S")
        filename = f"{name}_{suffix}{ext}"
        dest = os.path.join(downloads_dir, filename)
    try:
        shutil.copy2(file_path, dest)
        return f"{base_url}/download/{filename}"
    except Exception:
        return None


def upload_0x0(file_path: str) -> str | None:
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", str(UPLOAD_TIMEOUT),
             "-F", f"file=@{file_path}", UPLOAD_URL],
            capture_output=True, text=True,
            timeout=UPLOAD_TIMEOUT + 5,
        )
        url = result.stdout.strip()
        return url if url.startswith("https://") else None
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    args = parser.parse_args()

    path = args.file
    if not os.path.exists(path):
        print(json.dumps({"error": f"File not found: {path}"}))
        sys.exit(1)

    size = os.path.getsize(path)

    if size <= MAX_TG_BYTES:
        print(json.dumps({"action": "telegram", "path": path, "size_mb": round(size / 1024 / 1024, 1)}))
        return

    size_mb = round(size / 1024 / 1024, 1)

    base_url, downloads_dir = detect_fileshare()

    if base_url:
        print(json.dumps({"action": "uploading", "size_mb": size_mb,
                          "message": f"Файл {size_mb} МБ, копирую на локальный fileshare..."}))
        sys.stdout.flush()
        url = upload_local(path, base_url, downloads_dir)
        if url:
            print(json.dumps({"action": "upload", "url": url, "size_mb": size_mb, "method": "local"}))
            return

    print(json.dumps({"action": "uploading", "size_mb": size_mb,
                      "message": f"Файл {size_mb} МБ, загружаю на 0x0.st..."}))
    sys.stdout.flush()

    url = upload_0x0(path)
    if url:
        print(json.dumps({"action": "upload", "url": url, "size_mb": size_mb, "method": "0x0"}))
    else:
        print(json.dumps({
            "action": "error",
            "message": f"Файл {size_mb} МБ слишком большой для Telegram и загрузка не удалась. "
                       "Попробуй уменьшить размер или сжать файл."
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
