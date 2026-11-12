import { lazy, Suspense, useState } from 'react';
import type { Catalog, Run, Camera } from './types';
import s from './studio.module.css';
const Viewer = lazy(() => import('./Viewer'));
type Metrics = { psnr: number; ssim: number; lpips: number };
type Frame = { gt: string; pred: string };
type Choice = { id: string; label: string; metrics?: Metrics; roi?: Metrics; frames?: Frame[];
  model?: { id: string; label: string; cameras: Camera[]; run: Run }; };
export default function Quality({ catalog, scene, paused }: { catalog: Catalog; scene: string; paused: boolean }) {
  const research=catalog.visual_research;
  const experiment=catalog.quality?.experiments.find(e=>e.scene===scene);
  const [selected,setSelected]=useState('improvedgs'),[resolution,setResolution]=useState('native'),
    [index,setIndex]=useState(0),[show3d,setShow3d]=useState(false),[details,setDetails]=useState(false);
  if(!experiment)return <section className={s.research}><h2>Visual quality</h2><p>{catalog.quality?.reason||'No completed quality experiment for this scene.'}</p></section>;
  const q1=experiment.rows.find(r=>r.tag==='native-candidate-'+resolution)!;
  const half=experiment.rows.find(r=>r.tag==='half-control-'+resolution)!;
  const choices:Choice[]=[...(research?.q2?.rows.map(r=>{
    const cell=research.inspection?.cells.find(c=>c.method===r.method&&c.resolution===resolution&&c.variant==='direct');
    return {id:r.method,label:r.method==='improvedgs'?'Improved-GS · 300k · research candidate':'AbsGS · same-backend control',
      metrics:resolution==='native'?r.metrics:cell?.metrics,roi:resolution==='native'?r.roi_metrics:undefined,
      frames:resolution==='native'?r.frames:cell?.frames,model:r.model};
  })||[]),{id:'q1',label:'Q1 · native Splatfacto reference',metrics:q1.metrics,roi:q1.roi_metrics,frames:q1.frames,model:experiment.models[0]}];
  const current=choices.find(c=>c.id===selected)||choices[0];
  const reference=current.id==='q1'?{label:'30k half-trained control',metrics:half.metrics,frames:half.frames}:
    current.id==='absgs'?{label:'Q1 native reference',metrics:q1.metrics,frames:q1.frames}:choices.find(c=>c.id==='absgs');
  const model=current.model;
  const nativeHalf=experiment.rows.find(r=>r.tag==='half-control-native')?.roi_metrics;
  const target=resolution==='native'&&current.roi&&nativeHalf?current.roi.psnr>=nativeHalf.psnr+1&&current.roi.lpips<=nativeHalf.lpips*.85:null;
  return <section className={s.research}>
    <h2>Tea · Visual quality</h2>
    <p>105 train / 15 held-out views · 30k schedule · seed 42. Research results; compare within the same output resolution.</p>
    <div className={s.panelTools}>
      <label>Model <select aria-label="Quality model" value={current.id} onChange={e=>setSelected(e.target.value)}>{choices.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select></label>
      <label>Saved CUDA output <select aria-label="Quality resolution" value={resolution} onChange={e=>setResolution(e.target.value)}><option value="native">719 × 1279 · native</option><option value="half">359 × 639 · half</option></select></label>
      <label>Held-out view <select aria-label="Quality view" value={index} onChange={e=>setIndex(Number(e.target.value))}>{q1.frames.map((_,i)=><option key={i} value={i}>#{i}</option>)}</select></label>
    </div>
    <h3>{current.label}</h3>
    <p>Original object ROI target versus the half-trained 30k control: <b>{target===null?'not evaluated at this output':target?'met':'not met'}</b> (+1 dB PSNR and −15% LPIPS). This verdict belongs to the selected model.</p>
    <table aria-label="Quality benchmark"><thead><tr><th>Model at selected output</th><th>PSNR ↑</th><th>SSIM ↑</th><th>LPIPS ↓</th><th>ROI LPIPS ↓</th></tr></thead><tbody>
      {choices.map(c=><tr key={c.id} aria-selected={c.id===current.id}><th>{c.label}{c.id===current.id?' · selected':''}</th><td>{c.metrics?.psnr.toFixed(4)??'pending'}</td><td>{c.metrics?.ssim.toFixed(5)??'pending'}</td><td>{c.metrics?.lpips.toFixed(5)??'pending'}</td><td>{c.roi?.lpips.toFixed(5)??'not measured'}</td></tr>)}
    </tbody></table>
    {current.metrics&&reference?.metrics&&<p>Selected − {reference.label}: PSNR {(current.metrics.psnr-reference.metrics.psnr).toFixed(4)} dB; SSIM {(current.metrics.ssim-reference.metrics.ssim).toFixed(5)}; LPIPS {(current.metrics.lpips-reference.metrics.lpips).toFixed(5)}. Common RGB8 evaluator on identical cameras/GT.</p>}
    {current.frames&&reference?.frames?<div style={{display:'grid',gridTemplateColumns:'repeat(3,minmax(0,1fr))',gap:12}}>
      {[['Ground truth',current.frames[index].gt],[reference.label,reference.frames[index].pred],[current.label,current.frames[index].pred]].map(([label,url])=><figure key={label} style={{margin:0}}><figcaption>{label} · #{index}</figcaption><a href={url} target="_blank" rel="noreferrer"><img src={url} alt={label+' view '+index} style={{width:'100%'}}/></a></figure>)}
    </div>:<p role="status">This model has no verified saved images at the selected output yet. Native evidence and the 3D checkpoint remain available.</p>}
    {model&&<><p>3D uses the same selected checkpoint. Browser viewport resolution differs from the saved CUDA output above.</p><button onClick={()=>setShow3d(!show3d)} disabled={paused}>{(show3d?'Close ':'Open ')+current.id+' 3D'}</button>
      {paused&&<p>Research compute is active; interactive GPU rendering is paused.</p>}
      {show3d&&!paused&&<Suspense fallback={<p>Loading selected model…</p>}><Viewer key={model.id+index} catalog={catalog} mode="splatfacto" paused={paused} onMove={()=>{}} dataset={{id:model.id,title:current.label,methods:{splatfacto:model.run},views:model.cameras.map(camera=>({camera}))}} initialCamera={model.cameras[index]}/></Suspense>}
    </>}
    {research?.q2&&<><h3>Hardware cost · same-backend pair</h3><p>{research.q2.comparison}</p><table><thead><tr><th>Method</th><th>Gaussians</th><th>Optimizer updates</th><th>Train minutes</th><th>Offline CUDA FPS</th></tr></thead><tbody>{research.q2.rows.map(r=><tr key={r.method}><th>{r.method}</th><td>{r.gaussians.toLocaleString()}</td><td>{r.optimizer_updates.toLocaleString()}</td><td>{(r.training_seconds/60).toFixed(1)}</td><td>{r.offline_fps.toFixed(2)}</td></tr>)}</tbody></table><p>Offline FPS is not browser FPS. One seed on one capture; LPIPS and object details do not improve at every view.</p></>}
    {research?.confirmation&&<p>Confirmation: {research.confirmation.study} · {research.confirmation.status} · {research.confirmation.phase}. Native tmux/Status provides live progress.</p>}
    {research?.inspection&&<><h3>Measured browser profile</h3><p>SH3 · classic · {research.inspection.viewer_encoding} · LOD off. Parity uses calibrated native output; frame intervals use 1280 × 720, DPR 1, moving camera, GPU completion included. These are separate measurements from quality against ground truth.</p><table aria-label="Browser audit"><thead><tr><th>Model</th><th>Mean parity dB</th><th>Minimum parity dB</th><th>p95 frame interval ms</th></tr></thead><tbody>{research.inspection.browser.map(r=><tr key={r.method}><th>{r.method}</th><td>{r.mean_parity_db.toFixed(2)}</td><td>{r.minimum_parity_db.toFixed(2)}</td><td>{r.p95_frame_interval_ms.toFixed(2)}</td></tr>)}</tbody></table><p>Candidate gate: {research.inspection.status}. AbsGS parity misses remain visible; they do not represent the candidate.</p></>}
    {research?.confirmation_report&&<><h3>Paired seed confirmation</h3><p>Signal gate: {research.confirmation_report.signal_gate_met?'met':'not met'}. All declared seeds are included.</p><table><thead><tr><th>Paired metric</th><th>Mean</th><th>Std across seeds</th><th>Min</th><th>Max</th></tr></thead><tbody>{Object.entries(research.confirmation_report.statistics).map(([k,r])=><tr key={k}><th>{k}</th><td>{r.mean.toFixed(5)}</td><td>{r.std.toFixed(5)}</td><td>{r.min.toFixed(5)}</td><td>{r.max.toFixed(5)}</td></tr>)}</tbody></table></>}
    <button aria-expanded={details} onClick={()=>setDetails(!details)}>Historical and renderer diagnostics</button>
    {details&&<><p>{experiment.scope}</p><p>Q1 original native ROI target: {experiment.numeric_target_met?'met':'not met'}. Historical Q1 half-resolution regression is retained.</p>
      <table><thead><tr><th>Historical checkpoint/output</th><th>PSNR</th><th>SSIM</th><th>LPIPS</th></tr></thead><tbody>{experiment.rows.map(r=><tr key={r.tag}><th>{r.tag}</th><td>{r.metrics.psnr.toFixed(4)}</td><td>{r.metrics.ssim.toFixed(5)}</td><td>{r.metrics.lpips.toFixed(5)}</td></tr>)}</tbody></table>
      {research?.inspection&&<p>Current checkpoint scale audit: {research.inspection.status}. {JSON.stringify(research.inspection.checks)}</p>}
      <p>AA alone is not full Mip-Splatting. P0/P1 renderer measurements do not replace reconstruction metrics or independent scene validation.</p>
    </>}
  </section>;
}
