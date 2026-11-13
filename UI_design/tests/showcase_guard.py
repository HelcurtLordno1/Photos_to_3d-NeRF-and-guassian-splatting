"""Archive this UI revision and run its real browser acceptance under the GPU guard."""
import argparse
import json
import sys
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    for name in ('root', 'settings', 'directory', 'node'): parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(); root = args.root.resolve(); output = args.directory.resolve()
    sys.path.insert(0, str(root / 'src'))
    from topic16.contracts import read_json, write_json, sha256, relative, utc_now
    from topic16.runtime import gpu_lock, run_command
    from topic16.safety import current_guard
    settings = read_json(args.settings); output.mkdir(parents=True, exist_ok=True)
    files = [p for folder in ('frontend', 'dist') for p in (root / 'UI_design' / folder).rglob('*') if p.is_file()]
    files += [root / 'UI_design/tests' / n for n in ('showcase-browser.mjs', 'showcase_guard.py')]
    files += list((root / 'UI_design/backend').glob('*.py'))
    files.append(root / 'UI_design/scripts/Test-Showcase.ps1')
    sources = {relative(root, p): sha256(p) for p in files}
    with zipfile.ZipFile(output / 'ui-source.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for p in files: archive.write(p, relative(root, p))
    write_json(output / 'ui-source.json', sources)
    server = read_json(root / 'artifacts/ui/server.json')
    job = output / 'job.json'; write_json(job, {'url': server['url'], 'output': str(output)})
    with gpu_lock(root, settings):
        safety = current_guard().path
        run_command(root, [str(args.node), str(root / 'UI_design/tests/showcase-browser.mjs'), str(job)], output / 'browser.log')
    for name, expected in sources.items():
        if sha256(root / name) != expected: raise ValueError('UI source changed during browser acceptance: ' + name)
    result = read_json(output / 'browser-check.json')
    if result['status'] != 'passed' or len(result['scenes']) != 5: raise ValueError('Incomplete browser acceptance')
    write_json(output / 'acceptance.json', {'status': 'passed', 'finished_at': utc_now(),
        'browser': {'path': relative(root, output / 'browser-check.json'), 'sha256': sha256(output / 'browser-check.json')},
        'source_archive_sha256': sha256(output / 'ui-source.zip'),
        'safety': {'path': relative(root, safety), 'sha256': sha256(safety)},
        'scope': 'New UI acceptance only. Original scientific reports, checkpoints and completion records unchanged.'})
    print(json.dumps({'status': 'passed', 'report': str(output / 'acceptance.json')}), flush=True)


if __name__ == '__main__': main()
