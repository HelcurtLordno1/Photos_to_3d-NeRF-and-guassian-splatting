import type { Catalog, Dataset, Run } from './types';
export type EvidenceRow = {
  id: string;
  label: string;
  metrics: Run['metrics'];
  note?: string;
  seconds?: number;
  gaussians?: number;
  updates?: number;
  fps?: number;
};
export type EvidenceGroup = { id: string; title: string; scope: string; rows: EvidenceRow[] };

export function researchEvidence(catalog: Catalog, dataset: Dataset): EvidenceGroup[] {
  const groups: EvidenceGroup[] = [];
  const final = catalog.final_delivery?.scenes.find((s) => s.scene === dataset.id);
  if (final)
    groups.push({
      id: 'final',
      title: 'Selected final upgrade · native',
      scope:
        'Retained Splatfacto versus selected Improved-GS. Identical native GT/cameras and RGB8 evaluator. Training histories differ.' +
        (dataset.id === 'custom:tea_sets_2'
          ? ' Tea also changes training resolution; this gain is not an isolated architecture effect.'
          : ''),
      rows: (['baseline', 'upgrade'] as const).map((id) => ({
        id,
        label: id === 'baseline' ? 'Baseline · Splatfacto' : 'Upgrade · Improved-GS',
        metrics: final.models[id].metrics,
        seconds: final.models[id].training_seconds,
        gaussians: final.models[id].gaussians,
        note: '30k schedule · seed 42 · full training pool',
      })),
    });
  if (dataset.id === 'custom:tea_sets_2') {
    for (const experiment of catalog.quality?.experiments || []) {
      for (const resolution of ['native', 'half']) {
        const rows = experiment.rows.filter((r) => r.tag.endsWith('-' + resolution));
        if (rows.length)
          groups.push({
            id: experiment.id + ':' + resolution,
            title: 'Q1 · training resolution → ' + resolution + ' output',
            scope:
              experiment.scope +
              ' Only rows in this output-resolution group share its GT. This is resolution research, not Improved-GS.',
            rows: rows.map((r) => ({
              id: r.tag,
              label: r.tag.replaceAll('-', ' '),
              metrics: r.metrics,
              note: r.roi_metrics
                ? 'Object ROI LPIPS ' + r.roi_metrics.lpips.toFixed(5)
                : undefined,
            })),
          });
      }
    }
    const research = catalog.visual_research;
    if (research?.q15.length)
      groups.push({
        id: 'q15',
        title: 'Q1.5 · multi-scale inference',
        scope:
          'Existing checkpoints, direct and antialiased rendering. Tags identify training/output resolution; these are inference tests, not new training improvements.',
        rows: research.q15.map((r) => ({
          id: r.tag,
          label: r.tag.replaceAll('-', ' '),
          metrics: r.metrics,
          fps: r.fps,
        })),
      });
    if (research?.q2)
      groups.push({
        id: 'q2',
        title: 'Q2 · AbsGS / Improved-GS control',
        scope: research.q2.scope + ' ' + research.q2.comparison,
        rows: research.q2.rows.map((r) => ({
          id: r.method,
          label: r.method,
          metrics: r.metrics,
          seconds: r.training_seconds,
          gaussians: r.gaussians,
          updates: r.optimizer_updates,
          fps: r.offline_fps,
          note: '30k schedule; optimizer update counts differ',
        })),
      });
    const seeds = research?.confirmation_report?.seeds;
    if (seeds?.length)
      groups.push({
        id: 'seeds',
        title: 'Replication · seeds 42 / 17 / 2026',
        scope:
          'Same-backend control/candidate pairs. Seed42 reuses Q2; it is not a fourth independent trial. ROI regressions remain visible; these seeds test Tea only.',
        rows: seeds.flatMap((s) =>
          s.rows.map((r) => ({
            id: s.seed + ':' + r.method,
            label: r.method + ' · seed ' + s.seed,
            metrics: r.metrics,
            seconds: r.training_seconds,
            gaussians: r.gaussians,
            updates: r.optimizer_updates,
            fps: r.offline_fps,
            note: 'Object ROI LPIPS ' + r.roi_metrics.lpips.toFixed(5),
          })),
        ),
      });
    for (const resolution of ['native', 'half']) {
      const cells = research?.inspection?.cells.filter((c) => c.resolution === resolution) || [];
      if (cells.length)
        groups.push({
          id: 'replay:' + resolution,
          title: 'Checkpoint replay · ' + resolution + ' output',
          scope:
            'Direct / antialiased CUDA rendering at fixed checkpoints. Browser parity is a separate renderer check, not GT reconstruction quality.',
          rows: cells.map((c) => ({
            id: c.method + ':' + c.variant,
            label: c.method + ' · ' + c.variant,
            metrics: c.metrics,
            fps: c.fps,
          })),
        });
    }
  }
  const teacher = catalog.final_delivery?.teacher_room;
  if (dataset.id === 'room' && teacher?.status === 'ready' && teacher.rows)
    groups.push({
      id: 'teacher',
      title: 'Teacher assignment · Room Nerfacto A/B/C',
      scope: teacher.scope || '',
      rows: teacher.rows.map((r) => ({
        id: r.id,
        label:
          r.id === 'historical-nerfacto'
            ? 'Historical Nerfacto reference'
            : 'Fresh Nerfacto · ' + r.id,
        metrics: r.metrics,
        note:
          'Camera ' +
          (r.camera_optimizer === 'off' ? 'off' : 'on') +
          ' · appearance ' +
          r.appearance +
          ' · native float PSNR ' +
          r.native_psnr.toFixed(4) +
          ' dB',
      })),
    });
  return groups;
}
