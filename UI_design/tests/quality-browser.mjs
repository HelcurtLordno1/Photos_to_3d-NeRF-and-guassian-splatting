import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const base = process.argv[2] || 'http://127.0.0.1:7016';
const output = new URL('../../upgrade/reports/qa/quality-ui/', import.meta.url);
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
try {
  await page.addInitScript(() => localStorage.setItem('topic16-onboarded', '1'));
  const catalog = await (await page.request.get(base + '/api/catalog')).json();
  assert.equal(catalog.quality.status, 'ready');
  const q = catalog.quality.experiments[0];
  assert.equal(q.rows.length, 6);
  assert.equal(q.models.length, 1);
  assert.ok(!('nerfacto' in q.models[0]));
  await page.goto(base + '/?scene=custom%3Atea_sets_2&tab=quality');
  await page.getByLabel('Quality resolution').waitFor();
  assert.equal(await page.getByLabel('Quality resolution').inputValue(), 'native');
  await page.waitForFunction(() =>
    [...document.querySelectorAll('figure img')].every((i) => i.complete && i.naturalWidth === 719),
  );
  await page.getByLabel('Quality view').selectOption('10');
  await page.waitForFunction(() =>
    [...document.querySelectorAll('figure img')].every((i) => i.complete && i.naturalWidth === 719),
  );
  await page.screenshot({ path: fileURLToPath(new URL('q1-native.png', output)), fullPage: true });
  await page.getByLabel('Quality resolution').selectOption('half');
  await page.waitForFunction(() =>
    [...document.querySelectorAll('figure img')].every((i) => i.complete && i.naturalWidth === 359),
  );
  assert.match(
    await page.getByText('Q1 − 30k half-trained control:', { exact: false }).innerText(),
    /-1\.0114/,
  );
  await page.screenshot({ path: fileURLToPath(new URL('q1-half.png', output)), fullPage: true });
  if (process.argv.includes('--images-only')) {
    await page.waitForFunction(() =>
      [...document.querySelectorAll('button')].some(
        (b) => b.textContent === 'Open Q1 3D' && b.disabled,
      ),
    );
    assert.equal(catalog.visual_research.q15.length, 12);
    await page.getByText('Q1.5 · fixed-checkpoint rendering', { exact: true }).waitFor();
  } else {
    await page.getByRole('button', { name: 'Open Q1 3D', exact: true }).click();
    await page
      .getByText(/Gaussian splats.*browser renderer|SH3|splats loaded|289,331|289331/)
      .first()
      .waitFor({ timeout: 120000 });
  }
  assert.equal(errors.length, 0, errors.join('\n'));
  await page.screenshot({
    path: fileURLToPath(
      new URL(process.argv.includes('--images-only') ? 'q15-busy.png' : 'q1-3d.png', output),
    ),
    fullPage: true,
  });
  await writeFile(
    new URL(process.argv.includes('--images-only') ? 'q15-result.json' : 'result.json', output),
    JSON.stringify(
      {
        status: 'passed',
        study: catalog.visual_research?.study,
        checked_at: new Date().toISOString(),
        errors,
        scope: process.argv.includes('--images-only')
          ? 'Q1 actual images, Q1.5 table, GPU view correctly disabled during research'
          : 'Q1 route, actual native/half images, view10, visible negative delta, single-method Q1 3D',
      },
      null,
      2,
    ),
  );
} finally {
  await browser.close();
}
