import { lazy, Suspense, useState } from 'react';
import type { Catalog } from './types';
import s from './studio.module.css';
const Viewer = lazy(() => import('./Viewer'));

export default function Quality({
  catalog,
  scene,
  paused,
}: {
  catalog: Catalog;
  scene: string;
  paused: boolean;
}) {
  const [resolution, setResolution] = useState('native');
  const [index, setIndex] = useState(0);
  const [show3d, setShow3d] = useState(false);
  const [modelIndex, setModelIndex] = useState(0);
  const experiment = catalog.quality?.experiments.find((e) => e.scene === scene);
  if (!experiment)
    return (
      <section className={s.research}>
        <h2>Visual quality research</h2>
        <p>{catalog.quality?.reason || 'No completed quality experiment for this scene.'}</p>
      </section>
    );
  const rows = experiment.rows.filter((r) => r.tag.endsWith('-' + resolution));
  const control = rows.find((r) => r.tag.startsWith('half-control'))!;
  const candidate = rows.find((r) => r.tag.startsWith('native-candidate'))!;
  const research = catalog.visual_research;
  const models = [
    ...experiment.models,
    ...(research?.q2?.rows.flatMap((r) => (r.model ? [r.model] : [])) || []),
  ];
  const model = models[modelIndex] || models[0];
  return (
    <section className={s.research}>
      <h2>{experiment.label}</h2>
      <p>{experiment.scope}</p>
      <p>
        ROI target (+1 dB and −15% LPIPS):{' '}
        <b>{experiment.numeric_target_met ? 'met' : 'not met'}</b>. Training across attempts:{' '}
        {(experiment.train_seconds / 60).toFixed(1)} min.
      </p>
      <div className={s.panelTools}>
        <label>
          Output resolution{' '}
          <select
            aria-label="Quality resolution"
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
          >
            <option value="native">719 × 1279 · native</option>
            <option value="half">359 × 639 · direct half</option>
          </select>
        </label>
        <label>
          Held-out view{' '}
          <select
            aria-label="Quality view"
            value={index}
            onChange={(e) => setIndex(Number(e.target.value))}
          >
            {candidate.frames.map((f) => (
              <option key={f.index} value={f.index}>
                #{f.index}
              </option>
            ))}
          </select>
        </label>
      </div>
      <table>
        <thead>
          <tr>
            <th>Checkpoint</th>
            <th>PSNR ↑</th>
            <th>SSIM ↑</th>
            <th>LPIPS ↓</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.tag}>
              <th>{r.tag}</th>
              <td>{r.metrics.psnr.toFixed(4)}</td>
              <td>{r.metrics.ssim.toFixed(5)}</td>
              <td>{r.metrics.lpips.toFixed(5)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        Q1 − 30k half-trained control: PSNR{' '}
        {(candidate.metrics.psnr - control.metrics.psnr).toFixed(4)} dB; SSIM{' '}
        {(candidate.metrics.ssim - control.metrics.ssim).toFixed(5)}; LPIPS{' '}
        {(candidate.metrics.lpips - control.metrics.lpips).toFixed(5)}. Same GT pixels and camera;
        common RGB8 evaluator. This is a resolution intervention.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }}>
        {[
          ['Ground truth', candidate.frames[index].gt],
          ['30k half-trained control', control.frames[index].pred],
          ['Q1 native-trained', candidate.frames[index].pred],
        ].map(([label, url]) => (
          <figure key={label} style={{ margin: 0 }}>
            <figcaption>{label}</figcaption>
            <a href={url} target="_blank" rel="noreferrer">
              <img src={url} alt={label + ' view ' + index} style={{ width: '100%' }} />
            </a>
          </figure>
        ))}
      </div>
      {research && (
        <section>
          <h3>
            {research.study || 'Tea research'} · {research.status}
          </h3>
          {research.reason && <p>{research.reason}</p>}
          {research.phase && <p>Stage: {research.phase}</p>}
          {research.q15.length > 0 && (
            <>
              <h4>Q1.5 · fixed-checkpoint rendering</h4>
              <p>
                Compare within one output size. Float area2x preserves the exact camera. aa2d is an
                inference intervention, not full Mip-Splatting. CUDA render + filter FPS excludes
                image IO.
              </p>
              <table>
                <thead>
                  <tr>
                    <th>Variant</th>
                    <th>PSNR ↑</th>
                    <th>SSIM ↑</th>
                    <th>LPIPS ↓</th>
                    <th>Offline FPS</th>
                    <th>CUDA peak MiB</th>
                  </tr>
                </thead>
                <tbody>
                  {research.q15
                    .filter((r) => r.tag.includes('-' + resolution + '-'))
                    .map((r) => (
                      <tr key={r.tag}>
                        <th>{r.tag}</th>
                        <td>{r.metrics.psnr.toFixed(4)}</td>
                        <td>{r.metrics.ssim.toFixed(5)}</td>
                        <td>{r.metrics.lpips.toFixed(5)}</td>
                        <td>{r.fps.toFixed(1)}</td>
                        <td>{(r.peak_cuda_allocated_bytes / 2 ** 20).toFixed(0)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </>
          )}
          {research.q2 && (
            <>
              <h4>Q2 · official backend · native output</h4>
              <p>{research.q2.scope}</p>
              <p>{research.q2.comparison}</p>
              <table>
                <thead>
                  <tr>
                    <th>Method</th>
                    <th>PSNR ↑</th>
                    <th>SSIM ↑</th>
                    <th>LPIPS ↓</th>
                    <th>ROI LPIPS ↓</th>
                    <th>Gaussians</th>
                    <th>Updates</th>
                    <th>Minutes</th>
                  </tr>
                </thead>
                <tbody>
                  {research.q2.rows.map((r) => (
                    <tr key={r.method}>
                      <th>{r.method}</th>
                      <td>{r.metrics.psnr.toFixed(4)}</td>
                      <td>{r.metrics.ssim.toFixed(5)}</td>
                      <td>{r.metrics.lpips.toFixed(5)}</td>
                      <td>{r.roi_metrics.lpips.toFixed(5)}</td>
                      <td>{r.gaussians.toLocaleString()}</td>
                      <td>{r.optimizer_updates.toLocaleString()}</td>
                      <td>{(r.training_seconds / 60).toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                  gap: 12,
                }}
              >
                {research.q2.rows.map((r) => (
                  <figure key={r.method}>
                    <figcaption>
                      Q2 {r.method} · view #{index} · native
                    </figcaption>
                    <a href={r.frames[index].pred} target="_blank" rel="noreferrer">
                      <img
                        src={r.frames[index].pred}
                        alt={'Q2 ' + r.method}
                        style={{ width: '100%' }}
                      />
                    </a>
                  </figure>
                ))}
              </div>
              <p>{research.q2.next_gate}</p>
            </>
          )}
        </section>
      )}
      {model && (
        <>
          <label>
            3D checkpoint{' '}
            <select
              aria-label="Quality 3D checkpoint"
              value={modelIndex}
              onChange={(e) => setModelIndex(Number(e.target.value))}
            >
              {models.map((m, i) => (
                <option key={m.id} value={i}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
          <button onClick={() => setShow3d(!show3d)} disabled={paused}>
            {(show3d ? 'Close ' : 'Open ') + (modelIndex ? model.label : 'Q1') + ' 3D'}
          </button>
          <p>
            Browser rendering differs from saved CUDA images. Offline FPS is not browser FPS.
            Training pauses GPU views.
          </p>
          {show3d && !paused && (
            <Suspense fallback={<p>Loading Q1…</p>}>
              <Viewer
                key={model.id + index}
                catalog={catalog}
                mode="splatfacto"
                paused={paused}
                onMove={() => {}}
                dataset={{
                  id: model.id,
                  title: model.label,
                  methods: { splatfacto: model.run },
                  views: model.cameras.map((camera) => ({ camera })),
                }}
                initialCamera={model.cameras[index]}
              />
            </Suspense>
          )}
        </>
      )}
    </section>
  );
}
