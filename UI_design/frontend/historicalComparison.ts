import type { Method, Run, RunSet } from './types';

type Metrics = Run['metrics'];
export type HistoricalComparison = {
  status: 'available' | 'unavailable';
  reason: string;
  matchedBudget: boolean;
  rows: { method: Method; delta: Metrics; favorable: number; unfavorable: number }[];
};

export function historicalComparison(
  base: RunSet | undefined,
  candidate: RunSet | undefined,
): HistoricalComparison {
  const unavailable = (reason: string): HistoricalComparison => ({
    status: 'unavailable',
    reason,
    matchedBudget: false,
    rows: [],
  });
  if (!base || !candidate || base.variant !== 'baseline' || candidate.variant !== 'upgrade')
    return unavailable('Chọn Upgrade hoặc Compare để đối chiếu với baseline lịch sử.');
  if (
    !base.eval_camera_hash ||
    base.eval_camera_hash !== candidate.eval_camera_hash ||
    base.downscale !== candidate.downscale ||
    base.eval_count !== candidate.eval_count ||
    base.views.length !== candidate.views.length ||
    !base.views.length ||
    !base.views.every(
      (view, index) => view.gt_sha256 && view.gt_sha256 === candidate.views[index].gt_sha256,
    )
  )
    return unavailable(
      'Camera, ảnh ground truth hoặc độ phân giải chưa khớp; không tính chênh lệch chất lượng.',
    );
  const rows: HistoricalComparison['rows'] = [];
  for (const method of ['nerfacto', 'splatfacto'] as Method[]) {
    const left = base.methods[method],
      right = candidate.methods[method];
    const leftId = left.common_metrics
      ? left.common_evaluator_id
      : left.evaluator_id || base.evaluator_id;
    const rightId = right.common_metrics
      ? right.common_evaluator_id
      : right.evaluator_id || candidate.evaluator_id;
    if (!leftId || leftId !== rightId)
      return unavailable(
        'Chưa có số đo baseline và upgrade bằng cùng evaluator; chưa kết luận hơn/kém.',
      );
    const a = left.common_metrics || left.metrics,
      b = right.common_metrics || right.metrics;
    if (![a.psnr, a.ssim, a.lpips, b.psnr, b.ssim, b.lpips].every(Number.isFinite))
      return unavailable('Thiếu chỉ số chất lượng hợp lệ; chưa tính chênh lệch.');
    const delta = { psnr: b.psnr - a.psnr, ssim: b.ssim - a.ssim, lpips: b.lpips - a.lpips };
    const directions = [delta.psnr, delta.ssim, -delta.lpips];
    rows.push({
      method,
      delta,
      favorable: directions.filter((value) => value > 0).length,
      unfavorable: directions.filter((value) => value < 0).length,
    });
  }
  return {
    status: 'available',
    reason: '',
    matchedBudget:
      base.budget === candidate.budget &&
      base.train_count === candidate.train_count &&
      base.seed === candidate.seed,
    rows,
  };
}

export function signedDelta(value: number, digits: number): string {
  const rounded = Number(value.toFixed(digits));
  return `${rounded > 0 ? '+' : ''}${rounded.toFixed(digits)}`;
}
