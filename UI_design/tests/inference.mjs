import { mkdir, writeFile } from 'node:fs/promises';
const url = process.argv[2] || 'http://127.0.0.1:7016';
const catalog = await (await fetch(url + '/api/catalog')).json();
const post = async (path, body) => {
  const response = await fetch(url + path, {
    method: 'POST',
    headers: { Origin: url, 'X-UI-CSRF': catalog.csrf, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(JSON.stringify(data));
  return data;
};
const lease = await post('/api/lease', {});
const heartbeat = setInterval(
  () => post('/api/lease', { token: lease.token }).catch(console.error),
  10000,
);
let job;
try {
  const scene = catalog.scenes.find((s) => s.id === 'custom:tea_sets_2');
  const original = scene.views[0].camera;
  const width = 320,
    ratio = width / original.width;
  const camera = {
    width,
    height: Math.round(original.height * ratio),
    fx: original.fx * ratio,
    fy: original.fy * ratio,
    cx: original.cx * ratio,
    cy: original.cy * ratio,
    camera_to_world: structuredClone(original.camera_to_world),
  };
  // A real novel camera, translated 5 mm in the frozen model coordinate frame.
  camera.camera_to_world[0][3] += 0.005;
  job = await post('/api/jobs', {
    token: lease.token,
    scene: scene.id,
    revision: catalog.revision,
    methods: ['nerfacto', 'splatfacto'],
    camera,
    sequence: 1,
  });
  let previous = '';
  const start = Date.now();
  while (Date.now() - start < 600000) {
    job = await (await fetch(url + '/api/jobs/' + job.id)).json();
    if (job.phase !== previous) {
      console.log(job.status, job.phase || '', job.error || '');
      previous = job.phase;
    }
    if (['succeeded', 'failed', 'cancelled'].includes(job.status)) break;
    await new Promise((r) => setTimeout(r, 1000));
  }
  const out = new URL('../../artifacts/ui/qa/inference/', import.meta.url);
  await mkdir(out, { recursive: true });
  await writeFile(new URL('paired-novel-camera.json', out), JSON.stringify(job, null, 2));
  if (job.status !== 'succeeded') throw new Error(job.error || 'Inference timeout');
  for (const method of job.methods) {
    const response = await fetch(url + job.results[method].image);
    if (!response.ok) throw new Error('Published image not accessible');
    await writeFile(new URL(method + '.png', out), Buffer.from(await response.arrayBuffer()));
  }
  console.log('PAIRED NOVEL CAMERA PASS', job.id, JSON.stringify(job.results));
} finally {
  clearInterval(heartbeat);
  await post('/api/release', { token: lease.token });
}
