import React, { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ArrowUpRight,
  Box,
  Columns2,
  Image as ImageIcon,
  ChartNoAxesCombined,
  RotateCcw,
  Bookmark as BookmarkIcon,
  Camera as CameraIcon,
  HelpCircle,
  Sun,
  Moon,
  MoveUpRight,
  Download,
  Play,
  Square,
  Search,
  X,
} from 'lucide-react';
import type { Catalog, Dataset, Method, Bookmark, Job } from './types';
import type { ViewerHandle } from './Viewer';
import { api, download, infer } from './api';
import { importBookmarks } from './bookmarks';
import s from './studio.module.css';
import './global.css';
const Viewer = lazy(() => import('./Viewer')),
  Gallery = lazy(() => import('./Gallery')),
  Research = lazy(() => import('./Research')),
  Compare = lazy(() => import('./Compare'));
class Boundary extends React.Component<
  {
    children: React.ReactNode;
  },
  {
    error: string;
  }
> {
  state = { error: '' };
  static getDerivedStateFromError(error: Error) {
    return { error: error.message };
  }
  render() {
    return this.state.error ? (
      <div className={s.failure} role="alert">
        <h2>This view could not open.</h2>
        <p>{this.state.error}</p>
        <button
          onClick={() => {
            this.setState({ error: '' });
          }}
        >
          Retry view
        </button>{' '}
        <button onClick={() => location.reload()}>Reload studio</button>
      </div>
    ) : (
      this.props.children
    );
  }
}
function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null),
    [fatal, setFatal] = useState(''),
    [route, setRoute] = useState<'collection' | 'workspace' | 'gallery'>('collection'),
    [selected, setSelected] = useState('custom:tea_sets_2'),
    [tab, setTab] = useState<'3d' | 'images' | 'research'>('3d'),
    [mode, setMode] = useState<'both' | Method>('both'),
    [query, setQuery] = useState(''),
    [help, setHelp] = useState(false),
    [onboarding, setOnboarding] = useState(() => !localStorage.getItem('topic16-onboarded')),
    [step, setStep] = useState(0),
    [theme, setTheme] = useState(() => localStorage.getItem('topic16-theme') || 'light'),
    [locale, setLocale] = useState(() => localStorage.getItem('topic16-locale') || 'vi'),
    [shortcuts, setShortcuts] = useState(true),
    [rotating, setRotating] = useState(false),
    [bookmarks, setBookmarks] = useState<Bookmark[]>(() => {
      try {
        return importBookmarks(
          localStorage.getItem('topic16-bookmarks') || '{"schema_version":1,"bookmarks":[]}',
        );
      } catch {
        return [];
      }
    }),
    [bookmarkPanel, setBookmarkPanel] = useState(false),
    [notice, setNotice] = useState(''),
    [job, setJob] = useState<Job | null>(null),
    [complete, setComplete] = useState<Job | null>(null),
    [quality, setQuality] = useState(640),
    [submitting, setSubmitting] = useState(false),
    [imported, setImported] = useState<Bookmark[] | null>(null),
    [restored, setRestored] = useState<Bookmark | null>(null),
    [readiness, setReadiness] = useState<{
      state: string;
      reason?: string;
    }>({ state: 'checking' });
  const viewer = useRef<ViewerHandle>(null),
    token = useRef(''),
    sequence = useRef(0),
    poll = useRef<ReturnType<typeof setInterval> | null>(null),
    active = useRef<Job | null>(null);
  useEffect(() => {
    if (!notice) return;
    const timeout = setTimeout(() => setNotice(''), 8000);
    return () => clearTimeout(timeout);
  }, [notice]);
  const en = locale === 'en';
  const t = (vi: string, english: string) => (en ? english : vi);
  useEffect(() => {
    api<Catalog>('/api/catalog')
      .then((c) => {
        if (c.schema_version !== 1) throw new Error('Unsupported catalog version');
        setCatalog(c);
        const scene = new URLSearchParams(location.search).get('scene');
        if (scene && c.scenes.some((d) => d.id === scene)) setSelected(scene);
      })
      .catch((error) => setFatal(String(error)));
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.lang = locale;
    localStorage.setItem('topic16-theme', theme);
    localStorage.setItem('topic16-locale', locale);
  }, [theme, locale]);
  useEffect(() => {
    localStorage.setItem('topic16-bookmarks', JSON.stringify({ schema_version: 1, bookmarks }));
  }, [bookmarks]);
  useEffect(() => {
    if (!catalog) return;
    const ready = () =>
      api<{
        state: string;
        reason?: string;
      }>('/api/readiness')
        .then(setReadiness)
        .catch(() => {});
    ready();
    const readyTimer = setInterval(ready, 5000);
    const heartbeat = setInterval(() => {
      if (token.current && !document.hidden)
        api('/api/lease', { token: token.current }, catalog.csrf).catch((error) => {
          setNotice(String(error));
          token.current = '';
        });
    }, catalog.ui.HeartbeatSeconds * 1000);
    const unload = () => {
      if (token.current)
        fetch('/api/release', {
          method: 'POST',
          keepalive: true,
          headers: { 'Content-Type': 'application/json', 'X-UI-CSRF': catalog.csrf },
          body: JSON.stringify({ token: token.current }),
        }).catch(() => {});
    };
    const visibility = () => {
      if (document.hidden && token.current) {
        unload();
        token.current = '';
        sequence.current++;
        active.current = null;
      }
    };
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('pagehide', unload);
    return () => {
      clearInterval(heartbeat);
      clearInterval(readyTimer);
      document.removeEventListener('visibilitychange', visibility);
      window.removeEventListener('pagehide', unload);
      if (poll.current) clearInterval(poll.current);
    };
  }, [catalog]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (
        !shortcuts ||
        help ||
        onboarding ||
        (e.target as HTMLElement).closest('input,select,textarea,button,[contenteditable]')
      )
        return;
      if (e.code === 'Digit1') setTab('3d');
      if (e.code === 'Digit2') setTab('images');
      if (e.code === 'Digit3') setTab('research');
      if (e.code === 'KeyR') viewer.current?.reset();
      if (e.code === 'Escape') {
        setBookmarkPanel(false);
        setHelp(false);
      }
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [shortcuts, help, onboarding]);
  const move = () => {
    if (active.current?.status === 'succeeded') return;
    if (active.current) {
      if (catalog && token.current)
        api(`/api/jobs/${active.current.id}/cancel`, { token: token.current }, catalog.csrf).catch(
          () => {},
        );
      sequence.current++;
      active.current = null;
      setNotice(
        t(
          'Camera đã đổi; kết quả render cũ sẽ không áp dụng.',
          'Camera changed; stale results will not be applied.',
        ),
      );
    }
  };
  const choose = (d: Dataset) => {
    setRestored(null);
    sequence.current++;
    if (active.current && catalog && token.current)
      api(`/api/jobs/${active.current.id}/cancel`, { token: token.current }, catalog.csrf).catch(
        () => {},
      );
    active.current = null;
    setSelected(d.id);
    setComplete(null);
    // Keep tracking a cancelled worker until it unwinds; drawing stays paused.
    setRoute('workspace');
    setTab('3d');
    setRotating(false);
  };
  if (fatal)
    return (
      <div className={s.failure}>
        <h1>Studio could not connect</h1>
        <p>{fatal}</p>
        <button onClick={() => location.reload()}>Retry</button>
        <p>Run UI_design\scripts\Start-UI.ps1</p>
      </div>
    );
  if (!catalog)
    return (
      <div className={s.loading}>
        SPATIAL / STUDIO<span>Loading the verified collection…</span>
      </div>
    );
  const dataset = catalog.scenes.find((d) => d.id === selected) || catalog.scenes[0];
  const run = async () => {
    if (submitting || (job && ['queued', 'running'].includes(job.status))) return;
    setSubmitting(true);
    const id = ++sequence.current;
    viewer.current?.rotate(false);
    setRotating(false);
    try {
      if (!token.current) {
        const lease = await api<{
          token: string;
        }>('/api/lease', {}, catalog.csrf);
        token.current = lease.token;
      }
      if (document.hidden) {
        await api('/api/release', { token: token.current }, catalog.csrf);
        token.current = '';
        return;
      }
      if (id !== sequence.current) return;
      const camera = structuredClone(viewer.current?.camera() || dataset.views[0].camera);
      const ratio = quality / camera.width;
      camera.width = quality;
      camera.height = Math.round(camera.height * ratio);
      camera.fx *= ratio;
      camera.fy *= ratio;
      camera.cx *= ratio;
      camera.cy *= ratio;
      const requested = await infer(
        catalog,
        token.current,
        dataset.id,
        mode === 'both' ? ['nerfacto', 'splatfacto'] : [mode],
        camera,
        id,
      );
      if (id !== sequence.current || document.hidden) {
        await api(`/api/jobs/${requested.id}/cancel`, { token: token.current }, catalog.csrf);
      }
      setJob(requested);
      active.current = requested;
      setNotice(
        t(
          'Đang render camera này; hai model chạy tuần tự.',
          'Rendering this camera; the two models run sequentially.',
        ),
      );
      if (poll.current) clearInterval(poll.current);
      poll.current = setInterval(async () => {
        try {
          const status = await api<Job>('/api/jobs/' + requested.id);
          setJob(status);
          if (['succeeded', 'failed', 'cancelled'].includes(status.status)) {
            clearInterval(poll.current!);
            poll.current = null;
            active.current = null;
            if (status.status === 'succeeded' && status.sequence === sequence.current) {
              setComplete(status);
              setTab('images');
              setNotice(
                t(
                  'Đã hoàn tất render. Chọn live-N / live-S để so sánh.',
                  'Render complete. Select live-N / live-S to compare.',
                ),
              );
            } else if (status.status === 'failed' && status.sequence === sequence.current)
              setNotice(status.error || 'Render failed');
            else if (status.sequence === sequence.current)
              setNotice(
                t(
                  'Kết quả đã bị hủy hoặc camera không còn khớp.',
                  'Result was cancelled or its camera is stale.',
                ),
              );
          }
        } catch (error) {
          setNotice(String(error));
          clearInterval(poll.current!);
        }
      }, 1000);
    } catch (error) {
      setNotice(String(error));
    } finally {
      setSubmitting(false);
    }
  };
  const saveBookmark = () => {
    const b: Bookmark = {
      id: crypto.randomUUID(),
      scene: dataset.id,
      title: dataset.title + ' · ' + new Date().toLocaleTimeString(),
      revision: catalog.revision,
      camera: viewer.current?.camera() || dataset.views[0].camera,
      created_at: new Date().toISOString(),
    };
    setBookmarks((x) => [...x, b].slice(-200));
    setNotice(t('Đã lưu góc nhìn.', 'View bookmarked.'));
  };
  const print = new URLSearchParams(location.search).has('report');
  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className={s.header}>
        <button
          className={s.brand}
          onClick={() => setRoute('collection')}
          aria-label="Spatial Studio home"
        >
          <Box size={25} />
          <span>
            SPATIAL<span className={s.brandSlash}> / </span>STUDIO
            <small>NeRF & Gaussian splatting</small>
          </span>
        </button>
        <nav aria-label="Main navigation">
          <button
            aria-current={route === 'collection' ? 'page' : undefined}
            onClick={() => setRoute('collection')}
          >
            {t('Bộ sưu tập', 'Collection')}
          </button>
          <button
            aria-current={route === 'gallery' ? 'page' : undefined}
            onClick={() => setRoute('gallery')}
          >
            Art gallery <ArrowUpRight size={14} />
          </button>
          <button
            aria-current={route === 'workspace' ? 'page' : undefined}
            onClick={() => setRoute('workspace')}
          >
            {t('Không gian 3D', 'Workspace')}
          </button>
        </nav>
        <div className={s.headerActions}>
          <select aria-label="Language" value={locale} onChange={(e) => setLocale(e.target.value)}>
            <option value="vi">VI</option>
            <option value="en">EN</option>
          </select>
          <button
            className={s.iconButton}
            aria-label="Toggle theme"
            onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
          >
            {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
          </button>
          <button className={s.iconButton} aria-label="Help" onClick={() => setHelp(true)}>
            <HelpCircle size={19} />
          </button>
        </div>
      </header>
      <main id="main">
        {print ? (
          <Suspense fallback={<div className={s.loading}>Loading report…</div>}>
            <h1 className="srOnly">{dataset.title} · research report</h1>
            <Research catalog={catalog} dataset={dataset} />
            <button onClick={() => window.print()}>Print / Save PDF</button>
          </Suspense>
        ) : route === 'collection' ? (
          <>
            <section className={s.hero}>
              <div className={s.heroCopy}>
                <span className={s.eyebrow}>TOPIC 16 / COMPUTER VISION</span>
                <h1>
                  From photographs.
                  <br />
                  <em>Into space.</em>
                </h1>
                <p>
                  {t(
                    'Đi quanh một bức ảnh. Khám phá hai cách tái dựng không gian và tự đánh giá bằng cùng một góc nhìn.',
                    'Walk around a photograph. Explore two ways to reconstruct a space, and compare them from the same viewpoint.',
                  )}
                </p>
                <div className={s.heroButtons}>
                  <button className={s.primary} onClick={() => choose(catalog.scenes[0])}>
                    {t('Khám phá bộ trà', 'Explore the tea set')} <ArrowUpRight size={18} />
                  </button>
                  <button className={s.textButton} onClick={() => setRoute('gallery')}>
                    {t('Bước vào gallery', 'Enter the gallery')} <MoveUpRight size={18} />
                  </button>
                </div>
                <div className={s.heroStats}>
                  <div>
                    <b>{catalog.scenes.length.toString().padStart(2, '0')}</b>
                    <span>{t('không gian', 'scenes')}</span>
                  </div>
                  <div>
                    <b>02</b>
                    <span>{t('phương pháp', 'methods')}</span>
                  </div>
                  <div>
                    <b>30k</b>
                    <span>{t('iterations mỗi run', 'iterations per run')}</span>
                  </div>
                </div>
              </div>
              <div className={s.heroArt}>
                <img
                  src={catalog.scenes[0].cover}
                  alt="Tea sets from the actual held-out dataset"
                />
                <div className={s.heroArtLabel}>
                  <span>01 / TEA SETS</span>
                  <span>
                    Custom capture · reconstructed in 3D <ArrowUpRight size={18} />
                  </span>
                </div>
                <span className={s.heroArtIndex}>N / S</span>
              </div>
            </section>
            <section className={s.collection}>
              <div className={s.sectionTitle}>
                <div>
                  <span className={s.eyebrow}>{t('CHỌN MỘT KHÔNG GIAN', 'CHOOSE A SPACE')}</span>
                  <h2>{t('Một bộ ảnh. Hai cách nhìn.', 'One collection. Two perspectives.')}</h2>
                </div>
                <label className={s.search}>
                  <Search size={17} />
                  <input
                    aria-label="Search datasets"
                    placeholder={t('Tìm dataset…', 'Find a dataset…')}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </label>
              </div>
              <div className={s.cardGrid}>
                {catalog.scenes
                  .filter((d) =>
                    (d.title + ' ' + d.id + ' ' + d.subtitle)
                      .toLowerCase()
                      .includes(query.toLowerCase()),
                  )
                  .map((d, i) => (
                    <button className={s.datasetCard} key={d.id} onClick={() => choose(d)}>
                      <div className={s.cardImage}>
                        <img src={d.cover} alt={d.title + ' actual dataset image'} loading="lazy" />
                        <span>{String(i + 1).padStart(2, '0')}</span>
                        <div className={s.cardArrow}>
                          <ArrowUpRight size={23} />
                        </div>
                      </div>
                      <div className={s.cardText}>
                        <h3>{d.title}</h3>
                        <p>{d.subtitle}</p>
                        <div>
                          <span>
                            {d.train_count} train / {d.eval_count} eval
                          </span>
                          <b>{d.scope.toUpperCase()}</b>
                        </div>
                      </div>
                    </button>
                  ))}
              </div>
            </section>
            <footer className={s.footer}>
              <span>TOPIC 16 · PHOTOS TO 3D</span>
              <p>Nerfacto / Splatfacto · exact paired artifacts</p>
              <button
                onClick={() => {
                  setRoute('workspace');
                  setTab('research');
                }}
              >
                {t('Xem benchmark & kiến trúc', 'View benchmarks & architecture')} ↗
              </button>
            </footer>
          </>
        ) : route === 'gallery' ? (
          <Boundary>
            <Suspense fallback={<div className={s.loading}>Opening the gallery…</div>}>
              <Gallery
                catalog={catalog}
                onChoose={choose}
                paused={
                  readiness.state === 'busy' ||
                  (!!job && ['queued', 'running'].includes(job.status))
                }
              />
            </Suspense>
          </Boundary>
        ) : (
          <div className={s.workspace}>
            <h1 className="srOnly">
              {dataset.title} · {t('Không gian 3D', '3D workspace')}
            </h1>
            <div className={s.workspaceBar}>
              <div>
                <span className={s.eyebrow}>{t('KHÔNG GIAN ĐANG KHÁM PHÁ', 'CURRENT SPACE')}</span>
                <select
                  aria-label="Dataset"
                  value={dataset.id}
                  onChange={(e) => choose(catalog.scenes.find((d) => d.id === e.target.value)!)}
                >
                  {catalog.scenes.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.title} · {d.train_count} train / {d.eval_count} eval
                    </option>
                  ))}
                </select>
              </div>
              <div className={s.tabs}>
                {[
                  ['3d', Box, t('Khám phá 3D', 'Explore 3D')],
                  ['images', ImageIcon, t('So sánh ảnh', 'Image comparison')],
                  [
                    'research',
                    ChartNoAxesCombined,
                    t('Benchmark & kiến trúc', 'Benchmarks & architecture'),
                  ],
                ].map(([value, Icon, label]) => {
                  const Glyph = Icon as typeof Box;
                  return (
                    <button
                      key={String(value)}
                      aria-pressed={tab === value}
                      onClick={() => setTab(value as typeof tab)}
                    >
                      <Glyph size={17} />
                      {String(label)}
                    </button>
                  );
                })}
              </div>
              <button className={s.textButton} onClick={() => setRoute('gallery')}>
                Gallery ↗
              </button>
            </div>
            {tab === '3d' ? (
              <>
                <div className={s.controls}>
                  <div className={s.segment}>
                    {(['both', 'nerfacto', 'splatfacto'] as const).map((m) => (
                      <button
                        key={m}
                        aria-pressed={mode === m}
                        onClick={() => {
                          move();
                          setMode(m);
                        }}
                      >
                        {m === 'both' ? (
                          <>
                            <Columns2 size={16} /> {t('Song song', 'Side by side')}
                          </>
                        ) : m === 'nerfacto' ? (
                          'N · Nerfacto'
                        ) : (
                          'S · Splatfacto'
                        )}
                      </button>
                    ))}
                  </div>
                  <div className={s.controlsRight}>
                    <select
                      aria-label="Camera preset"
                      onChange={(e) => {
                        viewer.current?.preset(dataset.views[Number(e.target.value)].camera);
                        move();
                      }}
                    >
                      {dataset.views.map((v) => (
                        <option key={v.index} value={v.index}>
                          Camera #{v.index}
                        </option>
                      ))}
                    </select>
                    <button aria-label="Reset camera" onClick={() => viewer.current?.reset()}>
                      <RotateCcw size={17} />
                    </button>
                    <button
                      aria-label="Rotate object"
                      aria-pressed={rotating}
                      onClick={() => {
                        setRotating(!rotating);
                        viewer.current?.rotate(!rotating);
                      }}
                    >
                      <Play size={16} />
                    </button>
                    <button aria-label="Save camera bookmark" onClick={saveBookmark}>
                      <BookmarkIcon size={17} />
                    </button>
                    <button
                      aria-label="Export viewer screenshot"
                      onClick={() => viewer.current?.screenshot()}
                    >
                      <CameraIcon size={17} />
                    </button>
                    <button onClick={() => setBookmarkPanel(!bookmarkPanel)}>
                      {t('Góc đã lưu', 'Bookmarks')} ({bookmarks.length})
                    </button>
                  </div>
                </div>
                <Boundary key={dataset.id}>
                  <Suspense fallback={<div className={s.loading}>Loading 3D renderer…</div>}>
                    <Viewer
                      ref={viewer}
                      dataset={dataset}
                      mode={mode}
                      catalog={catalog}
                      onMove={move}
                      initialCamera={restored?.scene === dataset.id ? restored.camera : undefined}
                      paused={
                        readiness.state === 'busy' ||
                        (!!job && ['queued', 'running'].includes(job.status))
                      }
                    />
                  </Suspense>
                </Boundary>
                <div className={s.inferenceBar}>
                  <div>
                    <b>
                      {t('Render góc nhìn này', 'Render this viewpoint')} · {readiness.state}
                    </b>
                    <p>
                      {readiness.reason ||
                        t(
                          'Di chuyển mượt bằng preview; render checkpoint chính xác khi bạn dừng.',
                          'Explore with the preview; render the exact checkpoint when you stop.',
                        )}
                    </p>
                  </div>
                  <select
                    aria-label="Render resolution"
                    value={quality}
                    onChange={(e) => setQuality(Number(e.target.value))}
                  >
                    <option value={320}>320 px · quick</option>
                    <option value={640}>640 px · balanced</option>
                    <option value={960}>960 px · detailed</option>
                  </select>
                  <button
                    className={s.primary}
                    onClick={run}
                    disabled={
                      readiness.state === 'not-enabled' ||
                      readiness.state === 'checking' ||
                      submitting ||
                      (!!job && ['queued', 'running'].includes(job.status))
                    }
                  >
                    <CameraIcon size={17} />
                    {t('Render ảnh model', 'Render model image')}
                  </button>
                  {job && ['queued', 'running'].includes(job.status) && (
                    <button
                      onClick={() =>
                        api(`/api/jobs/${job.id}/cancel`, { token: token.current }, catalog.csrf)
                      }
                    >
                      <Square size={14} /> Cancel
                    </button>
                  )}
                </div>
                <p className={s.caption}>
                  Nerfacto:{' '}
                  {t(
                    'point cloud là proxy để di chuyển; ảnh model dùng checkpoint NeRF.',
                    'the point cloud is a navigation proxy; model images use the NeRF checkpoint.',
                  )}{' '}
                  Splatfacto: Spark browser preview. {dataset.alignment}
                </p>
                {job && (
                  <p className={s.jobStatus} role="status">
                    {job.status.toUpperCase()} · {job.phase || 'queued'} · #{job.id.slice(0, 8)}
                  </p>
                )}
              </>
            ) : (
              <Boundary key={tab + dataset.id}>
                <Suspense fallback={<div className={s.loading}>Loading panel…</div>}>
                  {tab === 'images' ? (
                    <Compare key={dataset.id} dataset={dataset} job={complete} />
                  ) : (
                    <Research catalog={catalog} dataset={dataset} />
                  )}
                </Suspense>
              </Boundary>
            )}
            {bookmarkPanel && (
              <aside className={s.bookmarks}>
                <div className={s.sectionTitle}>
                  <h3>{t('Góc nhìn đã lưu', 'Saved viewpoints')}</h3>
                  <button aria-label="Close bookmarks" onClick={() => setBookmarkPanel(false)}>
                    <X size={17} />
                  </button>
                </div>
                <button
                  onClick={() =>
                    download('spatial-bookmarks.json', { schema_version: 1, bookmarks })
                  }
                >
                  <Download size={15} /> Backup JSON
                </button>
                <label className={s.fileLabel}>
                  Import JSON
                  <input
                    type="file"
                    accept="application/json"
                    onChange={async (e) => {
                      try {
                        const file = e.target.files?.[0];
                        if (file) setImported(importBookmarks(await file.text()));
                      } catch (error) {
                        setNotice(String(error));
                      }
                      e.target.value = '';
                    }}
                  />
                </label>
                {imported && (
                  <div>
                    <p>
                      Preview: {imported.length} bookmarks ·{' '}
                      {imported.filter((b) => !catalog.scenes.some((d) => d.id === b.scene)).length}{' '}
                      unresolved scene references
                    </p>
                    <button
                      onClick={() => {
                        setBookmarks((x) =>
                          [...new Map([...x, ...imported].map((b) => [b.id, b])).values()].slice(
                            -200,
                          ),
                        );
                        setImported(null);
                      }}
                    >
                      Merge
                    </button>
                    <button
                      onClick={() => {
                        setBookmarks(imported);
                        setImported(null);
                      }}
                    >
                      Replace
                    </button>
                    <button onClick={() => setImported(null)}>Cancel</button>
                  </div>
                )}
                {bookmarks.map((b) => (
                  <div className={s.bookmarkRow} key={b.id}>
                    <button
                      onClick={() => {
                        if (b.scene !== dataset.id) {
                          const target = catalog.scenes.find((d) => d.id === b.scene);
                          if (target) {
                            choose(target);
                            setRestored(b);
                          } else setNotice('Unresolved scene: ' + b.scene);
                        } else {
                          viewer.current?.preset(b.camera);
                          move();
                          setNotice(
                            b.revision === catalog.revision
                              ? 'Camera restored'
                              : 'Camera restored from an earlier catalog revision',
                          );
                        }
                      }}
                    >
                      {b.title}
                      <small>{b.scene}</small>
                    </button>
                    <button
                      aria-label={'Delete ' + b.title}
                      onClick={() => setBookmarks((x) => x.filter((y) => y.id !== b.id))}
                    >
                      <X size={15} />
                    </button>
                  </div>
                ))}
              </aside>
            )}
          </div>
        )}
      </main>
      {notice && (
        <div className={s.toast} role="status">
          <span>{notice}</span>
          <button aria-label="Dismiss notification" onClick={() => setNotice('')}>
            <X size={16} />
          </button>
        </div>
      )}
      {(help || onboarding) && (
        <div className={s.modalBackdrop}>
          <section
            className={s.modal}
            role="dialog"
            aria-modal="true"
            aria-labelledby="help-title"
            tabIndex={-1}
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                setHelp(false);
                setOnboarding(false);
                localStorage.setItem('topic16-onboarded', '1');
              }
              if (e.key === 'Tab') {
                const buttons = e.currentTarget.querySelectorAll<HTMLElement>('button,input');
                const first = buttons[0],
                  last = buttons[buttons.length - 1];
                if (e.shiftKey && document.activeElement === first) {
                  e.preventDefault();
                  last.focus();
                } else if (!e.shiftKey && document.activeElement === last) {
                  e.preventDefault();
                  first.focus();
                }
              }
            }}
          >
            <span className={s.eyebrow}>
              {onboarding ? `WELCOME / 0${step + 1}` : 'STUDIO GUIDE'}
            </span>
            <h2 id="help-title">
              {onboarding
                ? [
                    t('Chọn một không gian.', 'Choose a space.'),
                    t('Di chuyển và so sánh.', 'Explore and compare.'),
                    t('Nhìn kỹ. Đo chính xác.', 'Look closer. Measure fairly.'),
                  ][step]
                : t('Bạn đang ở Spatial Studio.', 'You are in Spatial Studio.')}
            </h2>
            <p>
              {onboarding
                ? [
                    t(
                      'Mỗi ảnh đại diện lấy từ dữ liệu thật. Chọn ảnh ở Collection hoặc đi qua gallery để mở scene.',
                      'Every cover is an actual dataset image. Select a collection image or walk through the gallery.',
                    ),
                    t(
                      'Kéo để xoay, cuộn để zoom, chuột phải để pan. Hai model dùng chung camera; chọn N hoặc S để xem riêng.',
                      'Drag to orbit, scroll to zoom, right-drag to pan. Both views share a camera; choose N or S to show one.',
                    ),
                    t(
                      'Xem ảnh GT/model, wipe, error; đọc PSNR/SSIM/LPIPS và diagram. Render ảnh model khi muốn đánh giá một góc mới.',
                      'Compare GT/model images with wipe and error tools. Read benchmarks and diagrams. Render a model image to evaluate a new angle.',
                    ),
                  ][step]
                : t(
                    '1 = 3D · 2 = ảnh · 3 = benchmark · R = reset. Gallery: WASD/arrow, Enter mở tranh, Esc thoát mouse look. Touch: orbit một ngón, pinch zoom, hai ngón pan.',
                    '1 = 3D · 2 = images · 3 = benchmarks · R = reset. Gallery: WASD/arrows, Enter opens exhibit, Esc releases mouse look. Touch: one-finger orbit, pinch zoom, two-finger pan.',
                  )}
            </p>
            {!onboarding && (
              <>
                <label>
                  <input
                    type="checkbox"
                    checked={shortcuts}
                    onChange={(e) => setShortcuts(e.target.checked)}
                  />{' '}
                  Keyboard shortcuts
                </label>
                <p className={s.caption}>
                  Saved bookmarks belong to this browser origin. Use JSON backup when changing
                  ports. No dataset is trained automatically when opening the studio.
                </p>
                <button
                  onClick={() => {
                    setHelp(false);
                    setOnboarding(true);
                    setStep(0);
                  }}
                >
                  Reopen onboarding
                </button>
              </>
            )}
            <div className={s.modalButtons}>
              <button
                autoFocus
                onClick={() => {
                  setHelp(false);
                  setOnboarding(false);
                  localStorage.setItem('topic16-onboarded', '1');
                }}
              >
                {onboarding ? t('Bỏ qua', 'Skip') : t('Đóng', 'Close')}
              </button>
              {onboarding && (
                <button
                  className={s.primary}
                  onClick={() => {
                    if (step === 2) {
                      setOnboarding(false);
                      localStorage.setItem('topic16-onboarded', '1');
                    } else setStep(step + 1);
                  }}
                >
                  {step === 2 ? t('Bắt đầu', 'Start exploring') : t('Tiếp tục', 'Next')}{' '}
                  <ArrowUpRight size={16} />
                </button>
              )}
            </div>
          </section>
        </div>
      )}
    </>
  );
}
createRoot(document.getElementById('root')!).render(
  <Boundary>
    <App />
  </Boundary>,
);
