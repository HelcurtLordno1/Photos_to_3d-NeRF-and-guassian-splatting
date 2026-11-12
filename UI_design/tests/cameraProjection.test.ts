import { it, expect } from 'vitest';
import * as THREE from 'three';
import {
  setCalibratedProjection,
  extractIntrinsics,
  splatFilter,
} from '../frontend/cameraProjection';
import type { Camera } from '../frontend/types';
const c = {
  width: 359,
  height: 639,
  fx: 535.3967,
  fy: 532.4684,
  cx: 181.048,
  cy: 318.162,
  camera_to_world: [],
} as Camera;
it('round trips asymmetric camera intrinsics without recentering the optical axis', () => {
  const camera = new THREE.PerspectiveCamera();
  camera.aspect = c.width / c.height;
  setCalibratedProjection(camera, c);
  const got = extractIntrinsics(camera, c.width, c.height);
  for (const key of ['fx', 'fy', 'cx', 'cy'] as const) expect(got[key]).toBeCloseTo(c[key], 6);
  const point = new THREE.Vector3(0, 0, -1).project(camera);
  expect(((point.x + 1) * c.width) / 2).toBeCloseTo(c.cx, 6);
  expect(((1 - point.y) * c.height) / 2).toBeCloseTo(c.cy, 6);
});
it('keeps angular scale when resizing a portrait capture into a wide viewport', () => {
  const camera = new THREE.PerspectiveCamera();
  camera.aspect = 16 / 9;
  setCalibratedProjection(camera, c);
  const got = extractIntrinsics(camera, 1136, 639);
  expect(got.fy).toBeCloseTo(c.fy, 6);
  expect(got.fx / got.fy).toBeCloseTo(c.fx / c.fy, 6);
  expect(got.cx - 568).toBeCloseTo(c.cx - c.width / 2, 6);
});
it('chooses filters from the recorded rasterizer rather than applying one to all exports', () => {
  expect(splatFilter('classic')).toEqual({ preBlurAmount: 0.3, blurAmount: 0, sortRadial: false });
  expect(splatFilter('antialiased')).toEqual({
    preBlurAmount: 0,
    blurAmount: 0.3,
    sortRadial: false,
  });
  expect(splatFilter(undefined)).toEqual({});
});
