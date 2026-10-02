"""Internal dispatcher; public entrypoints are native Windows PowerShell scripts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from topic16.contracts import METHODS, native_workspace, read_json, utc_now, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--settings", type=Path, required=True)
    commands = parser.add_subparsers(dest="task", required=True)
    commands.add_parser('safety-check')
    commands.add_parser('runtime-check')
    watch = commands.add_parser('session-watch')
    watch.add_argument('--directory', type=Path, required=True)
    video = commands.add_parser('extract-video')
    video.add_argument('--video', type=Path, required=True)
    video.add_argument('--scene', required=True)
    video.add_argument('--frames', type=int)
    training = commands.add_parser("train")
    training.add_argument("--method", choices=METHODS, required=True)
    training.add_argument("--scene", required=True)
    training.add_argument("--iterations", type=int)
    training.add_argument("--seed", type=int)
    training.add_argument("--protocol", default="primary", choices=("primary", "diagnostic", "repeat"))
    training.add_argument("--result", type=Path)
    training.add_argument('--resume-config', type=Path)
    for name in ("evaluate", "render", "export"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        if name == "render":
            command.add_argument("--camera-path", type=Path)
    audit = commands.add_parser('audit-run')
    audit.add_argument('--config', type=Path, required=True)
    audit.add_argument('--require-evaluation', action='store_true')
    camera_path = commands.add_parser('camera-path')
    camera_path.add_argument('--config', type=Path, required=True)
    camera_path.add_argument('--output', type=Path, required=True)
    matrix = commands.add_parser("benchmark")
    matrix.add_argument("--scenes", nargs="+", required=True)
    matrix.add_argument("--matrix", type=Path, required=True)
    matrix.add_argument("--resume", action="store_true")
    matrix.add_argument("--iterations", type=int)
    matrix.add_argument("--seed", type=int)
    matrix.add_argument("--protocol", default="primary", choices=("primary", "diagnostic", "repeat"))
    capture = commands.add_parser("capture")
    capture.add_argument("--scene", required=True)
    capture.add_argument("--train", type=Path, required=True)
    capture.add_argument("--eval", type=Path, required=True)
    capture.add_argument('--cpu-only', action='store_true')
    capture.add_argument('--recover', action='store_true')
    colmap = commands.add_parser('colmap', add_help=False)
    colmap.add_argument('--log-dir', type=Path, required=True)
    colmap.add_argument('arguments', nargs=argparse.REMAINDER)
    approval = commands.add_parser("approve-capture")
    approval.add_argument("--scene", required=True)
    approval.add_argument("--reviewer", required=True)
    approval.add_argument("--notes", required=True)
    review_capture = commands.add_parser('review-capture')
    review_capture.add_argument('--scene', required=True)
    review_capture.add_argument('--verify-only', action='store_true')
    preparation = commands.add_parser('prepare')
    preparation.add_argument('--scene', required=True)
    analysis = commands.add_parser("analyze")
    analysis.add_argument("--matrices", nargs="+", type=Path, required=True)
    analysis.add_argument("--output", type=Path, required=True)
    analysis.add_argument("--review", type=Path)
    analysis.add_argument('--protocol', default='primary', choices=('primary', 'diagnostic', 'repeat'))
    selection = commands.add_parser("select-model")
    selection.add_argument("--config", type=Path, required=True)
    selection.add_argument("--gate", type=Path, required=True)
    selection.add_argument("--output", type=Path, required=True)
    selection.add_argument("--camera-path", type=Path, required=True)
    demo = commands.add_parser("demo")
    demo.add_argument("--model", type=Path, required=True)
    demo.add_argument("--health-only", action="store_true")
    demo.add_argument("--fallback", action="store_true")
    release = commands.add_parser("release")
    release.add_argument("--model", type=Path, required=True)
    release.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, settings = args.root.resolve(), read_json(args.settings)
    import os
    for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
        os.environ[name] = str(settings['CpuWorkerThreads'])
    if args.task == 'session-watch':
        from topic16.sessions import watch_session
        watch_session(args.directory)
    elif args.task == 'colmap':
        from topic16.data import cpu_colmap_arguments
        from topic16.runtime import run_command
        arguments = cpu_colmap_arguments(args.arguments, settings['CpuWorkerThreads'])
        run_command(root, ['colmap'] + arguments, args.log_dir / ('colmap-' + arguments[0].lstrip('-') + '.log'))
    elif args.task == 'runtime-check':
        from topic16.runtime import assert_runtime, gpu_lock
        with gpu_lock(root, settings):
            assert_runtime(root, settings)
            import torch
            import tinycudann
            x = torch.ones(1, device='cuda')
            print('torch', torch.__version__, 'cuda', torch.version.cuda)
            print('gpu', torch.cuda.get_device_name(0), 'value', x.item())
        print('Pinned runtime and protected GPU execution PASS')
    elif args.task == 'safety-check':
        from topic16.runtime import gpu_lock, native_output
        with gpu_lock(root, settings):
            print(native_output(['nvidia-smi', '-i', '0', '-q', '-d', 'POWER,CLOCK,TEMPERATURE'], root))
        print('GPU safety PASS: clock lock reapplied; start temperature, power and VRAM within policy')
    elif args.task == 'extract-video':
        from topic16.video import extract_video
        extract_video(root, settings, args.video, args.scene, args.frames)
    elif args.task == 'audit-run':
        from topic16.contracts import inside, load_run
        from topic16.runtime import validate_generated_config
        run = load_run(root, args.config.resolve(), require_eval=args.require_evaluation)
        protocol = run['manifest']['protocol']
        directory = root / Path(run['split']['train'][0]['path']).parent.parent
        validate_generated_config(run['config'], run['paths']['runs'], directory, run['manifest']['method'],
                                  protocol['iterations'], protocol['seed'], settings,
                                  inside(root, run['provenance']['resumed_from']['checkpoint']) if 'resumed_from' in run['provenance'] else None)
        print('Artifact audit PASS:', run['manifest']['run_key'])
    elif args.task == 'camera-path':
        from topic16.demo import create_camera_path
        create_camera_path(root, settings, args.config, args.output)
    elif args.task == "train":
        from topic16.runtime import train
        config = train(root, settings, args.method, args.scene, args.iterations, args.seed, args.protocol, args.resume_config)
        if args.result:
            write_json(args.result, {"config": str(config)})
    elif args.task in ("evaluate", "render", "export"):
        from topic16.runtime import evaluate, render, export
        config = args.config.resolve()
        if args.task == "evaluate":
            evaluate(root, settings, config)
        elif args.task == "render":
            render(root, settings, config, args.camera_path)
        else:
            export(root, settings, config)
    elif args.task == "benchmark":
        from topic16.experiments import benchmark
        benchmark(root, settings, args.scenes, args.matrix.resolve(), args.resume, args.iterations, args.seed, args.protocol)
    elif args.task == "capture":
        import re
        from topic16.data import capture_inputs, convert_capture_model, finish_capture, freeze_split, scene_source
        from topic16.runtime import gpu_lock, run_command
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", args.scene):
            raise ValueError("Invalid custom scene slug")
        inputs = capture_inputs(args.train.resolve(), args.eval.resolve())
        directory, _, _ = scene_source(root, f"custom:{args.scene}")
        if directory.exists():
            previous = read_json(directory / 'capture.json')
            if previous['inputs'] != inputs:
                raise ValueError('Existing capture inputs differ; preserve it and use a new scene slug')
            if previous['status'] in ('pending-review', 'ready'):
                from topic16.contracts import digest_json
                if digest_json(freeze_split(root, f'custom:{args.scene}', settings, check_capture=False)) != previous['split_hash']:
                    raise ValueError('Existing capture split changed')
                print('Capture already processed and checksum verified:', directory)
                return
            if not args.recover:
                raise ValueError('Partial capture preserved; -Recover can convert a completed qualifying COLMAP component')
        elif args.recover:
            raise ValueError('Recovery requires an existing capture attempt')
        with gpu_lock(root, None if args.cpu_only else settings):
            directory.mkdir(parents=True, exist_ok=True)
            if not args.recover:
                write_json(directory / "capture.json", {"status": "processing", "inputs": inputs,
                       'processing': {'gpu': not args.cpu_only, 'matching_method': settings['CaptureMatchingMethod'],
                                      'cpu_threads': settings['CpuWorkerThreads']}})
            try:
                arguments = [sys.executable, "-c", "from nerfstudio.scripts.process_data import entrypoint; entrypoint()",
                            "images", "--data", str(native_workspace(args.train.resolve())),
                            "--eval-data", str(native_workspace(args.eval.resolve())),
                            "--output-dir", str(native_workspace(root) / directory.relative_to(root)),
                            '--matching-method', settings['CaptureMatchingMethod'], '--sfm-tool', 'colmap',
                            '--num-downscales', str(settings['CaptureNumDownscales']), '--verbose']
                if args.cpu_only:
                    import subprocess
                    alias = native_workspace(root)
                    settings_alias = native_workspace(args.settings.resolve().parent) / args.settings.name
                    adapter = subprocess.list2cmdline([sys.executable, str(alias / 'src/topic16/cli.py'),
                        '--root', str(alias), '--settings', str(settings_alias), 'colmap',
                        '--log-dir', str(alias / directory.relative_to(root)), '--'])
                    arguments += ['--no-gpu', '--colmap-cmd', adapter]
                if not args.recover:
                    run_command(root, arguments, directory / "process.log")
                selection = convert_capture_model(root, f'custom:{args.scene}', settings, inputs)
                finish_capture(root, f"custom:{args.scene}", settings, inputs)
                report = read_json(directory / 'capture.json')
                report['model_selection'] = selection
                report['processing'] = {'gpu': not args.cpu_only, 'cpu_threads': settings['CpuWorkerThreads'],
                                        'matching_method': settings['CaptureMatchingMethod']}
                write_json(directory / 'capture.json', report)
            except BaseException as error:
                record = read_json(directory / "capture.json")
                record.update(status="failed", failure_reason=str(error))
                write_json(directory / "capture.json", record)
                raise
        print(f"Registration PASS; review frustums/cloud before Approve-Capture.ps1: {directory}")
    elif args.task == 'review-capture':
        from topic16.data import capture_preview, freeze_split
        from topic16.runtime import gpu_lock
        with gpu_lock(root):
            if args.verify_only:
                split = freeze_split(root, f'custom:{args.scene}', settings)
                print(f'Capture audit PASS: {len(split["train"])} train / {len(split["eval"])} eval; frozen split and review hashes verified')
            else:
                capture_preview(root, f'custom:{args.scene}', settings)
    elif args.task == "approve-capture":
        from topic16.contracts import digest_json, file_required, inside, relative, sha256
        from topic16.data import freeze_split, scene_source
        from topic16.runtime import gpu_lock
        with gpu_lock(root):
            directory, _, _ = scene_source(root, f"custom:{args.scene}")
            report = read_json(directory / "capture.json")
            if report["status"] != "pending-review":
                raise ValueError("Capture is not awaiting pose review")
            split = freeze_split(root, f"custom:{args.scene}", settings, check_capture=False)
            if digest_json(split) != report["split_hash"]:
                raise ValueError("Capture changed before visual review")
            if not args.reviewer.strip() or not args.notes.strip():
                raise ValueError('Pose review requires a named reviewer and concrete notes')
            evidence_path = root / 'reports/custom_capture' / args.scene / 'pose_evidence.json'
            evidence = read_json(file_required(evidence_path))
            if evidence['scene'] != f'custom:{args.scene}' or evidence['split_hash'] != report['split_hash']:
                raise ValueError('Pose evidence belongs to a different capture/split')
            for item in evidence['files']:
                if sha256(file_required(inside(root, item['path']))) != item['sha256']:
                    raise ValueError('Pose review images changed after evidence generation')
            report.update(status="ready", visual_review={"approved": True, "reviewer": args.reviewer,
                          "notes": args.notes, "reviewed_at": utc_now(),
                          'evidence': evidence['files'] + [{'path': relative(root, evidence_path), 'sha256': sha256(evidence_path)}]})
            write_json(directory / "capture.json", report)
    elif args.task == 'prepare':
        from topic16.data import prepare_scene
        from topic16.runtime import gpu_lock
        with gpu_lock(root):
            print(prepare_scene(root, args.scene, settings))
    elif args.task == "analyze":
        from topic16.analysis import analyze
        analyze(root, settings, args.matrices, args.output, args.review, args.protocol)
    else:
        from topic16.demo import select_model, start_demo, release
        if args.task == "select-model":
            select_model(root, settings, args.config, args.gate, args.camera_path, args.output)
        elif args.task == "demo":
            start_demo(root, settings, args.model, args.health_only, args.fallback)
        else:
            release(root, settings, args.model, args.output)


if __name__ == "__main__":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        main()
    except Exception as error:
        from topic16.sessions import SessionPaused
        if isinstance(error, SessionPaused):
            print(f'[topic16] PAUSED: {error}', flush=True)
            sys.exit(75)
        import traceback
        traceback.print_exc()
        print(f"[topic16] ERROR: {error}", file=sys.stderr)
        sys.exit(1)
