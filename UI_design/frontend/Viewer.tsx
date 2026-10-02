import { useEffect, useRef, useState, useImperativeHandle, forwardRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { SplatMesh, SparkRenderer } from '@sparkjsdev/spark';
import type { Dataset, Method, Camera, Catalog } from './types';
import s from './studio.module.css';
import { download } from './api';
export type ViewerHandle = {
  camera: () => Camera;
  reset: () => void;
  preset: (camera: Camera) => void;
  rotate: (value: boolean) => void;
  screenshot: () => void;
};
type Adapter = {
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  controls: OrbitControls;
  dispose: () => void;
  tick?: () => void;
  grid: THREE.GridHelper;
  axes: THREE.AxesHelper;
  frustums: THREE.Group;
  points?: THREE.Points;
  cancelLoad?: () => void;
};
function apply(camera: THREE.PerspectiveCamera, c: Camera) {
  const m = c.camera_to_world;
  const matrix = new THREE.Matrix4().set(
    ...([...m[0], ...m[1], ...m[2], 0, 0, 0, 1] as [
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
    ]),
  );
  matrix.decompose(camera.position, camera.quaternion, camera.scale);
  camera.up.set(m[0][1], m[1][1], m[2][1]).normalize();
  camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(c.height / (2 * c.fy)));
  camera.updateMatrixWorld();
}
export default forwardRef<
  ViewerHandle,
  {
    dataset: Dataset;
    mode: 'both' | Method;
    catalog: Catalog;
    onMove: () => void;
    initialCamera?: Camera;
    paused?: boolean;
  }
>(function Viewer({ dataset, mode, catalog, onMove, initialCamera, paused: renderPaused }, ref) {
  const hosts = useRef<Record<string, HTMLDivElement | null>>({});
  const adapters = useRef<Adapter[]>([]);
  const [states, setStates] = useState<Record<string, string>>({});
  const [fps, setFps] = useState(0);
  const paused = useRef(false);
  useEffect(() => {
    paused.current = !!renderPaused;
  }, [renderPaused]);
  const [retryKey, setRetryKey] = useState(0);
  const sync = useRef(true);
  const [syncEnabled, setSyncEnabled] = useState(true);
  const [overlays, setOverlays] = useState(false);
  const [frustumsVisible, setFrustumsVisible] = useState(false);
  const [pointSize, setPointSize] = useState(0.003);
  const retained = useRef<{
    scene: string;
    camera: Camera;
  } | null>(null);
  const activeAdapter = useRef<Adapter | null>(null);
  const fly = useRef(false);
  const [walking, setWalking] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const getCamera = (): Camera => {
    const a = activeAdapter.current || adapters.current[0];
    if (!a) return structuredClone(dataset.views[0].camera);
    a.camera.updateMatrixWorld();
    const m = a.camera.matrixWorld.elements;
    const width = 640,
      height = Math.round(width / (dataset.views[0].camera.width / dataset.views[0].camera.height));
    const fy = height / (2 * Math.tan(THREE.MathUtils.degToRad(a.camera.fov) / 2));
    return {
      width,
      height,
      fx: fy,
      fy,
      cx: width / 2,
      cy: height / 2,
      camera_to_world: [
        [m[0], m[4], m[8], m[12]],
        [m[1], m[5], m[9], m[13]],
        [m[2], m[6], m[10], m[14]],
      ],
    };
  };
  const preset = (c: Camera) => {
    for (const a of adapters.current) {
      apply(a.camera, c);
      // OrbitControls caches the up-frame; refresh it when restoring a camera
      // with a different roll, so subsequent dragging retains the saved pose.
      const internal = a.controls as unknown as {
        _quat: THREE.Quaternion;
        _quatInverse: THREE.Quaternion;
      };
      internal._quat.setFromUnitVectors(a.camera.up, new THREE.Vector3(0, 1, 0));
      internal._quatInverse.copy(internal._quat).invert();
      const target = new THREE.Vector3(0, 0, -1)
        .applyQuaternion(a.camera.quaternion)
        .multiplyScalar(Math.max(0.3, a.camera.position.length()))
        .add(a.camera.position);
      a.controls.target.copy(target);
      a.controls.update();
    }
  };
  useImperativeHandle(ref, () => ({
    camera: getCamera,
    preset,
    reset: () => preset(dataset.views[0].camera),
    rotate: (value) => {
      for (const a of adapters.current) a.controls.autoRotate = value;
    },
    screenshot: () => {
      const canvas = document.createElement('canvas');
      const views = adapters.current;
      canvas.width = views.reduce((n, a) => n + a.renderer.domElement.width, 0);
      canvas.height = Math.max(...views.map((a) => a.renderer.domElement.height)) + 55;
      const ctx = canvas.getContext('2d')!;
      ctx.fillStyle = '#141a1b';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      let offset = 0;
      views.forEach((a, i) => {
        ctx.drawImage(a.renderer.domElement, offset, 55);
        ctx.fillStyle = 'white';
        ctx.font = '20px Segoe UI';
        ctx.fillText(
          dataset.title +
            ' · ' +
            (mode === 'both'
              ? i === 0
                ? 'Nerfacto point proxy'
                : 'Splatfacto Gaussian'
              : mode === 'nerfacto'
                ? 'Nerfacto point proxy'
                : 'Splatfacto Gaussian'),
          offset + 15,
          33,
        );
        offset += a.renderer.domElement.width;
      });
      download(dataset.title + '-browser.metadata.json', {
        schema_version: 1,
        catalog_revision: catalog.revision,
        scene: dataset.id,
        mode,
        camera: getCamera(),
        runs: dataset.methods,
        browser: navigator.userAgent,
        representation: 'browser proxy / Gaussian; not CUDA evaluation',
      });
      if (canvas) {
        canvas.toBlob((blob) => {
          if (blob) {
            const a = document.createElement('a');
            a.download = dataset.title + '-browser.png';
            a.href = URL.createObjectURL(blob);
            a.click();
            setTimeout(() => URL.revokeObjectURL(a.href), 1000);
          }
        });
      }
    },
  }));
  useEffect(() => {
    let disposed = false,
      raf = 0,
      frames = 0,
      last = performance.now();
    const methods: Method[] = mode === 'both' ? ['nerfacto', 'splatfacto'] : [mode];
    setStates({});
    const instances: Adapter[] = [];
    adapters.current = instances;
    const update = (m: Method, value: string) => {
      if (!disposed) setStates((x) => ({ ...x, [m]: value }));
    };
    for (const method of methods) {
      const host = hosts.current[method];
      if (!host) continue;
      let renderer: THREE.WebGLRenderer;
      try {
        renderer = new THREE.WebGLRenderer({
          antialias: false,
          powerPreference: 'high-performance',
          preserveDrawingBuffer: true,
        });
      } catch (error) {
        update(method, 'WebGL unavailable: ' + String(error));
        continue;
      }
      renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
      renderer.setClearColor('#141a1b');
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      host.appendChild(renderer.domElement);
      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(55, 1, 0.01, 200);
      apply(
        camera,
        retained.current?.scene === dataset.id
          ? retained.current.camera
          : initialCamera || dataset.views[0].camera,
      );
      const controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = false;
      controls.dampingFactor = 0.1;
      controls.minDistance = 0.02;
      controls.maxDistance = 50;
      apply(
        camera,
        retained.current?.scene === dataset.id
          ? retained.current.camera
          : initialCamera || dataset.views[0].camera,
      );
      controls.target.copy(
        new THREE.Vector3(0, 0, -1)
          .applyQuaternion(camera.quaternion)
          .multiplyScalar(Math.max(0.3, camera.position.length()))
          .add(camera.position),
      );
      controls.update();
      const grid = new THREE.GridHelper(6, 30, 0x455456, 0x283336);
      grid.rotation.x = Math.PI / 2;
      grid.position.z = -0.8;
      grid.visible = overlays;
      scene.add(grid);
      const axes = new THREE.AxesHelper(0.2);
      axes.visible = overlays;
      scene.add(axes);
      const frustums = new THREE.Group();
      frustums.visible = frustumsVisible;
      dataset.views.forEach((v) => {
        const c = new THREE.PerspectiveCamera(50, v.camera.width / v.camera.height, 0.02, 0.12);
        apply(c, v.camera);
        c.updateProjectionMatrix();
        frustums.add(new THREE.CameraHelper(c));
      });
      scene.add(frustums);
      let pending: Promise<void> | null = null;
      const abort = new AbortController();
      let load: Promise<void> | null = null;
      let worker: Worker | undefined,
        mesh: SplatMesh | undefined,
        spark: SparkRenderer | undefined,
        points: THREE.Points | undefined;
      const observer = new ResizeObserver(() => {
        const { width, height } = host.getBoundingClientRect();
        renderer.setSize(Math.max(1, width), Math.max(1, height));
        camera.aspect = width / Math.max(1, height);
        camera.updateProjectionMatrix();
      });
      observer.observe(host);
      const instance: Adapter = {
        renderer,
        scene,
        camera,
        controls,
        grid,
        axes,
        frustums,
        cancelLoad: () => {
          abort.abort();
          worker?.terminate();
          update(method, 'Cancelled · use Retry assets to reopen');
        },
        dispose: () => {
          observer.disconnect();
          frustums.children.forEach((f) => (f as THREE.CameraHelper).dispose());
          worker?.terminate();
          abort.abort();
          controls.dispose();
          void Promise.allSettled([pending, load]).then(() => {
            mesh?.dispose();
            spark?.dispose();
            renderer.dispose();
            renderer.forceContextLoss();
          });
          points?.geometry.dispose();
          if (points) (points.material as THREE.Material).dispose();
          grid.geometry.dispose();
          (grid.material as THREE.Material).dispose();
          axes.geometry.dispose();
          (axes.material as THREE.Material).dispose();
          renderer.domElement.remove();
        },
      };
      instances.push(instance);
      let syncing = false;
      controls.addEventListener('start', () => {
        activeAdapter.current = instance;
        instances.forEach((a) => (a.controls.autoRotate = false));
      });
      controls.addEventListener('change', () => {
        if (syncing) return;
        activeAdapter.current = instance;
        onMove();
        if (!sync.current) return;
        for (const other of instances) {
          if (other === instance) continue;
          syncing = true;
          other.camera.position.copy(camera.position);
          other.camera.quaternion.copy(camera.quaternion);
          other.camera.fov = camera.fov;
          other.camera.updateProjectionMatrix();
          other.controls.target.copy(controls.target);
          syncing = false;
        }
      });
      renderer.domElement.addEventListener('webglcontextlost', (event) => {
        event.preventDefault();
        update(method, 'Graphics context lost. Reopen this scene to retry.');
      });
      const run = dataset.methods[method];
      update(method, 'Downloading · 0%');
      if (run.bytes > catalog.ui.DecodeLimitBytes || (run.vertices ?? 0) > catalog.ui.MaxVertices) {
        update(method, 'Asset exceeds decode budget');
        continue;
      }
      if (method === 'splatfacto') {
        spark = new SparkRenderer({
          renderer,
          autoUpdate: false,
          minSortIntervalMs: 0,
          enableLod: false,
        });
        scene.add(spark);
        instance.tick = () => {
          if (mesh?.isInitialized && !pending) {
            pending = spark!
              .update({ scene, camera })
              .catch((error) => {
                if (!disposed) update(method, String(error));
              })
              .finally(() => {
                pending = null;
              });
          }
        };
        load = fetch(run.asset, { signal: abort.signal })
          .then(async (response) => {
            if (!response.ok || !response.body) throw new Error('Gaussian download failed');
            const reader = response.body.getReader();
            const stream = new ReadableStream<Uint8Array>({
              async pull(controller) {
                try {
                  const chunk = await reader.read();
                  if (chunk.done) controller.close();
                  else controller.enqueue(chunk.value);
                } catch {
                  controller.close();
                }
              },
              cancel() {
                abort.abort();
                return reader.cancel().catch(() => {});
              },
            });
            mesh = new SplatMesh({
              stream,
              streamLength: run.bytes,
              fileName: 'splat.ply',
              lod: false,
              onProgress: (e) =>
                update(method, `Downloading · ${Math.round((e.loaded / run.bytes) * 100)}%`),
            });
            scene.add(mesh);
            await mesh.initialized;
            if (mesh.numSplats > catalog.ui.MaxVertices)
              throw new Error('Gaussian vertex budget exceeded');
          })
          .then(() => {
            if (disposed) return;
            update(method, `${mesh!.numSplats.toLocaleString()} Gaussian · ready`);
            performance.mark('gaussian-ready');
          })
          .catch((error) => update(method, String(error)));
      } else {
        worker = new Worker(new URL('./point.worker.ts', import.meta.url), { type: 'module' });
        worker.postMessage({
          url: run.asset,
          maxVertices: catalog.ui.MaxVertices,
          maxBytes: catalog.ui.DecodeLimitBytes,
        });
        worker.onmessage = (e) => {
          if (disposed) return;
          if (e.data.error) {
            update(method, e.data.error);
            return;
          }
          const geometry = new THREE.BufferGeometry();
          geometry.setAttribute('position', new THREE.BufferAttribute(e.data.position, 3));
          geometry.setAttribute('color', new THREE.BufferAttribute(e.data.color, 3));
          points = new THREE.Points(
            geometry,
            new THREE.PointsMaterial({
              size: pointSize,
              vertexColors: true,
              sizeAttenuation: true,
            }),
          );
          scene.add(points);
          instance.points = points;
          update(method, `${e.data.count.toLocaleString()} points · proxy ready`);
          worker?.terminate();
          performance.mark('point-ready');
        };
        worker.onerror = (e) => update(method, e.message);
      }
    }
    const keys = new Set<string>();
    const down = (e: KeyboardEvent) => {
      if (
        fly.current &&
        !(e.target as HTMLElement).closest('input,button,select,textarea') &&
        ['KeyW', 'KeyA', 'KeyS', 'KeyD'].includes(e.code)
      ) {
        e.preventDefault();
        keys.add(e.code);
      }
    };
    const up = (e: KeyboardEvent) => keys.delete(e.code);
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    let previous = performance.now();
    const animate = () => {
      raf = requestAnimationFrame(animate);
      if (document.hidden || paused.current) return;
      const nowTick = performance.now(),
        dt = Math.min(0.05, (nowTick - previous) / 1000);
      previous = nowTick;
      if (fly.current && keys.size) {
        const a = activeAdapter.current || instances[0];
        if (a) {
          const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(a.camera.quaternion),
            side = new THREE.Vector3(1, 0, 0).applyQuaternion(a.camera.quaternion);
          const shift = forward
            .multiplyScalar((keys.has('KeyW') ? 1 : 0) - (keys.has('KeyS') ? 1 : 0))
            .add(side.multiplyScalar((keys.has('KeyD') ? 1 : 0) - (keys.has('KeyA') ? 1 : 0)))
            .multiplyScalar(dt * 0.5);
          for (const b of sync.current ? instances : [a]) {
            if (b.camera.position.clone().add(shift).length() < 50) {
              b.camera.position.add(shift);
              b.controls.target.add(shift);
            }
          }
          onMove();
        }
      }
      for (const a of instances) {
        a.controls.update();
        a.tick?.();
        a.renderer.render(a.scene, a.camera);
      }
      frames++;
      const now = performance.now();
      if (now - last > 1000) {
        setFps(Math.round((frames * 1000) / (now - last)));
        last = now;
        frames = 0;
      }
    };
    animate();
    return () => {
      retained.current = { scene: dataset.id, camera: getCamera() };
      activeAdapter.current = null;
      disposed = true;
      cancelAnimationFrame(raf);
      window.removeEventListener('keydown', down);
      window.removeEventListener('keyup', up);
      instances.forEach((a) => a.dispose());
      adapters.current = [];
    };
  }, [dataset.id, mode, catalog.revision, retryKey]);
  return (
    <>
      <div className={s.structureTools}>
        <button onClick={() => adapters.current.forEach((a) => a.cancelLoad?.())}>
          Cancel loading
        </button>
        <button onClick={() => setRetryKey((x) => x + 1)}>Retry assets</button>
        <label>
          <input
            type="checkbox"
            checked={syncEnabled}
            onChange={(e) => {
              setSyncEnabled(e.target.checked);
              sync.current = e.target.checked;
              if (e.target.checked) {
                const c = getCamera();
                preset(c);
              }
            }}
          />{' '}
          Sync cameras
        </label>
        <label>
          <input
            type="checkbox"
            checked={overlays}
            onChange={(e) => {
              setOverlays(e.target.checked);
              adapters.current.forEach((a) => {
                a.grid.visible = e.target.checked;
                a.axes.visible = e.target.checked;
              });
            }}
          />{' '}
          Grid / axes
        </label>
        <label>
          <input
            type="checkbox"
            checked={frustumsVisible}
            onChange={(e) => {
              setFrustumsVisible(e.target.checked);
              adapters.current.forEach((a) => (a.frustums.visible = e.target.checked));
            }}
          />{' '}
          Eval camera coverage
        </label>
        <label>
          Point size
          <input
            aria-label="Point size"
            type="range"
            min=".001"
            max=".015"
            step=".001"
            value={pointSize}
            onChange={(e) => {
              const value = Number(e.target.value);
              setPointSize(value);
              adapters.current.forEach((a) => {
                if (a.points) (a.points.material as THREE.PointsMaterial).size = value;
              });
            }}
          />
        </label>
        <button onClick={() => root.current?.requestFullscreen().catch(() => {})}>
          Fullscreen
        </button>
        <button
          aria-pressed={walking}
          onClick={() => {
            setWalking(!walking);
            fly.current = !walking;
          }}
        >
          Walk in scene · WASD
        </button>
      </div>
      <div ref={root} className={s.viewports} data-testid="viewer">
        <div className={s.viewerHelp}>
          Drag orbit · scroll zoom · right-drag pan <span>{fps} browser FPS</span>
        </div>
        {(mode === 'both' ? ['nerfacto', 'splatfacto'] : [mode]).map((m) => (
          <section className={s.viewport} key={m} aria-label={m + ' 3D view'}>
            <div className={s.viewportLabel}>
              <b>{m === 'nerfacto' ? 'N · Nerfacto' : 'S · Splatfacto'}</b>
              <span>{m === 'nerfacto' ? 'Point cloud proxy' : 'Gaussian reconstruction'}</span>
            </div>
            <div
              className={s.canvasHost}
              ref={(node) => {
                hosts.current[m] = node;
              }}
            />
            <div className={s.viewportState} role="status">
              {states[m] || 'Starting renderer…'}
            </div>
          </section>
        ))}
      </div>
    </>
  );
});
