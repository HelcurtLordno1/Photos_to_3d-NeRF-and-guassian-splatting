"""GPU execution with one process at a time and immutable run provenance."""
from __future__ import annotations

from topic16.settings import experiment_settings_hash

import csv
import os
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from topic16.contracts import (
    digest_json, file_required, inside, load_run, read_json, relative, run_paths,
    native_workspace, sha256, utc_now, validate_camera_path, validate_export, validate_metrics, write_json,
)
from topic16.data import freeze_split, prepare_scene, scene_input
from topic16.sessions import SessionPaused, average_eval_metrics, check_stop, stop_requested


@contextmanager
def gpu_lock(root: Path, settings: dict | None = None):
    """OS lock releases on crashes too; a persistent file avoids unlink/open races."""
    import msvcrt
    path = root / "artifacts/logs/gpu.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise RuntimeError("Another Topic16 pipeline job holds the shared lock; wait for it to finish") from error
        try:
            if settings is None:
                yield
            else:
                from topic16.safety import GpuGuard
                with GpuGuard(root, settings):
                    yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def native_output(arguments: list[str], root: Path) -> str:
    return subprocess.check_output(arguments, cwd=root, encoding="utf-8", errors="replace", timeout=30).strip()


def gpu_identity(root: Path) -> dict:
    line = native_output(["nvidia-smi", "--query-gpu=name,uuid,driver_version,memory.total", "--format=csv,noheader,nounits", "--id=0"], root)
    name, uuid, driver, memory = [value.strip() for value in next(csv.reader([line]))]
    return {"gpu_name": name, "driver_version": driver, "uuid": uuid, "total_vram_mb": int(memory)}


def _runtime_snapshots() -> tuple[str, str]:
    """Separate installed packages from setuptools' import-dependent vendor path.

    Older snapshots included the bundled distributions after setuptools added
    its _vendor directory to sys.path. Reconstruct that exact legacy inventory
    from the same installed setuptools, without modifying saved run evidence.
    """
    from importlib.metadata import PackageNotFoundError, distribution, distributions
    try:
        vendor = Path(distribution('setuptools').locate_file('setuptools/_vendor')).resolve()
    except PackageNotFoundError:
        vendor = None
    installed = [f"{d.metadata['Name']}=={d.version}" for d in distributions()
                 if vendor is None or Path(d.locate_file('')).resolve() != vendor]
    bundled = [] if vendor is None else [f"{d.metadata['Name']}=={d.version}"
                                         for d in distributions(path=[str(vendor)])]
    def serialize(items):
        return '\n'.join(sorted(items)) + '\n'
    return serialize(installed), serialize(installed + bundled)


def runtime_snapshot() -> str:
    return _runtime_snapshots()[0]


def validate_runtime_snapshot(expected_sha256: str) -> None:
    installed, legacy = _runtime_snapshots()
    if expected_sha256 not in (digest_json(installed), digest_json(legacy)):
        raise ValueError('Installed dependencies differ from this exact trained model')


def assert_runtime(root: Path, settings: dict) -> None:
    import gsplat
    import nerfstudio
    import torch
    if 'CpuWorkerThreads' in settings:
        torch.set_num_threads(settings['CpuWorkerThreads'])
    source = root / 'third_party/nerfstudio'
    if native_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], root) != settings['NerfstudioCommit']:
        raise ValueError('Nerfstudio checkout differs from pinned commit')
    if native_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=no'], root):
        raise ValueError('Pinned upstream checkout has local modifications')
    if not Path(nerfstudio.__file__).resolve().is_relative_to(source.resolve()):
        raise ValueError('Installed Nerfstudio does not come from this pinned checkout')
    if torch.__version__ != settings['TorchVersion'] or gsplat.__version__ != settings['GsplatVersion']:
        raise ValueError('PyTorch/gsplat versions differ from registry')
    if not torch.cuda.is_available():
        raise ValueError('CUDA unavailable')


@contextmanager
def gpu_monitor(root: Path, destination: Path, interval: int):
    stop = threading.Event()
    failures = []
    header = ("timestamp_utc", "memory.used", "temperature.gpu", "power.draw", "utilization.gpu")
    def sample(stream):
        output = native_output(["nvidia-smi", "--id=0", "--query-gpu=memory.used,temperature.gpu,power.draw,utilization.gpu", "--format=csv,noheader,nounits"], root)
        csv.writer(stream).writerow([utc_now()] + [item.strip() for item in output.split(",")])
        stream.flush()
    def monitor():
        with destination.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerow(header)
            while True:
                try:
                    sample(stream)
                except Exception as error:
                    failures.append(str(error))
                    break
                if stop.wait(interval):
                    try:
                        sample(stream)
                    except Exception as error:
                        failures.append(str(error))
                    break
    worker = threading.Thread(target=monitor, daemon=True)
    worker.start()
    try:
        yield
    finally:
        stop.set()
        worker.join(timeout=30)
        if worker.is_alive():
            raise RuntimeError("GPU telemetry did not stop")
        if failures:
            raise RuntimeError(f"GPU telemetry failed: {failures[0]}")


def peak_vram(path: Path) -> float:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("Missing GPU samples")
    return max(float(row["memory.used"]) for row in rows)


def run_command(root: Path, arguments: list[str], log: Path, *, cooperative_training=False) -> None:
    """Stream output to an immediately flushed log, preserving native exit status."""
    environment = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        from topic16.safety import assert_safe, current_guard, stop_process_tree
        assert_safe()
        guard = current_guard()
        if guard:
            environment['OMP_NUM_THREADS'] = str(guard.settings['CpuWorkerThreads'])
            environment['MKL_NUM_THREADS'] = str(guard.settings['CpuWorkerThreads'])
        process = subprocess.Popen(arguments, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   encoding="utf-8", errors="replace", env=environment)
        if guard:
            guard.child = process
        request_stop = threading.Event()
        stopped = threading.Event()
        def watch_stop():
            while not request_stop.wait(0.5):
                if stop_requested():
                    stopped.set()
                    stop_process_tree(process)
                    return
        watcher = None
        if not cooperative_training:
            watcher = threading.Thread(target=watch_stop, daemon=True)
            watcher.start()
        try:
            assert process.stdout is not None
            for line in process.stdout:
                assert_safe()
                stream.write(line)
                stream.flush()
                print(line, end="", flush=True)
            code = process.wait()
            assert_safe()
            if code == 75 or stopped.is_set():
                raise SessionPaused('Training checkpoint committed' if code == 75 else 'Stage stopped by request')
            if code != 0:
                raise RuntimeError(f"Command exited {process.returncode}; see {relative(root, log)}")
        finally:
            request_stop.set()
            if watcher:
                watcher.join(timeout=6)
            if process.poll() is None:
                stop_process_tree(process)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if guard:
                guard.child = None


def write_training_manifest(root: Path, paths: dict, manifest: dict) -> None:
    # P1 owns the schema validator and atomic lifecycle writer; keep using that contract.
    source = paths["logs"] / ".manifest-input.json"
    write_json(source, manifest)
    try:
        subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(root / "scripts/Write-RunManifest.ps1"), "-InputPath", str(source)], check=True, cwd=root)
    finally:
        source.unlink(missing_ok=True)


def validate_generated_config(path: Path, run_directory: Path, data_directory: Path,
                              method: str, iterations: int, seed: int, settings: dict, resume_checkpoint=None) -> None:
    """Port the useful checks from the former Run.ps1 into the runtime owner."""
    import yaml
    config = yaml.load(path.read_text(encoding='utf-8'), Loader=yaml.Loader)
    parser = config.pipeline.datamanager.dataparser
    expected = (config.method_name == method and config.max_num_iterations == iterations
                and config.machine.seed == seed and config.machine.num_devices == 1
                and config.machine.num_machines == 1 and config.vis == 'tensorboard'
                and config.save_only_latest_checkpoint and config.load_dir is None
                and config.load_checkpoint == resume_checkpoint and config.load_step is None
                and config.get_base_dir().resolve() == run_directory.resolve()
                and config.get_checkpoint_dir().resolve() == (run_directory / 'nerfstudio_models').resolve()
                and parser.data.resolve() == data_directory.resolve()
                and parser.downscale_factor == settings['DownscaleFactor']
                and type(parser).__name__ == 'NerfstudioDataParserConfig'
                and parser.eval_mode in ('interval', 'filename'))
    if not expected:
        raise ValueError('Generated training config differs from the recorded single-GPU protocol')


def train(root: Path, settings: dict, method: str, scene: str, iterations: int | None = None,
          seed: int | None = None, protocol_id: str = "primary", resume_config: Path | None = None) -> Path:
    import re
    iterations = settings["TrainIterations"] if iterations is None else iterations
    seed = settings["RandomSeed"] if seed is None else seed
    if iterations < 1:
        raise ValueError("Iterations must be positive")
    if protocol_id not in ("primary", "diagnostic", "repeat"):
        raise ValueError("Protocol must be primary, diagnostic or repeat")
    if protocol_id == "primary" and (iterations != settings["TrainIterations"] or seed != settings["RandomSeed"]):
        raise ValueError("Primary protocol cannot silently override iterations or seed")
    if protocol_id == "repeat" and (iterations != settings["TrainIterations"] or seed not in (43, 44)):
        raise ValueError("Repeat protocol is full iterations with seed 43 or 44")
    check_stop()
    with gpu_lock(root, settings):
        assert_runtime(root, settings)
        prepare_scene(root, scene, settings)
        split = freeze_split(root, scene, settings)
        parent = None
        if resume_config is not None:
            from topic16.sessions import resume_source
            parent = resume_source(root, resume_config, settings, split, method, scene, iterations, seed, protocol_id)
            validate_runtime_snapshot(parent['provenance']['runtime_sha256'])
        hardware = gpu_identity(root)
        if parent and hardware != parent['provenance']['gpu']:
            raise ValueError('Resume GPU/driver identity changed')
        if protocol_id in ("primary", "repeat") and ("A4500" not in hardware["gpu_name"] or hardware["total_vram_mb"] < 16000):
            raise ValueError("Primary/repeat results require the target A4500 16 GB")
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")[:-3] + "Z"
        key = f"{scene.replace(':', '-')}/{method}/{run_id}"
        paths = run_paths(root, key)
        paths["runs"].mkdir(parents=True, exist_ok=False)
        paths["logs"].mkdir(parents=True, exist_ok=False)
        data_dir, parser, mode = scene_input(native_workspace(root), scene)
        worker_entry = 'import sys; sys.path.insert(0, sys.argv.pop(1)); from topic16.training_worker import entrypoint; entrypoint()'
        arguments = [sys.executable, "-c", worker_entry, str(root / 'src'), method,
                     "--output-dir", str(native_workspace(root) / "artifacts/runs"), "--experiment-name", scene.replace(":", "-"),
                     "--timestamp", run_id, "--max-num-iterations", str(iterations), "--machine.seed", str(seed),
                     "--steps-per-save", str(settings['TrainCheckpointInterval']),
                     "--vis", "tensorboard"]
        if parent:
            arguments += ['--load-checkpoint', str(parent['checkpoint'])]
        arguments += [parser, "--data", str(data_dir),
                     "--downscale-factor", str(settings["DownscaleFactor"]), "--eval-mode", mode]
        if parser == "colmap":
            arguments += ["--colmap-path", "sparse/0"]
        if mode == "interval":
            arguments += ["--eval-interval", str(settings["EvalInterval"])]
        command = subprocess.list2cmdline(arguments)
        (paths["logs"] / "command.txt").write_text(command + "\n", encoding="utf-8")
        write_json(paths["logs"] / "split.json", split)
        write_json(paths["logs"] / "settings.json", settings)
        commit = native_output(["git", "rev-parse", "HEAD"], root)
        git_status = native_output(["git", "status", "--porcelain"], root)
        diff = native_output(["git", "diff", "HEAD", "--", "scripts", "src", "configs"], root)
        # Include newly created source files, which git diff alone cannot see.
        source_hashes = {relative(root, p): sha256(p) for folder in ("src", "scripts", "configs")
                         for p in sorted((root / folder).rglob("*")) if p.suffix in (".py", ".ps1", ".psd1", ".json")}
        if parent and source_hashes != parent['provenance']['source_files']:
            raise ValueError('Resume project source changed; preserve the checkpoint and use the recorded source snapshot')
        import zipfile
        with zipfile.ZipFile(paths['logs'] / 'source.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name in source_hashes:
                archive.write(inside(root, name), arcname=name)
        provenance = {"protocol_id": protocol_id, "git_commit": commit, "git_dirty": bool(git_status),
                      "git_diff_sha256": digest_json({"diff": diff, "sources": source_hashes}),
                      'source_files': source_hashes, 'source_archive_sha256': sha256(paths['logs'] / 'source.zip'),
                      "settings_hash": experiment_settings_hash(settings), "gpu": hardware,
                      "runtime_sha256": digest_json(runtime_snapshot())}
        from topic16.safety import assert_safe, current_guard
        provenance['gpu_safety_path'] = relative(root, current_guard().path)
        if parent:
            provenance['resumed_from'] = {'run_key': parent['run_key'], 'checkpoint': relative(root, parent['checkpoint']),
                'checkpoint_sha256': parent['record']['checkpoint_sha256'], 'step': parent['step'],
                'evidence': [{'path': relative(root, path), 'sha256': sha256(path)}
                    for path in sorted(parent['paths']['logs'].glob('*')) if path.is_file()]}
        write_json(paths['logs'] / 'provenance.json', provenance)
        session_directory = os.environ.get('TOPIC16_SESSION_DIRECTORY')
        if session_directory:
            write_json(Path(session_directory) / 'active-run.json', {'run_key': key,
                'config': relative(root, paths['runs'] / 'config.yml'),
                'resume_record': relative(root, paths['logs'] / 'resume.json')})
        os.environ['TOPIC16_WORKSPACE'] = str(root)
        (paths["logs"] / "git-status.txt").write_text(git_status, encoding="utf-8")
        (paths["logs"] / "git-diff.txt").write_text(diff, encoding="utf-8")
        (paths["logs"] / "requirements.txt").write_text(runtime_snapshot(), encoding="utf-8")
        (paths["logs"] / "nvidia-smi.txt").write_text(native_output(["nvidia-smi", "-q"], root), encoding="utf-8")
        (paths["logs"] / "run.env").write_text(f"method={method}\ndataset={scene}\nprotocol={protocol_id}\niterations={iterations}\nseed={seed}\n", encoding="utf-8")
        started = utc_now()
        manifest = {"schema_version": "1.0", "run_key": key, "scene": scene, "method": method,
                    "status": "running", "started_at": started,
                    "provenance": {"git_commit_sha": commit, "dataset_split_hash": digest_json(split)},
                    "hardware": {"gpu_name": hardware["gpu_name"], "driver_version": hardware["driver_version"]},
                    "protocol": {"iterations": iterations, "downscale_factor": settings["DownscaleFactor"],
                                 "seed": seed, "eval_interval": settings["EvalInterval"]}}
        write_training_manifest(root, paths, manifest)
        start_clock = time.perf_counter()
        exit_code = 1
        try:
            with gpu_monitor(root, paths["logs"] / "gpu.csv", settings["GpuSampleSeconds"]):
                run_command(root, arguments, paths["logs"] / "train.log", cooperative_training=True)
            config = file_required(paths["runs"] / "config.yml")
            validate_generated_config(config, paths['runs'], data_dir, method, iterations, seed, settings,
                                      parent['checkpoint'] if parent else None)
            checkpoints = sorted((paths["runs"] / "nerfstudio_models").glob("step-*.ckpt"))
            if not checkpoints:
                raise ValueError("Training exited successfully without a checkpoint")
            checkpoint = file_required(checkpoints[-1])
            if int(checkpoint.stem.split("-")[-1]) != iterations - 1:
                raise ValueError("Checkpoint does not represent the requested final iteration")
            log_text = (paths["logs"] / "train.log").read_text(encoding="utf-8")
            if re.search(r"(?i)(?:loss|psnr)[^\n]{0,60}\b(?:nan|inf)\b|out of memory", log_text):
                raise ValueError("Training log contains non-finite loss or OOM")
            provenance.update(config_sha256=sha256(config), checkpoint_sha256=sha256(checkpoint),
                              checkpoint_path=relative(root, checkpoint), checkpoint_bytes=checkpoint.stat().st_size)
            write_json(paths["logs"] / "provenance.json", provenance)
            manifest.update(status="succeeded", finished_at=utc_now(),
                            execution_metrics={"wall_time_seconds": time.perf_counter() - start_clock,
                                               "peak_vram_mb": peak_vram(paths["logs"] / "gpu.csv")},
                            artifacts={"config_path": relative(root, config),
                                       "checkpoint_dir": relative(root, checkpoint.parent)})
            if parent:
                previous = read_json(parent['paths']['logs'] / 'segments.json')
                manifest['execution_metrics']['wall_time_seconds'] += previous['wall_time_seconds']
                manifest['execution_metrics']['peak_vram_mb'] = max(manifest['execution_metrics']['peak_vram_mb'], previous['peak_vram_mb'])
            assert_safe()
            write_training_manifest(root, paths, manifest)
            exit_code = 0
            print(f"Training complete: {config}")
            return config
        except BaseException as error:
            manifest.update(status="failed", finished_at=utc_now(), failure_reason=str(error) or type(error).__name__)
            write_json(paths["logs"] / "provenance.json", provenance)
            write_training_manifest(root, paths, manifest)
            if isinstance(error, SessionPaused):
                error.config = paths['runs'] / 'config.yml'
            raise
        finally:
            elapsed = time.perf_counter() - start_clock
            previous = read_json(parent['paths']['logs'] / 'segments.json') if parent else {'wall_time_seconds': 0, 'peak_vram_mb': 0}
            write_json(paths['logs'] / 'segments.json', {'wall_time_seconds': previous['wall_time_seconds'] + elapsed,
                'peak_vram_mb': max(previous['peak_vram_mb'], peak_vram(paths['logs'] / 'gpu.csv'))})
            (paths["logs"] / "timing.env").write_text(
                f"start_utc={started}\nend_utc={utc_now()}\nelapsed_seconds={time.perf_counter()-start_clock:.6f}\nexit_code={exit_code}\n", encoding="utf-8")


def load_pipeline(root: Path, run: dict):
    """Use eval_setup's documented callback to pin the checksum-verified checkpoint."""
    import torch
    from nerfstudio.utils.eval_utils import eval_setup
    assert_runtime(root, read_json(run['paths']['logs'] / 'settings.json'))
    validate_runtime_snapshot(run['provenance']['runtime_sha256'])
    if not torch.cuda.is_available():
        raise ValueError("CUDA is unavailable")
    def configure(config):
        parts = run["manifest"]["run_key"].split('/')
        if config.method_name != parts[1] or config.experiment_name != parts[0] or config.timestamp != parts[2]:
            raise ValueError("Generated config points to a different run")
        protocol = run['manifest']['protocol']
        parser = config.pipeline.datamanager.dataparser
        if config.max_num_iterations != protocol['iterations'] or config.machine.seed != protocol['seed']:
            raise ValueError('Generated config has different iteration budget/seed')
        if parser.downscale_factor != protocol['downscale_factor']:
            raise ValueError('Generated config has different image downscale')
        if config.machine.num_devices != 1 or config.machine.num_machines != 1:
            raise ValueError('Run must use one GPU on one machine')
        # Relocate only known paths when artifacts are transferred to another checkout.
        # Serialized config/checkpoint bytes stay immutable; poses and model settings stay exact.
        directory = native_workspace(root) / Path(run['split']['train'][0]['path']).parent.parent
        mode = 'filename' if run['manifest']['scene'].startswith('custom:') else 'interval'
        if parser.eval_mode != mode or (mode == 'interval' and parser.eval_interval != protocol['eval_interval']):
            raise ValueError('Generated config uses a different evaluation split')
        config.output_dir = native_workspace(root) / 'artifacts/runs'
        config.pipeline.datamanager.data = directory
        parser.data = directory
        config.load_step = int(run["checkpoint"].stem.split("-")[-1])
        return config
    config, pipeline, checkpoint, step = eval_setup(run["config"], test_mode="test", update_config_callback=configure)
    if checkpoint.resolve() != run["checkpoint"].resolve():
        raise ValueError("Upstream loaded a different checkpoint")
    pipeline.eval()
    return config, pipeline, step


def close_pipeline(pipeline) -> None:
    """Close upstream worker processes before Python tears down multiprocessing modules."""
    import gc
    import torch
    manager = pipeline.datamanager
    if hasattr(manager, 'data_procs'):
        for process in manager.data_procs:
            if process.is_alive():
                process.terminate()
            process.join(timeout=15)
            if process.is_alive():
                process.kill()
                process.join(timeout=5)
        manager.data_procs = []
    pipeline.to('cpu')
    gc.collect()
    torch.cuda.empty_cache()


def validate_loaded_split(root: Path, run: dict, pipeline) -> None:
    import torch
    for item in run['split'].get('pose_files', []):
        if sha256(file_required(inside(root, item['path']))) != item['sha256']:
            raise ValueError('Pose/sparse metadata changed after training')
    for label, dataset in (("train", pipeline.datamanager.train_dataset), ("eval", pipeline.datamanager.eval_dataset)):
        expected = run["split"][label]
        actual = [relative(root, path) for path in dataset.image_filenames]
        if actual != [frame["path"] for frame in expected]:
            raise ValueError(f"Loaded {label} split differs from frozen cameras")
        for index, frame in enumerate(expected):
            if sha256(inside(root, frame["path"])) != frame["sha256"]:
                raise ValueError("Dataset image changed after training")
            cameras = dataset.cameras
            if not torch.allclose(cameras.camera_to_worlds[index].cpu(), torch.tensor(frame["camera_to_world"]), atol=1e-6, rtol=1e-6):
                raise ValueError("Camera pose changed after training")
            for key in ("width", "height", "fx", "fy", "cx", "cy"):
                if abs(float(getattr(cameras, key)[index].item()) - frame[key]) > 1e-5:
                    raise ValueError(f"Camera {key} changed after training")
            if 'camera_type' in frame and int(cameras.camera_type[index].item()) != frame['camera_type']:
                raise ValueError('Camera model changed after training')
            if 'distortion_params' in frame:
                actual_distortion = cameras.distortion_params[index].tolist() if cameras.distortion_params is not None else []
                if actual_distortion != frame['distortion_params']:
                    raise ValueError('Camera distortion changed after training')


def evaluate(root: Path, settings: dict, config_path: Path) -> dict:
    import torch
    from PIL import Image
    check_stop()
    with gpu_lock(root, settings):
        run = load_run(root, config_path)
        paths = run["paths"]
        destination = paths["metrics"] / "evaluation.json"
        if destination.exists() and read_json(destination)["status"] == "succeeded":
            return load_run(root, config_path, require_eval=True)["evaluation"]
        paths["metrics"].mkdir(parents=True, exist_ok=True)
        paths["renders"].mkdir(parents=True, exist_ok=True)
        record = {"schema_version": "1.0", "status": "running", "run_key": run["manifest"]["run_key"], "started_at": utc_now()}
        from topic16.safety import current_guard
        record['gpu_safety_path'] = relative(root, current_guard().path)
        write_json(destination, record)
        pipeline = None
        try:
            config, pipeline, _ = load_pipeline(root, run)
            validate_loaded_split(root, run, pipeline)
            with torch.no_grad():
                results = average_eval_metrics(pipeline, output_path=paths["renders"], get_std=True)
            metrics = {"experiment_name": config.experiment_name, "method_name": config.method_name,
                       "checkpoint": relative(root, run["checkpoint"]), "results": results}
            validate_metrics(metrics)
            expected = run["split"]["eval"]
            images = sorted(paths["renders"].glob("eval_img_*.png"))
            if [p.name for p in images] != [f"eval_img_{i:04d}.png" for i in range(len(expected))]:
                raise ValueError("Held-out render count/index mismatch")
            frames = []
            for index, (path, frame) in enumerate(zip(images, expected)):
                with Image.open(path) as image:
                    if image.size != (2 * frame["width"], frame["height"]):
                        raise ValueError("Upstream GT/pred combined image has incorrect dimensions")
                    width = frame["width"]
                    gt, pred = paths["renders"] / f"gt_{index:04d}.png", paths["renders"] / f"pred_{index:04d}.png"
                    image.crop((0, 0, width, frame["height"])).save(gt)
                    image.crop((width, 0, width * 2, frame["height"])).save(pred)
                frames.append({"source": frame["path"], "gt": gt.name, "pred": pred.name,
                               "gt_sha256": sha256(gt), "pred_sha256": sha256(pred)})
            write_json(paths["metrics"] / "metrics.json", metrics)
            record.update(status="succeeded", finished_at=utc_now(), frames=frames,
                          split_hash=digest_json(run["split"]), config_sha256=run["provenance"]["config_sha256"],
                          checkpoint_sha256=run["provenance"]["checkpoint_sha256"],
                          metrics_sha256=sha256(paths["metrics"] / "metrics.json"),
                          checkpoint_bytes=run["checkpoint"].stat().st_size,
                          run_bytes=sum(path.stat().st_size for path in paths["runs"].rglob("*") if path.is_file()))
            write_json(destination, record)
            print(f"Held-out evaluation PASS: {destination}")
            return record
        except BaseException as error:
            record.update(status="failed", finished_at=utc_now(), failure_reason=str(error))
            write_json(destination, record)
            raise
        finally:
            if pipeline is not None:
                close_pipeline(pipeline)


def render(root: Path, settings: dict, config_path: Path, camera_path: Path | None = None) -> dict:
    """Measure GPU execution after warm-up; image encoding/file IO is outside timing."""
    import torch
    from PIL import Image
    check_stop()
    with gpu_lock(root, settings):
        run = load_run(root, config_path, require_eval=True)
        _, pipeline, _ = load_pipeline(root, run)
        try:
            validate_loaded_split(root, run, pipeline)
            if camera_path is None:
                cameras = pipeline.datamanager.eval_dataset.cameras.to(pipeline.device)
                camera_hash = digest_json(run["split"]["eval"])
            else:
                from nerfstudio.cameras.camera_paths import get_path_from_json
                document = read_json(file_required(camera_path))
                validate_camera_path(document)
                cameras = get_path_from_json(document).to(pipeline.device)
                camera_hash = sha256(camera_path)
            count = len(cameras)
            output = run["paths"]["videos"] / camera_hash[:16]
            if output.exists() and not (output / 'render.json').exists():
                pause_record = output / 'paused.json'
                if pause_record.exists():
                    archive = output.parent / '.attempts' / (output.name + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
                    archive.parent.mkdir(exist_ok=True)
                    output.rename(archive)
            if output.exists():
                from topic16.contracts import validate_render
                record = validate_render(output, run['provenance']['checkpoint_sha256'], root, settings)
                if (record['camera_sha256'] != camera_hash or record['warmup_frames'] != settings['RenderWarmupFrames']
                        or len(record['durations_seconds']) != settings['RenderRepeats']):
                    raise ValueError('Existing render has a different measurement protocol')
                if camera_path is not None and not (output / 'video.mp4').is_file():
                    raise ValueError('Completed camera-path render is missing its video')
                return record
            output.mkdir(parents=True)
            with torch.no_grad(), gpu_monitor(root, output / "gpu.csv", settings["GpuSampleSeconds"]):
                for index in range(settings["RenderWarmupFrames"]):
                    check_stop()
                    pipeline.model.get_outputs_for_camera(cameras[index % count:index % count + 1])
                torch.cuda.synchronize()
                durations = []
                for _ in range(settings["RenderRepeats"]):
                    start = time.perf_counter()
                    for index in range(count):
                        check_stop()
                        pipeline.model.get_outputs_for_camera(cameras[index:index + 1])
                        torch.cuda.synchronize()
                    durations.append(time.perf_counter() - start)
                for index in range(count):
                    check_stop()
                    rgb = pipeline.model.get_outputs_for_camera(cameras[index:index + 1])["rgb"]
                    Image.fromarray((rgb.clamp(0, 1).detach().cpu().numpy() * 255).round().astype("uint8")).save(output / f"frame_{index:04d}.png")
            record = {"schema_version": "1.0", "run_key": run["manifest"]["run_key"], "camera_sha256": camera_hash,
                      'status': 'succeeded',
                      "frame_count": count, "warmup_frames": settings["RenderWarmupFrames"],
                      "durations_seconds": durations, "fps": count * len(durations) / sum(durations),
                      "widths": cameras.width.flatten().tolist(), "heights": cameras.height.flatten().tolist(),
                      "peak_vram_mb": peak_vram(output / "gpu.csv"), "includes_image_io": False,
                      "checkpoint_sha256": run["provenance"]["checkpoint_sha256"],
                      'frames': [{'name': path.name, 'sha256': sha256(path)} for path in sorted(output.glob('frame_*.png'))]}
            if camera_path is not None:
                write_json(output / "camera_path.json", read_json(camera_path))
                fps = document.get("fps", 24)
                run_command(root, ["ffmpeg", "-n", "-framerate", str(fps), "-i", str(output / "frame_%04d.png"),
                                   "-c:v", "libx264", '-threads', str(settings['CpuWorkerThreads']),
                                   "-pix_fmt", "yuv420p", str(output / "video.mp4")], output / "ffmpeg.log")
                record['video_sha256'] = sha256(output / 'video.mp4')
            from topic16.safety import assert_safe, current_guard
            assert_safe()
            record['gpu_safety_path'] = relative(root, current_guard().path)
            write_json(output / "render.json", record)
            print(f"Offline render PASS: {output / 'render.json'}")
            return record
        except SessionPaused:
            if 'output' in locals() and output.exists() and not (output / 'render.json').exists():
                write_json(output / 'paused.json', {'status': 'paused', 'reason': 'Rerun timed measurement on resume; partial durations are excluded'})
            raise
        finally:
            close_pipeline(pipeline)


def export(root: Path, settings: dict, config_path: Path) -> Path:
    check_stop()
    with gpu_lock(root, settings):
        run = load_run(root, config_path, require_eval=True)
        destination = run["paths"]["exports"]
        if (destination / 'paused.json').exists():
            archive = destination.parent / '.attempts' / (destination.name + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
            archive.parent.mkdir(exist_ok=True)
            destination.rename(archive)
        if destination.exists():
            validate_export(destination, run['provenance']['checkpoint_sha256'], root, settings)
            return destination
        command = "gaussian-splat" if run["manifest"]["method"] == "splatfacto" else "pointcloud"
        arguments = [sys.executable, "-c", "from nerfstudio.scripts.exporter import entrypoint; entrypoint()",
                     command, "--load-config", str(run["config"]), "--output-dir",
                     str(native_workspace(root) / "artifacts/exports" / run["manifest"]["run_key"])]
        if command == 'pointcloud':
            # Default Nerfacto does not predict normals; the exporter default requires them.
            arguments += ['--normal-method', 'open3d']
        try:
            run_command(root, arguments, run["paths"]["logs"] / "export.log")
        except SessionPaused:
            destination.mkdir(parents=True, exist_ok=True)
            write_json(destination / 'paused.json', {'status': 'paused', 'reason': 'Resume reruns export from the exact completed model'})
            raise
        outputs = list(destination.glob("*.ply"))
        if not outputs:
            raise ValueError("Exporter returned no PLY")
        from topic16.safety import current_guard
        write_json(destination / "export.json", {"run_key": run["manifest"]["run_key"], "format": command,
                   'gpu_safety_path': relative(root, current_guard().path),
                   "checkpoint_sha256": run["provenance"]["checkpoint_sha256"],
                   "files": [{"name": p.name, "bytes": file_required(p).stat().st_size, "sha256": sha256(p)} for p in outputs]})
        print(f'Export PASS: {destination}')
        return destination
