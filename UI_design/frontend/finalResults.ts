import type { Dataset, FinalScene, Run } from './types';

export const finalResultId = (scene: string) => 'selected-final:' + scene;
export const FINAL_PREVIEW_PIXELS = 1280 * 720;
export function pairedPreview(
  data: FinalScene,
  limits: { MaxVertices: number; DecodeLimitBytes: number },
) {
  const rows = Object.values(data.models);
  return (
    rows.every((r) => r.gaussians <= limits.MaxVertices && r.bytes <= limits.DecodeLimitBytes) &&
    rows.reduce((n, r) => n + r.gaussians, 0) <= 1_500_000 &&
    rows.reduce((n, r) => n + r.bytes, 0) <= 384 * 2 ** 20
  );
}
export function finalRun(data: FinalScene, model: 'baseline' | 'upgrade'): Run {
  return {
    ...data.models[model].run,
    display_label: model === 'baseline' ? 'Baseline · Splatfacto' : 'Upgrade · Improved-GS',
  };
}

// Compare's N/S keys are image channels here, not model identities. Its public
// labels are supplied explicitly. No Gaussian is published as a Nerfacto run.
export function finalImages(dataset: Dataset, data: FinalScene): Dataset {
  return {
    ...dataset,
    inference: false,
    views: data.cameras.map((camera, i) => ({
      index: i,
      source: 'native/' + i,
      camera,
      gt: data.models.baseline.frames[i].gt,
      nerfacto: data.models.baseline.frames[i].pred,
      splatfacto: data.models.upgrade.frames[i].pred,
      nerfacto_error: data.models.baseline.frames[i].error || '',
      splatfacto_error: data.models.upgrade.frames[i].error || '',
    })),
  };
}
