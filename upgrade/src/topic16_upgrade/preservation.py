"""Read-only baseline inventory; hashing large model files is explicitly optional."""
from pathlib import Path
from .contracts import read_json, write_json, sha256, utc_now, inside


def inventory(root: Path, baseline: Path, full_hash=False):
    import time
    start = time.perf_counter()
    runs, matrices = [], []
    for path in sorted((baseline / 'artifacts/logs/matrices').glob('topic16-full-*.json')):
        matrix = read_json(path)
        matrices.append({'path': str(path.relative_to(baseline)), 'sha256': sha256(path)})
        for pair in matrix['pairs'].values():
            for method, config in pair['runs'].items():
                config_path = inside(baseline, config)
                key = config_path.parent.relative_to(baseline / 'artifacts/runs').as_posix()
                logs = baseline / 'artifacts/logs' / key
                provenance = read_json(logs / 'provenance.json')
                references = [config_path, logs / 'split.json', logs / 'settings.json',
                              logs / 'manifest.json', logs / 'provenance.json',
                              inside(baseline, provenance['checkpoint_path'])]
                references += list((baseline / 'artifacts/exports' / key).glob('*'))
                files = []
                for item in references:
                    exists = item.is_file()
                    entry = {'path': str(item.relative_to(baseline)), 'exists': exists}
                    if exists:
                        entry['bytes'] = item.stat().st_size
                        entry['mtime_ns'] = item.stat().st_mtime_ns
                        if full_hash or item.suffix not in ('.ckpt', '.ply'):
                            entry['sha256'] = sha256(item)
                    files.append(entry)
                runs.append({'run_key': key, 'method': method, 'scene': pair['scene'],
                             'recorded_provenance': provenance, 'files': files})
    result = {'schema_version': 'capture-inventory-1', 'created_at': utc_now(), 'inventory_seconds': time.perf_counter() - start,
              'baseline_root': str(baseline), 'large_files_fully_hashed': full_hash,
              'scope': 'Source snapshot is not a backup of datasets or checkpoints',
              'matrices': matrices, 'runs': runs}
    path = root / 'reports/baseline-inventory.json'
    if path.exists():
        previous = read_json(path)
        for run in previous['runs']:
            for item in run['files']:
                file = inside(baseline, item['path'])
                if item['exists'] and (not file.is_file() or file.stat().st_size != item['bytes']
                                      or file.stat().st_mtime_ns != item['mtime_ns']):
                    raise ValueError(f'Protected baseline artifact changed: {file}')
                if item.get('sha256') and sha256(file) != item['sha256']:
                    raise ValueError(f'Baseline checksum changed: {file}')
        if full_hash:
            for run in runs:
                provenance = run['recorded_provenance']
                for item in run['files']:
                    if item['path'] == provenance['checkpoint_path'] and item.get('sha256') != provenance['checkpoint_sha256']:
                        raise ValueError('Full hashing disagrees with the recorded baseline checkpoint')
            write_json(root / 'reports/baseline-inventory-full.json', result)
            return result
        return previous
    write_json(path, result)
    return result


def verify_source(root: Path, baseline: Path):
    source = read_json(root / 'reports/preservation/baseline-source.json')
    for name, expected in source['protected'].items():
        if sha256(inside(baseline, name)) != expected:
            raise ValueError(f'Protected source/report changed: {name}')
    return {'status': 'passed', 'protected_files': len(source['protected']), 'checked_at': utc_now()}
