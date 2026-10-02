from __future__ import annotations
import json
import mimetypes
import os
import re
import secrets
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote
from topic16.contracts import inside
from .catalog import load_catalog
from .jobs import Jobs


class UiHttpServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can bind a second listener to an occupied port.
    # Exclusive binding makes strict-port failure and auto fallback reliable.
    allow_reuse_address = False

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def serve(root, settings, port=None, profile="auto"):
    data = load_catalog(root)
    catalog = data["catalog"]
    assets = data["assets"]
    jobs = Jobs(root, settings, catalog)
    secret = secrets.token_urlsafe(32)
    verified = {}
    import ctypes

    elevated = os.name == "nt" and bool(ctypes.windll.shell32.IsUserAnAdmin())
    if profile == "inference" and not elevated:
        raise RuntimeError(
            "Inference requires Windows PowerShell Administrator for the GPU clock guard"
        )
    inference_enabled = elevated and profile != "artifacts"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def json(self, value, status=200):
            body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.headers_out("application/json", len(body))
            self.end_headers()
            self.wfile.write(body)

        def headers_out(self, kind, length):
            if kind in (
                "application/json",
                "text/html",
                "text/css",
                "application/javascript",
                "text/javascript",
            ):
                kind += "; charset=utf-8"
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(length))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")

        def do_HEAD(self):
            self.do_GET(head=True)

        def do_GET(self, head=False):
            try:
                if self.headers.get("Host") not in (
                    f"127.0.0.1:{self.server.server_port}",
                    f"localhost:{self.server.server_port}",
                ):
                    return self.json({"error": "Invalid Host"}, 403)
                path = unquote(urlsplit(self.path).path)
                if path == "/api/health":
                    return self.json(
                        {
                            "service": "topic16-ui",
                            "schema_version": 1,
                            "revision": catalog["revision"],
                            "url": f"http://127.0.0.1:{self.server.server_port}",
                            "pid": os.getpid(),
                            "root": str(root.resolve()),
                            "profile": (
                                "inference" if inference_enabled else "artifacts"
                            ),
                        }
                    )
                if path == "/api/catalog":
                    return self.json(catalog | {"csrf": secret})
                if path == "/api/readiness":
                    return self.json(
                        {
                            "state": (
                                "busy"
                                if jobs.active
                                else ("ready" if inference_enabled else "not-enabled")
                            ),
                            "reason": (
                                None
                                if inference_enabled
                                else "Launch Start-UI.ps1 in Windows PowerShell Administrator to enable guarded CUDA inference."
                            ),
                            "owner": bool(jobs.owner),
                        }
                    )
                if path.startswith("/api/jobs/") and "/image/" not in path:
                    return self.json(jobs.status(path.split("/")[3]))
                if path.startswith("/api/assets/"):
                    key = path.split("/")[-1]
                    if key not in assets:
                        raise FileNotFoundError("Unknown asset")
                    entry = assets[key]
                    file = inside(root, entry["path"])
                    if file.stat().st_size != entry["bytes"]:
                        raise ValueError("Asset changed; prepare catalog again")
                    signature = (file.stat().st_size, file.stat().st_mtime_ns)
                    if verified.get(key) != signature:
                        from topic16.contracts import sha256

                        if sha256(file) != entry["sha256"]:
                            raise ValueError(
                                "Asset checksum changed; prepare catalog again"
                            )
                        verified[key] = signature
                    return self.file(file, head, entry["sha256"])
                if path.startswith("/api/report/"):
                    name = path[len("/api/report/") :]
                    url = catalog["report_assets"].get(name)
                    if not url:
                        raise FileNotFoundError("Unknown report resource")
                    return self.file(
                        inside(root, assets[url.split("/")[-1]]["path"]), head
                    )
                if path.startswith("/api/jobs/") and "/image/" in path:
                    parts = path.split("/")
                    job = jobs.status(parts[3])
                    method = parts[-1]
                    if job["status"] != "succeeded" or method not in job["results"]:
                        raise FileNotFoundError("Pair not published")
                    return self.file(
                        root / "artifacts/ui/jobs" / job["id"] / (method + ".png"), head
                    )
                if path.startswith("/api/"):
                    raise FileNotFoundError("Unknown endpoint")
                directory = root / "UI_design/dist"
                file = inside(directory, path.lstrip("/") or "index.html")
                if not file.is_file():
                    file = directory / "index.html"
                return self.file(file, head)
            except (FileNotFoundError, KeyError) as error:
                self.json({"error": str(error)}, 404)
            except (ValueError, PermissionError) as error:
                self.json({"error": str(error)}, 400)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def file(self, path, head=False, etag=None):
            size = path.stat().st_size
            start, end = 0, size - 1
            status = 200
            byte_range = self.headers.get("Range")
            if byte_range:
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", byte_range)
                if not match or not any(match.groups()):
                    return self.json({"error": "Invalid byte range"}, 416)
                a, b = match.groups()
                if a:
                    start = int(a)
                    end = min(int(b) if b else size - 1, size - 1)
                else:
                    start = max(0, size - int(b))
                if start > end or start >= size:
                    return self.json({"error": "Range outside asset"}, 416)
                status = 206
            self.send_response(status)
            self.headers_out(
                mimetypes.guess_type(str(path))[0] or "application/octet-stream",
                end - start + 1,
            )
            self.send_header("Accept-Ranges", "bytes")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            if etag:
                self.send_header("ETag", '"' + etag + '"')
            self.end_headers()
            if head:
                return
            with path.open("rb") as stream:
                stream.seek(start)
                left = end - start + 1
                while left:
                    chunk = stream.read(min(left, 1048576))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)

        def do_POST(self):
            try:
                origin = self.headers.get("Origin")
                if (
                    origin
                    not in (
                        f"http://127.0.0.1:{self.server.server_port}",
                        f"http://localhost:{self.server.server_port}",
                    )
                    or self.headers.get("X-UI-CSRF") != secret
                ):
                    raise PermissionError("Same-origin UI token required")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise ValueError("Request body exceeds limit")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("JSON object required")
                path = urlsplit(self.path).path
                token = body.get("token")
                if path == "/api/lease":
                    return self.json(
                        {
                            "token": jobs.lease(token),
                            "seconds": settings["Ui"]["LeaseSeconds"],
                        }
                    )
                if path == "/api/release":
                    jobs.release(token)
                    return self.json({"released": True})
                if path == "/api/shutdown":
                    self.json({"stopping": True})
                    import threading

                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                if path == "/api/jobs":
                    if not inference_enabled:
                        raise PermissionError(
                            "Guarded inference is not enabled in this server profile"
                        )
                    return self.json(jobs.submit(body, token), 202)
                if path.endswith("/cancel"):
                    if token != jobs.owner:
                        raise PermissionError("Owner required")
                    jobs.cancel(path.split("/")[3])
                    return self.json({"cancelled": True})
                raise FileNotFoundError("Unknown action")
            except PermissionError as error:
                self.json({"error": str(error)}, 403)
            except RuntimeError as error:
                self.json({"error": str(error)}, 409)
            except (ValueError, KeyError, FileNotFoundError) as error:
                self.json({"error": str(error)}, 400)

    server = None
    for candidate in (
        [port] if port else range(settings["Ui"]["Port"], settings["Ui"]["MaxPort"] + 1)
    ):
        try:
            server = UiHttpServer(("127.0.0.1", candidate), Handler)
            break
        except OSError as error:
            if port:
                raise RuntimeError(
                    f"Requested UI port {port} is unavailable"
                ) from error
    if server is None:
        raise RuntimeError("UI port range occupied")
    url = f"http://127.0.0.1:{server.server_port}"
    from .catalog import atomic_json

    atomic_json(
        root / "artifacts/ui/server.json",
        {"url": url, "pid": os.getpid(), "revision": catalog["revision"]},
    )
    print("TOPIC16_UI_URL=" + url, flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        jobs.shutdown()
        server.server_close()
