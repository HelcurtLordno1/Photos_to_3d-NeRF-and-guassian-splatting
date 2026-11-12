"""Portable CSV, readable tables and one exportable scientific figure."""
import csv
from pathlib import Path
from .contracts import inside


def scene_tables(output,report):
    rows=[]
    for i,(old,new) in enumerate(zip(report['baseline']['per_view'],report['upgrade']['per_view'])):
        row={'view':i}
        for k in ('psnr','ssim','lpips'):row.update({k+'_baseline':old[k],k+'_upgrade':new[k],k+'_delta':new[k]-old[k]})
        rows.append(row)
    path=output/'per-view.csv'
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=['','## Every held-out view','',
        '|View|Baseline PSNR|Upgrade PSNR|PSNR delta|SSIM delta|LPIPS delta|','|---|---:|---:|---:|---:|---:|']
    for r in rows:lines.append('|'+str(r['view'])+'|'+ '|'.join(f'{r[k]:.6f}' for k in ('psnr_baseline','psnr_upgrade','psnr_delta','ssim_delta','lpips_delta'))+'|')
    if report.get('roi'):
        lines += ['','## Previously locked Tea object ROI','',
            'Baseline: '+str(report['roi']['baseline']['metrics']),
            'Selected upgrade: '+str(report['roi']['upgrade']['metrics']),
            'Original target versus the half-trained reference: '+str(report['roi']['original_target_met'])]
    (output/'report.md').write_text((output/'report.md').read_text(encoding='utf-8')+'\n'.join(lines)+'\n',encoding='utf-8')
    return [path]


def campaign_tables(output,document,reports,selection,confirmation):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=[]
    for r in reports:
        old,new=r['baseline'],r['upgrade'];shape=r['cameras'][0]
        rows.append({'scene':r['scene'],'train':r['train_count'],'eval':r['eval_count'],
            'native_width':shape['width'],'native_height':shape['height'],'gaussian_budget':r['gaussian_budget'],
            'psnr_delta':r['delta']['psnr'],'ssim_delta':r['delta']['ssim'],'lpips_delta':r['delta']['lpips'],
            'baseline_train_seconds_historical':old['training_seconds'],'upgrade_train_seconds':new['training_seconds'],
            'upgrade_optimizer_updates':new['optimizer_updates'],'upgrade_gaussians':new['gaussians'],
            'upgrade_ply_mib':resolve_bytes(output,new['model'])/2**20,
            'upgrade_peak_cuda_allocator_mib':new['peak_cuda_allocated_bytes']/2**20,
            'browser_p95_interval_ms':r['browser']['p95_frame_interval_ms'],
            'browser_parity_mean_db':r['browser']['mean_parity_db'],'browser_parity_min_db':r['browser']['minimum_parity_db']})
    path=output/'summary.csv'
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=['# Final selected upgrade — all five scenes','',document['scope'],
        '','Computation complete; final UI acceptance is tracked separately in completion.json.',
        '',f'Tea TRAIN-only capacity selection: {selection["chosen_budget"]:,} Gaussians; checks: {selection["checks"]}.',
        '', 'Tea paired-seed mean/std/min/max: '+str(confirmation['statistics']),
        '', '|Scene|Train/eval|Native output|PSNR delta|SSIM delta|LPIPS delta|', '|---|---:|---|---:|---:|---:|']
    for r in rows:lines.append(f'|{r["scene"]}|{r["train"]}/{r["eval"]}|{r["native_width"]}x{r["native_height"]}|{r["psnr_delta"]:.5f}|{r["ssim_delta"]:.5f}|{r["lpips_delta"]:.5f}|')
    lines+=['','## Descriptive resource measurements','',
        '|Scene|Historical train min|Upgrade train min|Upgrade updates|Gaussians|PLY MiB|CUDA allocator MiB|Browser p95 ms|',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:lines.append(f'|{r["scene"]}|{r["baseline_train_seconds_historical"]/60:.2f}|{r["upgrade_train_seconds"]/60:.2f}|{r["upgrade_optimizer_updates"]}|{r["upgrade_gaussians"]}|{r["upgrade_ply_mib"]:.2f}|{r["upgrade_peak_cuda_allocator_mib"]:.2f}|{r["browser_p95_interval_ms"]:.2f}|')
    lines += ['','Timing/allocator/device-residency scopes differ. No matched-compute or total-memory improvement is implied.',
        'New4K/8K outputs use existing model weights and calibrated scaled K; there is no GT at those outputs.',
        'Per-view losses, locked ROI, sampled hardware telemetry, exact references and optional-profile failures are retained in scenes/*/report.json.',
        'The original NeRF/Splatfacto baseline results remain in the preserved baseline report linked by report.json.',
        'Only Tea has the declared repeated-seed comparison; other scenes have one fixed-method transfer run. No significance or SOTA claim.',
        '', '![Per-scene native mean deltas](quality-deltas.svg)']
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    fig,axes=plt.subplots(1,2,figsize=(11,4.2),layout='constrained');labels=[r['scene'].replace('custom:tea_sets_2','Tea sets') for r in rows]
    for ax,key,title,favourable in [(axes[0],'psnr_delta','Native PSNR gain (dB)',lambda x:x>=0),(axes[1],'lpips_delta','Native LPIPS delta (lower is better)',lambda x:x<=0)]:
        values=[r[key] for r in rows];ax.barh(labels,values,color=['#24826b' if favourable(v) else '#bd534f' for v in values]);ax.axvline(0,color='#444',linewidth=.8);ax.set_xlabel(title);ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
    fig.suptitle('Selected model versus preserved baseline — matched output per scene')
    fig.savefig(output/'quality-deltas.svg');plt.close(fig)
    return [path,output/'report.md',output/'quality-deltas.svg']


def resolve_bytes(output,ref):
    # output is upgrade/reports/<campaign>; the model references declare owner.
    upgrade=Path(output).parents[1];base=upgrade.parent if ref['owner']=='baseline' else upgrade
    return inside(base,ref['path']).stat().st_size
