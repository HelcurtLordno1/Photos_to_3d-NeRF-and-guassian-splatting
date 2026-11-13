import { describe, it, expect } from 'vitest';
import {
  availableViews,
  comparisonBudget,
  relativeChange,
  signed,
} from '../frontend/finalSelection';
import type { Catalog, FinalScene } from '../frontend/types';

const ui = { MaxVertices: 3_000_000, DecodeLimitBytes: 600 * 2 ** 20 } as Catalog['ui'];
const scene = () =>
  ({
    cameras: [
      { width: 1557, height: 1037 },
      { width: 1557, height: 1037 },
    ],
    models: {
      baseline: { gaussians: 532932, bytes: 126 * 2 ** 20 },
      upgrade: { gaussians: 488875, bytes: 116 * 2 ** 20 },
    },
    high_resolution: [
      { model: 'baseline', edge: 3840, view: 0, width: 3840, height: 2558 },
      { model: 'upgrade', edge: 3840, view: 0, width: 3840, height: 2558 },
      { model: 'baseline', edge: 3840, view: 1, width: 3840, height: 2558 },
    ],
  }) as FinalScene;

describe('completed result capabilities', () => {
  it('allows the measured Room pair within the combined decoding allowance', () => {
    expect(comparisonBudget(scene(), ui).allowed).toBe(true);
  });
  it('keeps the large Garden pair to one 3D model while retaining all native image views', () => {
    const data = scene();
    data.models.baseline.gaussians = 1_656_903;
    data.models.upgrade.gaussians = 1_200_000;
    data.models.baseline.bytes = 392 * 2 ** 20;
    data.models.upgrade.bytes = 284 * 2 ** 20;
    expect(comparisonBudget(data, ui).allowed).toBe(false);
    expect(availableViews(data, 0, 'compare')).toEqual([0, 1]);
  });
  it('checks combined bytes as well as vertices and individual registry limits', () => {
    const data = scene();
    data.models.baseline.bytes = 300 * 2 ** 20;
    expect(comparisonBudget(data, ui).allowed).toBe(false);
    data.models.baseline.bytes = 100 * 2 ** 20;
    expect(comparisonBudget(data, { ...ui, MaxVertices: 500000 }).allowed).toBe(false);
  });
  it('requires both same-size high-resolution images for Compare', () => {
    const data = scene();
    expect(availableViews(data, 3840, 'baseline')).toEqual([0, 1]);
    expect(availableViews(data, 3840, 'upgrade')).toEqual([0]);
    expect(availableViews(data, 3840, 'compare')).toEqual([0]);
    data.high_resolution[1].width = 3839;
    expect(availableViews(data, 3840, 'compare')).toEqual([]);
    expect(availableViews(data, 7680, 'compare')).toEqual([]);
  });
  it('preserves signed regressions and does not invent percentages from zero', () => {
    expect(signed(-0.125, 3)).toBe('−0.125');
    expect(signed(0.125, 3)).toBe('+0.125');
    expect(relativeChange(0, 0.1)).toBeNull();
    expect(relativeChange(0.2, 0.1)).toBe(-50);
  });
});
