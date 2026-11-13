import { lazy, Suspense, useRef, useState } from 'react';
import type { Catalog, FinalScene } from './types';
import type { ViewerHandle } from './Viewer';
import {
  availableViews,
  comparisonBudget,
  PREVIEW_PIXELS,
  type DisplayMode,
  type WorkspacePanel,
} from './finalSelection';
import FinalImages from './FinalImages';
import FinalBenchmark from './FinalBenchmark';
import s from './final.module.css';
const Viewer = lazy(() => import('./Viewer'));
const TeaArchive = lazy(() => import('./Quality'));

export default function FinalQuality({
  catalog,
  data,
  paused,
  mode: controlledMode,
  onModeChange,
  panel = 'quality',
  onPanelChange,
  onSceneChange,
  onHistory,
}: {
  catalog: Catalog;
  data: FinalScene;
  paused: boolean;
  mode?: DisplayMode;
  onModeChange?: (mode: DisplayMode) => void;
  panel?: WorkspacePanel;
  onPanelChange?: (panel: WorkspacePanel) => void;
  onSceneChange?: (scene: string) => void;
  onHistory?: () => void;
}) {
  const [localMode, setLocalMode] = useState<DisplayMode>('upgrade');
  const mode = controlledMode ?? localMode,
    changeMode = onModeChange || setLocalMode;
  const [edge, setEdge] = useState(0),
    [view, setView] = useState(0);
  const [show3d, setShow3d] = useState(false),
    [archive, setArchive] = useState(false);
  const [singleModel, setSingleModel] = useState<'baseline' | 'upgrade'>('upgrade');
  const viewer = useRef<ViewerHandle>(null);
  const budget = comparisonBudget(data, catalog.ui),
    pair = mode === 'compare' && budget.allowed;
  const model = mode === 'compare' ? singleModel : mode;
  const available = availableViews(data, edge, mode),
    effectiveEdge = available.length ? edge : 0;
  const views = available.length ? available : availableViews(data, 0, mode);
  const index = views.includes(view) ? view : (views[0] ?? 0);
  const changeView = (i: number) => {
    setView(i);
    viewer.current?.preset(data.cameras[i]);
  };
  const run = (id: 'baseline' | 'upgrade') => ({
    ...data.models[id].run,
    display_label: id === 'baseline' ? 'Baseline · Splatfacto' : 'Upgrade · Improved-GS',
  });
  const open3d = () => {
    setShow3d(true);
    onPanelChange?.('3d');
  };
  return (
    <section
      className={s.finalWorkspace}
      data-final-scene={data.scene}
      data-display-mode={mode}
      data-workspace-panel={panel}
    >
      <div className={s.sceneHeading}>
        <div>
          <span className={s.kicker}>Completed reconstruction</span>
          <h2>{catalog.scenes.find((d) => d.id === data.scene)?.title || data.scene}</h2>
        </div>
        <p>
          {data.train_count} training photographs · {data.eval_count} held-out views
          <br />
          {mode === 'compare'
            ? 'Baseline and upgrade · same cameras'
            : mode === 'baseline'
              ? 'Splatfacto · preserved baseline'
              : 'Improved-GS · selected upgrade'}
        </p>
      </div>
      <div className={s.resultTools}>
        {!controlledMode && (
          <label>
            Display{' '}
            <select
              aria-label="Final model"
              value={mode}
              onChange={(e) => changeMode(e.target.value as DisplayMode)}
            >
              <option value="baseline">Baseline</option>
              <option value="upgrade">Upgrade</option>
              <option value="compare">Compare</option>
            </select>
          </label>
        )}
        {panel !== 'research' && (
          <label>
            Camera{' '}
            <select
              aria-label="Final view"
              value={index}
              onChange={(e) => changeView(Number(e.target.value))}
            >
              {views.map((i) => (
                <option key={i} value={i}>
                  View {String(i).padStart(2, '0')}
                </option>
              ))}
            </select>
          </label>
        )}
        {panel !== '3d' && panel !== 'research' && (
          <label>
            Saved output{' '}
            <select
              aria-label="Final output"
              value={effectiveEdge}
              onChange={(e) => {
                setEdge(Number(e.target.value));
                changeView(0);
              }}
            >
              <option value={0}>Native · benchmark</option>
              {[3840, 7680].map((value) => (
                <option
                  key={value}
                  value={value}
                  disabled={!availableViews(data, value, mode).length}
                >
                  {value === 3840 ? '4K' : '8K'} · render only
                </option>
              ))}
            </select>
          </label>
        )}
        {panel === 'research' && <span>Native evaluation · PSNR / SSIM / LPIPS</span>}
        {(panel === 'images' || panel === 'quality') && (
          <button onClick={open3d}>Explore selected 3D ↗</button>
        )}
      </div>
      {panel === '3d' ? (
        <section className={s.modelSection} aria-label="Final reconstruction viewer">
          <div className={s.modelIntroduction}>
            <div>
              <span className={s.kicker}>Interactive reconstruction</span>
              <h3>
                {pair
                  ? 'Synchronized reconstruction comparison'
                  : mode === 'compare'
                    ? 'Compare at the same camera'
                    : data.models[model].label}
              </h3>
              <p>
                {pair
                  ? 'Orbit, pan and zoom are synchronized. Both Gaussian models use the same saved camera frame.'
                  : 'The saved view and orbit position are retained when switching models.'}
              </p>
            </div>
            <span>
              {pair
                ? budget.vertices.toLocaleString()
                : data.models[model].gaussians.toLocaleString()}{' '}
              Gaussians
            </span>
          </div>
          {mode === 'compare' && !budget.allowed && (
            <div className={s.memoryNote}>
              <p>
                This pair is large. To keep the viewer responsive, load one model at a time and
                switch at the same camera. Matched image comparison remains available.
              </p>
              <div className={s.smallSegment} aria-label="Loaded comparison model">
                {(['baseline', 'upgrade'] as const).map((id) => (
                  <button
                    key={id}
                    aria-pressed={singleModel === id}
                    onClick={() => setSingleModel(id)}
                  >
                    {id === 'baseline' ? 'Baseline' : 'Upgrade'}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className={s.viewerActions}>
            <button disabled={paused} onClick={() => setShow3d((v) => !v)}>
              {show3d ? 'Close' : 'Open'} selected 3D
            </button>
            {show3d && (
              <>
                <button onClick={() => viewer.current?.preset(data.cameras[index])}>
                  Restore saved camera
                </button>
                <button onClick={() => viewer.current?.screenshot()}>Save viewer screenshot</button>
              </>
            )}
          </div>
          {paused && <p>Compute is active; interactive rendering is paused.</p>}
          {!show3d && (
            <div className={s.viewerPlaceholder}>
              <span>3D / {pair ? 'COMPARE' : model.toUpperCase()}</span>
              <p>
                Open this scene when you are ready to explore.
                <br />
                Other datasets stay unloaded.
              </p>
            </div>
          )}
          {show3d && !paused && (
            <Suspense fallback={<div className={s.viewerPlaceholder}>Opening the renderer…</div>}>
              <Viewer
                ref={viewer}
                catalog={catalog}
                mode="splatfacto"
                onMove={() => {}}
                cameraScope={data.scene}
                pixelRatio={1}
                pixelBudget={PREVIEW_PIXELS}
                initialCamera={data.cameras[index]}
                comparison={
                  pair ? { baseline: run('baseline'), upgrade: run('upgrade') } : undefined
                }
                dataset={{
                  id: data.scene + ':' + (pair ? 'compare' : model),
                  title: data.models[model].label,
                  methods: { splatfacto: run(model) },
                  views: data.cameras.map((camera) => ({ camera })),
                }}
              />
            </Suspense>
          )}
          <p className={s.finePrint}>
            Render on demand · capped preview resolution · model loads are sequential. Browser
            appearance is approximate; the benchmark uses saved native images.
          </p>
        </section>
      ) : panel === 'research' ? (
        <FinalBenchmark
          data={data}
          catalog={catalog}
          mode={mode}
          onModeChange={changeMode}
          view={index}
          onViewChange={changeView}
          expanded
          onSceneChange={onSceneChange}
        />
      ) : (
        <>
          <FinalImages key={data.scene} data={data} mode={mode} edge={effectiveEdge} view={index} />
          {panel === 'quality' && (
            <FinalBenchmark
              data={data}
              catalog={catalog}
              mode={mode}
              onModeChange={changeMode}
              view={index}
              onViewChange={changeView}
            />
          )}
        </>
      )}
      <div className={s.historyAccess}>
        <span>NeRF comparisons and earlier experiments remain in research history.</span>
        {onHistory && <button onClick={onHistory}>Open research history ↗</button>}
        {data.scene === 'custom:tea_sets_2' && (
          <button aria-expanded={archive} onClick={() => setArchive((v) => !v)}>
            Tea research archive
          </button>
        )}
      </div>
      {archive && data.scene === 'custom:tea_sets_2' && (
        <Suspense fallback={<p>Loading archived research…</p>}>
          <TeaArchive catalog={catalog} scene={data.scene} paused={paused} />
        </Suspense>
      )}
    </section>
  );
}
