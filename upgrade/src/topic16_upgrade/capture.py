"""Train-only capture statistics and deterministic coverage selection (CPU)."""
from pathlib import Path
import csv
import time
import numpy as np
from PIL import Image
from .contracts import read_json, write_json, sha256, digest_json, inside, validate_split

FEATURE_SCHEMA = 'capture-features-1'


def capture_split(baseline: Path, scene: str, split_path=None):
    if split_path:
        path = inside(baseline, split_path)
    else:
        paths = sorted((baseline / 'artifacts/logs/matrices').glob('topic16-full-*.json'))
        matches = [pair for p in paths for key, pair in read_json(p)['pairs'].items() if key == scene]
        if len(matches) != 1:
            raise ValueError('Supply -SplitPath for a fresh canonical capture with no baseline run')
        config = inside(baseline, matches[0]['runs']['nerfacto'])
        key = config.parent.relative_to(baseline / 'artifacts/runs')
        path = baseline / 'artifacts/logs' / key / 'split.json'
    split = read_json(path)
    validate_split(split)
    if split['scene'] != scene:
        raise ValueError('Capture scene differs from the explicit frozen split')
    # No held-out RGB is opened during feature extraction or selection.
    return split, {'split_path': str(path), 'split_sha256': sha256(path), 'input_root': str(baseline)}


def summarize(rows):
    positions = np.asarray([r['position'] for r in rows])
    distances = np.linalg.norm(positions[:,None] - positions[None,:], axis=2)
    np.fill_diagonal(distances, np.inf)
    return {'views': len(rows),
            'sharpness': float(np.median([r['sharpness'] for r in rows])),
            'clipped_fraction': float(np.mean([r['dark_fraction'] + r['bright_fraction'] for r in rows])),
            'luminance': float(np.mean([r['luminance'] for r in rows])),
            'coverage_bins': len({r['coverage_bin'] for r in rows}),
            'radius_spread': float(np.std([r['radius'] for r in rows])),
            'pose_redundancy': float(np.mean(np.exp(-distances.min(axis=1))))}


def audit(root: Path, baseline: Path, scene: str, split_path=None, image_size=256):
    start = time.perf_counter()
    split, provenance = capture_split(baseline, scene, split_path)
    poses = np.asarray([r['camera_to_world'] for r in split['train']], dtype=float)
    centers, directions = poses[:, :, 3], -poses[:, :, 2]
    center = np.median(centers, axis=0)
    offsets = centers - center
    scale = max(float(np.median(np.linalg.norm(offsets, axis=1))), 1e-8)
    distances = np.linalg.norm((centers[:, None] - centers[None, :]) / scale, axis=2)
    np.fill_diagonal(distances, np.inf)
    from .visibility import training_visibility
    tracks, overlap = training_visibility(baseline, split)
    extractor = {'image_size': image_size, 'capture_source': sha256(Path(__file__)),
                 'visibility_source': sha256(Path(__file__).with_name('visibility.py'))}
    output = inside(root / 'artifacts/features', scene.replace(':', '-'))
    cached_path = output / 'capture-features.json'
    if cached_path.exists():
        cached = read_json(cached_path)
        if (cached.get('extractor') == extractor and cached['provenance'] == provenance
                and cached['overlap'] == overlap and cached['pool_hash'] == digest_json(split['train'])):
            for frame in split['train']:
                if sha256(inside(baseline, frame['path'])) != frame['sha256']:
                    raise ValueError('Training image changed from cached capture')
            return cached
    overlap_matrix = None
    if tracks is not None:
        overlap_matrix = [[len(a & b) / max(1, len(a | b)) for b in tracks] for a in tracks]
    rows = []
    for index, frame in enumerate(split['train']):
        path = inside(baseline, frame['path'])
        if sha256(path) != frame['sha256']:
            raise ValueError('Training image changed from the frozen capture')
        with Image.open(path) as image:
            small = image.convert('L').resize((image_size, image_size), Image.Resampling.BILINEAR)
            gray = np.asarray(small, dtype=np.float64) / 255
        lap = (-4 * gray[1:-1, 1:-1] + gray[:-2, 1:-1] + gray[2:, 1:-1]
               + gray[1:-1, :-2] + gray[1:-1, 2:])
        # Look-direction bins avoid an object-centered sphere assumption.
        direction = directions[index] / np.linalg.norm(directions[index])
        azimuth = float(np.arctan2(direction[1], direction[0]))
        elevation = float(np.arcsin(np.clip(direction[2], -1, 1)))
        row = {'index': index, 'path': frame['path'], 'sha256': frame['sha256'],
               'sharpness': float(lap.var()), 'dark_fraction': float(np.mean(gray <= .02)),
               'bright_fraction': float(np.mean(gray >= .98)), 'luminance': float(gray.mean()),
               'azimuth': azimuth, 'elevation': elevation,
               'coverage_bin': f'{min(11, int((azimuth + np.pi) / (2*np.pi) * 12))}:{min(5, int((elevation + np.pi/2) / np.pi * 6))}',
               'position': ((centers[index] - center) / scale).tolist(),
               'direction': direction.tolist(), 'radius': float(np.linalg.norm(offsets[index]) / scale),
               'pose_redundancy': float(np.exp(-distances[index].min())),
               'thumbnail': gray[::16, ::16].ravel().tolist(), 'sparse_visibility': len(tracks[index]) if tracks is not None else None}
        rows.append(row)
    record = {'schema_version': FEATURE_SCHEMA, 'extractor': extractor, 'scene': scene, 'scene_group': scene,
              'provenance': provenance, 'pool_hash': digest_json(split['train']),
              'eval_camera_hash': digest_json(split['eval']), 'features': summarize(rows), 'frames': rows,
              'sfm_scope': 'known-camera / transductive SfM; no held-out RGB decoded',
              'overlap': overlap, 'overlap_matrix': overlap_matrix,
              'caveats': ['Laplacian depends on texture', 'Exposure depends on scene content',
                          'Coverage uses look directions, not object-centered spherical completeness'],
              'cpu_seconds': time.perf_counter() - start}
    output = inside(root / 'artifacts/features', scene.replace(':', '-'))
    write_json(output / 'capture-features.json', record)
    with (output / 'frames.csv').open('w', encoding='utf-8', newline='') as stream:
        fields = ['index', 'path', 'sharpness', 'dark_fraction', 'bright_fraction', 'luminance', 'coverage_bin', 'pose_redundancy']
        writer = csv.DictWriter(stream, fields, extrasaction='ignore'); writer.writeheader(); writer.writerows(rows)
    dots = ''.join(f'<circle cx="{30+(r["azimuth"]+np.pi)/(2*np.pi)*660:.2f}" cy="{25+(np.pi/2-r["elevation"])/np.pi*290:.2f}" r="3" fill="#2276b5"><title>Train {r["index"]}</title></circle>' for r in rows)
    (output / 'coverage.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 360"><rect width="720" height="360" fill="white"/><text x="30" y="345">Train camera look directions: azimuth / elevation (radians)</text>'+dots+'</svg>', encoding='utf-8')
    return record


def select(record: dict, count: int, recipe: str, seed=42):
    rows = record['frames']; n = len(rows)
    if not 1 <= count <= n or recipe not in ('uniform', 'coverage-overlap'):
        raise ValueError('Invalid view count or selector recipe')
    if recipe == 'uniform' or count == n:
        chosen = np.rint(np.linspace(0, n - 1, count)).astype(int).tolist()
        trace = [{'index': i, 'reason': 'nearest-uniform' if count < n else 'full-pool'} for i in chosen]
    else:
        positions = np.asarray([r['position'] for r in rows])
        directions = np.asarray([r['direction'] for r in rows])
        distance = np.linalg.norm(positions[:, None] - positions[None, :], axis=2)
        sparse_overlap = np.asarray(record['overlap_matrix']) if record.get('overlap_matrix') is not None else None
        angle = np.clip(1 - directions @ directions.T, 0, 2)
        appearance = np.asarray([r['thumbnail'] for r in rows])
        image_distance = np.mean(np.abs(appearance[:, None] - appearance[None, :]), axis=2)
        sharp = np.asarray([r['sharpness'] for r in rows]); sharp = (sharp - sharp.min()) / max(float(np.ptp(sharp)), 1e-12)
        clipping = np.asarray([r['dark_fraction'] + r['bright_fraction'] for r in rows])
        ties = np.random.default_rng(seed).random(n) * 1e-10
        chosen, trace, bins = [], [], set()
        for _ in range(count):
            if not chosen:
                score = .2 * sharp - .1 * clipping + ties
            else:
                novelty = np.minimum(distance[:, chosen] + angle[:, chosen], 2).min(axis=1)
                continuity = sparse_overlap[:, chosen].max(axis=1) if sparse_overlap is not None else np.exp(-distance[:, chosen]).max(axis=1)
                diversity = image_distance[:, chosen].min(axis=1)
                new_bins = np.asarray([r['coverage_bin'] not in bins for r in rows], dtype=float)
                score = .45 * novelty + .25 * new_bins + .15 * continuity + .1 * sharp + .1 * diversity - .1 * clipping + ties
                score[chosen] = -np.inf
            i = int(np.argmax(score)); chosen.append(i); bins.add(rows[i]['coverage_bin'])
            trace.append({'index': i, 'score': float(score[i]), 'reason': 'coverage + sparse-track overlap + sharpness + image diversity' if sparse_overlap is not None else 'coverage + pose-continuity proxy + sharpness + image diversity'})
    indices = sorted(chosen)
    # Full-pool identity intentionally does not depend on the selector name.
    identity = {'pool_hash': record['pool_hash'], 'indices': indices, 'seed': seed,
                'recipe': recipe if count < n else 'full-pool', 'version': 'selector-1'}
    return {**identity, 'selection_id': digest_json(identity), 'order': trace,
            'features': summarize([rows[i] for i in indices]),
            'overlap_evidence': record['overlap'], 'eval_camera_hash': record['eval_camera_hash']}
