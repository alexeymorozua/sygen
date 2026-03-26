#!/usr/bin/env python3
"""Send any file to Telegram, uploading to 0x0.st if > 45 MB.

Usage:
    python send_large_file.py --file /path/to/output.mp3
    python send_large_file.py --file /path/to/app.apk

Prints JSON: {"action": "telegram"|"upload", "path"|"url": "..."}
If upload fails, prints error message for the user.
"""
import argparse
import json
import os
import subprocess
import sys

MAX_TG_BYTES = 45 * 1024 * 1024  # 45 MB
UPLOAD_URL = "https://0x0.st"
UPLOAD_TIMEOUT = 45  # seconds


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
    print(json.dumps({"action": "uploading", "size_mb": size_mb,
                      "message": f"Файл {size_mb} МБ > 50 МБ, загружаю на хостинг..."}))
    sys.stdout.flush()

    url = upload_0x0(path)
    if url:
        print(json.dumps({"action": "upload", "url": url, "size_mb": size_mb}))
    else:
        print(json.dumps({
            "action": "error",
            "message": f"Файл {size_mb} МБ слишком большой для Telegram, и хостинг 0x0.st недоступен. "
                       "Попробуй уменьшить количество треков или сжать аудио (--audio-bitrate 128k)."
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
