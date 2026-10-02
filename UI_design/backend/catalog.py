from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path
from topic16.contracts import (
    inside,
    read_json,
    relative,
    sha256,
    validate_pair,
    validate_export,
    validate_render,
    utc_now,
)
from topic16.settings import assert_experiment_compatible, ui_settings_hash

LABELS = {
    "custom:tea_sets_2": ("Tea sets", "Bộ trà · dữ liệu tự chụp", "custom"),
    "bonsai": ("Bonsai", "Cây bonsai · không gian trong nhà", "calibration"),
    "garden": ("Garden", "Khu vườn · cảnh ngoài trời", "benchmark"),
    "room": ("Room", "Căn phòng · hình học và chi tiết", "benchmark"),
    "poster": ("Poster", "Tranh poster · smoke test, ngoài aggregate", "poster"),
}

# Read only reviewed model fields from a contract-verified config. BaseLoader
# does not construct Python objects from Nerfstudio's Python YAML tags.
ARCHITECTURE_FIELDS = {
    "nerfacto": (
        "appearance_embed_dim",
        "base_res",
        "max_res",
        "num_levels",
        "features_per_level",
        "hidden_dim",
        "hidden_dim_color",
        "implementation",
        "num_nerf_samples_per_ray",
        "num_proposal_iterations",
        "num_proposal_samples_per_ray",
        "proposal_net_args_list",
        "disable_scene_contraction",
        "predict_normals",
        "near_plane",
        "far_plane",
        "use_appearance_embedding",
        "eval_num_rays_per_chunk",
    ),
    "splatfacto": (
        "sh_degree",
        "rasterize_mode",
        "random_init",
        "num_random",
        "refine_every",
        "warmup_length",
        "densify_grad_thresh",
        "densify_size_thresh",
        "cull_alpha_thresh",
        "cull_scale_thresh",
        "n_split_samples",
        "stop_split_at",
        "ssim_lambda",
        "use_absgrad",
        "use_bilateral_grid",
        "num_downscales",
        "resolution_schedule",
    ),
}


def atomic_json(path: Path, value):
    from topic16.contracts import write_json

    write_json(path, value)


def ply_vertices(path: Path) -> int:
    """Bound parsing to the export header; never load the full binary asset."""
    with path.open("rb") as stream:
        header = stream.read(65536).split(b"end_header", 1)
    if len(header) != 2 or not header[0].startswith(b"ply"):
        raise ValueError("Invalid or oversized PLY header")
    match = re.search(rb"(?m)^element vertex (\d+)\r?$", header[0])
    if not match or int(match[1]) < 1:
        raise ValueError("PLY vertex count required")
    return int(match[1])


def prepare(root: Path, settings: dict, extra_matrix: Path | None = None):
    """Fully validate immutable records before publishing an allowlisted index."""
    from PIL import Image, ImageChops
    import yaml

    cache = root / "artifacts/ui"
    assets, scenes, evidence = {}, [], []

    def asset(path: Path, expected=None):
        path = inside(root, path)
        digest = sha256(path)
        if expected and digest != expected:
            raise ValueError(f"Asset checksum mismatch: {relative(root,path)}")
        key = hashlib.sha256((relative(root, path) + digest).encode()).hexdigest()[:32]
        assets[key] = {
            "path": relative(root, path),
            "sha256": digest,
            "bytes": path.stat().st_size,
        }
        return "/api/assets/" + key

    matrices = [
        root / f"artifacts/logs/matrices/topic16-full-{kind}.json"
        for kind in ("custom", "calibration", "benchmark", "poster")
    ]
    if extra_matrix:
        matrices.append(inside(root, extra_matrix))
    seen = set()
    for matrix in matrices:
        for scene_id, pair in read_json(matrix)["pairs"].items():
            if scene_id in seen:
                raise ValueError("Duplicate scene in catalog selection")
            seen.add(scene_id)
            runs = validate_pair(root, pair, primary_only=True)
            title, subtitle, scope = LABELS.get(
                scene_id, (scene_id, "Verified paired scene", "additional")
            )
            scene = {
                "id": scene_id,
                "title": title,
                "subtitle": subtitle,
                "scope": scope,
                "methods": {},
                "views": [],
                "alignment": "shared frozen OpenGL camera frame; no method-specific fit",
                "source_matrix": relative(root, matrix),
            }
            for method, run in zip(("nerfacto", "splatfacto"), runs):
                old = read_json(run["paths"]["logs"] / "settings.json")
                evidence.append(
                    {
                        "run_key": run["manifest"]["run_key"],
                        **assert_experiment_compatible(
                            settings, old, run["provenance"]["settings_hash"]
                        ),
                    }
                )
                export = validate_export(
                    run["paths"]["exports"],
                    run["provenance"]["checkpoint_sha256"],
                    root,
                    old,
                )
                render_records = sorted(
                    (root / "artifacts/videos" / run["manifest"]["run_key"]).glob(
                        "*/render.json"
                    )
                )
                if len(render_records) != 1:
                    raise ValueError("Expected one exact camera-path throughput record")
                render = validate_render(
                    render_records[0].parent,
                    run["provenance"]["checkpoint_sha256"],
                    root,
                    old,
                )
                ply = next(f for f in export["files"] if f["name"].endswith(".ply"))
                vertices = ply_vertices(run["paths"]["exports"] / ply["name"])
                if (
                    vertices > settings["Ui"]["MaxVertices"]
                    or ply["bytes"] > settings["Ui"]["DecodeLimitBytes"]
                ):
                    raise ValueError(
                        f"Export exceeds configured UI decode budget: {scene_id}/{method}"
                    )
                metrics = run["metrics"]["results"]
                generated = yaml.load(
                    run["config"].read_text(encoding="utf-8"), Loader=yaml.BaseLoader
                )
                model = generated["pipeline"]["model"]
                scene["methods"][method] = {
                    "run_key": run["manifest"]["run_key"],
                    "config": relative(root, run["config"]),
                    "checkpoint_sha256": run["provenance"]["checkpoint_sha256"],
                    "split_hash": run["evaluation"]["split_hash"],
                    "asset": asset(
                        run["paths"]["exports"] / ply["name"], ply["sha256"]
                    ),
                    "bytes": ply["bytes"],
                    "vertices": vertices,
                    "kind": (
                        "point-cloud proxy"
                        if method == "nerfacto"
                        else "Gaussian splats · browser renderer"
                    ),
                    "metrics": {k: metrics[k] for k in ("psnr", "ssim", "lpips")},
                    "train_seconds": run["manifest"]["execution_metrics"][
                        "wall_time_seconds"
                    ],
                    "peak_vram_mb": run["manifest"]["execution_metrics"][
                        "peak_vram_mb"
                    ],
                    "offline_fps": render["fps"],
                    "provenance": run["provenance"],
                    "architecture": {
                        key: model[key]
                        for key in ARCHITECTURE_FIELDS[method]
                        if key in model
                    },
                }
            for index, camera in enumerate(runs[0]["split"]["eval"]):
                frames = [r["evaluation"]["frames"][index] for r in runs]
                view = {
                    "index": index,
                    "source": camera["path"],
                    "camera": camera,
                    "gt": asset(
                        runs[0]["paths"]["renders"] / frames[0]["gt"],
                        frames[0]["gt_sha256"],
                    ),
                }
                for method, r, frame in zip(("nerfacto", "splatfacto"), runs, frames):
                    view[method] = asset(
                        r["paths"]["renders"] / frame["pred"], frame["pred_sha256"]
                    )
                    error = (
                        cache
                        / "images"
                        / scene_id.replace(":", "-")
                        / f"{method}-{index:04d}-error-v2.png"
                    )
                    if not error.exists():
                        error.parent.mkdir(parents=True, exist_ok=True)
                        with Image.open(
                            r["paths"]["renders"] / frame["gt"]
                        ) as gt, Image.open(
                            r["paths"]["renders"] / frame["pred"]
                        ) as pred:
                            ImageChops.difference(
                                gt.convert("RGB"), pred.convert("RGB")
                            ).point(lambda value: min(255, value * 4)).save(error)
                    view[method + "_error"] = asset(error)
                scene["views"].append(view)
            cover = cache / "images" / scene_id.replace(":", "-") / "cover.webp"
            cover.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(
                runs[0]["paths"]["renders"] / runs[0]["evaluation"]["frames"][0]["gt"]
            ) as image:
                image.thumbnail((1200, 800))
                image.convert("RGB").save(cover, "WEBP", quality=88)
            scene["cover"] = asset(cover)
            scene["train_count"] = len(runs[0]["split"]["train"])
            scene["eval_count"] = len(scene["views"])
            scene["inference"] = True
            scenes.append(scene)
    report_assets = {}
    report_dir = root / "reports/topic16-full"
    for path in report_dir.rglob("*"):
        if (
            path.is_file()
            and ".venv" not in path.parts
            and path.suffix.lower()
            in (".html", ".png", ".svg", ".css", ".js", ".json", ".md")
        ):
            report_assets[relative(report_dir, path)] = asset(path)
    cases_path = report_dir / "review/case-selection.json"
    catalog = {
        "schema_version": 1,
        "design_version": "1.1",
        "created_at": utc_now(),
        "scenes": scenes,
        "ui": settings["Ui"],
        "report_assets": report_assets,
        "cases": read_json(cases_path) if cases_path.exists() else [],
        "settings_compatibility": evidence,
    }
    catalog["revision"] = hashlib.sha256(
        json.dumps(
            {"scenes": scenes, "ui": ui_settings_hash(settings)}, sort_keys=True
        ).encode()
    ).hexdigest()
    payload = {"catalog": catalog, "assets": assets}
    # One atomic file publishes catalog and index as the same revision.
    atomic_json(cache / "catalog.json", payload)
    return payload


def load_catalog(root):
    data = read_json(root / "artifacts/ui/catalog.json")
    if data["catalog"]["schema_version"] != 1:
        raise ValueError("Unsupported catalog major version; prepare a validated copy")
    return data
