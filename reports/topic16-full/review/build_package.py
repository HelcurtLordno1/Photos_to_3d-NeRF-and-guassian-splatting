"""Publish an offline research report and hashed replay source/evidence inventory."""
from pathlib import Path
import argparse
import base64
import hashlib
import html
import json
import re
import subprocess
import zipfile

import markdown


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, record):
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


STYLE = '''body{margin:0;background:#f2f5f9;color:#172539;font:16px/1.7 "Segoe UI",Arial,sans-serif}
main{max-width:1120px;margin:32px auto;padding:48px;background:white;border:1px solid #dce4ef}
h1{font-size:32px;line-height:1.3}h2{margin-top:2em;border-bottom:2px solid #e5edf6;padding-bottom:8px}
h3{margin-top:1.6em}a{color:#1659a4}img{max-width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:13px}
td,th{border:1px solid #dce4ef;padding:9px;text-align:left}th{background:#eaf1f9}tr:nth-child(even){background:#f8fafc}
code{background:#edf2f7;overflow-wrap:anywhere;font-size:.88em}pre{white-space:pre-wrap;background:#edf2f7;padding:16px}
.notice{border-left:4px solid #d79924;background:#fff8e9;padding:16px}.case{border:1px solid #dce4ef;padding:20px;margin:24px 0}
nav{padding:16px;background:#eaf1f9}small{color:#50637b}.table-wrap{overflow-x:auto}
@media(max-width:800px){main{margin:0;padding:18px}h1{font-size:25px}}
@media print{body{background:white;font-size:10pt}main{border:0;margin:0;padding:0;max-width:none}nav{display:none}
img,table{break-inside:avoid}h2,h3{break-after:avoid}a{color:inherit;text-decoration:none}.case{break-inside:avoid}}
'''


def page(title, body):
    return ('<!doctype html><html lang="vi"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{STYLE}</style></head><body><main>{body}</main></body></html>')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    root = parser.parse_args().root.resolve()
    output = Path(__file__).resolve().parent
    selected = read(output.parent / 'g-core.json')
    audit = read(output / 'artifact-audit.json')
    diagnostics = read(output / 'diagnostic-method.json')
    assert audit['status'] == 'PASS' and audit['results_exactly_recomputed']
    assert audit['settings_hash'] == selected['settings_hash'] and audit['run_keys'] == selected['run_keys']
    assert diagnostics['view_count'] == 115 and diagnostics['case_count'] == 14
    notes = output / 'research_review.md'
    report = markdown.markdown(notes.read_text(encoding='utf-8'), extensions=['tables', 'fenced_code', 'toc'])
    def embedded(match):
        path = output / match.group(1)
        if path.suffix.lower() != '.png' or not path.is_file():
            return match.group(0)
        return 'src="data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode() + '"'
    report = re.sub(r'src="([^"]+)"', embedded, report)
    report = re.sub(r'(<table>.*?</table>)', r'<div class="table-wrap">\1</div>', report, flags=re.S)
    nav = '<nav><a href="research_review.md">Markdown</a> · <a href="case-gallery.html">14 camera cases</a> · <a href="replay_runbook.md">Replay runbook</a> · <a href="review.pending.json">Pending endorsement</a></nav>'
    notice = '<p class="notice">AI-authored technical analysis. Human approval and independent GPU replay remain pending. Original G-Core remains BLOCKED.</p>'
    (output / 'research_review.html').write_text(page('Topic 16 — research review', nav + notice + report), encoding='utf-8')
    cases = read(output / 'case-selection.json')
    body = '<h1>Held-out camera evidence — 14 cases</h1><p>115 held-out views: first, worst PNG-MSE of each method, and upper median Nerfacto error. Deduplicated selection. PNG diagnostics do not replace upstream float metrics.</p>' + notice
    body += '<nav><a href="research_review.html">Report</a> · <a href="case-selection.json">Source coordinates/checksums</a> · <a href="per-view-png-diagnostics.csv">All per-view measurements</a></nav>'
    for case in cases:
        body += f'<article class="case"><h2>{html.escape(case["scene"])} — camera {case["eval_index"]}</h2>'
        body += '<p>' + html.escape(', '.join(case['selection_reasons'])) + '</p>'
        body += f'<small>Source {html.escape(case["source"])}; resolution {case["original_size"]}; crop XYXY {case["crop_xyxy"]}</small>'
        body += f'<img src="{case["full_figure"]}" alt="Same-camera GT, Nerfacto and Splatfacto">'
        body += f'<p><a href="{case["crop_figure"]}">Source-pixel crop</a> · <a href="{case["error_figure"]}">Shared-scale RGB error map</a></p></article>'
    (output / 'case-gallery.html').write_text(page('Topic 16 — camera evidence', body), encoding='utf-8')
    review = {
        'settings_hash': selected['settings_hash'], 'run_keys': selected['run_keys'],
        'clean_machine_replay': {'approved': False, 'reviewer': '',
            'notes': 'Not performed. User has one host. Package-free same-host artifact audit does not qualify as fresh GPU setup/data/train/eval.',
            'evidence': ['reports/topic16-full/review/artifact-audit.json', 'reports/topic16-full/review/replay_runbook.md']},
        'research_review': {'approved': False, 'reviewer': '',
            'notes': 'AI technical analysis prepared for actual human review; no human signature or approval has been received.',
            'evidence': ['reports/topic16-full/review/research_review.md', 'reports/topic16-full/results.json',
                         'reports/topic16-full/review/paired-comparisons.json', 'reports/topic16-full/review/case-selection.json',
                         'reports/topic16-full/review/diagnostic-method.json', 'reports/topic16-full/review/evidence-index.json']},
    }
    write(output / 'review.pending.json', review)
    # Include current source even when files have not been committed. Never include
    # data, models, caches, secrets or the generated package itself.
    sources = []
    for folder in ('src', 'scripts', 'configs', 'tests', 'docs', '.github'):
        for path in (root / folder).rglob('*'):
            if path.is_file() and path.suffix.lower() in ('.py', '.ps1', '.psd1', '.json', '.md', '.yml', '.yaml') and '__pycache__' not in path.parts:
                sources.append(path)
    sources += list(root.glob('*.md')) + list(root.glob('*.ps1')) + [root / '.gitignore']
    sources = sorted(set(sources))
    archive = output / 'replay-source.zip'
    records = []
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sources:
            name = path.relative_to(root).as_posix()
            content = path.read_bytes()
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 2, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, content)
            records.append({'path': name, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
    head = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    status = subprocess.run(['git', '-C', str(root), 'status', '--porcelain'], capture_output=True, text=True, check=True).stdout
    write(output / 'replay-source-manifest.json', {
        'schema_version': '1.0', 'purpose': 'Current research implementation snapshot for a separate fresh replay root',
        'original_git_head': head, 'working_tree_dirty': bool(status), 'includes_uncommitted_source': True,
        'not_identical_to_training_source_archives': True,
        'archive': archive.name, 'archive_sha256': sha(archive), 'archive_bytes': archive.stat().st_size,
        'file_count': len(records), 'files': records,
        'excluded': ['raw/processed data', 'model artifacts', 'third-party checkouts', 'Conda environment', 'credentials/caches'],
    })
    files = []
    for path in sorted(output.rglob('*')):
        if not path.is_file() or any(part in ('.venv', '__pycache__') for part in path.relative_to(output).parts):
            continue
        if path.name == 'evidence-index.json':
            continue
        files.append({'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha(path)})
    write(output / 'evidence-index.json', {
        'schema_version': '1.0', 'scope': 'Research review package; original checkpoint artifacts remain under their run keys',
        'settings_hash': selected['settings_hash'], 'run_keys': selected['run_keys'],
        'author': 'Codex (AI assistant)', 'human_approved': False, 'independent_gpu_replay_performed': False,
        'files': files,
    })
    print(f'Published: offline HTML, {len(cases)} cases, {len(files)} evidence checksums, {len(records)} replay source files.', flush=True)


if __name__ == '__main__':
    main()
