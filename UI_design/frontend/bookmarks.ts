import type { Bookmark } from './types';
export function importBookmarks(raw: string): Bookmark[] {
  if (raw.length > 1000000) throw new Error('Bookmark file is too large');
  const parsed = JSON.parse(raw);
  if (
    !parsed ||
    parsed.schema_version !== 1 ||
    !Array.isArray(parsed.bookmarks) ||
    parsed.bookmarks.length > 200
  )
    throw new Error('Unsupported bookmark backup');
  const ids = new Set<string>();
  return parsed.bookmarks.map((b: Bookmark) => {
    if (
      typeof b.id !== 'string' ||
      ids.has(b.id) ||
      typeof b.title !== 'string' ||
      b.title.length > 120 ||
      typeof b.scene !== 'string' ||
      typeof b.revision !== 'string' ||
      !b.camera ||
      !Array.isArray(b.camera.camera_to_world) ||
      b.camera.camera_to_world.length !== 3 ||
      b.camera.camera_to_world.some(
        (r) => !Array.isArray(r) || r.length !== 4 || r.some((n) => !Number.isFinite(n)),
      ) ||
      ![b.camera.width, b.camera.height, b.camera.fx, b.camera.fy, b.camera.cx, b.camera.cy].every(
        Number.isFinite,
      ) ||
      b.camera.width < 32 ||
      !Number.isInteger(b.camera.width) ||
      !Number.isInteger(b.camera.height) ||
      b.camera.height < 32 ||
      b.camera.width > 4096 ||
      b.camera.height > 4096 ||
      b.camera.fx <= 0 ||
      b.camera.fy <= 0 ||
      b.camera.cx < 0 ||
      b.camera.cx > b.camera.width ||
      b.camera.cy < 0 ||
      b.camera.cy > b.camera.height
    )
      throw new Error('Invalid bookmark');
    const matrix = b.camera.camera_to_world;
    const determinant =
      matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1]) -
      matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0]) +
      matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0]);
    if (Math.abs(determinant - 1) > 1e-3) throw new Error('Invalid bookmark rotation');
    for (let i = 0; i < 3; i++)
      for (let j = 0; j < 3; j++)
        if (
          Math.abs(
            matrix[i].slice(0, 3).reduce((n, v, k) => n + v * matrix[j][k], 0) - (i === j ? 1 : 0),
          ) > 1e-3
        )
          throw new Error('Invalid bookmark rotation');
    ids.add(b.id);
    return b;
  });
}
