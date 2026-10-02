"""Synthetic CPU-only fixture server for CI; never represents research evidence."""

import base64
import json
import struct
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes

ROOT = Path(__file__).resolve().parents[1] / "dist"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg=="
)
CAMERA = {
    "width": 359,
    "height": 639,
    "fx": 535,
    "fy": 532,
    "cx": 180,
    "cy": 319,
    "camera_to_world": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 2]],
}
properties = [
    "x",
    "y",
    "z",
    "nx",
    "ny",
    "nz",
    "f_dc_0",
    "f_dc_1",
    "f_dc_2",
    "opacity",
    "scale_0",
    "scale_1",
    "scale_2",
    "rot_0",
    "rot_1",
    "rot_2",
    "rot_3",
]
GS = (
    "ply\nformat binary_little_endian 1.0\nelement vertex 1\n"
    + "".join("property float " + p + "\n" for p in properties)
    + "end_header\n"
).encode() + struct.pack("<17f", 0, 0, 0, 0, 0, 0, 1, 0, 0, 2, -2, -2, -2, 1, 0, 0, 0)
PC = (
    b"ply\nformat binary_little_endian 1.0\nelement vertex 1\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n"
    + struct.pack("<3f3B", 0, 0, 0, 180, 90, 50)
)
SCENES = []
for identifier, title in [
    ("custom:tea_sets_2", "Tea sets"),
    ("bonsai", "Bonsai"),
    ("garden", "Garden"),
    ("room", "Room"),
    ("poster", "Poster"),
]:
    methods = {
        m: {
            "run_key": identifier + "/" + m + "/fixture",
            "config": "fixture/config.yml",
            "checkpoint_sha256": "0" * 64,
            "split_hash": "0" * 64,
            "asset": "/fixture/" + m + ".ply",
            "bytes": len(PC if m == "nerfacto" else GS),
            "kind": "fixture",
            "metrics": {"psnr": 20, "ssim": 0.8, "lpips": 0.2},
            "train_seconds": 100,
            "peak_vram_mb": 100,
            "offline_fps": 10,
            "provenance": {"fixture": True},
        }
        for m in ("nerfacto", "splatfacto")
    }
    view = {
        "index": 0,
        "source": "fixture.png",
        "camera": CAMERA,
        **{
            k: "/fixture/image.png"
            for k in (
                "gt",
                "nerfacto",
                "splatfacto",
                "nerfacto_error",
                "splatfacto_error",
            )
        },
    }
    SCENES.append(
        {
            "id": identifier,
            "title": title,
            "subtitle": "Synthetic CI fixture",
            "cover": "/fixture/image.png",
            "scope": "fixture",
            "train_count": 2,
            "eval_count": 1,
            "views": [view],
            "methods": methods,
            "alignment": "fixture shared frame",
            "source_matrix": "fixture.json",
            "inference": False,
        }
    )
CATALOG = {
    "schema_version": 1,
    "revision": "fixture-v1",
    "created_at": "2026-10-02T00:00:00Z",
    "scenes": SCENES,
    "csrf": "fixture",
    "ui": {
        "MaxPixels": 2073600,
        "HeartbeatSeconds": 10,
        "DecodeLimitBytes": 629145600,
        "MaxVertices": 3000000,
    },
    "report_assets": {},
    "cases": [],
    "settings_compatibility": [],
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/health":
            body = b'{"service":"fixture"}'
            kind = "application/json"
        elif path == "/api/catalog":
            body = json.dumps(CATALOG).encode()
            kind = "application/json"
        elif path == "/api/readiness":
            body = b'{"state":"not-enabled","reason":"Synthetic CPU-only CI fixture"}'
            kind = "application/json"
        elif path == "/fixture/image.png":
            body = PNG
            kind = "image/png"
        elif path == "/fixture/nerfacto.ply":
            body = PC
            kind = "application/octet-stream"
        elif path == "/fixture/splatfacto.ply":
            body = GS
            kind = "application/octet-stream"
        else:
            file = (ROOT / path.lstrip("/")).resolve()
            if not file.is_relative_to(ROOT.resolve()):
                self.send_error(403)
                return
            if not file.is_file():
                file = ROOT / "index.html"
            body = file.read_bytes()
            kind = mimetypes.guess_type(str(file))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 7019), Handler).serve_forever()
