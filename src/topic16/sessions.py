"""Cooperative stop requests, committed checkpoints and a read-only log console."""
from __future__ import annotations

import os
import time
from pathlib import Path

from topic16.contracts import digest_json, file_required, inside, read_json, relative, run_paths, sha256


class SessionPaused(RuntimeError):
    def __init__(self, message='Session stopped by request', config=None):
        super().__init__(message)
        self.config = config


def stop_requested() -> bool:
    directory = os.environ.get('TOPIC16_SESSION_DIRECTORY')
    return bool(directory and (Path(directory) / 'stop.json').is_file())


def check_stop() -> None:
    if stop_requested():
        raise SessionPaused()


class StoppableLoader:
    """Keep upstream metric code, checking stop between evaluation cameras."""
    def __init__(self, loader):
        self.loader = loader

    def __len__(self):
        return len(self.loader)

    def __iter__(self):
        for item in self.loader:
            check_stop()
            yield item


def average_eval_metrics(pipeline, step=None, output_path=None, get_std=False):
    # fixed_indices_eval_dataloader is read-only on the pinned managers. Pass
    # its wrapped iterator to the SDK's public averaging function instead.
    return pipeline.get_average_image_metrics(
        StoppableLoader(pipeline.datamanager.fixed_indices_eval_dataloader),
        'eval', step=step, output_path=output_path, get_std=get_std)


def remaining_iterations(total: int, saved_step: int) -> int:
    if total < 1 or saved_step < 0 or saved_step >= total:
        raise ValueError('Checkpoint step is outside the requested total training budget')
    return total - saved_step - 1


def resume_source(root: Path, config: Path, settings: dict, split: dict, method: str,
                  scene: str, iterations: int, seed: int, protocol: str) -> dict:
    """Validate explicit committed resume evidence before deserializing a checkpoint."""
    config = inside(root / 'artifacts/runs', config)
    key = config.parent.relative_to(root / 'artifacts/runs').as_posix()
    paths = run_paths(root, key)
    manifest = read_json(paths['logs'] / 'manifest.json')
    provenance = read_json(paths['logs'] / 'provenance.json')
    record = read_json(paths['logs'] / 'resume.json')
    expected = {'iterations': iterations, 'seed': seed, 'downscale_factor': settings['DownscaleFactor'],
                'eval_interval': settings['EvalInterval']}
    if (manifest['scene'] != scene or manifest['method'] != method or manifest['protocol'] != expected
            or provenance['protocol_id'] != protocol or provenance['settings_hash'] != digest_json(settings)
            or digest_json(read_json(paths['logs'] / 'split.json')) != digest_json(split)):
        raise ValueError('Resume source has different scene, protocol, registry or frozen cameras')
    if record['status'] not in ('checkpoint-ready', 'paused'):
        raise ValueError('No committed checkpoint is available for resume')
    if manifest['status'] == 'succeeded':
        raise ValueError('Completed training must be reused, not resumed as a new attempt')
    if sha256(file_required(config)) != record['config_sha256']:
        raise ValueError('Resume configuration changed')
    checkpoint = file_required(inside(paths['runs'] / 'nerfstudio_models', inside(root, record['checkpoint'])))
    if checkpoint.name != f'step-{record["step"]:09d}.ckpt':
        raise ValueError('Checkpoint filename and committed step disagree')
    if sha256(checkpoint) != record['checkpoint_sha256']:
        raise ValueError('Resume checkpoint is missing, incomplete or changed')
    remaining_iterations(iterations, record['step'])
    from topic16.contracts import validate_safety_record
    validate_safety_record(root, provenance, settings)
    return {'config': config, 'checkpoint': checkpoint, 'step': record['step'],
            'run_key': key, 'provenance': provenance, 'record': record, 'paths': paths}


def watch_session(directory: Path) -> None:
    """Tmux is only a console: losing its client cannot terminate the Windows job."""
    log = directory / 'console.log'
    offset = 0
    try:
        while True:
            if log.exists():
                with log.open('rb') as stream:
                    stream.seek(offset)
                    content = stream.read()
                    offset = stream.tell()
                if content:
                    print(content.decode('utf-8', errors='replace'), end='', flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nConsole disconnected; use Stop-Session to request a checkpoint and release GPU.')
