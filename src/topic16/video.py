"""Deterministic timestamp sampling and immutable custom-scene capture provenance."""
from __future__ import annotations

import bisect
import json
import math
import shutil
import subprocess
from pathlib import Path

from topic16.contracts import digest_json, file_required, inside, native_workspace, read_json, sha256, utc_now, write_json


def contact_sheet(root: Path, target: Path, record: dict) -> None:
    from PIL import Image, ImageDraw, ImageOps
    output = root / 'reports/custom_capture' / (target.name + '_frames.jpg')
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new('RGB', (1200, 900), '#17202c')
    draw = ImageDraw.Draw(canvas)
    frames = record['frames']
    for slot in range(12):
        frame = frames[round(slot * (len(frames) - 1) / 11)]
        with Image.open(inside(target, frame['path'])) as image:
            thumbnail = ImageOps.contain(image.convert('RGB'), (270, 260))
        x, y = slot % 4 * 300, slot // 4 * 300
        canvas.paste(thumbnail, (x + (300 - thumbnail.width) // 2, y))
        draw.text((x + 12, y + 270), f"{frame['split']} / {frame['timestamp_seconds']:.2f}s", fill='white')
    canvas.save(output, quality=90)


def select_frames(timestamps: list[float], count: int) -> list[int]:
    if count < 16 or count > len(timestamps):
        raise ValueError('Frame count must be between 16 and the number of decoded frames')
    if any(not math.isfinite(t) for t in timestamps) or any(a >= b for a, b in zip(timestamps, timestamps[1:])):
        raise ValueError('Video frame timestamps must be finite and strictly increasing')
    # Equally spaced in time, supporting variable frame rate without assuming FPS.
    selected = []
    for index in range(count):
        target = timestamps[0] + (timestamps[-1] - timestamps[0]) * index / (count - 1)
        upper = min(bisect.bisect_left(timestamps, target), len(timestamps) - 1)
        lower = max(0, upper - 1)
        selected.append(min((lower, upper), key=lambda i: (abs(timestamps[i] - target), i)))
    if len(set(selected)) != count:
        raise ValueError('Requested frame sampling produces duplicate indices; reduce the frame count')
    return selected


def extract_video(root: Path, settings: dict, video: Path, scene: str, count: int | None = None) -> dict:
    import re
    from PIL import Image
    from topic16.data import capture_inputs
    from topic16.runtime import run_command
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', scene):
        raise ValueError('Invalid custom scene slug')
    video = file_required(video.resolve())
    count = settings['VideoFrameCount'] if count is None else count
    interval = settings['EvalInterval']
    if interval < 2:
        raise ValueError('Eval interval must be at least two')
    target = root / 'data/raw/custom' / scene
    policy = {'frame_count': count, 'eval_interval': interval, 'selection': 'nearest-uniform-timestamp-v1'}
    source_hash = sha256(video)
    if target.exists():
        record = read_json(target / 'video.json')
        if record['status'] != 'succeeded' or record['source_sha256'] != source_hash or record['policy'] != policy:
            raise ValueError('Existing extraction differs or is partial; preserve it and use a new scene slug')
        for frame in record['frames']:
            if sha256(file_required(inside(target, frame['path']))) != frame['sha256']:
                raise ValueError('Extracted frame changed after extraction')
        capture_inputs(target / 'train', target / 'eval')
        contact_sheet(root, target, record)
        return record
    input_path = native_workspace(video.parent) / video.name
    probe = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_frames',
                                     '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', str(input_path)],
                                    cwd=root, encoding='utf-8', errors='strict', timeout=120)
    timestamps = [float(frame['best_effort_timestamp_time']) for frame in json.loads(probe)['frames']]
    indices = select_frames(timestamps, count)
    target.mkdir(parents=True)
    record = {'schema_version': '1.0', 'status': 'running', 'created_at': utc_now(), 'scene': f'custom:{scene}',
              'source_video': str(video), 'source_sha256': source_hash, 'policy': policy,
              'decoded_frame_count': len(timestamps), 'frames': [],
              'limitations': 'Single-video held-out interpolation; temporally adjacent views are correlated. Poses use all views; eval pixels never train the models.'}
    write_json(target / 'video.json', record)
    try:
        staging = target / '.decoded'
        staging.mkdir()
        alias = native_workspace(root) / staging.relative_to(root)
        expression = '+'.join(f'eq(n\\,{index})' for index in indices)
        run_command(root, ['ffmpeg', '-hide_banner', '-n', '-threads', str(settings['CpuWorkerThreads']),
                          '-i', str(input_path), '-vf', 'select=' + expression, '-vsync', '0',
                          '-threads', str(settings['CpuWorkerThreads']), str(alias / 'frame_%05d.png')], target / 'extract.log')
        files = sorted(staging.glob('frame_*.png'))
        if len(files) != count:
            raise ValueError('FFmpeg did not produce exactly the selected frame count')
        for label in ('train', 'eval'):
            (target / label).mkdir()
        hashes = set()
        for order, (index, path) in enumerate(zip(indices, files)):
            label = 'eval' if order % interval == 0 else 'train'
            output = target / label / f'{label}_{order:05d}.png'
            with Image.open(path) as image:
                image.verify()
            digest = sha256(path)
            if digest in hashes:
                raise ValueError('Video contains identical selected frames; use a different interval/clip')
            hashes.add(digest)
            shutil.move(str(path), str(output))
            record['frames'].append({'source_frame_index': index, 'timestamp_seconds': timestamps[index],
                                     'split': label, 'path': output.relative_to(target).as_posix(), 'sha256': digest})
        staging.rmdir()
        capture_inputs(target / 'train', target / 'eval')
        record.update(status='succeeded', finished_at=utc_now(), frame_selection_hash=digest_json(record['frames']))
    except BaseException as error:
        record.update(status='failed', finished_at=utc_now(), failure_reason=str(error))
        raise
    finally:
        write_json(target / 'video.json', record)
    print(f'Video extraction PASS: {target} ({count - math.ceil(count / interval)} train, {math.ceil(count / interval)} eval)')
    contact_sheet(root, target, record)
    return record
