import { useState } from 'react';
import type { Dataset, Method, View } from './types';
import Compare from './Compare';

export default function RunSetCompare({ dataset }: { dataset: Dataset }) {
  const [method, setMethod] = useState<Method>('nerfacto');
  const base = dataset.run_sets?.find((r) => r.variant === 'baseline'),
    upgraded = dataset.run_sets?.find(
      (r) => r.id === dataset.active_run_set && r.variant === 'upgrade',
    );
  if (!base || !upgraded)
    return <p>Select a completed upgrade run set and a historical baseline to compare.</p>;
  const compatible =
    base.eval_camera_hash === upgraded.eval_camera_hash &&
    base.views.length === upgraded.views.length &&
    base.views.every((v, i) => {
      const b = upgraded.views[i];
      return (
        v.gt_sha256 &&
        v.gt_sha256 === b.gt_sha256 &&
        v.camera.width === b.camera.width &&
        v.camera.height === b.camera.height
      );
    });
  if (!compatible)
    return (
      <p>
        Saved camera frames or GT pixels differ. Open each run set separately; synchronized image
        comparison is unavailable.
      </p>
    );
  const views: View[] = base.views.map((v, i) => ({
    ...v,
    nerfacto: v[method],
    splatfacto: upgraded.views[i][method],
    nerfacto_error: v[`${method}_error`],
    splatfacto_error: upgraded.views[i][`${method}_error`],
  }));
  const comparison: Dataset = {
    ...dataset,
    views,
    methods: { nerfacto: base.methods[method], splatfacto: upgraded.methods[method] },
    inference: false,
  };
  return (
    <section>
      <label>
        Compare the same method{' '}
        <select value={method} onChange={(e) => setMethod(e.target.value as Method)}>
          <option value="nerfacto">Nerfacto</option>
          <option value="splatfacto">Splatfacto</option>
        </select>
      </label>
      <p>
        Historical baseline: {base.train_count} views / {base.budget} steps · Upgrade:{' '}
        {upgraded.train_count} views / {upgraded.budget} steps. This is a trade-off with separate
        source histories; no controlled improvement is claimed. Metrics use the common saved-image
        evaluator when its verified derivative is available.
      </p>
      <Compare
        key={method + upgraded.id}
        dataset={comparison}
        job={null}
        imageLabels={{ nerfacto: 'Baseline · ' + method, splatfacto: 'Upgrade · ' + method }}
      />
    </section>
  );
}
