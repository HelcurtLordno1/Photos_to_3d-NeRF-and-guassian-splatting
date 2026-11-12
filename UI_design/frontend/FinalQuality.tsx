import { lazy, Suspense, useRef, useState } from 'react';
import type { Catalog, FinalScene } from './types';
import type { ViewerHandle } from './Viewer';
import s from './studio.module.css';
const Viewer = lazy(() => import('./Viewer'));
const TeaArchive = lazy(() => import('./Quality'));

export default function FinalQuality({ catalog, data, paused }: { catalog: Catalog; data: FinalScene; paused: boolean }) {
  const [selected, setSelected] = useState<'baseline' | 'upgrade'>('upgrade');
  const [edge, setEdge] = useState(0), [view, setView] = useState(0);
  const [show3d, setShow3d] = useState(false), [archive, setArchive] = useState(false);
  const viewer = useRef<ViewerHandle>(null);
  const current = data.models[selected];
  const available = edge ? [...new Set(data.high_resolution.filter(p => p.edge === edge).map(p => p.view))].sort((a, b) => a - b) : data.cameras.map((_, i) => i);
  const index = available.includes(view) ? view : available[0] ?? 0;
  const changeView = (i: number) => { setView(i); viewer.current?.preset(data.cameras[i]); };
  const sources: { label: string; url?: string; model?: string }[] = edge ? (['baseline', 'upgrade'] as const).map(id => ({
    model: id, label: data.models[id].label,
    url: data.high_resolution.find(p => p.edge === edge && p.view === index && p.model === id)?.url,
  })) : [
    { label: 'Ground truth · native', url: data.models.upgrade.frames[index].gt },
    ...(['baseline', 'upgrade'] as const).map(id => ({ model: id, label: data.models[id].label, url: data.models[id].frames[index].pred })),
  ];
  return <section className={s.research} data-final-scene={data.scene}>
    <h2>Baseline and selected upgrade</h2>
    <p>{data.train_count} training / {data.eval_count} held-out views · 30k schedule · seed 42. Historical baseline models remain available in the 3D gallery.</p>
    <div className={s.panelTools}>
      <label>Model <select aria-label="Final model" value={selected} onChange={e => setSelected(e.target.value as 'baseline' | 'upgrade')}>
        <option value="baseline">{data.models.baseline.label}</option><option value="upgrade">{data.models.upgrade.label}</option>
      </select></label>
      <label>Saved output <select aria-label="Final output" value={edge} onChange={e => { setEdge(Number(e.target.value)); changeView(0); }}>
        <option value={0}>Native · benchmark GT</option>
        {[3840, 7680].map(value => <option key={value} value={value} disabled={!data.high_resolution.some(p => p.edge === value)}>{value === 3840 ? '4K' : '8K'} long edge · render only</option>)}
      </select></label>
      <label>Camera <select aria-label="Final view" value={index} onChange={e => changeView(Number(e.target.value))}>{available.map(i => <option key={i} value={i}>#{i}</option>)}</select></label>
    </div>
    <h3>{current.label} · selected</h3>
    {edge > 0 && <p>High-resolution render from the same model, with scaled camera intrinsics. No GT benchmark or claim of additional captured detail at this output. Integer pixel dimensions retain the capture aspect ratio.</p>}
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${sources.length}, minmax(0, 1fr))`, gap: 12 }}>
      {sources.map(item => <figure key={item.label} style={{ margin: 0, outline: item.model === selected ? '2px solid #56b8bd' : undefined }}>
        <figcaption>{item.label} · #{index}{item.model === selected ? ' · selected' : ''}</figcaption>
        {item.url ? <a href={item.url} target="_blank" rel="noreferrer"><img data-final-image src={item.url} alt={`${item.label} view ${index}`} style={{ width: '100%' }} /></a> : <p>Profile unavailable; native evidence is retained.</p>}
      </figure>)}
    </div>
    <h3>Native held-out benchmark · all {data.eval_count} views</h3>
    <p>One RGB8 evaluator and identical canonical GT/cameras. This table always describes native output, including when a 4K/8K render is selected.</p>
    <table aria-label="Final benchmark"><thead><tr><th>Model</th><th>PSNR ↑</th><th>SSIM ↑</th><th>LPIPS ↓</th><th>Gaussians</th><th>PLY MiB</th></tr></thead><tbody>
      {(['baseline', 'upgrade'] as const).map(id => { const row = data.models[id]; return <tr key={id} aria-selected={id === selected}><th>{row.label}</th><td>{row.metrics.psnr.toFixed(4)}</td><td>{row.metrics.ssim.toFixed(5)}</td><td>{row.metrics.lpips.toFixed(5)}</td><td>{row.gaussians.toLocaleString()}</td><td>{(row.bytes / 2 ** 20).toFixed(1)}</td></tr>; })}
    </tbody></table>
    <p>Upgrade − baseline: PSNR {data.delta.psnr.toFixed(4)} dB · SSIM {data.delta.ssim.toFixed(5)} · LPIPS {data.delta.lpips.toFixed(5)}. {data.quality_dominates ? 'All three mean metrics are favourable.' : 'The upgrade does not improve every mean metric.'} Per-view losses remain in the report.</p>
    {data.roi && <p>Locked Tea object ROI · {current.label}: PSNR {data.roi[selected].psnr.toFixed(4)}, SSIM {data.roi[selected].ssim.toFixed(5)}, LPIPS {data.roi[selected].lpips.toFixed(5)}.{selected === 'upgrade' ? ` Original upgrade ROI target: ${data.roi.original_target_met ? 'met' : 'not met'}.` : ''}</p>}
    <button disabled={paused} onClick={() => setShow3d(!show3d)}>{show3d ? 'Close' : 'Open'} selected 3D</button>
    <p>3D uses the selected checkpoint/camera and the browser viewport size. Saved output controls the images above.</p>
    {paused && <p>Managed compute is active; interactive GPU rendering is paused.</p>}
    {show3d && !paused && <Suspense fallback={<p>Loading selected model…</p>}><Viewer ref={viewer} key={data.scene + selected} catalog={catalog} mode="splatfacto" onMove={() => { }} initialCamera={data.cameras[index]}
      dataset={{ id: data.scene + ':' + selected, title: current.label, methods: { splatfacto: current.run }, views: data.cameras.map(camera => ({ camera })) }} /></Suspense>}
    <p>Browser candidate: mean parity {data.browser.mean_parity_db.toFixed(2)} dB, minimum {data.browser.minimum_parity_db.toFixed(2)} dB; p95 frame interval {data.browser.p95_frame_interval_ms.toFixed(2)} ms at 1280×720, DPR 1, SH3, LOD off. {data.browser.parity_met ? 'Measured parity target met.' : 'Approximate preview: parity target missed.'}</p>
    <details><summary>Costs, limitations and full report</summary>
      <p>{data.scope}</p><p>Historical baseline training: {(data.models.baseline.training_seconds / 60).toFixed(1)} min; current upgrade training: {(data.models.upgrade.training_seconds / 60).toFixed(1)} min. Setup/evaluation/checkpoint accounting and runtime differ; these are descriptive costs.</p>
      <p>Views with lower upgrade PSNR: {data.per_view_delta.filter(r => r.psnr < 0).map(r => '#' + r.view).join(', ') || 'none'}. Lower LPIPS and higher SSIM must also be checked.</p>
      {data.profile_notes.map((p, i) => <p key={i}>{p.model} · {p.edge} long edge: {p.reason}</p>)}
      <p><a href={data.report_url} target="_blank" rel="noreferrer">Open full measured report</a></p>
      {catalog.final_delivery?.files && <p>{Object.entries(catalog.final_delivery.files).map(([label, url]) => <a key={label} href={url} target="_blank" rel="noreferrer" style={{ marginRight: 16 }}>{label}</a>)}</p>}
    </details>
    {data.scene === 'custom:tea_sets_2' && <><button aria-expanded={archive} onClick={() => setArchive(!archive)}>Tea research archive</button>{archive && <Suspense fallback={<p>Loading archived research…</p>}><TeaArchive catalog={catalog} scene={data.scene} paused={paused} /></Suspense>}</>}
  </section>;
}
