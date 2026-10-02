import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import type { Catalog, Dataset } from './types';
import s from './studio.module.css';
const remembered = { x: 0, z: 5, yaw: 0 };
export default function Gallery({
  catalog,
  onChoose,
  paused = false,
}: {
  catalog: Catalog;
  onChoose: (d: Dataset) => void;
  paused?: boolean;
}) {
  const host = useRef<HTMLDivElement>(null),
    speedRef = useRef(1.6),
    tourRef = useRef(false),
    teleport = useRef<(i: number) => void>(() => {}),
    move = useRef({ x: 0, z: 0 });
  const pausedRef = useRef(paused);
  pausedRef.current = paused;
  const [speed, setSpeed] = useState(1.6),
    [tour, setTour] = useState(false),
    [focus, setFocus] = useState(0),
    [error, setError] = useState(''),
    [locked, setLocked] = useState(false);
  useEffect(() => {
    speedRef.current = speed;
  }, [speed]);
  useEffect(() => {
    tourRef.current = tour;
  }, [tour]);
  useEffect(() => {
    const container = host.current!;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    } catch (e) {
      setError(String(e));
      return;
    }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    renderer.setClearColor('#f0ebe0');
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog('#f0ebe0', 15, 40);
    const camera = new THREE.PerspectiveCamera(60, 1, 0.05, 80);
    camera.position.set(remembered.x, 1.65, remembered.z);
    let yaw = remembered.yaw,
      pitch = 0;
    scene.add(new THREE.HemisphereLight(0xffffff, 0xa49274, 2));
    const sun = new THREE.DirectionalLight(0xfff1db, 3);
    sun.position.set(4, 9, 2);
    scene.add(sun);
    const disposable: THREE.Object3D[] = [];
    const box = (
      w: number,
      h: number,
      d: number,
      color: string,
      x: number,
      y: number,
      z: number,
    ) => {
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(w, h, d),
        new THREE.MeshStandardMaterial({ color, roughness: 0.85 }),
      );
      mesh.position.set(x, y, z);
      scene.add(mesh);
      disposable.push(mesh);
      return mesh;
    };
    box(14, 0.1, 30, '#b5a792', 0, -0.05, -7);
    box(0.2, 5, 30, '#eee8dc', -7, 2.5, -7);
    box(0.2, 5, 30, '#eee8dc', 7, 2.5, -7);
    box(14, 5, 0.2, '#eee8dc', 0, 2.5, -22);
    box(14, 5, 0.2, '#eee8dc', 0, 2.5, 8);
    for (let z = -20; z < 8; z += 2) {
      box(14, 0.008, 0.02, '#9d8e7b', 0, 0.009, z);
    }
    const textureLoader = new THREE.TextureLoader();
    const textureList: THREE.Texture[] = [];
    const exhibits: THREE.Object3D[] = [];
    catalog.scenes.forEach((dataset, index) => {
      const left = index % 2 === 0;
      const x = left ? -5.2 : 5.2,
        z = 2 - Math.floor(index / 2) * 7;
      const group = new THREE.Group();
      group.position.set(x, 2.1, z);
      group.rotation.y = left ? Math.PI / 2 : -Math.PI / 2;
      scene.add(group);
      const ratio = dataset.views[0].camera.width / dataset.views[0].camera.height;
      const w = Math.min(3.5, 2.3 * ratio),
        h = w / ratio;
      const frame = new THREE.Mesh(
        new THREE.BoxGeometry(w + 0.25, h + 0.25, 0.15),
        new THREE.MeshStandardMaterial({ color: '#39312a', metalness: 0.3, roughness: 0.45 }),
      );
      group.add(frame);
      disposable.push(frame);
      const texture = textureLoader.load(dataset.cover);
      texture.colorSpace = THREE.SRGBColorSpace;
      textureList.push(texture);
      const picture = new THREE.Mesh(
        new THREE.PlaneGeometry(w, h),
        new THREE.MeshBasicMaterial({ map: texture }),
      );
      picture.position.z = 0.09;
      picture.userData.index = index;
      group.add(picture);
      exhibits.push(picture);
      disposable.push(picture);
      const canvas = document.createElement('canvas');
      canvas.width = 768;
      canvas.height = 140;
      const ctx = canvas.getContext('2d')!;
      ctx.fillStyle = '#f7f3ea';
      ctx.fillRect(0, 0, 768, 140);
      ctx.fillStyle = '#252b2c';
      ctx.font = 'bold 38px Segoe UI';
      ctx.fillText(String(index + 1).padStart(2, '0') + '  ' + dataset.title, 24, 52);
      ctx.font = '24px Segoe UI';
      ctx.fillText(
        dataset.train_count + ' train · ' + dataset.eval_count + ' held-out · N / S',
        24,
        98,
      );
      const labelTexture = new THREE.CanvasTexture(canvas);
      labelTexture.colorSpace = THREE.SRGBColorSpace;
      textureList.push(labelTexture);
      const label = new THREE.Mesh(
        new THREE.PlaneGeometry(2.7, 0.5),
        new THREE.MeshBasicMaterial({ map: labelTexture }),
      );
      label.position.set(0, -h / 2 - 0.45, 0.1);
      group.add(label);
      disposable.push(label);
      const light = new THREE.PointLight(0xffe9ca, 5, 8);
      light.position.set(x * 0.65, 4, z);
      scene.add(light);
    });
    const keys = new Set<string>(),
      raycaster = new THREE.Raycaster();
    let dragging = false,
      lastX = 0,
      lastY = 0,
      startX = 0,
      startY = 0,
      frame = 0,
      previous = performance.now(),
      current = 0;
    const applyLook = () => {
      camera.rotation.order = 'YXZ';
      camera.rotation.set(pitch, yaw, 0);
    };
    applyLook();
    teleport.current = (i) => {
      if (i < 0) {
        camera.position.set(0, 1.65, 5);
        yaw = 0;
        pitch = 0;
        applyLook();
        setFocus(0);
        return;
      }
      const left = i % 2 === 0;
      camera.position.set(left ? -2 : 2, 1.65, 2 - Math.floor(i / 2) * 7);
      yaw = left ? Math.PI / 2 : -Math.PI / 2;
      pitch = 0;
      applyLook();
      setFocus(i);
    };
    const keyDown = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest('input,select,textarea,button')) return;
      if (
        [
          'KeyW',
          'KeyA',
          'KeyS',
          'KeyD',
          'ArrowUp',
          'ArrowDown',
          'ArrowLeft',
          'ArrowRight',
        ].includes(e.code)
      ) {
        e.preventDefault();
        keys.add(e.code);
        tourRef.current = false;
        setTour(false);
      }
      if (e.code === 'Enter' || e.code === 'KeyE') onChoose(catalog.scenes[current]);
    };
    const keyUp = (e: KeyboardEvent) => keys.delete(e.code);
    const pointerDown = (e: PointerEvent) => {
      dragging = true;
      startX = lastX = e.clientX;
      startY = lastY = e.clientY;
      tourRef.current = false;
      setTour(false);
      renderer.domElement.setPointerCapture(e.pointerId);
    };
    const pointerMove = (e: PointerEvent) => {
      if (document.pointerLockElement === renderer.domElement) {
        yaw -= e.movementX * 0.002;
        pitch -= e.movementY * 0.002;
      } else if (dragging) {
        yaw -= (e.clientX - lastX) * 0.004;
        pitch -= (e.clientY - lastY) * 0.004;
        lastX = e.clientX;
        lastY = e.clientY;
      } else return;
      pitch = THREE.MathUtils.clamp(pitch, -1, 1);
      applyLook();
    };
    const pointerUp = (e: PointerEvent) => {
      dragging = false;
      if (Math.hypot(e.clientX - startX, e.clientY - startY) < 5) {
        const bounds = renderer.domElement.getBoundingClientRect();
        raycaster.setFromCamera(
          new THREE.Vector2(
            ((e.clientX - bounds.left) / bounds.width) * 2 - 1,
            (-(e.clientY - bounds.top) / bounds.height) * 2 + 1,
          ),
          camera,
        );
        const hit = raycaster.intersectObjects(exhibits)[0];
        if (hit && hit.distance < 10) onChoose(catalog.scenes[hit.object.userData.index]);
      }
    };
    const lockChange = () => setLocked(document.pointerLockElement === renderer.domElement);
    const doubleClick = () => renderer.domElement.requestPointerLock();
    window.addEventListener('keydown', keyDown);
    window.addEventListener('keyup', keyUp);
    const blur = () => {
      keys.clear();
      move.current = { x: 0, z: 0 };
    };
    window.addEventListener('blur', blur);
    document.addEventListener('pointerlockchange', lockChange);
    renderer.domElement.addEventListener('pointerdown', pointerDown);
    renderer.domElement.addEventListener('pointermove', pointerMove);
    renderer.domElement.addEventListener('pointerup', pointerUp);
    renderer.domElement.addEventListener('dblclick', doubleClick);
    const resize = new ResizeObserver(() => {
      renderer.setSize(container.clientWidth, container.clientHeight);
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
    });
    resize.observe(container);
    let tourTime = 0,
      tourIndex = 0;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      const now = performance.now(),
        dt = Math.min(0.05, (now - previous) / 1000);
      previous = now;
      if (document.hidden || pausedRef.current) return;
      const forward =
          (keys.has('KeyW') || keys.has('ArrowUp') ? 1 : 0) -
          (keys.has('KeyS') || keys.has('ArrowDown') ? 1 : 0) +
          move.current.z,
        side =
          (keys.has('KeyD') || keys.has('ArrowRight') ? 1 : 0) -
          (keys.has('KeyA') || keys.has('ArrowLeft') ? 1 : 0) +
          move.current.x;
      const norm = Math.max(1, Math.hypot(forward, side));
      camera.position.x +=
        ((-Math.sin(yaw) * forward + Math.cos(yaw) * side) / norm) * dt * speedRef.current;
      camera.position.z +=
        ((-Math.cos(yaw) * forward - Math.sin(yaw) * side) / norm) * dt * speedRef.current;
      camera.position.x = THREE.MathUtils.clamp(camera.position.x, -6.3, 6.3);
      camera.position.z = THREE.MathUtils.clamp(camera.position.z, -21, 7);
      if (tourRef.current) {
        tourTime += dt;
        const left = tourIndex % 2 === 0;
        const target = new THREE.Vector3(left ? -2 : 2, 1.65, 2 - Math.floor(tourIndex / 2) * 7);
        camera.position.lerp(target, 1 - Math.exp(-dt * speedRef.current));
        const desiredYaw = left ? Math.PI / 2 : -Math.PI / 2;
        const turn = Math.atan2(Math.sin(desiredYaw - yaw), Math.cos(desiredYaw - yaw));
        yaw += turn * (1 - Math.exp(-dt * speedRef.current));
        pitch *= Math.exp(-dt * speedRef.current);
        applyLook();
        if (tourTime > 6 / speedRef.current) {
          tourTime = 0;
          tourIndex = (tourIndex + 1) % catalog.scenes.length;
        }
      }
      raycaster.setFromCamera(new THREE.Vector2(0, 0), camera);
      const hits = raycaster.intersectObjects(exhibits);
      if (hits[0] && hits[0].distance < 10) {
        const next = hits[0].object.userData.index;
        if (current !== next) {
          current = next;
          setFocus(next);
        }
      }
      remembered.x = camera.position.x;
      remembered.z = camera.position.z;
      remembered.yaw = yaw;
      renderer.render(scene, camera);
    };
    animate();
    return () => {
      cancelAnimationFrame(frame);
      resize.disconnect();
      window.removeEventListener('keydown', keyDown);
      window.removeEventListener('keyup', keyUp);
      window.removeEventListener('blur', blur);
      document.removeEventListener('pointerlockchange', lockChange);
      if (document.pointerLockElement) document.exitPointerLock();
      textureList.forEach((t) => t.dispose());
      disposable.forEach((o) => {
        const m = o as THREE.Mesh;
        m.geometry.dispose();
        (m.material as THREE.Material).dispose();
      });
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    };
  }, [catalog.revision]);
  const selected = catalog.scenes[focus];
  return (
    <div className={s.gallery}>
      <div
        className={s.galleryCanvas}
        ref={host}
        role="img"
        aria-label="Walkable 3D image gallery"
      />
      {error && <div role="alert">{error} · Select a dataset below.</div>}
      <div className={s.galleryIntro}>
        <span className={s.eyebrow}>The spatial collection</span>
        <h1>Walk into the image.</h1>
        <p>
          WASD / arrows to walk · drag to look
          <br />
          Double-click for mouse look · Esc releases it
        </p>
      </div>
      <div className={s.crosshair}>+</div>
      <div className={s.gallerySelection}>
        <span>
          Exhibit {focus + 1} / {catalog.scenes.length}
        </span>
        <h2>{selected.title}</h2>
        <p>{selected.subtitle}</p>
        <button className={s.primary} onClick={() => onChoose(selected)}>
          Open reconstruction ↗
        </button>
      </div>
      <div className={s.galleryDock}>
        <label>
          Walking speed
          <input
            aria-label="Walking speed"
            type="range"
            min=".5"
            max="3"
            step=".1"
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
          />
          <span>{speed.toFixed(1)} m/s</span>
        </label>
        <button aria-pressed={tour} onClick={() => setTour(!tour)}>
          {tour ? 'Stop tour' : 'Guided tour'}
        </button>
        <button onClick={() => teleport.current(-1)}>Reset walk</button>
        <span>{locked ? 'Mouse look active' : 'Drag to look'}</span>
        <div className={s.touchArrows}>
          {[
            ['↑', 0, 1],
            ['←', -1, 0],
            ['↓', 0, -1],
            ['→', 1, 0],
          ].map(([label, x, z]) => (
            <button
              key={label}
              aria-label={'Walk ' + label}
              onPointerDown={(e) => {
                e.currentTarget.setPointerCapture(e.pointerId);
                move.current = { x: Number(x), z: Number(z) };
              }}
              onPointerUp={() => {
                move.current = { x: 0, z: 0 };
              }}
              onPointerCancel={() => {
                move.current = { x: 0, z: 0 };
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <nav className={s.galleryMap} aria-label="Gallery exhibits">
        {catalog.scenes.map((d, i) => (
          <button key={d.id} onClick={() => teleport.current(i)} aria-pressed={i === focus}>
            <img src={d.cover} alt="" />
            <span>
              {i + 1}. {d.title}
            </span>
          </button>
        ))}
      </nav>
    </div>
  );
}
