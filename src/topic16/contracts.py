"""Artifact contracts shared by training, evaluation, reports and demos.

This module uses only the standard library so reviewers can audit results without CUDA.
Paths stored in manifests are repository relative; user supplied paths are resolved once.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

METHODS = ("nerfacto", "splatfacto")
SCENES = ("garden", "bonsai", "room")
RUN_KEY = re.compile(r"^(poster|garden|bonsai|room|custom-[a-z0-9][a-z0-9_-]*)/(nerfacto|splatfacto)/\d{8}T\d{9}Z$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    def invalid(value: str) -> None:
        raise ValueError(f"Non-finite JSON value {value} in {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=invalid)


def write_json(path: Path, value: Any) -> None:
    """Replace one JSON document atomically; never leave a partial success record."""
    import uuid
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}-{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def digest_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def inside(root: Path, path: str | Path) -> Path:
    root = root.resolve()
    candidate = Path(path)
    result = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if not result.is_relative_to(root):
        raise ValueError(f"Path escapes {root}: {path}")
    return result


def relative(root: Path, path: Path) -> str:
    return inside(root, path).relative_to(root.resolve()).as_posix()


def native_workspace(root: Path) -> Path:
    """ASCII junction for native libraries whose Windows file APIs reject Unicode.

    The junction points at existing files, copies no data, and is recreated if missing.
    All manifest identities still resolve to the original repository.
    """
    import os
    import subprocess
    import tempfile
    root = root.resolve()
    if str(root).isascii() or os.name != "nt":
        return root
    parent = Path(tempfile.gettempdir()) / "topic16-workspaces"
    if not str(parent).isascii():
        raise ValueError("Windows TEMP path must be ASCII for the native-library workspace junction")
    parent.mkdir(exist_ok=True)
    alias = parent / digest_json(str(root))[:16]
    if alias.exists():
        if alias.resolve() != root:
            raise ValueError("Native workspace alias points to a different repository")
    else:
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(alias), str(root)],
                       check=True, stdout=subprocess.DEVNULL)
    return alias


def file_required(path: Path) -> Path:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Missing or empty artifact: {path}")
    return path


def finite_number(value: Any, name: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return float(value)


def validate_metrics(record: dict) -> dict:
    results = record["results"]
    for name in ("psnr", "ssim", "lpips"):
        finite_number(results[name], name)
    if not -1 <= results["ssim"] <= 1 or results["lpips"] < 0:
        raise ValueError("SSIM/LPIPS outside valid range")
    for name, value in results.items():
        finite_number(value, name)
    return results


def validate_split(split: dict) -> None:
    train, evaluation = split["train"], split["eval"]
    if not train or not evaluation:
        raise ValueError("Both train and held-out split must be nonempty")
    train_names = [item["path"] for item in train]
    eval_names = [item["path"] for item in evaluation]
    if len(set(train_names + eval_names)) != len(train_names + eval_names):
        raise ValueError("Duplicate image identity or train/eval leakage")
    if {item["sha256"] for item in train} & {item["sha256"] for item in evaluation}:
        raise ValueError("Identical image content in train and eval")
    for item in train + evaluation:
        if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("Invalid image checksum")
        if len(item["camera_to_world"]) != 3 or any(len(row) != 4 for row in item["camera_to_world"]):
            raise ValueError("Camera pose must be 3x4")
        for row in item["camera_to_world"]:
            for value in row:
                finite_number(value, "camera pose")


def validate_camera_path(document: dict) -> None:
    for field in ('render_width', 'render_height'):
        value = document[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 2 or value % 2:
            raise ValueError('Video camera resolution must be positive even integers')
    frames = document['camera_path']
    if not frames or len(frames) > 10000:
        raise ValueError('Camera trajectory must contain 1–10000 frames')
    if document.get('camera_type', 'perspective').lower() not in ('perspective', 'fisheye', 'equirectangular'):
        raise ValueError('Unsupported camera type')
    for frame in frames:
        pose = frame['camera_to_world']
        if len(pose) != 16:
            raise ValueError('Viewer camera_to_world must contain 16 numbers')
        for value in pose:
            finite_number(value, 'camera pose')
        if not 0 < finite_number(frame['fov'], 'field of view') < 180:
            raise ValueError('Camera field of view must be between 0 and 180 degrees')
    finite_number(document.get('fps', 24), 'video FPS', minimum=1)


def run_paths(root: Path, key: str) -> dict[str, Path]:
    if not RUN_KEY.fullmatch(key):
        raise ValueError(f"Invalid run key: {key}")
    return {kind: root / "artifacts" / kind / key for kind in ("runs", "logs", "metrics", "renders", "videos", "exports")}


def validate_safety_record(root: Path, record: dict, settings: dict) -> None:
    policy = {key: value for key, value in settings.items() if key.startswith('Gpu')}
    if 'gpu_safety_path' not in record:
        if 'GpuClockMinMHz' in settings:
            raise ValueError('GPU artifact lacks its completed safety record')
        return
    path = inside(root / 'artifacts/logs/safety', inside(root, record['gpu_safety_path']))
    safety = read_json(file_required(path))
    if safety['status'] != 'succeeded' or safety.get('policy') != policy:
        raise ValueError('GPU artifact did not finish under its recorded safety policy')


def validate_capture_review(root: Path, scene: str, split: dict) -> dict:
    report = read_json(file_required(inside(root / 'data/processed/custom', scene.split(':')[1]) / 'capture.json'))
    review = report.get('visual_review', {})
    if report['status'] != 'ready' or review.get('approved') is not True or report['split_hash'] != digest_json(split):
        raise ValueError('Custom capture requires review of this exact frozen split')
    if not review.get('reviewer', '').strip() or not review.get('notes', '').strip() or not review.get('evidence'):
        raise ValueError('Custom pose review requires reviewer, notes and visual evidence')
    for item in review['evidence']:
        if sha256(file_required(inside(root, item['path']))) != item['sha256']:
            raise ValueError('Custom pose review evidence changed after acceptance')
    return report


def validate_export(directory: Path, checkpoint_hash: str, root: Path, settings: dict) -> dict:
    record = read_json(file_required(directory / 'export.json'))
    if record['checkpoint_sha256'] != checkpoint_hash or not record['files']:
        raise ValueError('Export is empty or belongs to a different checkpoint')
    validate_safety_record(root, record, settings)
    for item in record['files']:
        path = file_required(inside(directory, item['name']))
        if path.stat().st_size != item['bytes'] or sha256(path) != item['sha256']:
            raise ValueError('Completed export is missing or modified')
    return record


def validate_render(directory: Path, checkpoint_hash: str, root: Path | None = None, settings: dict | None = None) -> dict:
    record = read_json(file_required(directory / 'render.json'))
    if record.get('status', 'succeeded') != 'succeeded' or record['checkpoint_sha256'] != checkpoint_hash:
        raise ValueError('Render is incomplete or belongs to a different checkpoint')
    if root is not None and settings is not None:
        validate_safety_record(root, record, settings)
    finite_number(record['fps'], 'offline FPS', minimum=0)
    durations = record['durations_seconds']
    if not durations or record['frame_count'] < 1:
        raise ValueError('Empty throughput measurement')
    for duration in durations:
        finite_number(duration, 'render duration', minimum=0)
        if duration <= 0:
            raise ValueError('Render duration must be positive')
    expected_fps = record['frame_count'] * len(durations) / sum(durations)
    if abs(record['fps'] - expected_fps) > 1e-6 * expected_fps:
        raise ValueError('FPS differs from synchronized measurement durations')
    if record['includes_image_io'] is not False:
        raise ValueError('Throughput must exclude image IO')
    for field in ('widths', 'heights'):
        values = record[field]
        if len(values) != record['frame_count'] or any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in values):
            raise ValueError('Invalid render camera dimensions')
    expected_names = [f'frame_{i:04d}.png' for i in range(record['frame_count'])]
    if [p.name for p in sorted(directory.glob('frame_*.png'))] != expected_names:
        raise ValueError('Render frame count/index mismatch')
    for item in record.get('frames', []):
        if sha256(file_required(inside(directory, item['name']))) != item['sha256']:
            raise ValueError('Rendered frame modified after measurement')
    if 'frames' in record and [item['name'] for item in record['frames']] != expected_names:
        raise ValueError('Render checksum list differs from frame identities')
    if 'video_sha256' in record and sha256(file_required(directory / 'video.mp4')) != record['video_sha256']:
        raise ValueError('Rendered video changed after measurement')
    return record


def load_run(root: Path, config_path: Path, require_eval: bool = False) -> dict:
    from topic16.settings import experiment_settings_hash
    root = root.resolve()
    config_path = inside(root / "artifacts" / "runs", config_path)
    if config_path.name != "config.yml":
        raise ValueError("Expected the exact generated config.yml")
    key = config_path.parent.relative_to((root / "artifacts" / "runs").resolve()).as_posix()
    paths = run_paths(root, key)
    manifest = read_json(paths["logs"] / "manifest.json")
    if manifest['schema_version'] != '1.0':
        raise ValueError('Unsupported run manifest schema')
    if manifest["run_key"] != key or manifest["status"] != "succeeded":
        raise ValueError("Run is incomplete, failed, or has mismatched identity")
    if manifest["scene"].replace(":", "-") != key.split("/")[0] or manifest["method"] != key.split("/")[1]:
        raise ValueError("Run scene/method mismatch")
    file_required(config_path)
    provenance = read_json(paths["logs"] / "provenance.json")
    if sha256(config_path) != provenance["config_sha256"]:
        raise ValueError("Generated configuration changed after training")
    checkpoint = inside(root, provenance["checkpoint_path"])
    if checkpoint.parent != paths["runs"] / "nerfstudio_models":
        raise ValueError("Checkpoint belongs to a different run")
    file_required(checkpoint)
    checkpoints = list(checkpoint.parent.glob('*.ckpt'))
    if checkpoints != [checkpoint]:
        raise ValueError('Run must have exactly its recorded final checkpoint')
    if sha256(checkpoint) != provenance["checkpoint_sha256"]:
        raise ValueError("Checkpoint changed after training")
    split = read_json(paths["logs"] / "split.json")
    validate_split(split)
    if digest_json(split) != manifest["provenance"]["dataset_split_hash"]:
        raise ValueError("Frozen split changed after training")
    settings = read_json(paths['logs'] / 'settings.json')
    if experiment_settings_hash(settings) != provenance['settings_hash']:
        raise ValueError('Registry snapshot changed after training')
    if 'source_archive_sha256' in provenance:
        import zipfile
        archive = file_required(paths['logs'] / 'source.zip')
        if sha256(archive) != provenance['source_archive_sha256']:
            raise ValueError('Archived project source changed after training')
        with zipfile.ZipFile(archive) as source:
            if set(source.namelist()) != set(provenance['source_files']):
                raise ValueError('Source archive differs from recorded file list')
            import hashlib
            for name, expected in provenance['source_files'].items():
                if hashlib.sha256(source.read(name)).hexdigest() != expected:
                    raise ValueError('Archived source file differs from its checksum')
        if digest_json(file_required(paths['logs'] / 'requirements.txt').read_text(encoding='utf-8')) != provenance['runtime_sha256']:
            raise ValueError('Dependency snapshot changed after training')
    validate_safety_record(root, provenance, settings)
    ancestor = provenance.get('resumed_from')
    visited = {key}
    while ancestor:
        if ancestor['run_key'] in visited:
            raise ValueError('Resume ancestry contains a cycle')
        visited.add(ancestor['run_key'])
        if sha256(file_required(inside(root, ancestor['checkpoint']))) != ancestor['checkpoint_sha256']:
            raise ValueError('Resume ancestor checkpoint changed')
        for item in ancestor['evidence']:
            if sha256(file_required(inside(root, item['path']))) != item['sha256']:
                raise ValueError('Resume ancestor evidence changed')
        previous = read_json(run_paths(root, ancestor['run_key'])['logs'] / 'provenance.json')
        validate_safety_record(root, previous, settings)
        ancestor = previous.get('resumed_from')
    finite_number(manifest['execution_metrics']['wall_time_seconds'], 'train wall time', minimum=0)
    finite_number(manifest['execution_metrics']['peak_vram_mb'], 'sampled peak VRAM', minimum=0)
    run = {"manifest": manifest, "provenance": provenance, "split": split, "paths": paths, "checkpoint": checkpoint, "config": config_path}
    for name in ("command.txt", "train.log", "timing.env", "gpu.csv", "run.env", "settings.json"):
        file_required(paths["logs"] / name)
    if require_eval:
        evaluation = read_json(paths["metrics"] / "evaluation.json")
        if evaluation["status"] != "succeeded" or evaluation["run_key"] != key:
            raise ValueError("Missing successful evaluation of this exact run")
        validate_safety_record(root, evaluation, settings)
        for name in ("config_sha256", "checkpoint_sha256"):
            if evaluation[name] != provenance[name]:
                raise ValueError(f"Evaluation {name} differs from trained artifact")
        if evaluation["split_hash"] != digest_json(split):
            raise ValueError("Evaluator used a different camera split")
        metrics_path = file_required(paths["metrics"] / "metrics.json")
        if sha256(metrics_path) != evaluation["metrics_sha256"]:
            raise ValueError("Metrics modified after evaluation")
        metrics = read_json(metrics_path)
        validate_metrics(metrics)
        if inside(root, metrics["checkpoint"]) != checkpoint:
            raise ValueError("Metrics identify the wrong checkpoint")
        expected = [item["path"] for item in split["eval"]]
        if [item["source"] for item in evaluation["frames"]] != expected:
            raise ValueError("Rendered camera identities differ from held-out split")
        for frame in evaluation["frames"]:
            for kind in ("gt", "pred"):
                artifact = inside(paths["renders"], frame[kind])
                file_required(artifact)
                if sha256(artifact) != frame[f"{kind}_sha256"]:
                    raise ValueError("Held-out image modified after evaluation")
        run["evaluation"], run["metrics"] = evaluation, metrics
    return run


def validate_pair(root: Path, record: dict, primary_only: bool = False) -> list[dict]:
    if record["status"] != "succeeded" or set(record["runs"]) != set(METHODS):
        raise ValueError("Pair must contain exactly two successful methods")
    runs = [load_run(root, inside(root, record["runs"][method]), require_eval=True) for method in METHODS]
    first = runs[0]
    for method, run in zip(METHODS, runs):
        manifest = run["manifest"]
        if manifest["method"] != method or manifest["scene"] != record["scene"]:
            raise ValueError("Wrong scene or method in pair")
        if manifest["protocol"] != first["manifest"]["protocol"] or run["split"] != first["split"]:
            raise ValueError("Pair has different protocol, cameras or image contents")
        for field in ("settings_hash", "runtime_sha256", "git_commit", "git_diff_sha256", "protocol_id"):
            if run["provenance"][field] != first["provenance"][field]:
                raise ValueError(f"Pair provenance differs: {field}")
        if manifest["hardware"] != first["manifest"]["hardware"]:
            raise ValueError("Pair ran on different hardware/driver")
        if run['provenance']['gpu'] != first['provenance']['gpu']:
            raise ValueError('Pair GPU identity differs')
        if primary_only and run["provenance"]["protocol_id"] != "primary":
            raise ValueError("Diagnostic runs cannot enter primary results")
    return runs
