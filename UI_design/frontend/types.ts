export type Method = 'nerfacto' | 'splatfacto';
export type Camera = {
  width: number;
  height: number;
  fx: number;
  fy: number;
  cx: number;
  cy: number;
  camera_to_world: number[][];
};
export type View = {
  index: number;
  source: string;
  camera: Camera;
  gt: string;
  gt_sha256?: string;
  nerfacto: string;
  splatfacto: string;
  nerfacto_error: string;
  splatfacto_error: string;
};
export type Run = {
  display_label?: string;
  background_rgb?: [number, number, number];
  run_key: string;
  config: string;
  checkpoint_sha256: string;
  split_hash: string;
  asset: string;
  bytes: number;
  vertices?: number;
  kind: string;
  metrics: {
    psnr: number;
    ssim: number;
    lpips: number;
  };
  common_metrics?: { psnr: number; ssim: number; lpips: number };
  common_evaluator_id?: string;
  train_seconds: number;
  peak_vram_mb: number;
  offline_fps: number | null;
  checkpoint_bytes?: number;
  budget?: number;
  seed?: number;
  downscale?: number;
  evaluator_id?: string;
  variant?: string;
  provenance: Record<string, unknown>;
  architecture?: Record<string, unknown>;
  rasterize_mode?: 'classic' | 'antialiased';
  splat_encoding?: 'packed' | 'ext32-full' | 'packed-ext';
};
export type Dataset = {
  id: string;
  title: string;
  subtitle: string;
  cover: string;
  scope: string;
  train_count: number;
  eval_count: number;
  views: View[];
  methods: Record<Method, Run>;
  alignment: string;
  source_matrix: string;
  inference: boolean;
  run_sets?: RunSet[];
  default_run_set?: string;
  active_run_set?: string;
  inference_reason?: string;
  view_mode?: 'baseline' | 'upgrade' | 'compare';
};
export type RunSet = {
  id: string;
  variant: 'baseline' | 'upgrade';
  label: string;
  recipe: string;
  budget: number;
  seed: number;
  downscale: number;
  evaluator_id: string;
  eval_camera_hash: string;
  train_count: number;
  eval_count: number;
  views: View[];
  methods: Record<Method, Run>;
  inference: boolean;
  inference_reason?: string;
  tier?: 'full' | 'pilot' | 'smoke';
  full_reference?: boolean;
};
export type UpgradeRow = {
  scene_group: string;
  method: Method;
  variant: string;
  recipe: string;
  views: number;
  budget: number;
  seed: number;
  downscale: number;
  study: string;
  evaluator_id: string;
  experiment_key: string;
  run_key: string;
  train_seconds: number;
  peak_vram_mb: number;
  checkpoint_bytes: number;
  metrics: { psnr: number; ssim: number; lpips: number };
  selection?: { indices: number[] };
  features: Record<string, number>;
  provenance: Record<string, unknown>;
};
export type Catalog = {
  final_delivery?: { status: string; phase?: string; campaign_status?: string; errors?: { reason: string }[]; scenes: FinalScene[]; files?: Record<string,string> };
  visual_research?: {
    inspection?: { status: string; checks: Record<string, boolean>; viewer_encoding: string;
      browser: { method: string; mean_parity_db: number; minimum_parity_db: number; p95_frame_interval_ms: number }[]; cells: {
      method: string; resolution: string; variant: string; metrics: { psnr: number; ssim: number; lpips: number };
      fps: number; frames: { gt: string; pred: string }[];
    }[] };
    confirmation?: { study: string; status: string; phase: string; jobs: { seed: number; status: string }[]; error?: string };
    confirmation_report?: { signal_gate_met: boolean; statistics: Record<string, { mean: number; std: number; min: number; max: number }> };
    status: string; study?: string; phase?: string; reason?: string;
    q15: { tag: string; metrics: { psnr: number; ssim: number; lpips: number }; fps: number;
      peak_cuda_allocated_bytes: number; frames: { gt: string; pred: string }[] }[];
    q2: null | { scope: string; comparison: string; next_gate: string;
      rows: { method: string; metrics: { psnr: number; ssim: number; lpips: number };
        roi_metrics: { psnr: number; ssim: number; lpips: number }; gaussians: number; optimizer_updates: number;
        training_seconds: number; offline_fps: number; frames: { gt: string; pred: string }[];
        model?: { id: string; label: string; cameras: Camera[]; run: Run } }[] };
  };
  quality?: {
    status: string; reason?: string;
    experiments: {
      id: string; scene: string; label: string; scope: string; numeric_target_met: boolean;
      train_seconds: number;
      rows: { tag: string; metrics: { psnr: number; ssim: number; lpips: number };
        roi_metrics?: { psnr: number; ssim: number; lpips: number };
        frames: { index: number; gt: string; pred: string; gt_sha256: string; size: number[] }[] }[];
      models: { id: string; label: string; cameras: Camera[]; run: Run }[];
    }[];
  };
  schema_version: 1;
  revision: string;
  created_at: string;
  scenes: Dataset[];
  csrf: string;
  upgrade?: {
    status: string;
    reason?: string;
    runs: UpgradeRow[];
    audits: {
      scene_group: string;
      coverage_url: string;
      previews?: { index: number; url: string }[];
      features: {
        features: Record<string, number>;
        cpu_seconds: number;
        sfm_scope: string;
        overlap: { status: string; reason?: string; kind?: string };
        frames: {
          index: number;
          azimuth: number;
          elevation: number;
          coverage_bin: string;
          sharpness: number;
          path: string;
        }[];
      };
    }[];
    models: {
      method: string;
      budget: number;
      status: string;
      reason: string;
      training_groups: string[];
      validation?: Record<string, { mae_db: number; rmse_db: number }>;
      out_of_fold?: { scene_group: string; observed: number; predicted: number }[];
    }[];
    controlled_comparisons?: {
      status: string;
      left: string;
      right: string;
      delta: Record<string, number>;
      units: Record<string, string>;
    }[];
  };
  ui: {
    MaxPixels: number;
    HeartbeatSeconds: number;
    DecodeLimitBytes: number;
    MaxVertices: number;
  };
  report_assets: Record<string, string>;
  cases: {
    scene: string;
    eval_index: number;
    selection_reasons: string[];
    crop_xyxy: number[];
    full_figure: string;
    crop_figure: string;
    error_figure: string;
  }[];
  settings_compatibility: unknown[];
};

export type FinalScene = {
  scene: string; campaign: string; cameras: Camera[]; train_count: number; eval_count: number;
  models: Record<'baseline' | 'upgrade', { label: string; frames: { gt: string; pred: string }[];
    metrics: { psnr: number; ssim: number; lpips: number }; training_seconds: number; gaussians: number; bytes: number; run: Run }>;
  delta: { psnr: number; ssim: number; lpips: number }; per_view_delta: { view: number; psnr: number; ssim: number; lpips: number }[];
  quality_dominates: boolean; preview_verdict: string; scope: string; report_url: string;
  browser: { mean_parity_db: number; minimum_parity_db: number; p95_frame_interval_ms: number; parity_met: boolean; timing_met: boolean; scope: string };
  high_resolution: { model: string; edge: number; view: number; width: number; height: number; url: string; render_seconds: number; peak_cuda_allocated_bytes: number }[];
  profile_notes: { model: string; edge: number; reason: string }[];
  roi?: null | { baseline: { psnr: number; ssim: number; lpips: number }; upgrade: { psnr: number; ssim: number; lpips: number }; original_target_met: boolean };
};
export type Job = {
  id: string;
  status: string;
  phase?: string;
  error?: string;
  sequence: number;
  camera: Camera;
  methods: Method[];
  results?: Partial<
    Record<
      Method,
      {
        image: string;
        seconds: number;
        sha256: string;
        run_key: string;
      }
    >
  >;
};
export type Bookmark = {
  id: string;
  scene: string;
  run_set_id?: string;
  title: string;
  revision: string;
  camera: Camera;
  created_at: string;
};
