from __future__ import annotations
import json
import math
import os
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path
from .catalog import atomic_json


def validate_camera(value, max_pixels):
    if not isinstance(value, dict):
        raise ValueError("Camera object required")
    for key in ("width", "height"):
        n = value.get(key)
        if isinstance(n, bool) or not isinstance(n, int) or not 32 <= n <= 4096:
            raise ValueError("Invalid render dimensions")
    if value["width"] * value["height"] > max_pixels:
        raise ValueError("Render pixel budget exceeded")
    for key in ("fx", "fy", "cx", "cy"):
        n = value.get(key)
        if (
            isinstance(n, bool)
            or not isinstance(n, (int, float))
            or not math.isfinite(n)
        ):
            raise ValueError("Invalid intrinsics")
    if min(value["fx"], value["fy"]) <= 0:
        raise ValueError("Focal length must be positive")
    if (
        not 0 <= value["cx"] <= value["width"]
        or not 0 <= value["cy"] <= value["height"]
    ):
        raise ValueError("Principal point outside image")
    matrix = value.get("camera_to_world")
    if (
        not isinstance(matrix, list)
        or len(matrix) != 3
        or any(not isinstance(row, list) or len(row) != 4 for row in matrix)
    ):
        raise ValueError("OpenGL 3x4 pose required")
    if any(
        isinstance(n, bool)
        or not isinstance(n, (float, int))
        or not math.isfinite(n)
        or abs(n) > 1e5
        for row in matrix
        for n in row
    ):
        raise ValueError("Invalid pose")
    # A reflection/shear cannot masquerade as a camera rotation.
    rows = [r[:3] for r in matrix]
    for i in range(3):
        for j in range(3):
            if (
                abs(
                    sum(rows[i][k] * rows[j][k] for k in range(3))
                    - (1 if i == j else 0)
                )
                > 1e-3
            ):
                raise ValueError("Camera rotation must be orthonormal")
    determinant = sum(
        rows[0][i]
        * (
            rows[1][(i + 1) % 3] * rows[2][(i + 2) % 3]
            - rows[1][(i + 2) % 3] * rows[2][(i + 1) % 3]
        )
        for i in range(3)
    )
    if abs(determinant - 1) > 1e-3:
        raise ValueError("Camera rotation must be right handed")
    return {
        k: value[k]
        for k in ("width", "height", "fx", "fy", "cx", "cy", "camera_to_world")
    }


class Jobs:
    def __init__(self, root, settings, catalog):
        self.root, self.settings, self.catalog = root, settings, catalog
        self.lock = threading.RLock()
        self.owner = None
        self.expires = 0
        self.active = None
        self.pending = None
        self.records = {}
        self.closed = False
        self.processes = {}
        threading.Thread(target=self.watch, daemon=True).start()

    def lease(self, token=None):
        with self.lock:
            now = time.monotonic()
            if self.owner and now < self.expires and token != self.owner:
                raise RuntimeError("Another tab owns the inference lease")
            if not token or token != self.owner:
                token = secrets.token_urlsafe(32)
            self.owner = token
            self.expires = now + self.settings["Ui"]["LeaseSeconds"]
            return token

    def release(self, token):
        with self.lock:
            if token != self.owner:
                raise PermissionError("Inference lease does not belong to this tab")
            self.cancel_all()
            self.owner = None
            self.expires = 0

    def submit(self, request, token):
        with self.lock:
            if token != self.owner or time.monotonic() > self.expires:
                raise PermissionError("Acquire an inference lease first")
            scene = next(
                (s for s in self.catalog["scenes"] if s["id"] == request.get("scene")),
                None,
            )
            if not scene:
                raise ValueError("Unknown exact scene")
            if request.get("revision") != self.catalog["revision"]:
                raise ValueError("Catalog revision changed")
            methods = request.get("methods")
            if (
                not isinstance(methods, list)
                or not methods
                or any(not isinstance(m, str) for m in methods)
                or len(set(methods)) != len(methods)
                or any(m not in ("nerfacto", "splatfacto") for m in methods)
            ):
                raise ValueError("Invalid method selection")
            camera = validate_camera(
                request.get("camera"), self.settings["Ui"]["MaxPixels"]
            )
            sequence = request.get("sequence", 0)
            if (
                isinstance(sequence, bool)
                or not isinstance(sequence, int)
                or not 0 <= sequence <= 1000000000
            ):
                raise ValueError("Invalid camera request sequence")
            self.evict()
            cache = self.root / "artifacts/ui/jobs"
            used = (
                sum(p.stat().st_size for p in cache.rglob("*") if p.is_file())
                if cache.exists()
                else 0
            )
            reserved = camera["width"] * camera["height"] * 6 * len(methods) + 1048576
            if used + reserved > self.settings["Ui"].get("CacheBytes", 2147483648):
                raise RuntimeError(
                    "UI render cache is full; active and current results are protected"
                )
            job_id = secrets.token_hex(16)
            folder = self.root / "artifacts/ui/jobs" / job_id
            from topic16.contracts import digest_json

            record = {
                "id": job_id,
                "status": "queued",
                "scene": scene["id"],
                "revision": self.catalog["revision"],
                "methods": methods,
                "camera": camera,
                "camera_hash": digest_json(camera),
                "sequence": request.get("sequence", 0),
                "created_at": time.time(),
            }
            atomic_json(
                folder / "request.json",
                {
                    "record": record,
                    "configs": {m: scene["methods"][m]["config"] for m in methods},
                    "root": str(self.root),
                    "settings": self.settings,
                },
            )
            atomic_json(folder / "status.json", record)
            self.records[job_id] = record
            if self.pending:
                self.cancel(self.pending)
            self.pending = job_id
            return record

    def cancel(self, job_id):
        with self.lock:
            if job_id not in self.records:
                raise ValueError("Unknown job")
            folder = self.root / "artifacts/ui/jobs" / job_id
            (folder / "cancel").touch()
            if job_id == self.pending:
                self.pending = None
                self.records[job_id]["status"] = "cancelled"
                atomic_json(folder / "status.json", self.records[job_id])

    def cancel_all(self):
        for job in (self.active, self.pending):
            if job:
                self.cancel(job)

    def status(self, job_id):
        if job_id not in self.records:
            raise ValueError("Unknown job")
        folder = self.root / "artifacts/ui/jobs" / job_id
        value = json.loads((folder / "status.json").read_text(encoding="utf-8"))
        if (folder / "cancel").exists() and value["status"] == "succeeded":
            value["status"] = "cancelled"
            value.pop("results", None)
        return value

    def watch(self):
        while not self.closed:
            with self.lock:
                if self.owner and time.monotonic() > self.expires:
                    self.cancel_all()
                    self.owner = None
                if self.pending and not self.active:
                    job = self.pending
                    self.pending = None
                    self.active = job
                    threading.Thread(target=self.run, args=(job,), daemon=True).start()
            time.sleep(0.25)

    def run(self, job):
        folder = self.root / "artifacts/ui/jobs" / job
        try:
            with (folder / "worker.log").open("w", encoding="utf-8") as log:
                # sys.executable is the already pinned project Conda Python.
                with self.lock:
                    if self.closed:
                        raise InterruptedError("UI server is stopping")
                    proc = subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "UI_design.backend.worker",
                            str(folder / "request.json"),
                        ],
                        cwd=self.root,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    )
                    self.processes[job] = proc
                proc.wait()
            status = self.status(job)
            if status["status"] not in ("succeeded", "cancelled", "failed"):
                status.update(
                    status="failed",
                    error=f"Inference worker exited ({proc.returncode}); see worker.log",
                )
                atomic_json(folder / "status.json", status)
        except Exception as error:
            status = self.records[job] | {"status": "failed", "error": str(error)}
            atomic_json(folder / "status.json", status)
        finally:
            with self.lock:
                self.active = None
                self.processes.pop(job, None)
            self.evict()

    def shutdown(self):
        with self.lock:
            self.closed = True
            self.cancel_all()
            processes = list(self.processes.values())
        # Let exact-model loading/rendering unwind cooperatively, then stop only
        # owned process trees if a CUDA/native call will not return.
        for proc in processes:
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                from topic16.safety import stop_process_tree

                stop_process_tree(proc)
                proc.wait(timeout=10)

    def evict(self):
        """Evict only completed UI cache jobs; active/pending are pinned."""
        with self.lock:
            folders = []
            total = 0
            for p in (self.root / "artifacts/ui/jobs").glob("*"):
                if not p.is_dir():
                    continue
                size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                total += size
                if p.name not in (self.active, self.pending):
                    folders.append((p.stat().st_mtime, p, size))
            import shutil

            limit = self.settings["Ui"]["CacheBytes"]
            complete = []
            for entry in folders:
                status = entry[1] / "status.json"
                if (
                    status.exists()
                    and json.loads(status.read_text(encoding="utf-8")).get("status")
                    == "succeeded"
                ):
                    complete.append(entry)
            newest = (
                max(complete or folders, key=lambda item: item[0])[1]
                if folders
                else None
            )
            for _, p, size in sorted(folders):
                if total <= limit:
                    break
                # Keep the newest complete pair and never touch original artifacts.
                if p == newest:
                    continue
                shutil.rmtree(p)
                self.records.pop(p.name, None)
                total -= size
