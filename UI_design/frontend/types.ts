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
  nerfacto: string;
  splatfacto: string;
  nerfacto_error: string;
  splatfacto_error: string;
};
export type Run = {
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
  train_seconds: number;
  peak_vram_mb: number;
  offline_fps: number;
  provenance: Record<string, unknown>;
  architecture?: Record<string, unknown>;
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
};
export type Catalog = {
  schema_version: 1;
  revision: string;
  created_at: string;
  scenes: Dataset[];
  csrf: string;
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
  title: string;
  revision: string;
  camera: Camera;
  created_at: string;
};
