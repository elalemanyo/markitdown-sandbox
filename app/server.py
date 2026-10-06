"""Minimal web UI for MarkItDown.

GET  /         serves the upload page.
POST /convert  takes the raw file as the request body (filename in the X-Filename header)
               and returns the Markdown as text/plain. Files are converted in memory and
               never written to disk.

Configuration (environment):
  PORT            port to listen on inside the container (default: 8000)
  MAX_UPLOAD_MB   largest accepted upload in megabytes (default: 50)
"""

import io
import os
import signal
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from markitdown import MarkItDown, StreamInfo

PORT = int(os.environ.get("PORT", "8000"))
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "50")) * 1024 * 1024
INDEX_HTML = (Path(__file__).parent / "index.html").read_bytes()

SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; script-src 'self' 'unsafe-inline'; "
    "style-src 'unsafe-inline'; connect-src 'self'; img-src data:; form-action 'none'; "
    "frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}

# One shared converter; conversions are serialized since thread safety isn't documented.
converter = MarkItDown()
converter_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = "markitdown-sandbox"
    sys_version = ""

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.respond(HTTPStatus.OK, INDEX_HTML, "text/html; charset=utf-8")
        elif self.path == "/healthz":
            self.respond(HTTPStatus.OK, b"ok", "text/plain; charset=utf-8")
        else:
            self.error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self):
        if self.path != "/convert":
            return self.error(HTTPStatus.NOT_FOUND, "Not found")

        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.error(HTTPStatus.LENGTH_REQUIRED, "Content-Length required")
        if length <= 0:
            return self.error(HTTPStatus.BAD_REQUEST, "Empty upload")
        if length > MAX_UPLOAD_BYTES:
            return self.error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                f"File too large (limit {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
            )

        data = self.rfile.read(length)
        filename = os.path.basename(unquote(self.headers.get("X-Filename", "")))
        extension = os.path.splitext(filename)[1] or None

        try:
            with converter_lock:
                result = converter.convert_stream(
                    io.BytesIO(data),
                    stream_info=StreamInfo(filename=filename or None, extension=extension),
                )
        except Exception as exc:  # report any converter failure to the UI
            return self.error(HTTPStatus.UNPROCESSABLE_ENTITY, f"Conversion failed: {exc}")

        self.respond(HTTPStatus.OK, result.markdown.encode("utf-8"), "text/markdown; charset=utf-8")

    def error(self, status, message):
        self.respond(status, message.encode("utf-8"), "text/plain; charset=utf-8")

    def respond(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)


def serve():
    # As PID 1 the default SIGTERM action is ignored; exit promptly on `docker stop`.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    # Bind all interfaces inside the container; restrict exposure with `-p 127.0.0.1:...`.
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"MarkItDown UI listening on port {PORT}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
