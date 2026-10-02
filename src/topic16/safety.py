"""Fail-closed GPU policy and a watchdog independent of training output."""
from __future__ import annotations

import _thread
import csv
import math
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from topic16.contracts import utc_now, write_json


FIELDS = ('temperature.gpu', 'clocks.gr', 'memory.used', 'memory.total', 'power.draw', 'power.limit')
_active_guard = None


class SafetyStop(RuntimeError):
    """The current job cannot run within the configured safety policy."""


def check_sample(sample: dict, settings: dict, *, starting=False) -> None:
    for key in FIELDS:
        value = sample.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise SafetyStop(f'Missing/invalid GPU telemetry: {key}')
    temperature_limit = settings['GpuStartTemperatureC'] if starting else settings['GpuStopTemperatureC']
    if sample['temperature.gpu'] >= temperature_limit:
        raise SafetyStop(f"GPU temperature {sample['temperature.gpu']} C reached {temperature_limit} C; allow cooling before retry")
    if sample['clocks.gr'] > settings['GpuClockMaxMHz'] + settings['GpuClockToleranceMHz']:
        raise SafetyStop('Observed graphics clock exceeds the configured clock ceiling')
    if sample['memory.total'] <= 0 or sample['memory.used'] >= sample['memory.total'] * settings['GpuMaxMemoryPercent'] / 100:
        raise SafetyStop('GPU memory exceeds the configured budget')
    if sample['power.limit'] <= 0 or sample['power.draw'] >= min(settings['GpuStopPowerWatts'], sample['power.limit']):
        raise SafetyStop('GPU power reached the configured stop threshold')


def query_sample(root: Path, settings: dict) -> dict:
    # On this WDDM driver power.limit is Requested Power Limit and is N/A.
    # The enforced limit is available and is the applicable safety ceiling.
    query_fields = [name if name != 'power.limit' else 'enforced.power.limit' for name in FIELDS]
    output = subprocess.check_output(
        ['nvidia-smi', '--id=0', '--query-gpu=' + ','.join(query_fields), '--format=csv,noheader,nounits'],
        cwd=root, encoding='utf-8', errors='replace', timeout=settings['GpuSafetyQueryTimeoutSeconds'])
    rows = list(csv.reader(output.strip().splitlines()))
    if len(rows) != 1 or len(rows[0]) != len(FIELDS):
        raise SafetyStop('nvidia-smi did not return exactly one GPU')
    try:
        return dict(zip(FIELDS, (float(value.strip()) for value in rows[0])))
    except ValueError as error:
        raise SafetyStop('GPU safety telemetry is unavailable; job blocked') from error


def apply_clock_limit(root: Path, settings: dict) -> str:
    """Reapply every job: an idle clock reading cannot prove an active lock."""
    result = subprocess.run(['nvidia-smi', '-i', '0', '-lgc',
                             f"{settings['GpuClockMinMHz']},{settings['GpuClockMaxMHz']}"],
                            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            encoding='utf-8', errors='replace', timeout=settings['GpuSafetyQueryTimeoutSeconds'])
    if result.returncode:
        raise SafetyStop(f'Clock lock could not be applied (exit {result.returncode}). '
                         'Run the project command in Windows PowerShell Administrator. '
                         'No GPU workload was started. ' + result.stdout.strip())
    return result.stdout.strip()


def wait_until_cool(root: Path, settings: dict, record: dict, path: Path) -> dict:
    deadline = time.monotonic() + settings['GpuCooldownMaximumSeconds']
    while True:
        sample = query_sample(root, settings)
        check_sample(sample, settings)  # Hard-stop thresholds apply during cooldown too.
        if sample['temperature.gpu'] < settings['GpuStartTemperatureC']:
            return sample
        if time.monotonic() >= deadline:
            raise SafetyStop('GPU did not cool below the start threshold within the bounded cooldown')
        record.update(status='cooling', last_sample=sample)
        write_json(path, record)
        print(f"GPU cooling: {sample['temperature.gpu']} C; no project GPU workload has started", flush=True)
        time.sleep(settings['GpuCooldownPollSeconds'])


def stop_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == 'nt':
        # Stop only this project's child, including COLMAP/FFmpeg descendants.
        result = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        if result.returncode == 0:
            return
    process.kill()


class GpuGuard:
    def __init__(self, root: Path, settings: dict):
        self.root, self.settings = root, settings
        self.stop = threading.Event()
        self.error = None
        self.child = None
        self.worker = None
        stamp = utc_now().replace(':', '').replace('-', '').replace('.', '')
        self.path = root / 'artifacts/logs/safety' / f'{stamp}-{os.getpid()}.json'
        self.record = {'schema_version': '1.0', 'status': 'checking', 'started_at': utc_now(),
                       'pid': os.getpid(), 'policy': {key: value for key, value in settings.items() if key.startswith('Gpu')}}

    def check(self):
        if self.error:
            raise SafetyStop(self.error)

    def __enter__(self):
        global _active_guard
        try:
            self.record['clock_lock_output'] = apply_clock_limit(self.root, self.settings)
            sample = wait_until_cool(self.root, self.settings, self.record, self.path)
            check_sample(sample, self.settings, starting=True)
            self.record.update(status='monitoring', first_sample=sample)
        except Exception as error:
            self.record.update(status='blocked', failure_reason=str(error), finished_at=utc_now())
            write_json(self.path, self.record)
            raise
        write_json(self.path, self.record)
        _active_guard = self
        self.worker = threading.Thread(target=self._watch, name='topic16-gpu-safety', daemon=True)
        self.worker.start()
        return self

    def _watch(self):
        while not self.stop.wait(self.settings['GpuSafetyPollSeconds']):
            try:
                sample = query_sample(self.root, self.settings)
                self.record['last_sample'] = sample
                check_sample(sample, self.settings)
            except Exception as error:
                self.error = f'GPU safety stop: {error}'
                self.record.update(status='unsafe-stopped', failure_reason=self.error, finished_at=utc_now())
                # Preserve the stop reason even if a hung CUDA call prevents unwinding.
                try:
                    write_json(self.path, self.record)
                finally:
                    if self.child is not None and self.child.poll() is None:
                        try:
                            stop_process_tree(self.child)
                        except (OSError, subprocess.SubprocessError):
                            pass
                    else:
                        _thread.interrupt_main()
                if not self.stop.wait(self.settings['GpuEmergencyGraceSeconds']):
                    # Include this job's data-loader children on Windows; the
                    # invoking PowerShell/Conda/Codex parent is outside this tree.
                    if os.name == 'nt':
                        subprocess.Popen(['taskkill', '/PID', str(os.getpid()), '/T', '/F'],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        time.sleep(2)
                    # Fallback terminates this Python job only, never the laptop.
                    os.kill(os.getpid(), signal.SIGTERM)
                return

    def __exit__(self, exc_type, exc, traceback):
        global _active_guard
        self.stop.set()
        self.worker.join(timeout=self.settings['GpuSafetyQueryTimeoutSeconds'] + 1)
        _active_guard = None
        if self.worker.is_alive():
            raise SafetyStop('GPU watchdog did not stop')
        if not self.error:
            try:
                self.record['last_sample'] = query_sample(self.root, self.settings)
                check_sample(self.record['last_sample'], self.settings)
            except Exception as error:
                self.error = f'GPU safety stop: {error}'
        from topic16.sessions import SessionPaused
        paused = isinstance(exc, SessionPaused)
        self.record.update(status='unsafe-stopped' if self.error else ('failed' if exc_type and not paused else 'succeeded'), finished_at=utc_now())
        if paused:
            self.record['job_outcome'] = 'paused'
        if self.error:
            self.record['failure_reason'] = self.error
        write_json(self.path, self.record)
        self.check()


def current_guard():
    return _active_guard


def assert_safe() -> None:
    if _active_guard:
        _active_guard.check()
