"""One owned CUDA process, two exact checkpoints, one immutable camera request."""

from __future__ import annotations
import json
import sys
import time
from pathlib import Path
from .catalog import atomic_json


def execute(request_path):
    from topic16.contracts import load_run, read_json, sha256
    from topic16.settings import assert_experiment_compatible
    from topic16.runtime import (
        gpu_lock,
        load_pipeline,
        close_pipeline,
        validate_loaded_split,
    )

    request_path = Path(request_path)
    folder = request_path.parent
    request = read_json(request_path)
    root = Path(request["root"])
    settings = request["settings"]
    record = request["record"]
    pipeline = None

    def check():
        if (folder / "cancel").exists():
            raise InterruptedError("Cancelled by owner or lease expiry")

    def status(phase):
        record.update(status="running", phase=phase)
        atomic_json(folder / "status.json", record)

    try:
        check()
        with gpu_lock(root, settings):
            from topic16.safety import current_guard
            from topic16.contracts import relative

            record["gpu_safety_path"] = relative(root, current_guard().path)
            import torch
            from PIL import Image
            from nerfstudio.cameras.cameras import Cameras, CameraType

            results = {}
            for method in record["methods"]:
                check()
                status("verify " + method)
                run = load_run(
                    root, root / request["configs"][method], require_eval=True
                )
                assert_experiment_compatible(
                    settings,
                    read_json(run["paths"]["logs"] / "settings.json"),
                    run["provenance"]["settings_hash"],
                )
                status("load " + method)
                _, pipeline, _ = load_pipeline(root, run)
                check()
                validate_loaded_split(root, run, pipeline)
                c = record["camera"]
                camera = Cameras(
                    camera_to_worlds=torch.tensor(
                        [c["camera_to_world"]], dtype=torch.float32
                    ),
                    fx=float(c["fx"]),
                    fy=float(c["fy"]),
                    cx=float(c["cx"]),
                    cy=float(c["cy"]),
                    width=c["width"],
                    height=c["height"],
                    camera_type=CameraType.PERSPECTIVE,
                ).to(pipeline.device)
                status("render " + method)
                torch.cuda.synchronize()
                started = time.perf_counter()
                with torch.no_grad():
                    if method == "splatfacto":
                        output = pipeline.model.get_outputs_for_camera(camera)["rgb"]
                    else:
                        output = pipeline.model.get_outputs_for_camera_ray_bundle(
                            camera.generate_rays(camera_indices=0)
                        )["rgb"]
                torch.cuda.synchronize()
                duration = time.perf_counter() - started
                check()
                name = method + ".png"
                Image.fromarray(
                    (output.clamp(0, 1).cpu().numpy() * 255).round().astype("uint8")
                ).save(folder / name)
                results[method] = {
                    "image": "/api/jobs/" + record["id"] + "/image/" + method,
                    "sha256": sha256(folder / name),
                    "seconds": duration,
                    "checkpoint_sha256": run["provenance"]["checkpoint_sha256"],
                    "config_sha256": run["provenance"]["config_sha256"],
                    "run_key": run["manifest"]["run_key"],
                }
                close_pipeline(pipeline)
                pipeline = None
            check()
        check()
        # Publish after every method AND the guard's final check succeed.
        record.update(
            status="succeeded",
            phase="complete",
            results=results,
            finished_at=time.time(),
        )
        atomic_json(folder / "status.json", record)
    except BaseException as error:
        record.update(
            status="cancelled" if isinstance(error, InterruptedError) else "failed",
            error=str(error),
            finished_at=time.time(),
        )
        atomic_json(folder / "status.json", record)
    finally:
        if pipeline is not None:
            close_pipeline(pipeline)


if __name__ == "__main__":
    execute(sys.argv[1])
