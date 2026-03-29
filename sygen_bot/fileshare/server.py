"""Built-in fileshare HTTP server for exchanging files with agents.

Upload:   drag & drop or click in browser UI
Download: click file link in browser or GET /downloads/{filename}
Agents:   read from uploads/, write to downloads/

The server runs in a background daemon thread using stdlib only.
"""

from __future__ import annotations

import html
import logging
import os
import re
import threading
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn

logger = logging.getLogger(__name__)

_CHUNK = 1024 * 1024  # 1 MB

_HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fileshare</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,system-ui,sans-serif;background:#1a1a2e;color:#e0e0e0;padding:20px;max-width:800px;margin:0 auto}
h1{font-size:1.4em;margin-bottom:16px;color:#fff}
h2{font-size:1.1em;margin:20px 0 10px;color:#aaa}
.drop{border:2px dashed #444;border-radius:12px;padding:40px 20px;text-align:center;cursor:pointer;transition:.2s;margin-bottom:20px}
.drop:hover,.drop.over{border-color:#6c63ff;background:#6c63ff10}
.drop input{display:none}
.drop p{color:#888;font-size:.95em}
.progress{display:none;margin:10px 0;height:6px;background:#333;border-radius:3px;overflow:hidden}
.progress .bar{height:100%;background:#6c63ff;width:0;transition:width .3s}
.status{color:#6c63ff;font-size:.9em;min-height:1.4em;margin-bottom:10px}
.files{list-style:none}
.files li{padding:8px 12px;background:#16213e;border-radius:8px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center}
.files a{color:#6c63ff;text-decoration:none;word-break:break-all}
.files a:hover{text-decoration:underline}
.size{color:#666;font-size:.85em;white-space:nowrap;margin-left:12px}
.empty{color:#555;font-style:italic;padding:10px}
</style>
</head>
<body>
<h1>Fileshare</h1>
<div class="drop" id="drop">
  <p>Drop files here or tap to select</p>
  <input type="file" id="file" multiple>
</div>
<div class="progress" id="prog"><div class="bar" id="bar"></div></div>
<div class="status" id="status"></div>

<h2>Uploads</h2>
$UPLOADS$

<h2>Downloads</h2>
$DOWNLOADS$

<script>
const drop=document.getElementById('drop'),fi=document.getElementById('file'),
      prog=document.getElementById('prog'),bar=document.getElementById('bar'),
      st=document.getElementById('status');
drop.onclick=()=>fi.click();
drop.ondragover=e=>{e.preventDefault();drop.classList.add('over')};
drop.ondragleave=()=>drop.classList.remove('over');
drop.ondrop=e=>{e.preventDefault();drop.classList.remove('over');upload(e.dataTransfer.files)};
fi.onchange=()=>upload(fi.files);
function upload(files){
  if(!files.length)return;
  let i=0;
  function next(){
    if(i>=files.length){st.textContent='Done!';setTimeout(()=>location.reload(),500);return}
    const f=files[i++],fd=new FormData();fd.append('file',f);
    st.textContent='Uploading '+f.name+'...';prog.style.display='block';bar.style.width='0%';
    const x=new XMLHttpRequest();
    x.upload.onprogress=e=>{if(e.lengthComputable)bar.style.width=(e.loaded/e.total*100)+'%'};
    x.onload=()=>{bar.style.width='100%';next()};
    x.onerror=()=>{st.textContent='Error uploading '+f.name};
    x.open('POST','/upload');x.send(fd);
  }
  next();
}
</script>
</body>
</html>"""


def _fmt_size(n: float) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}" if u != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


def _list_files(directory: str, url_prefix: str) -> str:
    if not os.path.isdir(directory):
        return '<p class="empty">Empty</p>'
    entries = []
    for f in sorted(
        os.listdir(directory),
        key=lambda x: os.path.getmtime(os.path.join(directory, x)),
        reverse=True,
    ):
        fp = os.path.join(directory, f)
        if os.path.isfile(fp):
            sz = _fmt_size(os.path.getsize(fp))
            name = html.escape(f)
            href = html.escape(urllib.parse.quote(f))
            entries.append(
                f'<li><a href="{url_prefix}/{href}">{name}</a>'
                f'<span class="size">{sz}</span></li>'
            )
    if not entries:
        return '<p class="empty">Empty</p>'
    return '<ul class="files">' + "\n".join(entries) + "</ul>"


def _make_handler(upload_dir: str, download_dir: str) -> type[BaseHTTPRequestHandler]:
    """Create a request handler class closed over the given directories."""

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            pass

        def do_GET(self) -> None:
            path = urllib.parse.unquote(self.path)
            if path in ("/", ""):
                page = _HTML_PAGE.replace(
                    "$UPLOADS$", _list_files(upload_dir, "/uploads")
                ).replace("$DOWNLOADS$", _list_files(download_dir, "/downloads"))
                self._respond(200, "text/html", page.encode())
            elif path.startswith("/uploads/"):
                self._serve_file(upload_dir, path[9:])
            elif path.startswith("/downloads/"):
                self._serve_file(download_dir, path[11:])
            elif path.startswith("/download/"):
                # Alias: /download/{name} -> same as /downloads/{name}
                self._serve_file(download_dir, path[10:])
            else:
                self._respond(404, "text/plain", b"Not found")

        def do_POST(self) -> None:
            if self.path != "/upload":
                self._respond(404, "text/plain", b"Not found")
                return
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._respond(400, "text/plain", b"Bad request")
                return
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._respond(400, "text/plain", b"Empty body")
                return

            m = re.search(r"boundary=(.+?)(?:;|$)", content_type)
            if not m:
                self._respond(400, "text/plain", b"No boundary")
                return
            boundary = b"--" + m.group(1).strip().encode()

            header_buf = b""
            while True:
                line = self.rfile.readline(65536)
                header_buf += line
                if b"\r\n\r\n" in header_buf:
                    break
                if len(header_buf) > 65536:
                    self._respond(400, "text/plain", b"Header too large")
                    return

            header_text = header_buf.decode("utf-8", errors="replace")
            fn_match = re.search(r'filename="(.+?)"', header_text)
            if not fn_match:
                self._respond(400, "text/plain", b"No filename")
                return

            filename = os.path.basename(fn_match.group(1))
            filepath = os.path.join(upload_dir, filename)
            if os.path.exists(filepath):
                name, ext = os.path.splitext(filename)
                ts = datetime.now().strftime("%H%M%S")
                filepath = os.path.join(upload_dir, f"{name}_{ts}{ext}")

            bytes_read = len(header_buf)
            remaining = content_length - bytes_read
            end_marker = b"\r\n" + boundary + b"--"

            with open(filepath, "wb") as f:
                buf = b""
                while remaining > 0:
                    to_read = min(_CHUNK, remaining)
                    chunk = self.rfile.read(to_read)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    buf += chunk
                    if len(buf) > len(end_marker) + _CHUNK:
                        safe = len(buf) - len(end_marker)
                        f.write(buf[:safe])
                        buf = buf[safe:]

                idx = buf.rfind(b"\r\n" + boundary)
                if idx != -1:
                    f.write(buf[:idx])
                else:
                    f.write(buf)

            self._respond(200, "text/plain", b"OK")

        def _serve_file(self, base: str, name: str) -> None:
            if ".." in name:
                self._respond(403, "text/plain", b"Forbidden")
                return
            filepath = os.path.join(base, name)
            if not os.path.isfile(filepath):
                self._respond(404, "text/plain", b"Not found")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(os.path.getsize(filepath)))
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{os.path.basename(filepath)}"',
            )
            self.end_headers()
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(_CHUNK)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

        def _respond(self, code: int, content_type: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return _Handler


class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class FileshareServer:
    """Manages a fileshare HTTP server running in a background daemon thread."""

    def __init__(
        self,
        host: str,
        port: int,
        upload_dir: str | Path,
        download_dir: str | Path,
    ) -> None:
        self._host = host
        self._port = port
        self._upload_dir = str(upload_dir)
        self._download_dir = str(download_dir)
        self._server: _ThreadedHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    async def start(self) -> None:
        """Start the HTTP server in a background daemon thread."""
        handler = _make_handler(self._upload_dir, self._download_dir)
        self._server = _ThreadedHTTPServer((self._host, self._port), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="fileshare-server",
            daemon=True,
        )
        self._thread.start()
        logger.info("Fileshare server started on %s", self.base_url)

    async def stop(self) -> None:
        """Shut down the HTTP server."""
        if self._server is not None:
            self._server.shutdown()
            self._server = None
            self._thread = None
            logger.info("Fileshare server stopped")
