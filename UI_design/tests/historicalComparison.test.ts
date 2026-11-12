import { describe, expect, it } from 'vitest';
import { historicalComparison, signedDelta } from '../frontend/historicalComparison';
import type { RunSet } from '../frontend/types';

function pair() {
  const native = { psnr: 20, ssim: 0.6, lpips: 0.15 };
  const common = { psnr: 21, ssim: 0.7, lpips: 0.1 };
  const base = {
    id: 'baseline',
    variant: 'baseline',
    budget: 30000,
    train_count: 105,
    seed: 42,
    downscale: 2,
    eval_count: 1,
    eval_camera_hash: 'camera-frame',
    views: [{ gt_sha256: 'pixels' }],
    evaluator_id: 'native',
    methods: Object.fromEntries(
      ['nerfacto', 'splatfacto'].map((method) => [
        method,
        {
          metrics: native,
          common_metrics: common,
          common_evaluator_id: 'shared-rgb8',
        },
      ]),
    ),
  } as unknown as RunSet;
  const candidate = {
    ...structuredClone(base),
    id: 'new',
    variant: 'upgrade',
    evaluator_id: 'shared-rgb8',
    methods: Object.fromEntries(
      ['nerfacto', 'splatfacto'].map((method) => [
        method,
        {
          metrics: { psnr: 21.2, ssim: 0.71, lpips: 0.099 },
          evaluator_id: 'shared-rgb8',
        },
      ]),
    ),
  } as unknown as RunSet;
  return { base, candidate };
}
describe('historical quality comparison', () => {
  it('uses common baseline scores and treats lower LPIPS as favorable', () => {
    const { base, candidate } = pair();
    const result = historicalComparison(base, candidate);
    expect(result.status).toBe('available');
    expect(result.matchedBudget).toBe(true);
    expect(result.rows[0].delta.psnr).toBeCloseTo(0.2);
    expect(result.rows[0].favorable).toBe(3);
    expect(result.rows[0].unfavorable).toBe(0);
  });
  it('does not turn mixed metric directions into a universal win', () => {
    const { base, candidate } = pair();
    candidate.methods.splatfacto.metrics.psnr = 20.9;
    const row = historicalComparison(base, candidate).rows[1];
    expect(row.favorable).toBe(2);
    expect(row.unfavorable).toBe(1);
  });
  it.each(['evaluator', 'pixels', 'camera', 'resolution', 'nonfinite'])(
    'rejects an unsupported comparison: %s',
    (kind) => {
      const { base, candidate } = pair();
      if (kind === 'evaluator') base.methods.nerfacto.common_evaluator_id = 'different';
      if (kind === 'pixels') candidate.views[0].gt_sha256 = 'other-pixels';
      if (kind === 'camera') candidate.eval_camera_hash = 'other-camera';
      if (kind === 'resolution') candidate.downscale = 4;
      if (kind === 'nonfinite') candidate.methods.nerfacto.metrics.psnr = NaN;
      expect(historicalComparison(base, candidate).status).toBe('unavailable');
    },
  );
  it('labels fewer images or fewer iterations as a trade-off', () => {
    const { base, candidate } = pair();
    candidate.train_count = 60;
    candidate.budget = 10000;
    const result = historicalComparison(base, candidate);
    expect(result.status).toBe('available');
    expect(result.matchedBudget).toBe(false);
  });
  it('never compares a baseline selection with itself or silently mixes native scores', () => {
    const { base, candidate } = pair();
    expect(historicalComparison(base, base).status).toBe('unavailable');
    delete base.methods.nerfacto.common_metrics;
    expect(historicalComparison(base, candidate).status).toBe('unavailable');
  });
  it('keeps small measured differences visible without displaying negative zero', () => {
    expect(signedDelta(-0.00004228, 5)).toBe('-0.00004');
    expect(signedDelta(-0.00000001, 5)).toBe('0.00000');
    expect(signedDelta(0.23183, 3)).toBe('+0.232');
  });
});
