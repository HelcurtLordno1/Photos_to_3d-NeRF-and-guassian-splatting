"""Local serial inference adapter and checksum-backed release manifests."""
from __future__ import annotations

from topic16.settings import experiment_settings_hash

import io
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from topic16.analysis import collect_pairs, core_gate
from topic16.contracts import digest_json, file_required, inside, load_run, read_json, relative, sha256, utc_now, validate_camera_path, validate_render, validate_safety_record, write_json


def create_camera_path(root: Path, settings: dict, config: Path, output: Path) -> dict:
    """A deterministic demo path through frozen poses; no optimizer or GPU needed."""
    import math
    run = load_run(root, config.resolve(), require_eval=True)
    frames = []
    for camera in run['split']['eval']:
        matrix = camera['camera_to_world'] + [[0, 0, 0, 1]]
        frames.append({'camera_to_world': [value for row in matrix for value in row],
                       'fov': math.degrees(2 * math.atan(camera['height'] / (2 * camera['fy'])))})
    record = {'camera_type': 'perspective', 'render_width': settings['DemoWidth'],
              'render_height': settings['DemoHeight'], 'camera_path': frames, 'fps': 24,
              'source_split_hash': digest_json(run['split']),
              'description': 'Frozen evaluation poses with centered perspective intrinsics at demo resolution; not the held-out metric camera grid.'}
    validate_camera_path(record)
    output = inside(root / 'reports', output)
    if output.exists():
        if read_json(output) != record:
            raise ValueError('Camera path differs; preserve it and use a new output version')
    else:
        write_json(output, record)
    print(f'Shared camera path: {output}')
    return record


def verified_gate(root: Path, settings: dict, path: Path) -> dict:
    gate = read_json(file_required(path))
    if gate["status"] != "PASS" or not all(gate["checks"].values()) or gate["settings_hash"] != experiment_settings_hash(settings):
        raise ValueError("G-Core is not PASS for the current registry")
    if not gate.get('review'):
        raise ValueError('G-Core lacks its recorded human review manifest')
    review_path = file_required(inside(root, gate['review']['path']))
    if sha256(review_path) != gate['review']['sha256']:
        raise ValueError('Human review manifest changed after G-Core acceptance')
    matrices = []
    for record in gate["matrices"] + gate["review_evidence"]:
        artifact = file_required(inside(root, record["path"]))
        if sha256(artifact) != record["sha256"]:
            raise ValueError("Core gate evidence changed after review")
    for record in gate["matrices"]:
        matrices.append(inside(root, record["path"]))
    pairs = collect_pairs(root, matrices)
    current = core_gate(root, settings, pairs, matrices, review_path)
    if current['status'] != 'PASS' or current['checks'] != gate['checks']:
        raise ValueError('Core artifacts and human review no longer satisfy every gate')
    if current["run_keys"] != gate["run_keys"]:
        raise ValueError("Core run selection changed")
    return gate


def select_model(root: Path, settings: dict, config: Path, gate_path: Path, camera_path: Path, output: Path) -> dict:
    gate_path = inside(root, gate_path)
    gate = verified_gate(root, settings, gate_path)
    run = load_run(root, config.resolve(), require_eval=True)
    if run["manifest"]["run_key"] not in gate["run_keys"]:
        raise ValueError("Selected model was not included in G-Core evidence")
    camera_path = file_required(inside(root, camera_path))
    camera_hash = sha256(camera_path)
    document = read_json(camera_path)
    validate_camera_path(document)
    measurement_path = run["paths"]["videos"] / camera_hash[:16] / "render.json"
    measurement = validate_render(measurement_path.parent, run['provenance']['checkpoint_sha256'], root, settings)
    if measurement["camera_sha256"] != camera_hash or measurement["checkpoint_sha256"] != run["provenance"]["checkpoint_sha256"]:
        raise ValueError("Fallback trajectory/model mismatch")
    fallback = file_required(measurement_path.parent / "video.mp4")
    record = {"schema_version": "1.0", "selected_at": utc_now(), "method": run["manifest"]["method"],
              "run_key": run["manifest"]["run_key"], "config": relative(root, run["config"]),
              "checkpoint": relative(root, run["checkpoint"]), "config_sha256": run["provenance"]["config_sha256"],
              "checkpoint_sha256": run["provenance"]["checkpoint_sha256"],
              "settings_hash": experiment_settings_hash(settings), "runtime_sha256": run["provenance"]["runtime_sha256"],
              "gate": relative(root, gate_path), "gate_sha256": sha256(gate_path),
              "camera_path": relative(root, camera_path), "camera_sha256": camera_hash,
              "fallback_video": relative(root, fallback), "fallback_sha256": sha256(fallback),
              "input": {"camera_index_min": 0, "camera_index_max": len(document["camera_path"]) - 1,
                        "render_width": document["render_width"], "render_height": document["render_height"]}}
    if output.exists():
        raise ValueError("Model selection manifest already exists; use a new version")
    write_json(inside(root / "reports", output), record)
    return record


def verify_model(root: Path, settings: dict, model: Path) -> tuple[dict, dict]:
    record = read_json(file_required(model))
    if record["settings_hash"] != experiment_settings_hash(settings):
        raise ValueError("Demo registry differs from model selection")
    for path_field, hash_field in (("gate", "gate_sha256"), ("camera_path", "camera_sha256"),
                                  ("fallback_video", "fallback_sha256")):
        if sha256(file_required(inside(root, record[path_field]))) != record[hash_field]:
            raise ValueError(f"Missing or modified demo artifact: {path_field}")
    verified_gate(root, settings, inside(root, record["gate"]))
    run = load_run(root, inside(root, record["config"]), require_eval=True)
    if record["run_key"] != run["manifest"]["run_key"] or record["method"] != run["manifest"]["method"]:
        raise ValueError("Model selection identity differs from loaded run")
    for name in ("checkpoint_sha256", "config_sha256", "runtime_sha256"):
        if record[name] != run["provenance"][name]:
            raise ValueError("Model selection provenance mismatch")
    measurement = run['paths']['videos'] / record['camera_sha256'][:16]
    validate_render(measurement, record['checkpoint_sha256'], root, settings)
    return record, run


def start_demo(root: Path, settings: dict, model: Path, health_only=False, fallback=False) -> None:
    from topic16.runtime import close_pipeline, gpu_lock, load_pipeline, validate_runtime_snapshot, validate_loaded_split
    from topic16.sessions import check_stop, stop_requested
    check_stop()
    record, run = verify_model(root, settings, model)
    if fallback:
        import os
        os.startfile(str(inside(root, record["fallback_video"])))
        return
    import torch
    from PIL import Image
    from nerfstudio.cameras.camera_paths import get_path_from_json
    validate_runtime_snapshot(record["runtime_sha256"])
    with gpu_lock(root, settings):
        _, pipeline, _ = load_pipeline(root, run)
        try:
            validate_loaded_split(root, run, pipeline)
            cameras = get_path_from_json(read_json(inside(root, record["camera_path"]))).to(pipeline.device)
            def image_bytes(index):
                check_stop()
                with torch.no_grad():
                    rgb = pipeline.model.get_outputs_for_camera(cameras[index:index + 1])["rgb"]
                    if not torch.isfinite(rgb).all():
                        raise ValueError("Model produced non-finite pixels")
                    pixels = (rgb.clamp(0, 1).cpu().numpy() * 255).round().astype("uint8")
                stream = io.BytesIO()
                Image.fromarray(pixels).save(stream, format="PNG")
                return stream.getvalue()
            for _ in range(settings["RenderWarmupFrames"]):
                image_bytes(0)
            # Actual repeated inference checks startup determinism at PNG precision.
            if image_bytes(0) != image_bytes(0):
                raise ValueError("Repeated fixed-camera inference is not deterministic at 8-bit precision")
            from topic16.safety import current_guard
            write_json(model.with_suffix('.health.json'), {'schema_version': '1.0', 'status': 'succeeded',
                'checked_at': utc_now(), 'model_sha256': sha256(model),
                'checkpoint_sha256': record['checkpoint_sha256'],
                'checks': {'cuda_inference': True, 'fixed_camera': True, 'png_determinism': True},
                'gpu_safety_path': relative(root, current_guard().path)})
            if health_only:
                print("Demo health PASS: CUDA, model hashes, fixed camera and repeated inference")
                return
            html = f'''<!doctype html><html lang="vi"><meta charset="utf-8"><title>Topic 16 — 3D demo</title>
    <style>body{{margin:32px auto;max-width:1100px;font:18px system-ui;background:#151b26;color:#eee}}img{{width:100%;border-radius:12px}}input{{width:100%}}</style>
    <h1>Khám phá cảnh 3D</h1><p>Di chuyển thanh trượt để xem các góc chụp.</p>
    <input id="camera" type="range" min="0" max="{len(cameras)-1}" value="0"><p id="status">Góc nhìn 1</p><img id="image" src="/frame?i=0">
    <script>const slider=document.querySelector('#camera');slider.onchange=()=>{{document.querySelector('#status').textContent='Đang tải góc nhìn…';const image=document.querySelector('#image');image.onload=()=>document.querySelector('#status').textContent='Góc nhìn '+(+slider.value+1);image.src='/frame?i='+slider.value;}};</script></html>'''.encode()
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    parsed = urlparse(self.path)
                    try:
                        if parsed.path == "/":
                            content, kind = html, "text/html; charset=utf-8"
                        elif parsed.path == "/health":
                            content, kind = json.dumps({"status": "ready", "method": record["method"]}).encode(), "application/json"
                        elif parsed.path == "/frame":
                            index = int(parse_qs(parsed.query).get("i", ["0"])[0])
                            if not 0 <= index < len(cameras):
                                raise ValueError("Camera index out of bounds")
                            content, kind = image_bytes(index), "image/png"
                        else:
                            self.send_error(404)
                            return
                        self.send_response(200)
                        self.send_header("Content-Type", kind)
                        self.send_header("Content-Length", str(len(content)))
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        self.wfile.write(content)
                    except (ValueError, RuntimeError) as error:
                        self.send_error(400, str(error))
            class SerialServer(HTTPServer):
                request_queue_size = settings["DemoQueueCapacity"]
                def get_request(self):
                    connection, address = super().get_request()
                    connection.settimeout(15)
                    return connection, address
            with SerialServer(("127.0.0.1", settings["DemoPort"]), Handler) as server:
                print(f"Demo ready: http://127.0.0.1:{settings['DemoPort']} — Ctrl+C to stop", flush=True)
                try:
                    server.timeout = 0.5
                    while not stop_requested():
                        server.handle_request()
                except KeyboardInterrupt:
                    pass
        finally:
            close_pipeline(pipeline)


def validate_demo_health(root: Path, settings: dict, model: Path, checkpoint_hash: str) -> Path:
    path = file_required(model.with_suffix('.health.json'))
    record = read_json(path)
    if (record['status'] != 'succeeded' or record['model_sha256'] != sha256(model)
            or record['checkpoint_sha256'] != checkpoint_hash
            or record.get('checks') != {'cuda_inference': True, 'fixed_camera': True, 'png_determinism': True}):
        raise ValueError('Release requires a successful health check of this exact selected model')
    validate_safety_record(root, record, settings)
    return path


def release(root: Path, settings: dict, model: Path, output: Path) -> dict:
    record = read_json(file_required(model))
    verify_model(root, settings, model)
    health = validate_demo_health(root, settings, model, record['checkpoint_sha256'])
    run = load_run(root, inside(root, record["config"]), require_eval=True)
    gate = verified_gate(root, settings, inside(root, record['gate']))
    files = [model, run["config"], run["checkpoint"], run["paths"]["logs"] / "requirements.txt",
             health, inside(root, read_json(health)['gpu_safety_path']),
             inside(root, record["gate"]), inside(root, record["camera_path"]), inside(root, record["fallback_video"])]
    # Gate revalidation on another checkout needs the exact evidence graph, not
    # just the selected model. Enumerate references; never bundle files into Git.
    for item in gate['matrices'] + gate['review_evidence'] + [gate['review']]:
        files.append(file_required(inside(root, item['path'])))
    for key in gate['run_keys']:
        from topic16.contracts import run_paths
        paths = run_paths(root, key)
        evidence = load_run(root, paths['runs'] / 'config.yml', require_eval=True)
        ancestor = evidence['provenance'].get('resumed_from')
        while ancestor:
            files.append(file_required(inside(root, ancestor['checkpoint'])))
            files.extend(file_required(inside(root, item['path'])) for item in ancestor['evidence'])
            previous = read_json(root / 'artifacts/logs' / ancestor['run_key'] / 'provenance.json')
            files.append(file_required(inside(root, previous['gpu_safety_path'])))
            ancestor = previous.get('resumed_from')
        files.extend([evidence['config'], evidence['checkpoint']])
        for category in ('logs', 'metrics', 'renders', 'videos', 'exports'):
            files.extend(p for p in paths[category].rglob('*') if p.is_file())
        for section in ('provenance', 'evaluation'):
            if 'gpu_safety_path' in evidence[section]:
                files.append(file_required(inside(root, evidence[section]['gpu_safety_path'])))
        for path in paths['videos'].glob('*/render.json'):
            item = read_json(path)
            files.append(file_required(inside(root, item['gpu_safety_path'])))
        item = read_json(paths['exports'] / 'export.json')
        files.append(file_required(inside(root, item['gpu_safety_path'])))
        if evidence['manifest']['scene'].startswith('custom:'):
            from topic16.data import scene_source
            capture = scene_source(root, evidence['manifest']['scene'])[0]
            files.extend(p for p in capture.rglob('*') if p.is_file())
            approval = read_json(capture / 'capture.json')['visual_review']
            files.extend(file_required(inside(root, item['path'])) for item in approval['evidence'])
    # Inference still loads the selected dataset's metadata/points/images.
    directory = inside(root / 'data/processed/canonical', root / Path(run['split']['train'][0]['path']).parent.parent)
    files.extend(p for p in directory.rglob('*') if p.is_file())
    preparation = read_json(directory / 'preparation.json')
    files.extend(file_required(inside(root, item['path'])) for item in preparation['source_files'])
    if run['manifest']['scene'].startswith('custom:'):
        from topic16.data import scene_source
        capture = scene_source(root, run['manifest']['scene'])[0]
        files.extend(p for p in capture.rglob('*') if p.is_file())
    for folder in ('src', 'scripts', 'configs'):
        files.extend(p for p in (root / folder).rglob('*') if p.suffix in ('.py', '.ps1', '.psd1', '.json'))
    files.extend([root / 'Invoke-Topic16.ps1', root / 'setup_full_command.md'])
    files = sorted(set(file_required(path).resolve() for path in files))
    record = {"schema_version": "1.0", "created_at": utc_now(), "git_commit": run["provenance"]["git_commit"],
              "source_diff_sha256": run["provenance"]["git_diff_sha256"], "run_key": record["run_key"],
              "files": [{"path": relative(root, path), "sha256": sha256(path), "bytes": path.stat().st_size} for path in files],
              "citations": ["https://jonbarron.info/mipnerf360/", "https://arxiv.org/abs/2302.04264", "https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/"],
              "retrieval": "Use the pinned PowerShell runbook for runtime; transfer every listed file with its relative path and verify checksums. The graph includes gate runs, reviews, safety, source and selected canonical data. Original private video and other raw benchmark archives remain separately retained inputs."}
    if output.exists():
        raise ValueError("Release manifest already exists; use a new version")
    write_json(inside(root / "reports", output), record)
    return record
