import { describe, it, expect } from 'vitest';
import { preferredRunSet, resolveRunSet } from '../frontend/runSelection';
import type { RunSet } from '../frontend/types';

function set(id: string, overrides: Partial<RunSet> = {}): RunSet {
  return {
    id,
    variant: 'upgrade',
    label: id,
    budget: 10000,
    train_count: 60,
    recipe: 'uniform',
    methods: { nerfacto: { asset: '' }, splatfacto: { asset: '' } },
    ...overrides,
  } as RunSet;
}
describe('research result defaults', () => {
  it('never chooses a smoke run, even from a stale saved link', () => {
    const smoke = set('smoke', { tier: 'smoke', budget: 10, train_count: 6 });
    const pilot = set('pilot');
    expect(resolveRunSet([smoke, pilot], 'smoke', 'upgrade')?.id).toBe('pilot');
    expect(preferredRunSet([smoke], 'upgrade')).toBeUndefined();
  });
  it('promotes a completed full-pool paired 3D reference', () => {
    const reference = set('full', {
      budget: 30000,
      train_count: 105,
      full_reference: true,
      methods: {
        nerfacto: { asset: '/n.ply' },
        splatfacto: { asset: '/s.ply' },
      } as RunSet['methods'],
    });
    expect(
      preferredRunSet([set('pilot'), set('subset30k', { budget: 30000 }), reference], 'upgrade')
        ?.id,
    ).toBe('full');
  });
  it('preserves an explicitly selected valid condition and the baseline mode', () => {
    const baseline = set('baseline', { variant: 'baseline', budget: 30000, train_count: 105 });
    const uniform = set('uniform'),
      coverage = set('coverage');
    expect(resolveRunSet([baseline, uniform, coverage], 'coverage', 'upgrade')?.id).toBe(
      'coverage',
    );
    expect(resolveRunSet([baseline, uniform], 'uniform', 'baseline')?.id).toBe('baseline');
    expect(preferredRunSet([uniform], 'baseline')).toBeUndefined();
  });
});
