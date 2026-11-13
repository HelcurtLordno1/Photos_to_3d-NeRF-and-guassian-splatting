import { useState } from 'react';
import type { Catalog, FinalScene } from './types';
import { relativeChange, signed, type DisplayMode } from './finalSelection';
import s from './final.module.css';

export default function FinalBenchmark({
  data,
  catalog,
  mode,
  onModeChange,
  view,
  onViewChange,
  expanded = false,
  onSceneChange,
}: {
  data: FinalScene;
  catalog: Catalog;
  mode: DisplayMode;
  onModeChange: (mode: DisplayMode) => void;
  view: number;
  onViewChange: (index: number) => void;
  expanded?: boolean;
  onSceneChange?: (scene: string) => void;
}) {
  const [metric, setMetric] = useState<'psnr' | 'ssim' | 'lpips'>('psnr');
  const base = data.models.baseline,
    candidate = data.models.upgrade;
  const lpips = relativeChange(base.metrics.lpips, candidate.metrics.lpips);
  const maxFootprint = Math.max(base.gaussians, candidate.gaussians, 1);
  const maxDelta = Math.max(...data.per_view_delta.map((r) => Math.abs(r[metric])), 0.0001);
  const wins = data.per_view_delta.filter((r) =>
    metric === 'lpips' ? r[metric] < 0 : r[metric] > 0,
  ).length;
  return (
    <section
      className={s.benchmark}
      aria-label="Reconstruction benchmark"
      data-benchmark-scene={data.scene}
    >
      <div className={s.benchmarkHeading}>
        <div>
          <span className={s.kicker}>
            Native evaluation · {mode === 'compare' ? 'upgrade − baseline' : mode}
          </span>
          <h2>The measured difference.</h2>
        </div>
        <p>
          {data.eval_count} held-out views
          <br />
          {data.cameras[0].width.toLocaleString()} × {data.cameras[0].height.toLocaleString()} px
        </p>
      </div>
      <div className={s.metricStrip}>
        {(['psnr', 'ssim', 'lpips'] as const).map((key) => {
          const favourable = key === 'lpips' ? data.delta[key] <= 0 : data.delta[key] >= 0;
          const decimals = key === 'psnr' ? 2 : key === 'ssim' ? 4 : 4;
          return (
            <article
              key={key}
              className={s.metricCell}
              data-metric={key}
              data-metric-model={mode}
              data-metric-value={
                mode === 'compare' ? data.delta[key] : data.models[mode].metrics[key]
              }
            >
              <span>
                {key.toUpperCase()}{' '}
                <small>{key === 'lpips' ? 'lower is better' : 'higher is better'}</small>
              </span>
              <strong>
                {mode === 'compare'
                  ? signed(data.delta[key], decimals)
                  : data.models[mode].metrics[key].toFixed(decimals)}
                {key === 'psnr' && <small>dB</small>}
              </strong>
              <div>
                {mode === 'compare' ? (
                  <span>
                    {base.metrics[key].toFixed(decimals)} →{' '}
                    {candidate.metrics[key].toFixed(decimals)}
                  </span>
                ) : (
                  <>
                    <span className={favourable ? s.gain : s.loss}>
                      Upgrade Δ {signed(data.delta[key], decimals)}
                      {key === 'psnr' ? ' dB' : ''}
                    </span>
                    <span>
                      {mode === 'baseline'
                        ? 'upgrade ' + candidate.metrics[key].toFixed(decimals)
                        : 'baseline ' + base.metrics[key].toFixed(decimals)}
                    </span>
                  </>
                )}
              </div>
            </article>
          );
        })}
      </div>
      <p className={s.benchmarkContext}>
        Splatfacto baseline → selected Improved-GS · full training pool · 30,000 steps · seed 42.
        {lpips !== null && (
          <>
            {' '}
            LPIPS changed by <b>{signed(lpips, 1)}%</b>.
          </>
        )}
        {data.scene.startsWith('custom:') && (
          <> Tea also changes training resolution; this is the combined final upgrade.</>
        )}
      </p>
      <div className={s.tableScroll}>
        <table aria-label="Final benchmark" className={s.benchmarkTable}>
          <thead>
            <tr>
              <th>Reconstruction</th>
              <th>PSNR ↑</th>
              <th>SSIM ↑</th>
              <th>LPIPS ↓</th>
              <th>Gaussians</th>
              <th>PLY</th>
            </tr>
          </thead>
          <tbody>
            {(['baseline', 'upgrade'] as const).map((id) => {
              const row = data.models[id];
              return (
                <tr key={id} data-model={id} aria-selected={mode === id || mode === 'compare'}>
                  <th>
                    <button
                      onClick={() => onModeChange(id)}
                      aria-label={'Select ' + id + ' result'}
                    >
                      {id === 'baseline' ? 'Baseline' : 'Upgrade'}
                      <small>{id === 'baseline' ? 'Splatfacto' : 'Improved-GS'}</small>
                    </button>
                  </th>
                  <td>{row.metrics.psnr.toFixed(4)}</td>
                  <td>{row.metrics.ssim.toFixed(5)}</td>
                  <td>{row.metrics.lpips.toFixed(5)}</td>
                  <td>{row.gaussians.toLocaleString()}</td>
                  <td>{(row.bytes / 2 ** 20).toFixed(1)} MiB</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className={s.finePrint}>
        Same RGB8 evaluator, canonical cameras and GT. These metrics always describe native held-out
        output, including when a 4K/8K image is displayed. Source histories differ.
      </p>
      {expanded && (
        <>
          <div className={s.evidenceColumns}>
            <section className={s.viewEvidence}>
              <div className={s.subheading}>
                <h3>Across the views</h3>
                <select
                  aria-label="Per-view metric"
                  value={metric}
                  onChange={(e) => setMetric(e.target.value as typeof metric)}
                >
                  <option value="psnr">PSNR</option>
                  <option value="ssim">SSIM</option>
                  <option value="lpips">LPIPS</option>
                </select>
              </div>
              <p>
                {wins} of {data.eval_count} views improve on {metric.toUpperCase()}. Select a bar to
                choose the camera used in Image comparison.
              </p>
              <svg
                viewBox="0 0 760 156"
                className={s.viewChart}
                role="group"
                aria-label="Per-view upgrade deltas"
              >
                <line x1="0" x2="760" y1="78" y2="78" stroke="currentColor" opacity=".35" />
                {data.per_view_delta.map((r, i) => {
                  const x = (i * 760) / data.eval_count,
                    width = Math.max(2, 760 / data.eval_count - 4);
                  const height = Math.max(1, (Math.abs(r[metric]) / maxDelta) * 62),
                    good = metric === 'lpips' ? r[metric] < 0 : r[metric] > 0;
                  return (
                    <g
                      key={r.view}
                      tabIndex={0}
                      role="button"
                      aria-label={
                        'View ' +
                        r.view +
                        ': ' +
                        metric.toUpperCase() +
                        ' delta ' +
                        signed(r[metric], 4)
                      }
                      onClick={() => onViewChange(r.view)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          onViewChange(r.view);
                        }
                      }}
                    >
                      <title>
                        View {r.view} · {metric.toUpperCase()} {signed(r[metric], 4)}
                      </title>
                      <rect x={x} y="4" width={width} height="148" fill="transparent" />
                      <rect
                        x={x}
                        y={r[metric] >= 0 ? 78 - height : 78}
                        width={width}
                        height={height}
                        fill={good ? 'var(--s)' : 'var(--accent)'}
                        stroke={view === r.view ? 'var(--ink)' : 'none'}
                        strokeWidth="2"
                      />
                    </g>
                  );
                })}
              </svg>
              <div className={s.chartLegend}>
                <span>View 0</span>
                <span>Upgrade − baseline · zero at the rule</span>
                <span>View {data.eval_count - 1}</span>
              </div>
              <p className={s.finePrint}>
                Positive PSNR/SSIM and negative LPIPS are favourable. Teal bars improve; rust bars
                regress. One seed per transferred scene.
              </p>
            </section>
            <section className={s.footprint}>
              <h3>Reconstruction footprint</h3>
              <p>Quality gains and model size are separate trade-offs.</p>
              {(['baseline', 'upgrade'] as const).map((id) => (
                <div key={id} className={s.footprintRow}>
                  <div>
                    <b>{id === 'baseline' ? 'Baseline' : 'Upgrade'}</b>
                    <span>{(data.models[id].gaussians / 1e6).toFixed(2)}M Gaussians</span>
                  </div>
                  <div className={s.footprintTrack}>
                    <span
                      style={{
                        width: (data.models[id].gaussians / maxFootprint) * 100 + '%',
                        background: id === 'upgrade' ? 'var(--s)' : 'var(--muted)',
                      }}
                    />
                  </div>
                  <small>
                    {(data.models[id].bytes / 2 ** 20).toFixed(1)} MiB PLY ·{' '}
                    {(data.models[id].training_seconds / 60).toFixed(1)} min training
                  </small>
                </div>
              ))}
              <p className={s.finePrint}>
                Historical and current training use different runtimes and setup/checkpoint
                accounting. Times are descriptive, not a matched-compute speedup.
              </p>
            </section>
          </div>
          <section className={s.collectionBenchmark}>
            <div className={s.subheading}>
              <div>
                <span className={s.kicker}>The complete collection</span>
                <h3>Across the collection</h3>
              </div>
              <span>Native PSNR · dB</span>
            </div>
            <div className={s.tableScroll}>
              <table aria-label="Collection benchmark" className={s.benchmarkTable}>
                <thead>
                  <tr>
                    <th>Scene</th>
                    <th>Baseline</th>
                    <th>Upgrade</th>
                    <th>Δ PSNR</th>
                    <th>Δ LPIPS</th>
                    <th>Test views</th>
                  </tr>
                </thead>
                <tbody>
                  {catalog.final_delivery?.scenes.map((scene) => (
                    <tr
                      key={scene.scene}
                      aria-current={scene.scene === data.scene ? 'true' : undefined}
                    >
                      <th>
                        <button onClick={() => onSceneChange?.(scene.scene)}>
                          <img
                            src={catalog.scenes.find((d) => d.id === scene.scene)?.cover}
                            alt=""
                            loading="lazy"
                            width="38"
                            height="38"
                          />
                          <span>
                            {catalog.scenes.find((d) => d.id === scene.scene)?.title || scene.scene}
                            {scene.scene.startsWith('custom:') && (
                              <small>Includes native-resolution training</small>
                            )}
                          </span>
                        </button>
                      </th>
                      <td>{scene.models.baseline.metrics.psnr.toFixed(2)}</td>
                      <td>{scene.models.upgrade.metrics.psnr.toFixed(2)}</td>
                      <td className={scene.delta.psnr >= 0 ? s.gain : s.loss}>
                        {signed(scene.delta.psnr)}
                      </td>
                      <td className={scene.delta.lpips <= 0 ? s.gain : s.loss}>
                        {signed(scene.delta.lpips, 4)}
                      </td>
                      <td>{scene.eval_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className={s.finePrint}>
              Per-scene comparisons, not a pooled score. Other scenes have one selected upgrade;
              repeated-seed research was performed on Tea. No SOTA claim.
            </p>
          </section>
        </>
      )}
      {expanded &&
        data.scene === 'room' &&
        catalog.final_delivery?.teacher_room?.status === 'ready' && (
          <details className={s.reportDetails}>
            <summary>Nerfacto configuration check · Room A/B/C</summary>
            <p>
              This separate diagnostic addresses the teacher’s configuration question. It is not a
              Gaussian upgrade. A/B/C start fresh; the original on/average run is a historical
              reference.
            </p>
            <div className={s.tableScroll}>
              <table className={s.benchmarkTable} aria-label="Room Nerfacto diagnostic">
                <thead>
                  <tr>
                    <th>Run</th>
                    <th>Camera optimization</th>
                    <th>Appearance</th>
                    <th>PSNR RGB8</th>
                    <th>SSIM</th>
                    <th>LPIPS</th>
                  </tr>
                </thead>
                <tbody>
                  {catalog.final_delivery.teacher_room.rows.map((row) => (
                    <tr key={row.id}>
                      <th>{row.id === 'historical-nerfacto' ? 'Historical reference' : row.id}</th>
                      <td>{row.camera_optimizer === 'off' ? 'Off' : 'On'}</td>
                      <td>{row.appearance}</td>
                      <td>{row.metrics.psnr.toFixed(4)}</td>
                      <td>{row.metrics.ssim.toFixed(5)}</td>
                      <td>{row.metrics.lpips.toFixed(5)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p>
              Run C native float PSNR:{' '}
              {catalog.final_delivery.teacher_room.rows
                .find((row) => row.id === 'C')
                ?.native_psnr.toFixed(4)}{' '}
              dB. The table uses the shared RGB8 evaluator; float and saved-image scores are
              recorded separately.
            </p>
            <p>{catalog.final_delivery.teacher_room.scope}</p>
            <a href={catalog.final_delivery.teacher_room.csv_url} target="_blank" rel="noreferrer">
              Download diagnostic results CSV ↗
            </a>
            {' · '}
            <a
              href={catalog.final_delivery.teacher_room.report_url}
              target="_blank"
              rel="noreferrer"
            >
              Open exact diagnostic report ↗
            </a>
          </details>
        )}
      <div
        className={s.previewNote}
        data-preview-warning={!data.browser.parity_met || !data.browser.timing_met}
      >
        <b>Browser preview</b>
        <span>
          {data.browser.parity_met
            ? 'Measured parity target met'
            : 'Some views miss the parity target'}{' '}
          · {data.browser.p95_frame_interval_ms.toFixed(1)} ms p95 at the recorded 1280 × 720
          profile{!data.browser.timing_met ? ' · timing target missed' : ''}.
        </span>
      </div>
      <details className={s.reportDetails}>
        <summary>Protocol, limitations and full report</summary>
        <p>{data.scope}</p>
        <p>
          Browser parity: mean {data.browser.mean_parity_db.toFixed(2)} dB, minimum{' '}
          {data.browser.minimum_parity_db.toFixed(2)} dB. Browser previews and native evaluation use
          different renderers; previous measurements are retained and do not certify every viewport.
        </p>
        {data.roi && (
          <p>
            Locked Tea ROI: upgrade PSNR {data.roi.upgrade.psnr.toFixed(4)}, SSIM{' '}
            {data.roi.upgrade.ssim.toFixed(5)}, LPIPS {data.roi.upgrade.lpips.toFixed(5)}. Original
            ROI target: {data.roi.original_target_met ? 'met' : 'not met'}.
          </p>
        )}
        <p>
          Views with lower upgrade PSNR:{' '}
          {data.per_view_delta
            .filter((r) => r.psnr < 0)
            .map((r) => '#' + r.view)
            .join(', ') || 'none'}
          . Per-view losses remain visible in the report.
        </p>
        {data.profile_notes.map((p, i) => (
          <p key={i}>
            {p.model} · {p.edge} long edge: {p.reason}
          </p>
        ))}
        <a href={data.report_url} target="_blank" rel="noreferrer">
          Open measured scene report ↗
        </a>
        {catalog.final_delivery?.files && (
          <p>
            {Object.entries(catalog.final_delivery.files)
              .filter(([name]) => ['comparison.csv', 'report.md', 'per-view.csv'].includes(name))
              .map(([name, url]) => (
                <a key={name} href={url} target="_blank" rel="noreferrer" className={s.reportLink}>
                  {name} ↗
                </a>
              ))}
          </p>
        )}
      </details>
    </section>
  );
}
