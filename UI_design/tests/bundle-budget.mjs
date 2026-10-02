import { readFile, readdir, writeFile } from 'node:fs/promises';
import { gzipSync } from 'node:zlib';
const root = new URL('../dist/', import.meta.url),
  html = await readFile(new URL('index.html', root), 'utf8');
const initial = [...html.matchAll(/(?:src|href)="(\/assets\/[^\"]+\.(?:js|css))"/g)].map(
  (m) => m[1],
);
let bytes = 0;
for (const file of initial) bytes += gzipSync(await readFile(new URL('.' + file, root))).length;
if (bytes > 180 * 1024) throw new Error(`Initial bundle exceeds 180 KiB gzip: ${bytes}`);
const chunks = [];
for (const file of await readdir(new URL('assets/', root))) {
  if (file.endsWith('.js'))
    chunks.push({ file, gzip: gzipSync(await readFile(new URL('assets/' + file, root))).length });
}
// Spark embeds decoder WASM + worker JS; it is a lazy renderer-only exception.
for (const c of chunks) {
  const limit = c.file.startsWith('Viewer-') ? 1100 * 1024 : 600 * 1024;
  if (c.gzip > limit) throw new Error(`Lazy chunk budget exceeded: ${c.file}`);
}
console.log(
  JSON.stringify(
    {
      initial_gzip_bytes: bytes,
      initial_limit: 180 * 1024,
      largest: chunks.sort((a, b) => b.gzip - a.gzip).slice(0, 5),
    },
    null,
    2,
  ),
);
