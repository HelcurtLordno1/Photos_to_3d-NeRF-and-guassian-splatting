import * as THREE from 'three';
import type { Camera } from './types';

/** Preserve full pinhole intrinsics; fit height without stretching when viewport changes. */
export function setCalibratedProjection(camera: THREE.PerspectiveCamera, calibration?: Camera) {
  if (calibration) camera.userData.calibration = { ...calibration };
  const c = camera.userData.calibration as Camera | undefined;
  if (!c) {
    camera.updateProjectionMatrix();
    return;
  }
  const width = c.height * camera.aspect;
  const cx = width / 2 + c.cx - c.width / 2;
  const n = camera.near;
  camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(c.height / (2 * c.fy)));
  camera.projectionMatrix.makePerspective(
    (-cx * n) / c.fx,
    ((width - cx) * n) / c.fx,
    (c.cy * n) / c.fy,
    (-(c.height - c.cy) * n) / c.fy,
    n,
    camera.far,
  );
  camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
}

export function extractIntrinsics(camera: THREE.PerspectiveCamera, width: number, height: number) {
  const e = camera.projectionMatrix.elements;
  return {
    fx: (e[0] * width) / 2,
    fy: (e[5] * height) / 2,
    cx: ((1 - e[8]) * width) / 2,
    cy: ((1 + e[9]) * height) / 2,
  };
}

export function splatFilter(mode: unknown) {
  return mode === 'classic'
    ? { preBlurAmount: 0.3, blurAmount: 0, sortRadial: false }
    : mode === 'antialiased'
      ? { preBlurAmount: 0, blurAmount: 0.3, sortRadial: false }
      : {};
}
