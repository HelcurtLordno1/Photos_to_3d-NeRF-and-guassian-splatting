import { useEffect, useState } from 'react';
import type { Catalog, Dataset, Method, RunSet } from './types';
import { diagnostic, preferredRunSet } from './runSelection';
import { historicalComparison, signedDelta } from './historicalComparison';
import s from './studio.module.css';

const methods: Method[] = ['nerfacto', 'splatfacto'];
const number = (n: number | null | undefined, digits = 3) =>
  n == null || !Number.isFinite(n) ? '—' : n.toFixed(digits);
const label = (set: RunSet) =>
  `${set.tier === 'pilot' ? 'Pilot · ' : ''}${set.full_reference ? 'Full reference' : set.label}`;

export default function CaptureIntelligence({
  catalog,
  dataset,
}: {
  catalog: Catalog;
  dataset: Dataset;
}) {
  const [scope, setScope] = useState('selection');
  const [metric, setMetric] = useState<'psnr' | 'lpips'>('psnr');
  const [page, setPage] = useState(0);
  useEffect(() => {
    setPage(0);
    setScope('selection');
  }, [dataset.id, dataset.active_run_set, dataset.view_mode]);
  const sets = (dataset.run_sets || []).filter((set) => !diagnostic(set));
  const active =
    sets.find((set) => set.id === dataset.active_run_set) ||
    sets.find((set) => set.variant === 'baseline') ||
    sets[0];
  if (!active) return <p>Chưa có cặp kết quả đã kiểm chứng.</p>;
  const baseline = sets.find((set) => set.variant === 'baseline');
  const candidate = active.variant === 'upgrade' ? active : undefined;
  const assessment = historicalComparison(baseline, candidate);
  const suggested = preferredRunSet(sets, 'upgrade');
  const selected = sets.filter(
    (set) =>
      scope === 'studies' ||
      (scope === 'conditions'
        ? set.budget === active.budget
        : set.id === active.id || (candidate && set.variant === 'baseline')),
  );
  const rows = selected.flatMap((set) =>
    methods.map((method) => ({
      set,
      method,
      run: set.methods[method],
      metrics: set.methods[method].common_metrics || set.methods[method].metrics,
    })),
  );
  const xs = rows.map((row) => row.run.train_seconds / 60),
    ys = rows.map((row) => row.metrics[metric]);
  const xmin = Math.min(0, ...xs),
    xmax = Math.max(1, ...xs) * 1.08;
  const ylo = Math.min(...ys),
    yhi = Math.max(...ys),
    margin = Math.max((yhi - ylo) * 0.15, metric === 'psnr' ? 0.5 : 0.01);
  const ymin = Math.max(0, ylo - margin),
    ymax = yhi + margin;
  const x = (v: number) => 65 + ((v - xmin) / (xmax - xmin)) * 615;
  const y = (v: number) => 280 - ((v - ymin) / (ymax - ymin)) * 245;
  const upgrade = catalog.upgrade;
  const eligible = (upgrade?.runs || []).filter(
    (row) => row.scene_group === dataset.id && row.budget === active.budget,
  );
  const keys = new Map(eligible.map((row) => [row.run_key, row]));
  const comparisons = (upgrade?.controlled_comparisons || []).filter(
    (pair) => keys.has(pair.left) && keys.has(pair.right),
  );
  const audit = upgrade?.audits.find((item) => item.scene_group === dataset.id);
  const previews = audit?.previews || [];
  const kept = new Set(
    upgrade?.runs.find((row) => row.run_key === active.methods.nerfacto.run_key)?.selection
      ?.indices || [],
  );
  const pages = Math.max(1, Math.ceil(previews.length / 12));
  return (
    <section aria-label="Measured research results">
      <h3>{dataset.title} · kết quả đã đo</h3>
      <section className={s.comparisonNote} aria-label="Historical baseline comparison">
        <h4>Upgrade có tốt hơn baseline?</h4>
        {assessment.status === 'available' ? (
          <>
            <p>
              Baseline: {baseline!.train_count} ảnh / {baseline!.budget.toLocaleString()} bước →
              đang chọn: {candidate!.train_count} ảnh / {candidate!.budget.toLocaleString()} bước ·{' '}
              {candidate!.eval_count} camera held-out · cùng evaluator.
            </p>
            {assessment.rows.map((row) => (
              <p key={row.method}>
                <strong>{row.method === 'nerfacto' ? 'Nerfacto' : 'Splatfacto'}:</strong>{' '}
                {row.unfavorable === 0 && row.favorable > 0
                  ? `Trung bình thuận hơn ở ${row.favorable}/3 chỉ số trên bộ ảnh này.`
                  : row.favorable === 0 && row.unfavorable > 0
                    ? `Trung bình kém hơn ở ${row.unfavorable}/3 chỉ số trên bộ ảnh này.`
                    : row.favorable === 0 && row.unfavorable === 0
                      ? 'Các chỉ số trung bình không đổi.'
                      : 'Các chỉ số trái chiều; chưa có kết quả tốt hơn toàn diện.'}{' '}
                ΔPSNR {signedDelta(row.delta.psnr, 3)} dB · ΔSSIM {signedDelta(row.delta.ssim, 4)} ·
                ΔLPIPS {signedDelta(row.delta.lpips, 5)}.
              </p>
            ))}
            <p className={s.caption}>
              {assessment.matchedBudget
                ? 'Cùng số ảnh, số bước và seed; đây là đối chiếu với lần chạy lịch sử có nguồn mã khác.'
                : 'Khác số ảnh, số bước hoặc seed: đây là đánh đổi điều kiện chạy, không phải bằng chứng cải tiến thuật toán.'}{' '}
              Chỉ một seed trên một dataset; chưa xác nhận độ ổn định qua nhiều lần chạy. Δ =
              upgrade − baseline; PSNR/SSIM tăng là tốt, LPIPS giảm là tốt. Không suy ra khác biệt
              nhìn thấy rõ từ chênh lệch nhỏ.
            </p>
          </>
        ) : (
          <>
            <p>{assessment.reason}</p>
            {!candidate && suggested && (
              <a
                href={`/?scene=${encodeURIComponent(dataset.id)}&runSet=${encodeURIComponent(suggested.id)}&tab=research`}
              >
                Xem đối chiếu · {suggested.train_count} ảnh / {suggested.budget.toLocaleString()}{' '}
                bước ↗
              </a>
            )}
          </>
        )}
      </section>
      <div className={s.panelTools}>
        <label>
          Phạm vi kết quả{' '}
          <select
            aria-label="Benchmark scope"
            value={scope}
            onChange={(event) => setScope(event.target.value)}
          >
            <option value="selection">Điều kiện đang chọn</option>
            <option value="conditions">Các điều kiện cùng số bước</option>
            <option value="studies">Tất cả thí nghiệm của dataset</option>
          </select>
        </label>
        <label>
          Trục chất lượng{' '}
          <select
            aria-label="Quality axis"
            value={metric}
            onChange={(event) => setMetric(event.target.value as 'psnr' | 'lpips')}
          >
            <option value="psnr">PSNR (dB ↑)</option>
            <option value="lpips">LPIPS (↓)</option>
          </select>
        </label>
      </div>
      <p className={s.caption}>
        {active.train_count} ảnh train · {active.budget.toLocaleString()} bước · seed {active.seed}{' '}
        · {active.eval_count} held-out views. So sánh selector chỉ có kiểm soát khi cùng số ảnh, số
        bước, split, nguồn mã và evaluator.
      </p>
      <svg
        viewBox="0 0 730 330"
        role="img"
        aria-label="Measured quality versus training minutes"
        style={{ width: '100%', maxHeight: 360 }}
      >
        {[0, 1, 2, 3, 4].map((tick) => {
          const xv = xmin + ((xmax - xmin) * tick) / 4,
            yv = ymin + ((ymax - ymin) * tick) / 4;
          return (
            <g key={tick} fill="currentColor" fontSize="11">
              <path d={`M${x(xv)},35V280 M65,${y(yv)}H680`} stroke="currentColor" opacity=".12" />
              <text x={x(xv)} y="299" textAnchor="middle">
                {number(xv, 1)}
              </text>
              <text x="57" y={y(yv) + 4} textAnchor="end">
                {number(yv, metric === 'psnr' ? 1 : 3)}
              </text>
            </g>
          );
        })}
        <text x="65" y="20" fill="currentColor" fontSize="12">
          {metric === 'psnr' ? 'PSNR · dB ↑' : 'LPIPS ↓'}
        </text>
        <text x="370" y="324" fill="currentColor" textAnchor="middle" fontSize="12">
          Thời gian train · phút (↓)
        </text>
        {rows.map(({ set, method, run, metrics }) => (
          <a
            key={`${set.id}:${method}`}
            href={`/?scene=${encodeURIComponent(dataset.id)}&runSet=${encodeURIComponent(set.id)}&tab=images`}
          >
            <g
              fill={set.variant === 'baseline' ? '#697b89' : '#c45f22'}
              stroke="white"
              strokeWidth="1.5"
            >
              <title>
                {label(set)} · {method} · {number(metrics[metric])} ·{' '}
                {number(run.train_seconds / 60, 1)} phút
              </title>
              {method === 'nerfacto' ? (
                <circle cx={x(run.train_seconds / 60)} cy={y(metrics[metric])} r="6" />
              ) : (
                <rect
                  x={x(run.train_seconds / 60) - 6}
                  y={y(metrics[metric]) - 6}
                  width="12"
                  height="12"
                />
              )}
            </g>
          </a>
        ))}
      </svg>
      <p className={s.caption}>
        ● Nerfacto · ■ Splatfacto · xám: baseline lịch sử · cam: nghiên cứu mới. Đây là số đo thực
        tế; khác số ảnh hoặc số bước là đánh đổi chi phí/chất lượng.
      </p>
      <div className={s.tableWrap}>
        <table>
          <thead>
            <tr>
              <th>Điều kiện / phương pháp</th>
              <th>Ảnh / bước</th>
              <th>PSNR ↑</th>
              <th>SSIM ↑</th>
              <th>LPIPS ↓</th>
              <th>Train (phút)</th>
              <th>VRAM lấy mẫu (MiB)</th>
              <th>Checkpoint (MiB)</th>
              <th>Offline FPS ↑</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ set, method, run, metrics }) => {
              const delta =
                set.id === candidate?.id
                  ? assessment.rows.find((row) => row.method === method)?.delta
                  : undefined;
              return (
                <tr key={`${set.id}:${method}`}>
                  <td>
                    {label(set)}
                    <br />
                    {method}
                  </td>
                  <td>
                    {set.train_count} / {set.budget.toLocaleString()}
                  </td>
                  <td>
                    {number(metrics.psnr)}
                    {delta && (
                      <small className={s.metricDelta}>Δ {signedDelta(delta.psnr, 3)} dB</small>
                    )}
                  </td>
                  <td>
                    {number(metrics.ssim, 4)}
                    {delta && (
                      <small className={s.metricDelta}>Δ {signedDelta(delta.ssim, 4)}</small>
                    )}
                  </td>
                  <td>
                    {number(metrics.lpips, 5)}
                    {delta && (
                      <small className={s.metricDelta}>Δ {signedDelta(delta.lpips, 5)}</small>
                    )}
                  </td>
                  <td>{number(run.train_seconds / 60, 1)}</td>
                  <td>{number(run.peak_vram_mb, 0)}</td>
                  <td>
                    {number(
                      run.checkpoint_bytes == null ? null : run.checkpoint_bytes / 2 ** 20,
                      1,
                    )}
                  </td>
                  <td>{number(run.offline_fps, 1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <details>
        <summary>Điều kiện đo và evaluator</summary>
        <p>
          Downscale {active.downscale} · {active.eval_count} camera held-out cố định. FPS là
          throughput offline, không phải FPS trình duyệt. Dấu — là chưa đo.
        </p>
        {selected.map((set) => (
          <p key={set.id}>
            {label(set)} · evaluator:{' '}
            <code>{set.methods.nerfacto.common_evaluator_id || set.evaluator_id}</code> · run set:{' '}
            <code>{set.id}</code>
          </p>
        ))}
        <p>
          Baseline dùng evaluator gốc cho đến khi có bản chấm lại ảnh đã lưu bằng evaluator chung.
          Nguồn mã baseline và nguồn mã nghiên cứu mới vẫn khác nhau; không quy mọi chênh lệch thành
          cải tiến thuật toán.
        </p>
      </details>
      <details>
        <summary>Đối chứng selector cùng điều kiện</summary>
        {comparisons.length ? (
          comparisons.map((pair) => (
            <p key={`${pair.left}:${pair.right}`}>
              {keys.get(pair.left)?.method} · {keys.get(pair.left)?.views} ảnh ·{' '}
              {active.budget.toLocaleString()} bước · ΔPSNR {number(pair.delta.psnr)} dB · ΔSSIM{' '}
              {number(pair.delta.ssim)} · ΔLPIPS {number(pair.delta.lpips)} · {pair.status}
            </p>
          ))
        ) : (
          <p>Chưa có cặp selector đủ điều kiện kiểm soát trong phạm vi này.</p>
        )}
        <p>Chênh lệch âm được giữ nguyên. Δ là phải trừ trái theo cặp đã lưu trong báo cáo.</p>
      </details>
      {audit && (
        <details>
          <summary>Capture audit · quan sát train</summary>
          <p>
            Chỉ số ảnh train; pose và sparse cloud mang tính transductive theo capture gốc. Không
            dùng chất lượng held-out để chọn ảnh.
          </p>
          <img
            src={audit.coverage_url}
            alt={`${dataset.title} camera coverage`}
            loading="lazy"
            style={{ width: '100%', maxWidth: 720, maxHeight: 280, objectFit: 'contain' }}
          />
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill,minmax(130px,1fr))',
              gap: 8,
            }}
          >
            {previews.slice(page * 12, (page + 1) * 12).map((frame) => (
              <figure key={frame.index} style={{ margin: 0 }}>
                <img
                  src={frame.url}
                  loading="lazy"
                  alt={`Train view ${frame.index}`}
                  style={{ width: '100%', maxHeight: 120, objectFit: 'contain' }}
                />
                <figcaption>
                  #{frame.index}
                  {kept.size ? (kept.has(frame.index) ? ' · được chọn' : ' · không chọn') : ''}
                </figcaption>
              </figure>
            ))}
          </div>
          <div className={s.panelTools}>
            <button disabled={page === 0} onClick={() => setPage(page - 1)}>
              Trước
            </button>
            <span>
              {page + 1} / {pages}
            </span>
            <button disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>
              Sau
            </button>
          </div>
        </details>
      )}
      <details>
        <summary>Dự báo chất lượng · trạng thái bằng chứng</summary>
        {(upgrade?.models || [])
          .filter((model) => model.budget === active.budget)
          .map((model) => (
            <p key={`${model.method}:${model.budget}`}>
              {model.method} · {model.status} · {model.training_groups.length} dataset groups ·{' '}
              {model.reason}
            </p>
          ))}
        <p>
          Không công bố PSNR dự đoán hoặc khoảng tin cậy khi chưa đủ dataset độc lập. Các điểm trên
          biểu đồ là kết quả đã đo.
        </p>
      </details>
    </section>
  );
}
