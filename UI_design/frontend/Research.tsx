import { useState, useEffect, useRef } from 'react';
import type { Catalog, Dataset, Method } from './types';
import s from './studio.module.css';
const units: Record<string, string> = {
  psnr: 'dB ↑',
  ssim: '↑',
  lpips: '↓',
  train_seconds: 's ↓',
  peak_vram_mb: 'MiB ↓',
  offline_fps: 'FPS ↑',
};
export default function Research({ catalog, dataset }: { catalog: Catalog; dataset: Dataset }) {
  const [scope, setScope] = useState(new URLSearchParams(location.search).get('scope') || 'all'),
    [metric, setMetric] = useState(new URLSearchParams(location.search).get('metric') || 'psnr'),
    [diagram, setDiagram] = useState('pipeline'),
    [diagramZoom, setDiagramZoom] = useState(1),
    [node, setNode] = useState('');
  const diagramRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let cancelled = false;
    import('mermaid')
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'strict',
          theme: 'neutral',
          fontFamily: 'Segoe UI',
        });
        const source =
          diagram === 'pipeline'
            ? 'flowchart LR\n A[Photos + COLMAP] --> B[Frozen cameras and split]\n B --> N[Nerfacto: rays + hash grid + MLP]\n B --> S[Splatfacto: anisotropic Gaussians + SH]\n N --> E[Exact-checkpoint evaluation]\n S --> E\n E --> M[PSNR / SSIM / LPIPS]\n E --> X[PLY exports]\n X --> U[Browser proxy and Gaussian viewer]'
            : diagram === 'nerfacto'
              ? 'flowchart LR\n C[Camera] --> R[Rays]\n R --> P[Proposal sampling]\n P --> H[Multiresolution hash encoding]\n H --> F[Density + appearance MLP]\n F --> V[Volume rendering]\n V --> I[RGB image]'
              : 'flowchart LR\n C[Camera] --> G[3D means + covariance + opacity]\n G --> P[Projected elliptical splats]\n P --> O[Depth ordering]\n H[Spherical harmonics color] --> O\n O --> A[Alpha compositing]\n A --> I[RGB image]';
        const { svg } = await mermaid.render(
          'diagram-' + crypto.randomUUID().replaceAll('-', ''),
          source,
        );
        if (!cancelled && diagramRef.current) diagramRef.current.innerHTML = svg;
      })
      .catch((error) => {
        if (diagramRef.current) diagramRef.current.textContent = String(error);
      });
    return () => {
      cancelled = true;
    };
  }, [diagram]);
  const scenes = catalog.scenes.filter((d) => scope === 'all' || d.id === scope);
  const values = scenes.flatMap((d) =>
    (['nerfacto', 'splatfacto'] as Method[]).map((m) => ({
      title: d.title,
      method: m,
      value:
        metric in d.methods[m].metrics
          ? d.methods[m].metrics[metric as 'psnr']
          : d.methods[m][metric as 'offline_fps'],
    })),
  );
  const max = Math.max(...values.map((v) => v.value));
  return (
    <div className={s.research}>
      <div className={s.sectionTitle}>
        <div>
          <span className={s.eyebrow}>Evidence, not estimates</span>
          <h2>Measure what the eye sees.</h2>
        </div>
        <div>
          <button
            onClick={() =>
              window.open(
                '/?report=1&scene=' +
                  encodeURIComponent(dataset.id) +
                  '&scope=' +
                  encodeURIComponent(scope) +
                  '&metric=' +
                  metric,
                '_blank',
                'noopener',
              )
            }
          >
            Print / save PDF
          </button>{' '}
          <a href="/api/report/review/research_review.html" target="_blank" rel="noreferrer">
            Original report ↗
          </a>
        </div>
      </div>
      <div className={s.panelTools}>
        <label>
          Dataset
          <select value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="all">All scenes · no aggregate</option>
            {catalog.scenes.map((d) => (
              <option key={d.id} value={d.id}>
                {d.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          Metric
          <select value={metric} onChange={(e) => setMetric(e.target.value)}>
            {Object.keys(units).map((x) => (
              <option key={x} value={x}>
                {x} · {units[x]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className={s.chart}>
        {values.map((v) => (
          <div className={s.barRow} key={v.title + v.method}>
            <span>
              {v.title} · {v.method === 'nerfacto' ? 'N' : 'S'}
            </span>
            <div className={s.barTrack}>
              <div
                className={v.method === 'nerfacto' ? s.barN : s.barS}
                style={{ width: `${(v.value / max) * 100}%` }}
              />
            </div>
            <b>{v.value.toFixed(3)}</b>
          </div>
        ))}
      </div>
      <div className={s.tableWrap}>
        <table>
          <caption>Exact paired runs · 30,000 iterations · seed 42 · downscale 2</caption>
          <thead>
            <tr>
              <th>Scene / method</th>
              {Object.entries(units).map(([k, u]) => (
                <th key={k}>
                  {k}
                  <small>{u}</small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {scenes.flatMap((d) =>
              (['nerfacto', 'splatfacto'] as Method[]).map((m) => (
                <tr key={d.id + m}>
                  <th>
                    {d.title}
                    <span className={s.methodBadge}>{m === 'nerfacto' ? 'N' : 'S'}</span>
                    <small>{d.scope}</small>
                  </th>
                  <td>{d.methods[m].metrics.psnr.toFixed(2)}</td>
                  <td>{d.methods[m].metrics.ssim.toFixed(4)}</td>
                  <td>{d.methods[m].metrics.lpips.toFixed(4)}</td>
                  <td>{d.methods[m].train_seconds.toFixed(1)}</td>
                  <td>{d.methods[m].peak_vram_mb.toFixed(0)}</td>
                  <td>{d.methods[m].offline_fps.toFixed(3)}</td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>
      <p className={s.caption}>
        Offline FPS is the original synchronized CUDA camera-path measurement and excludes image IO.
        Browser FPS and live inference latency are separate measurements. Poster is a smoke scene
        and is excluded from benchmark aggregation.
      </p>
      <div className={s.diagramHeader}>
        <h3>Inside the reconstruction</h3>
        <div>
          {['pipeline', 'nerfacto', 'splatfacto'].map((d) => (
            <button key={d} aria-pressed={diagram === d} onClick={() => setDiagram(d)}>
              {d}
            </button>
          ))}
          <button
            onClick={() => {
              const svg = diagramRef.current?.querySelector('svg');
              if (svg) {
                const url = URL.createObjectURL(
                  new Blob([svg.outerHTML], { type: 'image/svg+xml' }),
                );
                const a = document.createElement('a');
                a.download = diagram + '-architecture.svg';
                a.href = url;
                a.click();
                setTimeout(() => URL.revokeObjectURL(url), 1000);
              }
            }}
          >
            Export SVG
          </button>
        </div>
      </div>
      <div
        ref={diagramRef}
        className={s.diagram}
        style={{ zoom: diagramZoom }}
        onClick={(e) => {
          const target = (e.target as Element).closest('.node');
          if (target) setNode(target.textContent || '');
        }}
        role="img"
        aria-label={diagram + ' architecture diagram'}
      />
      <div className={s.panelTools}>
        <label>
          Diagram zoom
          <input
            aria-label="Diagram zoom"
            type="range"
            min=".7"
            max="2"
            step=".1"
            value={diagramZoom}
            onChange={(e) => setDiagramZoom(Number(e.target.value))}
          />
        </label>
        {node && <span>Selected node: {node} · explanation below</span>}
      </div>
      <section className={s.curated}>
        <h3>Curated evaluation cases · {dataset.title}</h3>
        <p className={s.caption}>
          The original review selected these views using PNG diagnostics, not per-view LPIPS.
          Figures retain the original source and crop coordinates.
        </p>
        {catalog.cases
          .filter((c) => c.scene === dataset.id)
          .map((c) => (
            <details key={c.eval_index}>
              <summary>
                View #{c.eval_index} · {c.selection_reasons.join(' / ')}
              </summary>
              <p className={s.caption}>Source-pixel ROI: [{c.crop_xyxy.join(', ')}]</p>
              {[c.full_figure, c.crop_figure, c.error_figure].map((figure) => (
                <a
                  key={figure}
                  href={'/api/report/review/' + figure}
                  target="_blank"
                  rel="noreferrer"
                >
                  <img
                    loading="lazy"
                    src={'/api/report/review/' + figure}
                    alt={dataset.title + ' · ' + figure.split('/').at(-1)}
                  />
                </a>
              ))}
            </details>
          ))}
      </section>
      <details>
        <summary>Architecture explanation and sources</summary>
        <p>
          Nerfacto samples camera rays with proposal networks, encodes positions in a
          multiresolution hash grid and learns density and appearance with MLPs. Volume rendering
          integrates these predictions into pixels.
        </p>
        <p>
          Splatfacto optimizes anisotropic Gaussian centers, scales, orientations, opacity and
          spherical harmonics. Camera projection and ordered alpha compositing produce an image.
          Browser Spark and CUDA gsplat are different rasterizers.
        </p>
        <a
          href="https://docs.nerf.studio/nerfology/methods/nerfacto.html"
          target="_blank"
          rel="noreferrer"
        >
          Nerfacto documentation
        </a>{' '}
        ·{' '}
        <a
          href="https://docs.nerf.studio/nerfology/methods/splat.html"
          target="_blank"
          rel="noreferrer"
        >
          Splatfacto documentation
        </a>{' '}
        ·{' '}
        <a href="https://sparkjs.dev/docs/" target="_blank" rel="noreferrer">
          Spark renderer
        </a>
      </details>
      <details>
        <summary>Provenance · {dataset.title}</summary>
        {(['nerfacto', 'splatfacto'] as Method[]).map((m) => (
          <div key={m}>
            <h4>{m}</h4>
            <details>
              <summary>Actual model configuration</summary>
              <pre>{JSON.stringify(dataset.methods[m].architecture, null, 2)}</pre>
            </details>
            <p>
              Run: <code>{dataset.methods[m].run_key}</code>
            </p>
            <p>
              Checkpoint SHA-256: <code>{dataset.methods[m].checkpoint_sha256}</code>
            </p>
            <p>
              Split SHA-256: <code>{dataset.methods[m].split_hash}</code>
            </p>
            <pre>{JSON.stringify(dataset.methods[m].provenance, null, 2)}</pre>
          </div>
        ))}
      </details>
      <p className={s.caption}>
        Catalog revision: {catalog.revision} · created {catalog.created_at} · original artifacts are
        read-only.
      </p>
      <section className={s.printEvidence}>
        <h3>Report selection and exact sources</h3>
        <p>
          Filter: {scope} · selected metric: {metric} ({units[metric]}) · focused scene:{' '}
          {dataset.id}
        </p>
        {scenes.map((d) => (
          <div key={d.id}>
            <h4>
              {d.title} · {d.scope}
            </h4>
            <p>Matrix: {d.source_matrix}</p>
            {(['nerfacto', 'splatfacto'] as Method[]).map((m) => (
              <div key={m}>
                <p>
                  {m} · Run: {d.methods[m].run_key}
                </p>
                <p>Config: {d.methods[m].config}</p>
                <p>Checkpoint SHA-256: {d.methods[m].checkpoint_sha256}</p>
                <p>Split SHA-256: {d.methods[m].split_hash}</p>
              </div>
            ))}
          </div>
        ))}
      </section>
    </div>
  );
}
