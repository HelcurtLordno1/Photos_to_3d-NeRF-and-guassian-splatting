"""Honest Room diagnosis supplement, separated from historical and GS claims."""
from __future__ import annotations

import csv
import html
import os
from pathlib import Path
from urllib.parse import quote

from .contracts import digest_json, inside, read_json, sha256, utc_now, validate_metrics, write_json
from .teacher import reference, resolve


def conditional_effects(rows):
    lookup = {r['id']: r for r in rows}
    effects = []
    for left, description in [('B', 'Camera optimizer off, with appearance already off'),
                               ('A', 'Appearance off, with camera optimizer already off')]:
        if left in lookup and 'C' in lookup:
            effects.append({'comparison': 'C-minus-' + left, 'intervention': description,
                'delta': {k: lookup['C']['metrics'][k] - lookup[left]['metrics'][k]
                    for k in ('psnr', 'ssim', 'lpips')},
                'scope': 'Current fresh controlled arms, one seed; no significance claim'})
    return effects


def gallery(root, output, doc, rows):
    import numpy as np
    from PIL import Image
    baseline = Path(doc['baseline'])
    models = []
    for row in rows:
        if row['id'].startswith('historical-'):
            method = row['id'].removeprefix('historical-'); item = doc['baselines'][method]
            evaluated = read_json(resolve(baseline, item['evaluation']))
            frames = [{k: inside(baseline, item['render_directory']) / f[k] for k in ('gt', 'pred')}
                for f in evaluated['frames']]
        else:
            evaluation = read_json(resolve(root, row['evaluation']))
            frames = [{k: resolve(root, f[k]) for k in ('gt', 'pred')} for f in evaluation['frames']]
        models.append((row['id'], frames))
    def url(path):
        return quote(os.path.relpath(path, output).replace('\\', '/'), safe='/.-_')
    body = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>Room diagnostic — all39 views</title>',
        '<style>body{font:15px system-ui;background:#17191c;color:#eee;margin:24px}section{margin:32px 0}',
        '.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}',
        'img{width:100%;height:auto}figure{margin:0}a{color:#9bcaff}figcaption{padding:8px}</style>',
        '<h1>Room — teacher diagnostic</h1><p>All39 held-out views. Click for original pixels. ',
        'Error maps show mean absolute RGB error ×4 with a fixed scale. Native outputs; no sharpening.</p>']
    for i in range(39):
        body.append(f'<section><h2>Held-out view {i}</h2><div class="grid">')
        gt = models[0][1][i]['gt']
        body.append(f'<figure><a href="{url(gt)}"><img loading="lazy" src="{url(gt)}"></a><figcaption>GT</figcaption></figure>')
        with Image.open(gt) as image: target = np.asarray(image.convert('RGB'), dtype=np.float32) / 255
        for label, frames in models:
            pred = frames[i]['pred']
            with Image.open(pred) as image: pixels = np.asarray(image.convert('RGB'), dtype=np.float32) / 255
            error = np.clip(np.abs(pixels - target).mean(-1) * 4, 0, 1)
            heat = np.zeros((*error.shape, 3), dtype=np.uint8)
            heat[..., 0] = (error * 255).astype('uint8'); heat[..., 1] = (error * 120).astype('uint8')
            path = output / 'errors' / f'{label}-{i:04d}.png'; path.parent.mkdir(exist_ok=True)
            Image.fromarray(heat).save(path)
            body.append(f'<figure><a href="{url(pred)}"><img loading="lazy" src="{url(pred)}"></a>'
                f'<figcaption>{html.escape(label)} · <a href="{url(path)}">error ×4</a></figcaption></figure>')
        body.append('</div></section>')
    body.append('</html>'); path = output / 'gallery.html'
    path.write_text('\n'.join(body), encoding='utf-8')
    return [path, *sorted((output / 'errors').glob('*.png'))]


def publish(root, doc, state, final=False):
    output = root / 'reports' / doc['study']; output.mkdir(parents=True, exist_ok=True)
    baseline = Path(doc['baseline']); rows = []
    for method in ('nerfacto', 'splatfacto'):
        path = output / 'historical' / (method + '-common.json')
        if not path.exists(): continue
        common = read_json(path); item = doc['baselines'][method]
        native = read_json(resolve(baseline, item['metrics']))['results']
        manifest = read_json(resolve(baseline, item['manifest']))
        rows.append({'id': 'historical-' + method, 'scope': 'Historical reference, unchanged weights',
            'camera_optimizer': 'SO3xR3' if method == 'nerfacto' else 'off',
            'appearance': 'average' if method == 'nerfacto' else 'not-applicable',
            'metrics': common['metrics'], 'native_metrics': native, 'per_view': common['frames'],
            'common': reference(root, path), 'training_seconds': manifest['execution_metrics']['wall_time_seconds'],
            'sampled_peak_device_vram_mb': manifest['execution_metrics']['peak_vram_mb']})
    for arm in ('A', 'B', 'C'):
        if state['arms'].get(arm, {}).get('status') != 'complete': continue
        folder = inside(root, state['arms'][arm]['output'])
        trained = read_json(folder / 'training.json'); evaluated = read_json(folder / 'evaluation.json')
        common = read_json(folder / 'common.json'); execution = read_json(folder / 'train-execution.json')
        if trained['step'] != 29999 or not trained['fresh_initialization'] or not evaluated['all39_gt_pixels_equal_historical']:
            raise ValueError('Incomplete teacher arm cannot enter the scientific report')
        rows.append({'id': arm, 'scope': 'Fresh30k current controlled arm',
            'camera_optimizer': 'SO3xR3' if arm == 'B' else 'off',
            'appearance': 'average' if arm == 'A' else 'off',
            'metrics': common['metrics'], 'native_metrics': evaluated['native_metrics'],
            'per_view': common['frames'], 'common': reference(root, folder / 'common.json'),
            'training': reference(root, folder / 'training.json'),
            'evaluation': reference(root, folder / 'evaluation.json'),
            'initialization': reference(root, folder / 'initialization.json'),
            'recipe_diff': reference(root, folder / 'recipe-diff.json'),
            'execution': reference(root, folder / 'train-execution.json'),
            'training_seconds': trained['training_seconds'],
            'sampled_peak_device_vram_mb': execution['sampled_peak_device_vram_mb'],
            'camera_corrections': trained['camera_corrections'], 'attempts': state['arms'][arm]['attempts']})
    for row in rows:
        validate_metrics({'results': row['metrics']})
        if len(row['per_view']) != 39: raise ValueError('Missing per-view results')
    completed = [r['id'] for r in rows if r['id'] in ('A', 'B', 'C')]
    if final and (set(completed) != {'A', 'B', 'C'} or len(rows) != 5):
        raise ValueError('Teacher report requires all three fresh arms and both historical common evaluations')
    old = next((r for r in rows if r['id'] == 'historical-nerfacto'), None)
    if old:
        for row in rows:
            row['delta_vs_historical_nerfacto'] = {k: row['metrics'][k] - old['metrics'][k] for k in ('psnr', 'ssim', 'lpips')}
    limitations = [
        'Historical on/average cell is not a new contemporaneous control; do not infer a full2x2 interaction.',
        'A–C are single-seed fresh runs; no statistical significance or all-scene generalization.',
        'Teacher29–31dB is an expected range, not a score target or execution gate.',
        'Common metrics use saved RGB8. Original float/native metrics are separate and may differ.',
        'No appearance fitting on test pixels, no color correction, no test-driven parameter search.',
        'Literature scores require matched implementation/split/resolution/budget; Room name alone is insufficient.',
        'Original submitted DOCX and NeRF-vs-GS ranking remain historical/provisional; GS improvements do not repair the Nerfacto diagnosis.']
    candidate = next((r for r in rows if r['id'] == 'C'), None)
    diagnostic = {'expected_c_psnr_db': [29, 31], 'expectation_is_acceptance_gate': False,
        'c_native_psnr_db': candidate['native_metrics']['psnr'] if candidate else None,
        'cause_status': 'Evaluate conditional effects and gallery; an observed gain alone does not prove all confounds resolved',
        'if_unexplained': 'Audit normalization, camera/GT alignment, distortion/crop, photometric variation and convergence before separately declaring further experiments'}
    payload = {'schema_version': 'teacher-room-supplement-1', 'status': 'complete' if final else 'running',
        'study': doc['study'], 'completed_arms': completed, 'rows': rows,
        'conditional_effects': conditional_effects(rows), 'diagnostic': diagnostic,
        'baseline_runtime_matches_current': doc['baseline_runtime_matches_current'],
        'limitations': limitations, 'split': doc['split'], 'source_pin': doc['source_pin'],
        'runtime_sha256': doc['runtime_sha256'], 'updated_at': utc_now()}
    fields = ['id', 'camera_optimizer', 'appearance', 'psnr', 'ssim', 'lpips',
        'native_psnr', 'native_ssim', 'native_lpips', 'training_seconds', 'sampled_peak_device_vram_mb', 'scope']
    with (output / 'results.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fields); writer.writeheader()
        for row in rows:
            writer.writerow({**{k: row[k] for k in fields if k in row}, **row['metrics'],
                **{'native_' + k: row['native_metrics'][k] for k in ('psnr', 'ssim', 'lpips')}})
    with (output / 'per-view.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, ['id', 'index', 'psnr', 'ssim', 'lpips']); writer.writeheader()
        for row in rows:
            for frame in row['per_view']:
                writer.writerow({'id': row['id'], **{k: frame[k] for k in ('index', 'psnr', 'ssim', 'lpips')}})
    lines = ['# Room — teacher Nerfacto diagnostic supplement', '',
        'Status: ' + payload['status'] + '. Fresh arms completed: ' + ', '.join(completed),
        '', '272train /39held-out, seed42,30k,1557x1037. Common saved-RGB evaluator.', '',
        '|Run|Camera|Appearance|PSNR|SSIM|LPIPS|Native float PSNR|Train min|',
        '|---|---|---|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f'|{r["id"]}|{r["camera_optimizer"]}|{r["appearance"]}|{r["metrics"]["psnr"]:.6f}|'
            f'{r["metrics"]["ssim"]:.6f}|{r["metrics"]["lpips"]:.6f}|{r["native_metrics"]["psnr"]:.6f}|{r["training_seconds"]/60:.2f}|')
    lines += ['', '## Conditional interventions (current fresh arms)', '']
    for effect in payload['conditional_effects']:
        lines.append(effect['comparison'] + ': ' + effect['intervention'] + '. Delta: ' + str(effect['delta']))
    if candidate:
        score = candidate['native_metrics']['psnr']
        lines += ['', f'C native PSNR is {score:.6f}dB. Teacher expected approximately29–31dB.',
            'Expectation reached.' if 29 <= score <= 31 else
            ('Above the expected interval; inspect controls and alignment before attributing the gain.' if score > 31 else
             'Below the expected interval: the low-score concern is not fully resolved; preserve this negative finding and audit remaining causes.'),
            'The queue does not tune or choose a new NeRF configuration against these test scores.']
    lines += ['', '## Limits and interpretation', '', *['- ' + s for s in limitations], '',
        'Current package fingerprint matches historical Nerfacto: ' + str(doc['baseline_runtime_matches_current']),
        'Package identity alone does not prove identical executable binaries or bitwise training.', '',
        'Full-resolution evidence: [gallery](gallery.html), [per-view CSV](per-view.csv), [exact evidence](report.json).',
        'No historical manuscript, baseline checkpoint or metric has been overwritten.']
    (output / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    extra = gallery(root, output, doc, rows) if final else []
    payload['report_artifacts'] = [reference(root, p) for p in [output / 'results.csv', output / 'per-view.csv', output / 'report.md', *extra]]
    write_json(output / 'report.json', payload)
    return [output / 'report.json', output / 'report.md', output / 'results.csv', output / 'per-view.csv', *extra]
