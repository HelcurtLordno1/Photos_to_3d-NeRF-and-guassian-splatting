import assert from 'node:assert/strict';
import { writeFile, mkdir } from 'node:fs/promises';
const url = process.argv[2] || 'http://127.0.0.1:7016';
const catalog = await (await fetch(url + '/api/catalog')).json();
const post = (path, body, headers = {}) =>
  fetch(url + path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Origin: url,
      'X-UI-CSRF': catalog.csrf,
      ...headers,
    },
    body: JSON.stringify(body),
  });
assert.equal(catalog.scenes.length, 5);
const range = await fetch(url + catalog.scenes[0].methods.splatfacto.asset, {
  headers: { Range: 'bytes=0-15' },
});
assert.equal(range.status, 206);
assert.equal((await range.arrayBuffer()).byteLength, 16);
assert.equal(
  (
    await fetch(url + catalog.scenes[0].methods.splatfacto.asset, {
      headers: { Range: 'bytes=99999999999-' },
    })
  ).status,
  416,
);
assert.equal((await fetch(url + '/api/assets/unknown')).status, 404);
assert.equal((await post('/api/lease', {}, { 'X-UI-CSRF': 'wrong' })).status, 403);
assert.equal((await post('/api/lease', {}, { Origin: 'http://untrusted.invalid' })).status, 403);
const token = (await (await post('/api/lease', {})).json()).token;
try {
  assert.equal((await post('/api/lease', {})).status, 409);
  const camera = structuredClone(catalog.scenes[0].views[0].camera);
  camera.camera_to_world[0][0] = 10;
  const request = {
    token,
    revision: catalog.revision,
    scene: catalog.scenes[0].id,
    methods: ['nerfacto', 'splatfacto'],
    camera,
  };
  assert.equal((await post('/api/jobs', request)).status, 400);
  request.camera = structuredClone(catalog.scenes[0].views[0].camera);
  request.revision = 'stale';
  assert.equal((await post('/api/jobs', request)).status, 400);
  assert.equal((await post('/api/jobs', [])).status, 400);
} finally {
  assert.equal((await post('/api/release', { token })).status, 200);
}
assert.equal((await fetch(url + '/api/report/review/research_review.html')).status, 200);
const out = new URL('../../artifacts/ui/qa/api/', import.meta.url);
await mkdir(out, { recursive: true });
await writeFile(
  new URL('result.json', out),
  JSON.stringify(
    {
      status: 'passed',
      revision: catalog.revision,
      checks: [
        'five exact scenes',
        'byte ranges',
        'unknown asset',
        'CSRF',
        'Origin',
        'single owner',
        'invalid pose',
        'stale revision',
        'malformed body',
        'release',
        'original report',
      ],
    },
    null,
    2,
  ),
);
console.log('API CONTRACTS PASS', catalog.revision);
