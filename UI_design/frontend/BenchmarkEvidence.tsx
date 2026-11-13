import { useEffect, useState } from 'react';
import type { Catalog, Dataset, Run } from './types';
import { researchEvidence } from './researchEvidence';
import { finalResultId } from './finalResults';
import { signedDelta } from './historicalComparison';
import s from './studio.module.css';
import b from './benchmark.module.css';

const fmt = (v: number | undefined, digits = 1) =>
  v == null || !Number.isFinite(v) ? '—' : v.toFixed(digits);
export default function BenchmarkEvidence({
  catalog,
  dataset,
}: {
  catalog: Catalog;
  dataset: Dataset;
}) {
  const [selection, setSelection] = useState('final'),
    [metric, setMetric] = useState<keyof Run['metrics']>('psnr');
  useEffect(() => {
    setSelection('final');
  }, [dataset.id]);
  const groups = researchEvidence(catalog, dataset),
    group = groups.find((g) => g.id === selection) || groups[0];
  const final = catalog.final_delivery?.scenes.find((s) => s.scene === dataset.id);
  if (!group) return null;
  const isFinal = group.id === 'final';
  const positive =
    final?.per_view_delta.filter((r) => (metric === 'lpips' ? r[metric] < 0 : r[metric] > 0))
      .length || 0;
  const extent = Math.max(
    ...(final?.per_view_delta.map((r) => Math.abs(r[metric])) || [1]),
    0.00001,
  );
  const imageLink = (view: number) =>
    '/?scene=' +
    encodeURIComponent(dataset.id) +
    '&runSet=' +
    encodeURIComponent(finalResultId(dataset.id)) +
    '&variant=compare&tab=images&view=' +
    view;
  return (
    <section aria-label="Completed experiment evidence" className={b.evidence}>
      <h3>Completed research · {dataset.title}</h3>
      <p>
        The final reconstruction and the experiments that led to it. Each group keeps its own
        evaluation conditions; unfinished pilots are not quality results.
      </p>
      <div className={s.panelTools}>
        <label>
          Evidence group{' '}
          <select
            aria-label="Evidence group"
            value={group.id}
            onChange={(e) => setSelection(e.target.value)}
          >
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.title}
              </option>
            ))}
          </select>
        </label>
        {isFinal && (
          <label>
            Per-view metric{' '}
            <select
              aria-label="Evidence metric"
              value={metric}
              onChange={(e) => setMetric(e.target.value as keyof Run['metrics'])}
            >
              <option value="psnr">PSNR · dB ↑</option>
              <option value="ssim">SSIM ↑</option>
              <option value="lpips">LPIPS ↓</option>
            </select>
          </label>
        )}
        <span>
          {groups.length} evidence groups · {group.rows.length} results in this group
        </span>
      </div>
      <h4>{group.title}</h4>
      <p className={b.scope}>{group.scope}</p>
      <div className={s.tableWrap}>
        <table aria-label="Completed experiment metrics">
          <thead>
            <tr>
              <th>Experiment / model</th>
              <th>PSNR ↑</th>
              <th>SSIM ↑</th>
              <th>LPIPS ↓</th>
              <th>Train min</th>
              <th>Gaussians</th>
              <th>Optimizer updates</th>
              <th>Offline FPS ↑</th>
            </tr>
          </thead>
          <tbody>
            {group.rows.map((row) => (
              <tr key={row.id} data-evidence-row={row.id}>
                <th scope="row">
                  {row.label}
                  {row.note && <small>{row.note}</small>}
                </th>
                <td>{fmt(row.metrics.psnr, 4)}</td>
                <td>{fmt(row.metrics.ssim, 5)}</td>
                <td>{fmt(row.metrics.lpips, 5)}</td>
                <td>{fmt(row.seconds == null ? undefined : row.seconds / 60)}</td>
                <td>{row.gaussians?.toLocaleString() || '—'}</td>
                <td>{row.updates?.toLocaleString() || '—'}</td>
                <td>{fmt(row.fps)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={b.scope}>
        — means unreported for this test. Training costs have their recorded scope; they are not a
        matched-compute speedup. Horizontal scroll keeps every table column readable on smaller
        screens.
      </p>
      {isFinal && final && (
        <>
          <div className={s.comparisonNote}>
            <h4>Upgrade − baseline · native, {final.eval_count} held-out views</h4>
            <p className={b.delta}>
              PSNR <strong>{signedDelta(final.delta.psnr, 3)} dB</strong>
              <span>
                SSIM <strong>{signedDelta(final.delta.ssim, 4)}</strong>
              </span>
              <span>
                LPIPS <strong>{signedDelta(final.delta.lpips, 5)}</strong>
              </span>
            </p>
            <p>
              Higher PSNR/SSIM and lower LPIPS are favourable.{' '}
              {final.quality_dominates
                ? 'All three mean metrics improve.'
                : 'The mean metrics show a trade-off.'}{' '}
              Individual views can still become worse.
            </p>
          </div>
          <h4>Across the held-out cameras · {metric.toUpperCase()}</h4>
          <p>
            {positive} / {final.eval_count} views improve on this metric. Select a bar to inspect
            the native image pair.
          </p>
          <div className={b.chartScroll}>
            <svg
              className={b.perView}
              viewBox="0 0 960 170"
              role="img"
              aria-label="Per-view upgrade minus baseline"
            >
              <path d="M0 76H960" stroke="var(--muted)" opacity=".5" />
              <text x="0" y="162" fill="currentColor" fontSize="14">
                View 0
              </text>
              <text x="960" y="162" textAnchor="end" fill="currentColor" fontSize="14">
                View {final.eval_count - 1}
              </text>
              {final.per_view_delta.map((r, i) => {
                const v = r[metric],
                  h = Math.max(1, (Math.abs(v) / extent) * 65),
                  w = 960 / final.eval_count;
                return (
                  <a
                    key={r.view}
                    href={imageLink(r.view)}
                    aria-label={'View ' + r.view + ', delta ' + fmt(v, 4)}
                  >
                    <title>
                      View {r.view}: {signedDelta(v, 4)}
                    </title>
                    <rect
                      x={i * w + 2}
                      y={v >= 0 ? 76 - h : 76}
                      width={Math.max(1, w - 4)}
                      height={h}
                      fill={(metric === 'lpips' ? v < 0 : v > 0) ? 'var(--s)' : 'var(--accent)'}
                    />
                  </a>
                );
              })}
            </svg>
          </div>
          <p className={b.scope}>
            Zero line: no change. Teal: favourable; rust: regression. Bar direction is the signed
            difference, including LPIPS where a negative difference is favourable.
          </p>
          <details>
            <summary>Model footprint, browser limitations and high-resolution outputs</summary>
            <p>{final.scope}</p>
            <p>
              PLY: baseline {(final.models.baseline.bytes / 2 ** 20).toFixed(1)} MiB → upgrade{' '}
              {(final.models.upgrade.bytes / 2 ** 20).toFixed(1)} MiB.
            </p>
            <p>
              Browser candidate parity: mean {fmt(final.browser.mean_parity_db, 2)} dB, minimum{' '}
              {fmt(final.browser.minimum_parity_db, 2)} dB.{' '}
              {final.browser.parity_met
                ? 'Recorded parity gate met.'
                : 'Some views miss the stricter parity target.'}{' '}
              Recorded p95 frame interval {fmt(final.browser.p95_frame_interval_ms, 2)} ms at
              1280×720, DPR1;{' '}
              {final.browser.timing_met ? 'timing target met.' : 'timing target missed.'} These are
              archived fixed-profile measurements, not live FPS for this page.
            </p>
            <p>
              4K/8K are saved inference outputs from existing weights, not higher-resolution source
              photographs or new GT metrics.
            </p>
            <div className={s.tableWrap}>
              <table aria-label="Saved high-resolution output coverage">
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Output</th>
                    <th>Camera</th>
                    <th>Pixels</th>
                    <th>Render s</th>
                    <th>CUDA allocated MiB</th>
                  </tr>
                </thead>
                <tbody>
                  {final.high_resolution.map((p) => (
                    <tr key={p.model + ':' + p.edge + ':' + p.view}>
                      <th>{p.model}</th>
                      <td>
                        <a href={p.url} target="_blank" rel="noreferrer">
                          {p.edge === 3840 ? '4K' : '8K'} image ↗
                        </a>
                      </td>
                      <td>#{p.view}</td>
                      <td>
                        {p.width} × {p.height}
                      </td>
                      <td>{fmt(p.render_seconds, 2)}</td>
                      <td>{fmt(p.peak_cuda_allocated_bytes / 2 ** 20)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {final.profile_notes.map((p, i) => (
              <p key={i}>
                {p.model} / {p.edge}: {p.reason}
              </p>
            ))}
          </details>
          <p>
            <a href={final.report_url} target="_blank" rel="noreferrer">
              Full measured scene report ↗
            </a>
            {catalog.final_delivery?.files &&
              Object.entries(catalog.final_delivery.files).map(([name, url]) => (
                <a className={b.reportLink} key={name} href={url} target="_blank" rel="noreferrer">
                  {name} ↗
                </a>
              ))}
          </p>
        </>
      )}
      {group.id === 'teacher' && (
        <p>
          <a
            href={catalog.final_delivery?.teacher_room?.report_url}
            target="_blank"
            rel="noreferrer"
          >
            Teacher diagnostic report ↗
          </a>{' '}
          ·{' '}
          <a href={catalog.final_delivery?.teacher_room?.csv_url} target="_blank" rel="noreferrer">
            Results CSV ↗
          </a>
          <br />
          The table uses the common RGB8 evaluator. Native float PSNR is recorded separately in each
          row; C is about30.30dB. This diagnosis does not represent a Gaussian upgrade.
        </p>
      )}
      {group.id === 'seeds' && (
        <p>
          Signal gate:{' '}
          {catalog.visual_research?.confirmation_report?.signal_gate_met ? 'met' : 'not met'}. Each
          seed’s control and candidate remain visible, including higher candidate ROI LPIPS where it
          occurs. A repeated Tea result is not independent validation across datasets.
        </p>
      )}
      {dataset.id === 'custom:tea_sets_2' && (
        <details>
          <summary>Browser precision diagnosis · retained negative results</summary>
          <p>
            Same trained checkpoints: a 2×2 check of input and render-accumulator precision. Parity
            compares the browser image with CUDA, not with ground truth. These values are separate
            from reconstruction PSNR above and describe the archived fixed-profile renderer tests.
          </p>
          {catalog.visual_research?.inspection_history?.length ? (
            <div className={s.tableWrap}>
              <table aria-label="Browser precision investigation">
                <thead>
                  <tr>
                    <th>Input / accumulator</th>
                    <th>Method</th>
                    <th>Mean parity dB</th>
                    <th>Minimum parity dB</th>
                    <th>p95 interval ms</th>
                    <th>Recorded matrix decision</th>
                  </tr>
                </thead>
                <tbody>
                  {catalog.visual_research.inspection_history.map((r) => (
                    <tr key={r.encoding + ':' + r.method}>
                      <th>
                        <a href={r.report_url} target="_blank" rel="noreferrer">
                          {r.encoding === 'packed'
                            ? 'Packed / packed'
                            : r.encoding === 'ext32'
                              ? 'Extended / packed'
                              : r.encoding === 'ext32-full'
                                ? 'Extended / extended'
                                : 'Packed / extended'}{' '}
                          ↗
                        </a>
                      </th>
                      <td>{r.method}</td>
                      <td>{fmt(r.mean_parity_db, 2)}</td>
                      <td>{fmt(r.minimum_parity_db, 2)}</td>
                      <td>{fmt(r.p95_frame_interval_ms, 2)}</td>
                      <td>{r.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>
              {catalog.visual_research?.inspection_history_error
                ? 'Historical summary could not be verified; current completed results remain available.'
                : 'No committed precision-history summary is available.'}
            </p>
          )}
          <p>
            The recorded matrix decision concerns adoption of the selected research profile. It is
            not a claim that every method/view passed. Packed-input / extended-accumulator was
            retained; extending input alone did not solve the issue, and fully extended rendering
            missed the timing gate. All measured values and failed decisions remain visible.
          </p>
        </details>
      )}
    </section>
  );
}
