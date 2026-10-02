import { describe, it, expect } from 'vitest';
import { importBookmarks } from '../frontend/bookmarks';
const bookmark = {
  id: 'one',
  title: 'Tea',
  scene: 'custom:tea_sets_2',
  revision: 'r1',
  created_at: '2026-10-02',
  camera: {
    width: 320,
    height: 480,
    fx: 100,
    fy: 100,
    cx: 160,
    cy: 240,
    camera_to_world: [
      [1, 0, 0, 0],
      [0, 1, 0, 0],
      [0, 0, 1, 0],
    ],
  },
};
describe('portable bookmarks', () => {
  it('preserves scene, immutable revision and camera', () =>
    expect(importBookmarks(JSON.stringify({ schema_version: 1, bookmarks: [bookmark] }))).toEqual([
      bookmark,
    ]));
  it.each([
    null,
    {},
    { schema_version: 2, bookmarks: [] },
    { schema_version: 1, bookmarks: [bookmark, bookmark] },
    {
      schema_version: 1,
      bookmarks: [
        {
          ...bookmark,
          camera: {
            ...bookmark.camera,
            camera_to_world: [
              [1, 0, 0, 0],
              [0, 1, 0, 0],
              [0, 0, -1, 0],
            ],
          },
        },
      ],
    },
    {
      schema_version: 1,
      bookmarks: [
        {
          ...bookmark,
          camera: {
            ...bookmark.camera,
            camera_to_world: [
              [1, 0],
              [0, 1],
              [0, 0],
            ],
          },
        },
      ],
    },
  ])('rejects malformed or unsupported backups %j', (value) =>
    expect(() => importBookmarks(JSON.stringify(value))).toThrow(),
  );
});
