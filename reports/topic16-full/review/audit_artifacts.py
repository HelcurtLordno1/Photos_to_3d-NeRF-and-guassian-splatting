"""Read-only contract replay in a new, package-free native Windows Python venv.

This is artifact verification on the original host, NOT independent GPU replay.
"""
from pathlib import Path
import argparse
import importlib.metadata
import importlib.util
import platform
import shutil
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--settings', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    output = Path(__file__).resolve().parent
    isolated = output / 'isolated-source' / 'topic16'
    isolated.mkdir(parents=True, exist_ok=True)
    names = ('__init__.py', 'contracts.py', 'analysis.py')
    for name in names:
        shutil.copyfile(root / 'src' / 'topic16' / name, isolated / name)
    sys.path.insert(0, str(isolated.parent))
    from topic16.contracts import digest_json, inside, read_json, sha256, utc_now, write_json
    from topic16.analysis import collect_pairs, core_gate, result_rows
    copied = {name: sha256(isolated / name) for name in names}
    assert all(copied[name] == sha256(root / 'src' / 'topic16' / name) for name in names)
    packages = sorted(f'{item.metadata["Name"]}=={item.version}'
                      for item in importlib.metadata.distributions())
    assert sys.prefix != sys.base_prefix, 'Requires a separate Python venv'
    assert not packages, f'Requires a package-free venv: {packages}'
    assert importlib.util.find_spec('torch') is None, 'Torch must not be available'
    selected = read_json(output.parent / 'g-core.json')
    matrices = [root / item['path'] for item in selected['matrices']]
    assert all(sha256(root / item['path']) == item['sha256'] for item in selected['matrices'])
    settings = read_json(args.settings)
    assert digest_json(settings) == selected['settings_hash']
    print('Validating selected checkpoints, source archives, ancestry, GT/pred, pairs...', flush=True)
    pairs = collect_pairs(root, matrices)
    print('Checking current frozen input image/pose bytes against every selected split...', flush=True)
    input_checks = []
    for scene, runs in pairs.items():
        split = runs[0]['split']
        images = split['train'] + split['eval']
        for item in images + split['pose_files']:
            if sha256(inside(root, item['path'])) != item['sha256']:
                raise ValueError(f'Frozen input changed: {item["path"]}')
        input_checks.append({'scene': scene, 'image_count': len(images),
                             'pose_file_count': len(split['pose_files']), 'status': 'PASS'})
    print('Validating safety records, synchronized renders and exports...', flush=True)
    gate = core_gate(root, settings, pairs, matrices, None)
    assert gate['run_keys'] == selected['run_keys']
    rows = result_rows(pairs)
    assert rows == read_json(output.parent / 'results.json'), 'Recomputed table differs'
    summaries = []
    for scene, runs in pairs.items():
        for run in runs:
            m = run['manifest']
            summaries.append({
                'scene': scene, 'method': m['method'], 'run_key': m['run_key'],
                'train_count': len(run['split']['train']),
                'eval_count': len(run['split']['eval']),
                'eval_resolutions': sorted({(f['width'], f['height']) for f in run['split']['eval']}),
                'checkpoint_sha256': run['provenance']['checkpoint_sha256'],
                'source_archive_sha256': run['provenance']['source_archive_sha256'],
                'has_resume_ancestry': bool(run['provenance'].get('resumed_from')),
                'metric_view_std': {k: v for k, v in run['metrics']['results'].items() if k.endswith('_std')},
            })
    record = {
        'schema_version': '1.0', 'checked_at': utc_now(), 'status': 'PASS',
        'scope': 'same-host package-free Python artifact verification and table recomputation',
        'qualifies_as_independent_gpu_replay': False,
        'hardware_independence': False, 'fresh_dataset_preparation': False,
        'fresh_cuda_environment': False, 'fresh_training': False, 'fresh_model_evaluation': False,
        'host': platform.node(), 'platform': platform.platform(),
        'python': sys.version, 'executable': sys.executable,
        'prefix': sys.prefix, 'base_prefix': sys.base_prefix,
        'isolated_mode': bool(sys.flags.isolated), 'installed_distributions': packages,
        'copied_validator_sha256': copied, 'settings_hash': gate['settings_hash'],
        'run_keys': gate['run_keys'], 'technical_checks': gate['checks'],
        'results_exactly_recomputed': True, 'frozen_input_checks': input_checks, 'runs': summaries,
    }
    write_json(output / 'artifact-audit.json', record)
    write_json(output / 'recomputed-results.json', rows)
    print('PASS: 10 selected runs; original results reproduced exactly. This is not GPU replay.', flush=True)


if __name__ == '__main__':
    main()
