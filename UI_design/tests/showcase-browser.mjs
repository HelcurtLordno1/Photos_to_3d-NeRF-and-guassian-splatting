import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';

const job = JSON.parse(await readFile(process.argv[2], 'utf8'));
await mkdir(job.output, { recursive: true });
const catalog = await (await fetch(job.url + '/api/catalog')).json();
const scenes = catalog.final_delivery.scenes;
assert.equal(scenes.length, 5);
assert.equal(catalog.final_delivery.teacher_room?.status, 'ready');
const browser = await chromium.launch({
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  headless: true,
  args: ['--use-angle=d3d11'],
});
const page = await browser.newPage({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 1,
  locale: 'en-US',
});
page.setDefaultTimeout(30000);
const errors = [],
  requests = [],
  rows = [];
page.on('pageerror', (e) => errors.push(e.message));
const plyUrls = new Set(
  scenes.flatMap((s) => Object.values(s.models).map((m) => new URL(m.run.asset, job.url).href)),
);
page.on('request', (req) => {
  if (plyUrls.has(req.url()))
    requests.push({ request: req, url: req.url(), start: performance.now() });
});
page.on('requestfinished', (req) => {
  const row = requests.find((r) => r.request === req);
  if (row) row.end = performance.now();
});
const downloads = (url) => requests.filter((r) => r.url === new URL(url, job.url).href).length;
const tab = (name) => page.getByRole('button', { name, exact: true }).click();
const capture = async (name) => {
  await page.evaluate(() => document.activeElement?.blur?.());
  await page.screenshot({ path: path.join(job.output, name), fullPage: true });
};
const contexts = () =>
  page.evaluate(() => Number(document.documentElement.dataset.viewerContexts || 0));
const release = () =>
  page.waitForFunction(
    () => Number(document.documentElement.dataset.viewerContexts || 0) === 0,
    null,
    { timeout: 30000 },
  );
const imageReady = (width) =>
  page.waitForFunction(
    (w) => {
      const images = [...document.querySelectorAll('img[data-final-image]')];
      return images.length > 0 && images.every((im) => im.complete && im.naturalWidth === w);
    },
    width,
    { timeout: 120000 },
  );
const pose = (canvas) => canvas.getAttribute('data-camera-pose').then(JSON.parse);
const ready = (count) =>
  page
    .getByText(count.toLocaleString('en-US') + ' Gaussian · ready', { exact: true })
    .waitFor({ timeout: 180000 });
try {
  await page.addInitScript(() => {
    localStorage.setItem('topic16-onboarded', '1');
    localStorage.setItem('topic16-locale', 'en');
    localStorage.setItem('topic16-theme', 'light');
    window.__showcaseContexts = [];
    new MutationObserver((records) =>
      records.forEach((r) => {
        if (r.attributeName === 'data-viewer-contexts')
          window.__showcaseContexts.push(Number(r.target.getAttribute(r.attributeName)));
      }),
    ).observe(document, {
      attributes: true,
      subtree: true,
      attributeFilter: ['data-viewer-contexts'],
    });
  });
  await page.goto(job.url + '/?scene=' + encodeURIComponent(scenes[0].scene) + '&tab=quality');
  await page.locator('[data-final-scene]').waitFor();
  for (const scene of scenes) {
    console.log('[showcase] ' + scene.scene + ' | controls, native images and benchmark');
    await page.getByLabel('Dataset', { exact: true }).selectOption(scene.scene);
    await page.waitForFunction(
      (id) => document.querySelector('[data-final-scene]')?.getAttribute('data-final-scene') === id,
      scene.scene,
    );
    assert.equal(await page.getByLabel('Result collection').inputValue(), 'final');
    const variant = page.getByLabel('Variant', { exact: true });
    for (const value of ['baseline', 'upgrade', 'compare'])
      assert.equal(await variant.locator('option[value=' + value + ']').isDisabled(), false);
    const initialRequests = requests.length;
    await tab('Image comparison');
    const index = Math.floor(scene.cameras.length / 2);
    await page.getByLabel('Final view').selectOption(String(index));
    for (const model of ['baseline', 'upgrade']) {
      await variant.selectOption(model);
      await imageReady(scene.cameras[index].width);
      const sources = await page
        .locator('img[data-final-image]')
        .evaluateAll((images) => images.map((im) => im.getAttribute('data-image-model')));
      assert.deepEqual(sources.sort(), ['gt', model].sort());
      assert.equal(
        await page.locator('img[data-image-model=' + model + ']').getAttribute('src'),
        scene.models[model].frames[index].pred,
      );
      await tab('Benchmark');
      assert.equal(
        Number(await page.locator('[data-metric=psnr]').getAttribute('data-metric-value')),
        scene.models[model].metrics.psnr,
      );
      await tab('Image comparison');
      assert.equal(await page.getByLabel('Final view').inputValue(), String(index));
    }
    await variant.selectOption('compare');
    await imageReady(scene.cameras[index].width);
    await page.getByLabel('Comparison split').press('Home');
    assert.equal(await page.getByLabel('Comparison split').inputValue(), '0');
    await page.getByLabel('Comparison split').press('End');
    await page.getByRole('button', { name: 'Difference ×4', exact: true }).click();
    await page.waitForFunction(() => {
      const c = document.querySelector('canvas[aria-label="Absolute RGB difference preview"]');
      return c && c.dataset.differenceReady === 'true' && c.width > 1 && c.height > 1;
    });
    const diff = await page
      .getByLabel('Absolute RGB difference preview')
      .evaluate((c) => ({ width: c.width, height: c.height }));
    assert.ok(Math.max(diff.width, diff.height) <= 1024);
    await page.getByRole('button', { name: 'Wipe', exact: true }).click();
    await page.getByLabel('Comparison split').press('Home');
    for (let i = 0; i < 50; i++) await page.getByLabel('Comparison split').press('ArrowRight');
    await capture(scene.scene.replace(':', '-') + '-images.png');
    await tab('Benchmark');
    assert.match(
      await page
        .getByRole('table', { name: 'Final benchmark', exact: true })
        .locator('tr[data-model=upgrade]')
        .innerText(),
      new RegExp(scene.models.upgrade.metrics.psnr.toFixed(4).replace('.', '\\.')),
    );
    assert.equal(
      await page.getByRole('table', { name: 'Collection benchmark' }).locator('tbody tr').count(),
      5,
    );
    await page.getByRole('button', { name: /^View 0:/ }).click();
    if (scene.scene === 'room') {
      await page.getByText('Nerfacto configuration check · Room A/B/C', { exact: true }).click();
      const diagnostic = page.getByRole('table', { name: 'Room Nerfacto diagnostic' });
      assert.equal(await diagnostic.locator('tbody tr').count(), 4);
      const expected = catalog.final_delivery.teacher_room.rows.find((r) => r.id === 'C');
      assert.ok(
        (await diagnostic.locator('tbody tr').last().innerText()).includes(
          expected.metrics.psnr.toFixed(4),
        ),
      );
    }
    await capture(scene.scene.replace(':', '-') + '-benchmark.png');
    assert.equal(requests.length, initialRequests, 'Image/benchmark navigation fetched a PLY');
    await tab('Image comparison');
    assert.equal(await page.getByLabel('Final view').inputValue(), '0');
    const profiles = [];
    for (const edge of [3840, 7680]) {
      const option = page.getByLabel('Final output').locator('option[value="' + edge + '"]');
      if (await option.isDisabled()) {
        profiles.push({ edge, status: 'unavailable-as-declared' });
        continue;
      }
      await page.getByLabel('Final output').selectOption(String(edge));
      const high = scene.high_resolution.find((p) => p.edge === edge && p.view === 0);
      await imageReady(high.width);
      assert.equal(await page.locator('img[data-final-image]').count(), 2);
      profiles.push({ edge, status: 'matched-images-loaded', width: high.width });
    }
    await page.getByLabel('Final output').selectOption('0');
    await tab('Explore 3D');
    assert.equal(await page.locator('[data-testid=viewer] canvas').count(), 0);
    assert.equal(await contexts(), 0);
    console.log('[showcase] ' + scene.scene + ' | real Gaussian loading and cleanup');
    const pairAllowed =
      scene.models.baseline.gaussians + scene.models.upgrade.gaussians <= 1500000 &&
      scene.models.baseline.bytes + scene.models.upgrade.bytes <= 384 * 2 ** 20;
    const begin = requests.length;
    await page.getByRole('button', { name: 'Open selected 3D', exact: true }).click();
    await ready(scene.models.upgrade.gaussians);
    if (pairAllowed) await ready(scene.models.baseline.gaussians);
    const canvases = page.locator('[data-testid=viewer] canvas');
    assert.equal(await canvases.count(), pairAllowed ? 2 : 1);
    assert.equal(await contexts(), pairAllowed ? 2 : 1);
    const sizes = await canvases.evaluateAll((nodes) =>
      nodes.map((c) => ({ width: c.width, height: c.height })),
    );
    assert.ok(sizes.every((s) => s.width * s.height <= 1280 * 720));
    if (pairAllowed) {
      const baseline = requests
        .slice(begin)
        .find((r) => r.url === new URL(scene.models.baseline.run.asset, job.url).href);
      const upgrade = requests
        .slice(begin)
        .find((r) => r.url === new URL(scene.models.upgrade.run.asset, job.url).href);
      assert.ok(
        baseline && upgrade && baseline.end <= upgrade.start + 20,
        'Gaussian pair downloads overlapped',
      );
    } else
      assert.equal(downloads(scene.models.baseline.run.asset), 0, 'Large pair loaded both models');
    await page.waitForTimeout(2000);
    const before = await canvases.evaluateAll((nodes) => nodes.map((c) => c.dataset.renderCount));
    await page.waitForTimeout(900);
    assert.deepEqual(
      await canvases.evaluateAll((nodes) => nodes.map((c) => c.dataset.renderCount)),
      before,
      'Idle scene continued drawing',
    );
    const first = canvases.first();
    await first.scrollIntoViewIfNeeded();
    const bounds = await first.boundingBox();
    await page.mouse.move(bounds.x + bounds.width * 0.4, bounds.y + bounds.height * 0.5);
    await page.mouse.down();
    await page.mouse.move(bounds.x + bounds.width * 0.6, bounds.y + bounds.height * 0.55, {
      steps: 8,
    });
    await page.mouse.up();
    await page.waitForTimeout(700);
    const orbited = await pose(first);
    if (pairAllowed)
      assert.deepEqual(await pose(canvases.nth(1)), orbited, 'Comparison cameras drifted');
    await capture(scene.scene.replace(':', '-') + '-compare-3d.png');
    if (pairAllowed) await variant.selectOption('baseline');
    else
      await page
        .locator('[aria-label="Loaded comparison model"]')
        .getByRole('button', { name: 'Baseline', exact: true })
        .click();
    await ready(scene.models.baseline.gaussians);
    const current = page.locator('[data-testid=viewer] canvas');
    assert.equal(await current.count(), 1);
    await page.waitForTimeout(800);
    assert.deepEqual(await pose(current), orbited, 'Switching models lost the orbit camera');
    const count = downloads(scene.models.baseline.run.asset);
    await page.getByLabel('Final view').selectOption('1');
    await page.waitForTimeout(700);
    assert.equal(
      downloads(scene.models.baseline.run.asset),
      count,
      'Camera change re-downloaded a PLY',
    );
    await page.screenshot({
      path: path.join(job.output, scene.scene.replace(':', '-') + '-3d.png'),
      fullPage: true,
    });
    await page.getByRole('button', { name: 'Close selected 3D', exact: true }).click();
    await release();
    assert.equal(await current.count(), 0);
    rows.push({
      scene: scene.scene,
      status: 'passed',
      controls: 'all-three-enabled',
      metrics: 'matched-committed-values',
      preview: pairAllowed ? 'synchronized-sequentially-loaded-pair' : 'one-model-memory-fallback',
      orbit_preserved: true,
      idle: 'no-redraw',
      canvas_sizes: sizes,
      difference: diff,
      profiles,
    });
    console.log('[showcase] ' + scene.scene + ' | PASS');
  }
  console.log('[showcase] rapid scene change, history and responsive layouts');
  await page.getByLabel('Variant').selectOption('upgrade');
  await tab('Explore 3D');
  await page.getByRole('button', { name: 'Open selected 3D', exact: true }).click();
  await page.getByLabel('Dataset', { exact: true }).selectOption('bonsai');
  await release();
  assert.equal(await page.locator('[data-testid=viewer] canvas').count(), 0);
  await tab('Benchmark');
  await page
    .getByRole('table', { name: 'Collection benchmark' })
    .getByRole('button', { name: 'Room', exact: true })
    .click();
  assert.equal(await page.locator('[data-final-scene]').getAttribute('data-final-scene'), 'room');
  assert.equal(
    await page.locator('[data-final-scene]').getAttribute('data-workspace-panel'),
    'research',
  );
  await page.getByLabel('Result collection').selectOption('history');
  await page.getByLabel('Run set', { exact: true }).waitFor();
  assert.equal(await page.locator('[data-final-scene]').count(), 0);
  await page.getByLabel('Result collection').selectOption('final');
  await tab('Benchmark');
  await page.setViewportSize({ width: 390, height: 844 });
  await capture('mobile-benchmark.png');
  assert.ok(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2),
    'Mobile layout overflows',
  );
  await page.getByRole('button', { name: 'Toggle theme', exact: true }).click();
  await capture('mobile-dark-benchmark.png');
  assert.equal(errors.length, 0, errors.join('\n'));
  const contextSamples = await page.evaluate(() => window.__showcaseContexts);
  assert.ok(Math.max(0, ...contextSamples) <= 2, 'More than the current pair remained allocated');
  await writeFile(
    path.join(job.output, 'browser-check.json'),
    JSON.stringify(
      {
        status: 'passed',
        scenes: rows,
        page_errors: errors,
        maximum_viewer_contexts: Math.max(0, ...contextSamples),
        final_contexts: await contexts(),
        rapid_switch: 'passed',
        history: 'passed',
        responsive: 'passed',
        checked_at: new Date().toISOString(),
        scope:
          'Built app, real saved assets. Resource limits are preview policy, not a GPU-memory certification or new quality measurement.',
      },
      null,
      2,
    ),
  );
} catch (error) {
  await page
    .screenshot({ path: path.join(job.output, 'failure.png'), fullPage: true })
    .catch(() => {});
  await writeFile(
    path.join(job.output, 'browser-failure.json'),
    JSON.stringify(
      { error: String(error.stack || error), scenes: rows, page_errors: errors },
      null,
      2,
    ),
  );
  throw error;
} finally {
  await browser.close();
}
