import { useEffect, useState } from 'react';
import type { Dataset, Job } from './types';
import s from './studio.module.css';
import { download } from './api';
export default function Compare({ dataset, job }: { dataset: Dataset; job: Job | null }) {
  const [index, setIndex] = useState(0),
    [left, setLeft] = useState('gt'),
    [right, setRight] = useState('splatfacto'),
    [source, setSource] = useState<'saved' | 'live'>('saved'),
    [wipe, setWipe] = useState(50),
    [zoom, setZoom] = useState(1),
    [error, setError] = useState(false),
    [crop, setCrop] = useState(false),
    [roi, setRoi] = useState({ x: 0.5, y: 0.5 });
  const group = (live: boolean) => {
    setSource(live ? 'live' : 'saved');
    setLeft(live ? 'live-' + job!.methods[0] : 'gt');
    setRight(live ? 'live-' + job!.methods.at(-1) : 'splatfacto');
    setError(false);
    setZoom(1);
    setCrop(false);
  };
  useEffect(() => {
    if (job?.status === 'succeeded') group(true);
  }, [job?.id]);
  const view = dataset.views[Math.min(index, dataset.views.length - 1)],
    camera = source === 'live' && job ? job.camera : view.camera;
  const image = (name: string) =>
    name.startsWith('live-')
      ? job?.results?.[name.substring(5) as 'nerfacto']?.image
      : (view as unknown as Record<string, string>)[
          name + (error && name !== 'gt' ? '_error' : '')
        ];
  const labels =
    source === 'live' ? job!.methods.map((m) => 'live-' + m) : ['gt', 'nerfacto', 'splatfacto'];
  const roiWidth = camera.width / (crop ? zoom * 2 : zoom),
    roiHeight = camera.height / (crop ? zoom * 2 : zoom);
  const scale = crop ? zoom * 2 : zoom;
  const transform = {
    transform: `translate(${(0.5 - roi.x) * scale * 100}%,${(0.5 - roi.y) * scale * 100}%) scale(${scale})`,
    transformOrigin: '50% 50%',
  };
  return (
    <section className={s.compare}>
      <div className={s.panelTools}>
        <label>
          Image source
          <select
            aria-label="Image source"
            value={source}
            onChange={(e) => group(e.target.value === 'live')}
          >
            <option value="saved">Saved held-out evaluation</option>
            {job?.status === 'succeeded' && <option value="live">Latest exact-model render</option>}
          </select>
        </label>
        <label>
          Held-out view{' '}
          <select
            disabled={source === 'live'}
            aria-label="Held-out view"
            value={index}
            onChange={(e) => {
              setIndex(Number(e.target.value));
              setRoi({ x: 0.5, y: 0.5 });
            }}
          >
            {dataset.views.map((v) => (
              <option key={v.index} value={v.index}>
                #{v.index.toString().padStart(2, '0')} · {v.source.split('/').at(-1)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Left
          <select aria-label="Left image" value={left} onChange={(e) => setLeft(e.target.value)}>
            {labels.map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label>
          Right
          <select aria-label="Right image" value={right} onChange={(e) => setRight(e.target.value)}>
            {labels.map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label>
          <input
            disabled={source === 'live'}
            type="checkbox"
            checked={error}
            onChange={(e) => setError(e.target.checked)}
          />{' '}
          Absolute error ×4
        </label>
        <label>
          <input
            type="checkbox"
            checked={crop}
            onChange={(e) => {
              setCrop(e.target.checked);
              if (!e.target.checked) setRoi({ x: 0.5, y: 0.5 });
            }}
          />{' '}
          ROI lens
        </label>
        <label>
          Zoom
          <input
            aria-label="Image zoom"
            type="range"
            min="1"
            max="4"
            step=".1"
            value={zoom}
            onChange={(e) => setZoom(Number(e.target.value))}
          />
        </label>
      </div>
      <div
        className={s.wipeArea}
        style={{
          width: (520 * camera.width) / camera.height,
          aspectRatio: `${camera.width}/${camera.height}`,
          maxHeight: 520,
        }}
        onPointerDown={(e) => {
          if (!crop) return;
          const bounds = e.currentTarget.getBoundingClientRect();
          setRoi({
            x: Math.min(
              0.9,
              Math.max(0.1, roi.x + ((e.clientX - bounds.left) / bounds.width - 0.5) / scale),
            ),
            y: Math.min(
              0.9,
              Math.max(0.1, roi.y + ((e.clientY - bounds.top) / bounds.height - 0.5) / scale),
            ),
          });
        }}
      >
        <div className={s.wipeImages} style={transform}>
          <img src={image(left)} alt={left + ' reconstruction'} draggable={false} />
        </div>
        <div className={s.wipeRight} style={{ clipPath: `inset(0 0 0 ${wipe}%)` }}>
          <div className={s.wipeImages} style={transform}>
            <img src={image(right)} alt={right + ' reconstruction'} draggable={false} />
          </div>
        </div>
        <div className={s.wipeLine} style={{ left: `${wipe}%` }} />
        <span className={s.leftImageLabel}>{left}</span>
        <span className={s.rightImageLabel}>{right}</span>
      </div>
      <label className={s.wipeSlider}>
        Comparison split
        <input
          aria-label="Comparison split"
          type="range"
          min="0"
          max="100"
          value={wipe}
          onChange={(e) => setWipe(Number(e.target.value))}
        />
      </label>
      {crop && (
        <div className={s.panelTools}>
          <label>
            ROI X
            <input
              aria-label="ROI X"
              type="range"
              min=".1"
              max=".9"
              step=".01"
              value={roi.x}
              onChange={(e) => setRoi({ ...roi, x: Number(e.target.value) })}
            />
          </label>
          <label>
            ROI Y
            <input
              aria-label="ROI Y"
              type="range"
              min=".1"
              max=".9"
              step=".01"
              value={roi.y}
              onChange={(e) => setRoi({ ...roi, y: Number(e.target.value) })}
            />
          </label>
          <span>Click image to move the shared lens.</span>
        </div>
      )}
      <p className={s.caption}>
        {source === 'saved'
          ? 'Saved evaluation · same held-out camera'
          : 'Exact model render · same immutable camera request'}{' '}
        · source {camera.width} × {camera.height} px. Error is absolute RGB difference ×4; it is not
        LPIPS. ROI [{Math.round(Math.max(0, roi.x * camera.width - roiWidth / 2))},{' '}
        {Math.round(Math.max(0, roi.y * camera.height - roiHeight / 2))},{' '}
        {Math.round(Math.min(camera.width, roi.x * camera.width + roiWidth / 2))},{' '}
        {Math.round(Math.min(camera.height, roi.y * camera.height + roiHeight / 2))}] source pixels.
      </p>
      {source === 'live' && job && (
        <div className={s.panelTools}>
          <button onClick={() => download(dataset.title + '-render.json', job)}>
            Export render metadata
          </button>
          {job.methods.map((m) => (
            <a key={m} href={job.results?.[m]?.image} download={dataset.title + '-' + m + '.png'}>
              Download {m} PNG
            </a>
          ))}
        </div>
      )}
      {source === 'live' && job && (
        <p className={s.caption}>
          Render #{job.id.slice(0, 8)} · {job.methods.join(' + ')} ·{' '}
          {job.methods
            .map((m) => m + ': ' + job.results?.[m]?.seconds.toFixed(3) + ' s')
            .join(' / ')}{' '}
          · camera, run keys and SHA-256 are available in the render record. This camera has no
          measured PSNR/SSIM/LPIPS or ground-truth photograph.
        </p>
      )}
    </section>
  );
}
