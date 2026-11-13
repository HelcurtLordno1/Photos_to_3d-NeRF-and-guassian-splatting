import { useEffect, useRef, useState } from 'react';
import type { FinalScene } from './types';
import type { DisplayMode } from './finalSelection';
import s from './final.module.css';

export default function FinalImages({
  data,
  mode,
  edge,
  view,
}: {
  data: FinalScene;
  mode: DisplayMode;
  edge: number;
  view: number;
}) {
  const [layout, setLayout] = useState<'wipe' | 'side' | 'error'>('wipe');
  const [split, setSplit] = useState(50),
    [zoom, setZoom] = useState(1),
    [showGT, setShowGT] = useState(false);
  const baseline = useRef<HTMLImageElement>(null),
    upgrade = useRef<HTMLImageElement>(null),
    canvas = useRef<HTMLCanvasElement>(null);
  const [loaded, setLoaded] = useState(0),
    [error, setError] = useState('');
  const source = (model: 'baseline' | 'upgrade') =>
    edge
      ? data.high_resolution.find((p) => p.edge === edge && p.view === view && p.model === model)
          ?.url
      : data.models[model].frames[view]?.pred;
  const left = source('baseline'),
    right = source('upgrade');
  const high = data.high_resolution.find((p) => p.edge === edge && p.view === view);
  const camera = edge && high ? high : data.cameras[view];
  const actualLayout = mode === 'compare' ? (edge && layout === 'error' ? 'wipe' : layout) : 'side';

  useEffect(() => {
    setZoom(1);
    setError('');
  }, [view, edge, data.scene]);
  useEffect(() => {
    if (actualLayout !== 'error' || mode !== 'compare') return;
    const a = baseline.current,
      b = upgrade.current,
      target = canvas.current;
    if (!a?.complete || !b?.complete || !a.naturalWidth || !b.naturalWidth || !target) return;
    // A bounded display diagnostic. No full-resolution canvas or metric inference.
    const scale = Math.min(1, 1024 / Math.max(a.naturalWidth, a.naturalHeight));
    const width = Math.max(1, Math.round(a.naturalWidth * scale)),
      height = Math.max(1, Math.round(a.naturalHeight * scale));
    target.width = width;
    target.height = height;
    const ctx = target.getContext('2d', { willReadFrequently: true })!;
    try {
      ctx.drawImage(a, 0, 0, width, height);
      const x = ctx.getImageData(0, 0, width, height);
      ctx.drawImage(b, 0, 0, width, height);
      const y = ctx.getImageData(0, 0, width, height);
      for (let i = 0; i < x.data.length; i += 4) {
        for (let c = 0; c < 3; c++)
          x.data[i + c] = Math.min(255, Math.abs(x.data[i + c] - y.data[i + c]) * 4);
        x.data[i + 3] = 255;
      }
      ctx.putImageData(x, 0, 0);
      target.dataset.differenceReady = 'true';
    } catch {
      setError('The difference preview could not be drawn. The saved images remain available.');
    }
    return () => {
      target.dataset.differenceReady = 'false';
      target.width = 1;
      target.height = 1;
    };
  }, [actualLayout, mode, left, right, loaded]);

  const image = (model: 'baseline' | 'upgrade', overlay = false) => (
    <figure className={s.imageFigure} data-image-model={model}>
      <figcaption>
        <span>{model === 'baseline' ? 'Baseline' : 'Upgrade'}</span>
        <small>{model === 'baseline' ? 'Splatfacto' : 'Improved-GS'}</small>
      </figcaption>
      {source(model) ? (
        <a
          href={source(model)}
          target="_blank"
          rel="noreferrer"
          aria-label={'Open full-resolution ' + model + ' image'}
        >
          <img
            ref={model === 'baseline' ? baseline : upgrade}
            data-final-image
            data-image-model={model}
            src={source(model)}
            alt={data.models[model].label + ' · view ' + view}
            draggable={false}
            decoding="async"
            onLoad={() => setLoaded((n) => n + 1)}
            onError={() =>
              setError('A saved image could not be loaded. Try another view or reopen the scene.')
            }
            style={overlay ? { transform: 'scale(' + zoom + ')' } : undefined}
          />
        </a>
      ) : (
        <p>Saved output unavailable for this model and camera.</p>
      )}
    </figure>
  );

  return (
    <section aria-label="Matched image comparison" className={s.imageSection}>
      <div className={s.imageToolbar}>
        <div>
          <span className={s.kicker}>{edge ? 'Large output' : 'Held-out photograph'}</span>
          <h3>
            View {String(view).padStart(2, '0')} <span> / {data.eval_count}</span>
          </h3>
        </div>
        {mode === 'compare' && (
          <div className={s.smallSegment} aria-label="Image comparison layout">
            <button aria-pressed={actualLayout === 'wipe'} onClick={() => setLayout('wipe')}>
              Wipe
            </button>
            <button aria-pressed={actualLayout === 'side'} onClick={() => setLayout('side')}>
              Side by side
            </button>
            <button
              disabled={!!edge}
              aria-pressed={actualLayout === 'error'}
              onClick={() => setLayout('error')}
            >
              Difference ×4
            </button>
          </div>
        )}
      </div>
      {mode === 'compare' && actualLayout !== 'side' ? (
        <>
          <div
            className={s.imageStage}
            data-image-layout={actualLayout}
            style={{
              aspectRatio: camera.width + '/' + camera.height,
              width: 'min(100%, ' + Math.round((560 * camera.width) / camera.height) + 'px)',
            }}
          >
            <div
              className={s.wipeLayer}
              style={actualLayout === 'error' ? { visibility: 'hidden' } : undefined}
            >
              {image('baseline', true)}
            </div>
            <div
              className={s.wipeLayer}
              style={
                actualLayout === 'error'
                  ? { visibility: 'hidden' }
                  : { clipPath: 'inset(0 0 0 ' + split + '%)' }
              }
            >
              {image('upgrade', true)}
            </div>
            {actualLayout === 'wipe' ? (
              <>
                <div className={s.splitLine} style={{ left: split + '%' }} />
                <span className={s.wipeLabel}>Baseline</span>
                <span className={s.wipeLabelRight}>Upgrade</span>
              </>
            ) : (
              <canvas
                ref={canvas}
                className={s.difference}
                aria-label="Absolute RGB difference preview"
              />
            )}
          </div>
          {actualLayout === 'wipe' && (
            <div className={s.imageAdjustments}>
              <label>
                Comparison split{' '}
                <input
                  aria-label="Comparison split"
                  type="range"
                  min="0"
                  max="100"
                  value={split}
                  onChange={(e) => setSplit(Number(e.target.value))}
                />
              </label>
              <label>
                Detail zoom{' '}
                <input
                  aria-label="Detail zoom"
                  type="range"
                  min="1"
                  max="4"
                  step=".1"
                  value={zoom}
                  onChange={(e) => setZoom(Number(e.target.value))}
                />
              </label>
            </div>
          )}
        </>
      ) : (
        <div className={s.imageGrid}>
          {!edge && mode !== 'compare' && (
            <figure className={s.imageFigure}>
              <figcaption>
                <span>Ground truth</span>
                <small>Reference photograph</small>
              </figcaption>
              <a href={data.models.upgrade.frames[view].gt} target="_blank" rel="noreferrer">
                <img
                  data-final-image
                  data-image-model="gt"
                  src={data.models.upgrade.frames[view].gt}
                  alt={'Ground truth · view ' + view}
                  decoding="async"
                />
              </a>
            </figure>
          )}
          {(mode === 'compare' ? (['baseline', 'upgrade'] as const) : [mode]).map((model) => (
            <div key={model}>{image(model)}</div>
          ))}
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      <div className={s.imageFooter}>
        <p>
          {camera.width.toLocaleString()} × {camera.height.toLocaleString()} px ·{' '}
          {edge
            ? 'Render from existing weights; no high-resolution GT benchmark.'
            : 'Same frozen camera and GT for both models.'}
          {actualLayout === 'error' &&
            ' Display-size RGB difference ×4 (maximum 1024 px long edge); not LPIPS or a new metric.'}
        </p>
        {!edge && mode === 'compare' && (
          <button aria-expanded={showGT} onClick={() => setShowGT((v) => !v)}>
            {showGT ? 'Hide' : 'Show'} ground truth
          </button>
        )}
      </div>
      {showGT && !edge && mode === 'compare' && (
        <figure className={s.referenceImage}>
          <figcaption>Ground-truth photograph · same camera</figcaption>
          <a href={data.models.upgrade.frames[view].gt} target="_blank" rel="noreferrer">
            <img
              data-final-image
              data-image-model="gt"
              src={data.models.upgrade.frames[view].gt}
              alt={'Ground truth · view ' + view}
            />
          </a>
        </figure>
      )}
    </section>
  );
}
