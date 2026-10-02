"""Derived diagnostics from saved PNGs; never replace upstream official metrics."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math

import numpy as np
from PIL import Image, ImageDraw
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rgb(path):
    with Image.open(path) as image:
        return np.asarray(image.convert('RGB')).copy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    root = parser.parse_args().root.resolve()
    output = Path(__file__).resolve().parent
    figures = output / 'figures'
    figures.mkdir(exist_ok=True)
    rows = read(output.parent / 'results.json')
    scenes = sorted({row['scene'] for row in rows})
    comparisons, per_view, selected = [], [], []
    for scene in scenes:
        pair = {r['method']: r for r in rows if r['scene'] == scene}
        n, s = pair['nerfacto'], pair['splatfacto']
        comparisons.append({'scene': scene, 'psnr_delta_db': s['psnr'] - n['psnr'],
                            'ssim_delta': s['ssim'] - n['ssim'], 'lpips_delta': s['lpips'] - n['lpips'],
                            'fps_ratio_splat_over_nerf': s['offline_fps'] / n['offline_fps'],
                            'time_ratio_splat_over_nerf': s['train_seconds'] / n['train_seconds'],
                            'vram_ratio_splat_over_nerf': s['peak_vram_mb'] / n['peak_vram_mb'],
                            'checkpoint_ratio_splat_over_nerf': s['checkpoint_bytes'] / n['checkpoint_bytes']})
        evals = {m: read(root / 'artifacts' / 'metrics' / r['run_key'] / 'evaluation.json') for m, r in pair.items()}
        directories = {m: root / 'artifacts' / 'renders' / r['run_key'] for m, r in pair.items()}
        scene_views = []
        for i, frame in enumerate(evals['nerfacto']['frames']):
            other = evals['splatfacto']['frames'][i]
            assert frame['source'] == other['source'] and frame['gt_sha256'] == other['gt_sha256']
            gt = rgb(directories['nerfacto'] / frame['gt']).astype(np.float32) / 255
            entry = {'scene': scene, 'eval_index': i, 'source': frame['source']}
            for method in ('nerfacto', 'splatfacto'):
                f = evals[method]['frames'][i]
                pred = rgb(directories[method] / f['pred']).astype(np.float32) / 255
                assert pred.shape == gt.shape
                mse = float(np.mean(np.square(gt - pred), dtype=np.float64))
                entry[f'{method}_png_mse'] = mse
                entry[f'{method}_png_psnr_db'] = -10 * math.log10(mse) if mse > 0 else None
            scene_views.append(entry)
        per_view.extend(scene_views)
        order = sorted(range(len(scene_views)), key=lambda i: scene_views[i]['nerfacto_png_mse'])
        selections = [(0, 'first'), (order[-1], 'worst-nerfacto-png-mse'),
                      (max(range(len(scene_views)), key=lambda i: scene_views[i]['splatfacto_png_mse']), 'worst-splatfacto-png-mse'),
                      (order[len(order) // 2], 'median-nerfacto-png-mse')]
        used = set()
        for i, reason in selections:
            if i in used:
                next(item for item in selected if item['scene'] == scene and item['eval_index'] == i)['selection_reasons'].append(reason)
                continue
            used.add(i)
            f = evals['nerfacto']['frames'][i]
            paths = [directories['nerfacto'] / f['gt']] + [directories[m] / evals[m]['frames'][i]['pred'] for m in ('nerfacto', 'splatfacto')]
            images = [Image.fromarray(rgb(p)) for p in paths]
            w, h = images[0].size
            crop_w, crop_h = min(w // 2, 640), min(h // 2, 640)
            x, y = (w - crop_w) // 2, (h - crop_h) // 2
            box = (x, y, x + crop_w, y + crop_h)
            slug = scene.replace(':', '-')
            name = f'{slug}-view-{i:03d}'
            preview_w = 400
            preview_h = round(h * preview_w / w)
            sheet = Image.new('RGB', (preview_w * 3, preview_h + 40), 'white')
            draw = ImageDraw.Draw(sheet)
            crop_sheet = Image.new('RGB', (crop_w * 3, crop_h + 40), 'white')
            cd = ImageDraw.Draw(crop_sheet)
            for j, (im, label) in enumerate(zip(images, ('Ground truth', 'Nerfacto', 'Splatfacto'))):
                sheet.paste(im.resize((preview_w, preview_h), Image.Resampling.LANCZOS), (j * preview_w, 40))
                draw.text((j * preview_w + 5, 5), f'{label} | view {i} | {reason}', fill='black')
                crop_sheet.paste(im.crop(box), (j * crop_w, 40))
                cd.text((j * crop_w + 5, 4), label, fill='black')
                cd.text((j * crop_w + 5, 20), f'view {i} | crop', fill='black')
            sheet.save(figures / f'{name}-full.png')
            crop_sheet.save(figures / f'{name}-crop.png')
            gt = np.asarray(images[0]).astype(np.float32) / 255
            heat, axes = plt.subplots(1, 2, figsize=(10, 4))
            for ax, im, method in zip(axes, images[1:], ('nerfacto', 'splatfacto')):
                error = np.mean(np.abs(gt - np.asarray(im).astype(np.float32) / 255), axis=2)
                plot = ax.imshow(error, cmap='magma', vmin=0, vmax=0.15)
                ax.set_title(f'{method}: mean absolute RGB error')
                ax.axis('off')
            heat.colorbar(plot, ax=axes.ravel().tolist(), label='RGB error (0-1); shared scale, clipped at 0.15')
            heat.savefig(figures / f'{name}-error.png', dpi=140, bbox_inches='tight')
            plt.close(heat)
            selected.append({'scene': scene, 'eval_index': i, 'source': f['source'], 'selection_reasons': [reason],
                             'original_size': [w, h], 'crop_xyxy': box,
                             'run_keys': [n['run_key'], s['run_key']],
                             'inputs': [{'path': p.relative_to(root).as_posix(), 'sha256': checksum(p)} for p in paths],
                             'full_figure': f'figures/{name}-full.png', 'crop_figure': f'figures/{name}-crop.png',
                             'error_figure': f'figures/{name}-error.png'})
        print(f'{scene}: {len(scene_views)} held-out views, {len(used)} selected cases', flush=True)
    write(output / 'paired-comparisons.json', comparisons)
    write(output / 'case-selection.json', selected)
    for name, records in (('paired-comparisons.csv', comparisons), ('per-view-png-diagnostics.csv', per_view)):
        with (output / name).open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    write(output / 'diagnostic-method.json', {
        'scope': 'CPU comparison of already saved 8-bit RGB PNGs; no model inference',
        'official_metrics': '../results.json: upstream float-render PSNR/SSIM/LPIPS remain authoritative',
        'png_psnr': '-10*log10(mean((GT/255-PRED/255)^2)); float32 differences, float64 mean',
        'warning': 'PNG quantization makes these diagnostic PSNR values differ from upstream float-render PSNR',
        'selection': 'first, largest Nerfacto PNG MSE, largest Splatfacto PNG MSE, upper median Nerfacto PNG MSE; deduplicated',
        'crops': 'center crop: width=min(original_width//2,640); height=min(original_height//2,640); XYXY in case-selection.json',
        'heatmap': 'mean absolute RGB difference; both methods share fixed 0..0.15 color scale',
        'view_count': len(per_view), 'case_count': len(selected),
    })
    metrics = [('psnr', 'PSNR (dB); higher better', False), ('ssim', 'SSIM; higher better', False),
               ('lpips', 'LPIPS; lower better', False), ('offline_fps', 'Synchronized FPS; log scale', True),
               ('train_seconds', 'Training time (minutes)', False), ('checkpoint_bytes', 'Checkpoint (MiB); log scale', True)]
    chart, axes = plt.subplots(2, 3, figsize=(14, 8))
    x = np.arange(len(scenes))
    for ax, (metric, label, log) in zip(axes.ravel(), metrics):
        for j, method in enumerate(('nerfacto', 'splatfacto')):
            values = [next(r[metric] for r in rows if r['scene'] == scene and r['method'] == method) for scene in scenes]
            divisor = 60 if metric == 'train_seconds' else (2**20 if metric == 'checkpoint_bytes' else 1)
            ax.bar(x + (j - 0.5) * 0.36, np.asarray(values) / divisor, width=0.36, label=method)
        ax.set_xticks(x, [s.replace('custom:', '') for s in scenes], rotation=15)
        ax.set_title(label)
        if log:
            ax.set_yscale('log')
        ax.grid(axis='y', alpha=0.25)
    axes[0, 0].legend()
    chart.suptitle('Topic 16: observed primary results, 30k steps / seed 42 / one A4500 Laptop\nCustom scene is a separate data group; no pooled score or multi-seed confidence interval')
    chart.tight_layout()
    chart.savefig(figures / 'research-comparison.png', dpi=170)
    plt.close(chart)


if __name__ == '__main__':
    main()
