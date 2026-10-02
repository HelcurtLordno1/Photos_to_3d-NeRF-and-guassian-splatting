import type { Catalog, Job, Camera, Method } from './types';
export async function api<T>(path: string, body?: unknown, csrf?: string): Promise<T> {
  const response = await fetch(
    path,
    body === undefined
      ? undefined
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-UI-CSRF': csrf || '' },
          body: JSON.stringify(body),
        },
  );
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data as T;
}
export async function infer(
  catalog: Catalog,
  token: string,
  scene: string,
  methods: Method[],
  camera: Camera,
  sequence: number,
) {
  return api<Job>(
    '/api/jobs',
    { token, scene, methods, camera, sequence, revision: catalog.revision },
    catalog.csrf,
  );
}
export function download(name: string, value: unknown) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }),
  );
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
