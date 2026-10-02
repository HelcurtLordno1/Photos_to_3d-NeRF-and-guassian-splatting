import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('../../', import.meta.url));
const url = process.argv[2] || 'http://127.0.0.1:7016';
const primary = await (await fetch(url + '/api/health')).json();
assert.equal(primary.profile, 'inference', 'Start the primary inference profile before service QA');
const quote = (value) => "'" + value.replaceAll("'", "''") + "'";
const common = quote(path.join(root, 'UI_design/scripts/Common-UI.ps1'));
const state = path.join(root, 'artifacts/ui/server.json');
const original = await readFile(state, 'utf8');
const launch = (script) => {
  const child = spawn('powershell.exe', [
    '-NoProfile',
    '-EncodedCommand',
    Buffer.from(script, 'utf16le').toString('base64'),
  ]);
  let output = '';
  child.stdout.on('data', (data) => (output += data.toString()));
  child.stderr.on('data', (data) => (output += data.toString()));
  const done = new Promise((resolve) => child.on('close', (code) => resolve({ code, output })));
  return { child, done };
};
const bounded = (promise, ms) =>
  Promise.race([
    promise,
    new Promise((_, reject) => {
      const timer = setTimeout(() => reject(new Error('Owned service did not stop in time')), ms);
      timer.unref();
    }),
  ]);
const strict = launch(
  `. ${common}; Invoke-UiPython -Arguments @('serve','--profile','artifacts','--port','${new URL(url).port}')`,
);
try {
  const result = await bounded(strict.done, 15000);
  assert.notEqual(result.code, 0);
  assert.match(result.output, /Requested UI port \d+ is unavailable/);
} finally {
  if (strict.child.exitCode === null)
    execFileSync('taskkill.exe', ['/PID', String(strict.child.pid), '/T', '/F']);
}
const fallback = launch(
  `& ${quote(path.join(root, 'UI_design/scripts/Start-UI.ps1'))} -NoBrowser -Profile artifacts`,
);
let owned;
try {
  for (let i = 0; i < 60; i++) {
    const record = JSON.parse((await readFile(state, 'utf8')).replace(/^\uFEFF/, ''));
    if (record.pid !== primary.pid) {
      const health = await (await fetch(record.url + '/api/health')).json();
      if (health.pid === record.pid && health.profile === 'artifacts') {
        owned = health;
        break;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  assert.ok(owned, 'Auto fallback server did not start');
  assert.notEqual(owned.url, primary.url);
  const catalog = await (await fetch(owned.url + '/api/catalog')).json();
  const shutdown = await fetch(owned.url + '/api/shutdown', {
    method: 'POST',
    headers: {
      Origin: owned.url,
      'X-UI-CSRF': catalog.csrf,
      'Content-Type': 'application/json',
    },
    body: '{}',
  });
  assert.equal(shutdown.status, 200);
  assert.equal((await bounded(fallback.done, 15000)).code, 0);
  assert.equal((await (await fetch(url + '/api/health')).json()).pid, primary.pid);
  await writeFile(
    path.join(root, 'artifacts/ui/qa/ports.json'),
    JSON.stringify(
      {
        status: 'passed',
        strict_occupied_port_rejected: true,
        fallback_url: owned.url,
        fallback_pid: owned.pid,
        stopped: true,
        primary_pid: primary.pid,
        primary_untouched: true,
      },
      null,
      2,
    ),
  );
  console.log('STRICT PORT / AUTO FALLBACK / OWNED STOP PASS');
} finally {
  if (fallback.child.exitCode === null)
    execFileSync('taskkill.exe', ['/PID', String(fallback.child.pid), '/T', '/F']);
  await writeFile(state, original);
}
