"""Validated single-method experiments; never manufacture a Nerfacto partner."""
import sys
from pathlib import Path
from topic16.contracts import read_json, sha256, inside


def quality_results(root, asset, limits):
    upgrade = root / 'upgrade'
    state_path = upgrade / 'artifacts/jobs/quality/tea-quality-v2.json'
    if not state_path.exists():
        return {'status': 'unavailable', 'experiments': []}
    sys.path.insert(0, str(upgrade / 'src'))
    from topic16_upgrade.contracts import load_run, digest_json, validate_export
    state = read_json(state_path)
    if state['status'] != 'succeeded':
        return {'status': state['status'], 'experiments': []}
    report_path = inside(upgrade, state['report'])
    if sha256(report_path) != state['report_sha256']:
        raise ValueError('Quality report checksum changed')
    report = read_json(report_path)
    config = inside(upgrade, report['config'])
    run = load_run(upgrade, config, require_eval=True)
    if (run['manifest']['status'] != 'succeeded' or run['manifest']['protocol']['iterations'] != 30000
            or digest_json(run['split']['eval']) != report['native_eval_hash']
            or len(run['split']['train']) != 105 or len(run['split']['eval']) != 15):
        raise ValueError('Quality report disagrees with the completed run')
    rows = []
    for result in report['comparisons']:
        common = inside(upgrade, result['path'])
        scored = read_json(common)
        if sha256(common) != result['sha256'] or scored['metrics'] != result['metrics']:
            raise ValueError('Quality metric evidence changed')
        rendered = read_json(common.parent / 'renders.json')
        if rendered['identity'] != scored['identity'] or rendered['status'] != 'succeeded':
            raise ValueError('Quality render identity differs')
        frames = []
        from PIL import Image
        for i, frame in enumerate(rendered['frames']):
            row = {'index': i}
            for kind in ('gt', 'pred'):
                path = inside(upgrade, common.parent / frame[kind])
                if sha256(path) != frame[kind + '_sha256']:
                    raise ValueError('Quality image evidence changed')
                row[kind] = asset(path, frame[kind + '_sha256'])
                with Image.open(path) as image:
                    size = list(image.size)
                if kind == 'gt':
                    row['size'] = size
                elif size != row['size']:
                    raise ValueError('Quality GT/pred dimensions differ')
            row['gt_sha256'] = frame['gt_sha256']
            frames.append(row)
        rows.append({'tag': result['tag'], 'metrics': result['metrics'],
                     'roi_metrics': result.get('roi_metrics'), 'frames': frames})
    # Compare only identical GT bytes. Both resolutions remain visible, including losses.
    for suffix in ('native', 'half'):
        group = [r for r in rows if r['tag'].endswith('-' + suffix)]
        if len(group) != 3 or any([f['gt_sha256'] for f in r['frames']] !=
                                  [f['gt_sha256'] for f in group[0]['frames']] for r in group):
            raise ValueError('Quality comparison GT cameras differ')
    models = []
    for label, owner, source in [('Q1 native', upgrade, config)]:
        loaded = load_run(owner, source, require_eval=True)
        record = loaded['paths']['exports'] / 'export.json'
        exported = validate_export(record.parent, loaded['provenance']['checkpoint_sha256'], owner,
                                   read_json(loaded['paths']['logs'] / 'settings.json'))
        # Follow the contract's registered PLY rather than guessing a filename.
        ply = inside(record.parent, next(f['name'] for f in exported['files'] if f['name'].endswith('.ply')))
        from .catalog import ply_vertices
        count = ply_vertices(ply)
        if count > limits['MaxVertices'] or ply.stat().st_size > limits['DecodeLimitBytes']:
            continue
        models.append({'label': label, 'id': loaded['manifest']['run_key'],
                       'cameras': loaded['split']['eval'],
                       'run': {'run_key': loaded['manifest']['run_key'], 'config': 'upgrade/' + report['config'],
                               'asset': asset(ply), 'bytes': ply.stat().st_size, 'vertices': count,
                               'kind': 'Gaussian splats', 'rasterize_mode': 'classic', 'background_rgb': [.1490,.1647,.2157],
                               'checkpoint_sha256': loaded['provenance']['checkpoint_sha256'],
                               'split_hash': digest_json(loaded['split']), 'metrics': next(r['metrics'] for r in rows if r['tag']=='native-candidate-native'),
                               'train_seconds': report['training_wall_seconds_all_attempts'],
                               'peak_vram_mb': loaded['manifest']['execution_metrics']['peak_vram_mb'],
                               'offline_fps': report['native_offline_throughput'],
                               'provenance': {'scope': 'Single-method Q1; no Nerfacto partner',
                                              'memory_scope': 'Sampled total GPU memory.used; not allocator peak'}}})
    return {'status': 'ready', 'experiments': [{'id': state['study'], 'scene': 'custom:tea_sets_2',
            'label': 'Q1 · native Splatfacto · 105 views / 30k / seed 42', 'rows': rows, 'models': models,
            'numeric_target_met': report['numeric_target_met'], 'train_seconds': report['training_wall_seconds_all_attempts'],
            'scope': 'Exploratory, one seed. Compare within one output resolution. Native improves; direct half-resolution regresses.'}]}
