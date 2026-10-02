"""Validate evidence, publish measured tables/figures, and compute the core gate."""
from __future__ import annotations

from topic16.settings import experiment_settings_hash

import csv
from pathlib import Path

from topic16.contracts import (
    SCENES, digest_json, file_required, inside, read_json, relative, sha256,
    utc_now, validate_capture_review, validate_export, validate_pair, validate_render, write_json,
)


def collect_pairs(root: Path, matrices: list[Path], protocol_id: str = 'primary') -> dict[str, list[dict]]:
    pairs = {}
    for path in sorted(matrices):
        matrix = read_json(file_required(path))
        if matrix["status"] != "succeeded":
            raise ValueError(f"Incomplete matrix: {path}")
        if matrix["protocol"]["id"] != protocol_id:
            raise ValueError("Matrix protocol differs from the explicitly selected report protocol")
        if set(matrix["pairs"]) != set(matrix["scenes"]):
            raise ValueError("Matrix scene list differs from its pairs")
        for scene, record in sorted(matrix["pairs"].items()):
            if scene in pairs:
                raise ValueError(f"Ambiguous duplicate scene selection: {scene}")
            runs = validate_pair(root, record, primary_only=(protocol_id == 'primary'))
            if any(run['provenance']['protocol_id'] != protocol_id for run in runs):
                raise ValueError('Matrix label differs from actual run protocol')
            if runs[0]["manifest"]["scene"] != scene:
                raise ValueError("Matrix pair stored under the wrong scene")
            for first, second in zip(runs[0]["evaluation"]["frames"], runs[1]["evaluation"]["frames"]):
                if first["gt_sha256"] != second["gt_sha256"]:
                    raise ValueError("Methods evaluated against different ground-truth pixels")
            pairs[scene] = runs
    return dict(sorted(pairs.items()))


def paired_throughput(runs: list[dict]) -> dict[str, float]:
    """Report only a common camera path and resolution; omit unpaired measurements."""
    measurements = []
    for run in runs:
        records = {}
        for path in sorted(run["paths"]["videos"].glob("*/render.json")):
            record = validate_render(path.parent, run['provenance']['checkpoint_sha256'])
            records[record["camera_sha256"]] = record
        measurements.append(records)
    common = sorted(set(measurements[0]) & set(measurements[1]))
    if not common:
        return {}
    # Keep the held-out measurement stable after adding demo trajectories.
    held_out = digest_json(runs[0]['split']['eval'])
    if held_out in common:
        selected = held_out
    elif len(common) == 1:
        selected = common[0]
    else:
        raise ValueError("Multiple shared render paths; select one trajectory per analysis")
    records = [collection[selected] for collection in measurements]
    for field in ("frame_count", "widths", "heights", "warmup_frames"):
        if records[0][field] != records[1][field]:
            raise ValueError(f"Throughput measurements differ: {field}")
    return {run["manifest"]["method"]: record["fps"] for run, record in zip(runs, records)}


def result_rows(pairs: dict[str, list[dict]], include_poster: bool = False) -> list[dict]:
    rows = []
    for scene, runs in pairs.items():
        if scene == "poster" and not include_poster:
            continue
        throughput = paired_throughput(runs)
        for run in runs:
            manifest = run["manifest"]
            rows.append({"scene": scene, "method": manifest["method"],
                         "run_key": manifest["run_key"], "git_commit": manifest["provenance"]["git_commit_sha"],
                         "seed": manifest["protocol"]["seed"],
                         'iterations': manifest['protocol']['iterations'],
                         'downscale_factor': manifest['protocol']['downscale_factor'],
                         'protocol_id': run['provenance']['protocol_id'],
                         **{key: run["metrics"]["results"][key] for key in ("psnr", "ssim", "lpips")},
                         "train_seconds": manifest["execution_metrics"]["wall_time_seconds"],
                         "peak_vram_mb": manifest["execution_metrics"]["peak_vram_mb"],
                         "checkpoint_bytes": run["evaluation"]["checkpoint_bytes"],
                         "offline_fps": throughput.get(manifest["method"], "")})
    return rows


def figures(root: Path, output: Path, pairs: dict, rows: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image, ImageDraw
    destination = output / "figures"
    destination.mkdir(exist_ok=True)
    crops = []
    for scene, runs in pairs.items():
        if scene == "poster":
            continue
        # Identical first held-out view and documented center crop. Human analysis may
        # select more views later; these are evidence figures, not invented failure claims.
        frame = runs[0]["evaluation"]["frames"][0]
        sources = [runs[0]["paths"]["renders"] / frame["gt"]]
        sources += [run["paths"]["renders"] / run["evaluation"]["frames"][0]["pred"] for run in runs]
        with Image.open(sources[0]) as image:
            width, height = image.size
        box = (width // 4, height // 4, width * 3 // 4, height * 3 // 4)
        panel = Image.new("RGB", ((box[2] - box[0]) * 3, box[3] - box[1] + 24), "white")
        draw = ImageDraw.Draw(panel)
        for index, (path, label) in enumerate(zip(sources, ("GT", "Nerfacto", "Splatfacto"))):
            with Image.open(path) as image:
                if image.size != (width, height):
                    raise ValueError("Paired figure resolution mismatch")
                panel.paste(image.convert("RGB").crop(box), (index * (box[2] - box[0]), 24))
            draw.text((index * (box[2] - box[0]) + 4, 4), label, fill="black")
        panel.save(destination / f"{scene.replace(':', '-')}.png")
        crops.append({"scene": scene, "camera": frame["source"], "crop_xyxy": box,
                      "run_keys": [run["manifest"]["run_key"] for run in runs]})
    write_json(output / "crops.json", crops)
    if rows:
        scenes = sorted({row["scene"] for row in rows})
        figure, axes = plt.subplots(1, 3, figsize=(max(9, len(scenes) * 2), 3.5))
        for axis, (metric, label) in zip(axes, (("psnr", "PSNR (dB) ↑"), ("train_seconds", "Train time (s) ↓"), ("peak_vram_mb", "Sampled peak VRAM (MiB) ↓"))):
            for index, method in enumerate(("nerfacto", "splatfacto")):
                values = [next(row[metric] for row in rows if row["scene"] == scene and row["method"] == method) for scene in scenes]
                axis.bar([i + index * 0.35 for i in range(len(scenes))], values, width=0.35, label=method)
            axis.set_xticks([i + 0.175 for i in range(len(scenes))], scenes, rotation=20)
            axis.set_ylabel(label)
        axes[0].legend()
        figure.tight_layout()
        figure.savefig(destination / "comparison.png", dpi=180)
        plt.close(figure)


def core_gate(root: Path, settings: dict, pairs: dict, matrices: list[Path], review_path: Path | None) -> dict:
    checks = {"poster_pair": "poster" in pairs, "bonsai_calibration": "bonsai" in pairs,
              "benchmark_matrix": all(scene in pairs for scene in SCENES),
              "custom_pair": any(scene.startswith("custom:") for scene in pairs),
              "artifact_contracts": bool(pairs), 'paired_render': bool(pairs), 'exports': bool(pairs),
              "clean_machine_replay": False,
              "research_review": False}
    for runs in pairs.values():
        if not paired_throughput(runs):
            checks['paired_render'] = False
        for run in runs:
            if run['provenance']['settings_hash'] != experiment_settings_hash(settings):
                raise ValueError('Primary evidence belongs to a different registry/safety policy')
            if 'GpuClockMinMHz' in settings and 'gpu_safety_path' not in run['provenance']:
                raise ValueError('Primary evidence has no completed GPU safety record')
            protocol = run["manifest"]["protocol"]
            if protocol != {"iterations": settings["TrainIterations"], "seed": settings["RandomSeed"],
                            "downscale_factor": settings["DownscaleFactor"], "eval_interval": settings["EvalInterval"]}:
                raise ValueError("Run does not match the current primary registry")
            gpu = run["provenance"]["gpu"]
            if "A4500" not in gpu["gpu_name"] or gpu["total_vram_mb"] < 16000:
                raise ValueError("Primary evidence was collected on the wrong GPU")
            if run['manifest']['scene'].startswith('custom:'):
                validate_capture_review(root, run['manifest']['scene'], run['split'])
            render_path = run['paths']['videos'] / digest_json(run['split']['eval'])[:16]
            if (render_path / 'render.json').is_file():
                validate_render(render_path, run['provenance']['checkpoint_sha256'], root, settings)
            else:
                checks['paired_render'] = False
            if (run['paths']['exports'] / 'export.json').is_file():
                validate_export(run['paths']['exports'], run['provenance']['checkpoint_sha256'], root, settings)
            else:
                checks['exports'] = False
    review_evidence = []
    review_record = None
    if review_path:
        review_path = file_required(inside(root, review_path))
        review_record = {'path': relative(root, review_path), 'sha256': sha256(review_path)}
        review = read_json(review_path)
        if any(review.get(name, {}).get('approved') is True for name in ('clean_machine_replay', 'research_review')):
            expected_keys = sorted(run['manifest']['run_key'] for runs in pairs.values() for run in runs)
            if review.get('run_keys') != expected_keys or review.get('settings_hash') != experiment_settings_hash(settings):
                raise ValueError('Human review does not endorse the current selected runs and registry')
        for name in ("clean_machine_replay", "research_review"):
            entry = review.get(name, {})
            if entry.get("approved") is True:
                if not entry.get("reviewer") or not entry.get("notes") or not entry.get("evidence"):
                    raise ValueError("Review approval requires reviewer, notes and actual evidence files")
                for evidence in entry["evidence"]:
                    path = file_required(inside(root, evidence))
                    review_evidence.append({"path": relative(root, path), "sha256": sha256(path)})
                checks[name] = True
    return {"schema_version": "1.0", "status": "PASS" if all(checks.values()) else "BLOCKED",
            "checked_at": utc_now(), "checks": checks, "settings_hash": experiment_settings_hash(settings),
            "matrices": [{"path": relative(root, path), "sha256": sha256(path)} for path in sorted(matrices)],
            "review_evidence": review_evidence,
            'review': review_record,
            "run_keys": sorted(run["manifest"]["run_key"] for runs in pairs.values() for run in runs)}


def analyze(root: Path, settings: dict, matrices: list[Path], output: Path, review: Path | None = None,
            protocol_id: str = 'primary') -> dict:
    matrices = [inside(root, path) for path in matrices]
    pairs = collect_pairs(root, matrices, protocol_id)
    rows = result_rows(pairs, include_poster=(protocol_id != 'primary'))
    output = inside(root / "reports", output)
    output.mkdir(parents=True, exist_ok=True)
    if rows:
        with (output / "results.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    write_json(output / "results.json", rows)
    figures(root, output, pairs, rows)
    gate = core_gate(root, settings, pairs, matrices, review) if protocol_id == 'primary' else {
        'schema_version': '1.0', 'status': 'BLOCKED', 'protocol_id': protocol_id,
        'reason': 'Diagnostic/repeat reports do not satisfy the primary G-Core gate'}
    gate_path = output / 'g-core.json'
    previous = read_json(gate_path) if gate_path.exists() else None
    identity = lambda record: {key: value for key, value in record.items() if key != 'checked_at'}
    if previous is not None and identity(previous) == identity(gate):
        gate = previous  # Preserve the checksum used by existing model selections.
    else:
        write_json(gate_path, gate)
    header = "| Scene | Method | Steps | PSNR ↑ | SSIM ↑ | LPIPS ↓ | Train s | VRAM MiB | Checkpoint bytes | FPS ↑ | Run |\n|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|\n"
    table = "".join(f"| {row['scene']} | {row['method']} | {row['iterations']} | {row['psnr']:.4f} | {row['ssim']:.4f} | {row['lpips']:.4f} | {row['train_seconds']:.2f} | {row['peak_vram_mb']:.0f} | {row['checkpoint_bytes']} | {row['offline_fps']} | `{row['run_key']}` |\n" for row in rows)
    (output / "results.md").write_text(f"# Measured results — {protocol_id}\n\n" + header + table +
        "\nPoster is a gate only. Custom results form a separate scene group. Empty FPS means no paired synchronized measurement.\n"
        "\nLimitations: one laptop, one primary seed, Windows runtime, 10-second VRAM sampling, different batch semantics. "
        "No cross-hardware/general-method claim follows from these observations. Figures use identical held-out camera/crop; "
        "manual failure interpretation is required.\n", encoding="utf-8")
    print(f"Research artifacts: {output}; G-Core={gate['status']}")
    return gate
