from topic16.settings import experiment_settings_hash
"""Sequential matrices with explicit attempts and resume at run boundaries."""
from pathlib import Path

from topic16.contracts import METHODS, digest_json, inside, load_run, read_json, relative, utc_now, validate_pair, write_json
from topic16.sessions import SessionPaused, check_stop


def benchmark(root: Path, settings: dict, scenes: list[str], matrix_path: Path,
              resume=False, iterations=None, seed=None, protocol_id="primary") -> dict:
    from topic16.runtime import evaluate, train
    if len(set(scenes)) != len(scenes):
        raise ValueError("Scene list contains duplicates")
    protocol = {"id": protocol_id, "iterations": settings["TrainIterations"] if iterations is None else iterations,
                "seed": settings["RandomSeed"] if seed is None else seed, "settings_hash": experiment_settings_hash(settings)}
    matrix_path = inside(root / "artifacts/logs/matrices", matrix_path)
    if matrix_path.exists():
        if not resume:
            raise ValueError("Matrix exists; use -Resume with its explicit path")
        matrix = read_json(matrix_path)
        if matrix["scenes"] != scenes or matrix["protocol"] != protocol:
            raise ValueError("Cannot resume with different scenes or protocol")
    else:
        if resume:
            raise ValueError("Resume requires an existing explicit matrix")
        matrix = {"schema_version": "1.0", "status": "running", "created_at": utc_now(),
                  "scenes": scenes, "protocol": protocol, "pairs": {}, "attempts": []}
        write_json(matrix_path, matrix)
    try:
        for scene in scenes:
            check_stop()
            pair = matrix["pairs"].setdefault(scene, {"scene": scene, "status": "running", "runs": {}})
            if pair["status"] == "succeeded":
                validate_pair(root, pair)
                continue
            for method in METHODS:
                config = None
                if method in pair["runs"]:
                    config = inside(root, pair["runs"][method])
                    load_run(root, config)
                if config is None:
                    paused = pair.get('paused', {}).get(method)
                    try:
                        if paused:
                            config = train(root, settings, method, scene, iterations, seed, protocol_id, inside(root, paused))
                        else:
                            config = train(root, settings, method, scene, iterations, seed, protocol_id)
                    except SessionPaused as error:
                        if error.config:
                            pair.setdefault('paused', {})[method] = relative(root, error.config)
                            write_json(matrix_path, matrix)
                        raise
                    pair["runs"][method] = relative(root, config)
                    matrix["attempts"].append({"scene": scene, "method": method, "config": relative(root, config)})
                    write_json(matrix_path, matrix)
                evaluate(root, settings, config)
                write_json(matrix_path, matrix)
            pair["status"] = "succeeded"
            validate_pair(root, pair)
            write_json(matrix_path, matrix)
        matrix.update(status="succeeded", finished_at=utc_now())
        matrix.pop("failure_reason", None)
    except SessionPaused as error:
        matrix.update(status='paused', failure_reason=str(error), finished_at=utc_now())
        raise
    except BaseException as error:
        matrix.update(status="failed", failure_reason=str(error), finished_at=utc_now())
        raise
    finally:
        write_json(matrix_path, matrix)
    print(f"Paired matrix PASS: {matrix_path}")
    return matrix
