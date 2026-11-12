import type { RunSet } from './types';

export function diagnostic(set: RunSet): boolean {
  return set.tier === 'smoke' || set.budget < 10000 || /smoke|diagnostic/i.test(set.label);
}

export function hasGeometry(set: Pick<RunSet, 'methods'>): boolean {
  return Boolean(set.methods.nerfacto.asset && set.methods.splatfacto.asset);
}

export function preferredRunSet(
  sets: RunSet[],
  variant: 'baseline' | 'upgrade',
): RunSet | undefined {
  return sets
    .filter((s) => s.variant === variant && !diagnostic(s))
    .sort(
      (a, b) =>
        Number(b.full_reference && hasGeometry(b)) - Number(a.full_reference && hasGeometry(a)) ||
        b.budget - a.budget ||
        b.train_count - a.train_count ||
        Number(b.recipe === 'uniform') - Number(a.recipe === 'uniform') ||
        a.id.localeCompare(b.id),
    )[0];
}

export function resolveRunSet(
  sets: RunSet[],
  id: string,
  variant: 'baseline' | 'upgrade',
): RunSet | undefined {
  return (
    sets.find((s) => s.id === id && s.variant === variant && !diagnostic(s)) ||
    preferredRunSet(sets, variant)
  );
}
