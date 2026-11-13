import type { Catalog, FinalScene } from './types';

export type DisplayMode = 'baseline' | 'upgrade' | 'compare';
export type WorkspacePanel = '3d' | 'images' | 'quality' | 'research';

// Combined limits, in addition to the existing per-file registry limits.
// Garden stays available one model at a time; opening Compare never loads it twice.
export const COMPARISON_VERTICES = 1_500_000;
export const COMPARISON_BYTES = 384 * 2 ** 20;
export const PREVIEW_PIXELS = 1280 * 720;

export function comparisonBudget(data: FinalScene, ui: Catalog['ui']) {
  const models = [data.models.baseline, data.models.upgrade];
  const vertices = models.reduce((n, m) => n + m.gaussians, 0);
  const bytes = models.reduce((n, m) => n + m.bytes, 0);
  const allowed =
    models.every((m) => m.gaussians <= ui.MaxVertices && m.bytes <= ui.DecodeLimitBytes) &&
    vertices <= COMPARISON_VERTICES &&
    bytes <= COMPARISON_BYTES;
  return { allowed, vertices, bytes };
}

export function availableViews(data: FinalScene, edge: number, mode: DisplayMode): number[] {
  if (!edge) return data.cameras.map((_, index) => index);
  const models = mode === 'compare' ? ['baseline', 'upgrade'] : [mode];
  return [...new Set(data.high_resolution.filter((p) => p.edge === edge).map((p) => p.view))]
    .filter((view) => {
      const frames = models.map((model) =>
        data.high_resolution.find((p) => p.edge === edge && p.view === view && p.model === model),
      );
      return (
        frames.every(Boolean) &&
        frames.every((p) => p!.width === frames[0]!.width && p!.height === frames[0]!.height)
      );
    })
    .sort((a, b) => a - b);
}

export function signed(value: number, decimals = 2) {
  return (value > 0 ? '+' : value < 0 ? '−' : '') + Math.abs(value).toFixed(decimals);
}

export function relativeChange(baseline: number, upgrade: number): number | null {
  return baseline > 0 ? ((upgrade - baseline) / baseline) * 100 : null;
}
