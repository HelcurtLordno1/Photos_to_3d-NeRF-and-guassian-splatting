"""Temporary, allowlisted artifact server for renderer acceptance, not the UI server."""
import json
import mimetypes
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[2]
DIST = Path(__file__).parent / 'dist'
assets = {}
for matrix in (ROOT / 'artifacts/logs/matrices').glob('topic16-full-*.json'):
    for scene, pair in json.loads(matrix.read_text(encoding='utf-8-sig'))['pairs'].items():
        for method, config in pair['runs'].items():
            key = Path(config).parent.relative_to('artifacts/runs')
            assets[f'{scene}-{method}'] = ROOT / 'artifacts/exports' / key / ('splat.ply' if method == 'splatfacto' else 'point_cloud.ply')


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import urlsplit, unquote
        path = unquote(urlsplit(self.path).path)
        if path.startswith('/asset/'):
            p = assets.get(path[7:])
        else:
            p = (DIST / (path.lstrip('/') or 'index.html')).resolve()
            if not p.is_relative_to(DIST.resolve()): p = None
        if p is None or not p.is_file(): self.send_error(404); return
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(p.stat().st_size))
        self.end_headers()
        try:
            with p.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''): self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError): pass

    def log_message(self, *args): pass


if __name__ == '__main__':
    print('Spike server http://127.0.0.1:7015', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 7015), Handler).serve_forever()
