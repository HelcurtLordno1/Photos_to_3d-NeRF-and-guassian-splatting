import { describe, expect, it } from 'vitest';
import { finalImages, finalRun, pairedPreview } from '../frontend/finalResults';
import { researchEvidence } from '../frontend/researchEvidence';
import type { Catalog, Dataset, FinalScene, Run } from '../frontend/types';
const metrics = { psnr: 31, ssim: 0.9, lpips: 0.1 };
const run = { run_key: 'real-checkpoint', asset: '/real.ply', metrics } as Run;
const camera = { width: 101, height: 99 };
const model = {
  run,
  metrics,
  training_seconds: 60,
  gaussians: 500000,
  bytes: 120 * 2 ** 20,
  frames: [{ gt: '/frozen-gt', pred: '/frozen-pred', error: '/derived-error' }],
};
const final = {
  scene: 'bonsai',
  cameras: [camera],
  models: {
    baseline: model,
    upgrade: { ...model, run: { ...run, run_key: 'candidate-checkpoint' } },
  },
} as FinalScene;
const dataset = {
  id: 'bonsai',
  methods: { nerfacto: { run_key: 'original-nerf' }, splatfacto: run },
} as Dataset;
describe('integrating final results into the existing UI', () => {
  it('keeps the real Gaussian checkpoint identity and explicit model label', () => {
    expect(finalRun(final, 'upgrade').run_key).toBe('candidate-checkpoint');
    expect(finalRun(final, 'upgrade').display_label).toBe('Upgrade · Improved-GS');
  });
  it('reuses the image controls without manufacturing a Nerfacto model', () => {
    const images = finalImages(dataset, final);
    expect(images.methods.nerfacto.run_key).toBe('original-nerf');
    expect(images.views[0].gt).toBe('/frozen-gt');
    expect(images.views[0].splatfacto_error).toBe('/derived-error');
    expect(images.inference).toBe(false);
  });
  it('allows a bounded pair and rejects combined size or per-asset excess', () => {
    const limits = { MaxVertices: 3e6, DecodeLimitBytes: 600 * 2 ** 20 };
    expect(pairedPreview(final, limits)).toBe(true);
    expect(
      pairedPreview(
        { ...final, models: { ...final.models, upgrade: { ...model, gaussians: 1200000 } } },
        limits,
      ),
    ).toBe(false);
    expect(
      pairedPreview(
        { ...final, models: { ...final.models, upgrade: { ...model, bytes: 300 * 2 ** 20 } } },
        limits,
      ),
    ).toBe(false);
    expect(pairedPreview(final, { ...limits, MaxVertices: 100 })).toBe(false);
  });
  it('never propagates Tea experiments to other datasets', () => {
    const catalog = {
      final_delivery: { scenes: [final] },
      quality: { experiments: [{ id: 'tea', rows: [] }] },
      visual_research: { q15: [] },
    } as unknown as Catalog;
    const groups = researchEvidence(catalog, dataset);
    expect(groups.map((g) => g.id)).toEqual(['final']);
    expect(groups[0].rows[1].metrics).toEqual(metrics);
  });
  it('keeps a worse repeated-seed result and its ROI loss visible', () => {
    const catalog = {
      visual_research: {
        q15: [],
        confirmation_report: {
          seeds: [
            {
              seed: 17,
              rows: [
                {
                  method: 'improvedgs',
                  metrics: { ...metrics, psnr: 29 },
                  roi_metrics: { ...metrics, lpips: 0.2 },
                },
              ],
            },
          ],
        },
      },
    } as unknown as Catalog;
    const groups = researchEvidence(catalog, { ...dataset, id: 'custom:tea_sets_2' });
    expect(groups[0].rows[0].metrics.psnr).toBe(29);
    expect(groups[0].rows[0].note).toContain('0.20000');
  });
});
