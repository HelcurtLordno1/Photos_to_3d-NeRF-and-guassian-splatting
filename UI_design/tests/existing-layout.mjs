import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
const job = JSON.parse(await readFile(process.argv[2], 'utf8'));
await mkdir(job.output, { recursive: true });
const catalog = await (await fetch(job.url + '/api/catalog')).json();
const scenes = catalog.final_delivery.scenes;
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
  results = [];
page.on('pageerror', (e) => errors.push(e.message));
const models = new Set(
  scenes.flatMap((s) => Object.values(s.models).map((r) => new URL(r.run.asset, job.url).href)),
);
page.on('request', (r) => {
  if (models.has(r.url())) requests.push(r.url());
});
await page.addInitScript(() => {
  localStorage.setItem('topic16-onboarded', '1');
  localStorage.setItem('topic16-locale', 'en');
});
const contexts = () =>
  page.evaluate(() => Number(document.documentElement.dataset.viewerContexts || 0));
const release = () =>
  page.waitForFunction(
    () => Number(document.documentElement.dataset.viewerContexts || 0) === 0,
    null,
    { timeout: 45000 },
  );
const tab = (name) => page.getByRole('button', { name, exact: true }).click();
const ready = (count) =>
  page.waitForFunction(
    (n) =>
      document.querySelectorAll('[data-testid="viewer"] canvas').length === n &&
      [...document.querySelectorAll('[data-testid="viewer"] [role="status"]')].filter((e) =>
        /Gaussian · ready/.test(e.textContent),
      ).length === n,
    count,
    { timeout: 180000 },
  );
const allImages = () =>
  page.waitForFunction(() =>
    [...document.querySelectorAll('main img')].every((i) => i.complete && i.naturalWidth > 0),
  );
const capture = async (name, fullPage = false) => {
  await page.evaluate(() => {
    document.activeElement?.blur?.();
    window.scrollTo(0, 0);
  });
  await page.screenshot({ path: path.join(job.output, name), fullPage });
};
let maximumContexts = 0;
try {
  for (const scene of scenes) {
    console.log('Checking ' + scene.scene);
    await page.goto(job.url + '/?scene=' + encodeURIComponent(scene.scene) + '&tab=images');
    const variant = page.getByLabel('Variant', { exact: true });
    await variant.waitFor();
    for (const value of ['baseline', 'upgrade', 'compare'])
      assert.equal(await variant.locator('option[value="' + value + '"]').isDisabled(), false);
    await variant.selectOption('upgrade');
    assert.equal(
      await page.getByLabel('Run set', { exact: true }).inputValue(),
      'selected-final:' + scene.scene,
    );
    assert.equal(await page.getByLabel('Left image', { exact: true }).inputValue(), 'gt');
    assert.equal(await page.getByLabel('Right image', { exact: true }).inputValue(), 'splatfacto');
    await allImages();
    await variant.selectOption('compare');
    await allImages();
    assert.equal(await page.getByLabel('Left image', { exact: true }).inputValue(), 'nerfacto');
    assert.equal(
      await page.locator('img[alt="Baseline · Splatfacto reconstruction"]').getAttribute('src'),
      scene.models.baseline.frames[0].pred,
    );
    assert.equal(
      await page.locator('img[alt="Upgrade · Improved-GS reconstruction"]').getAttribute('src'),
      scene.models.upgrade.frames[0].pred,
    );
    const frame = Math.floor(scene.cameras.length / 2);
    await page.getByLabel('Held-out view', { exact: true }).selectOption(String(frame));
    await allImages();
    await page.getByLabel('Absolute error ×4', { exact: true }).check();
    await allImages();
    assert.equal(
      await page.locator('img[alt="Upgrade · Improved-GS reconstruction"]').getAttribute('src'),
      scene.models.upgrade.frames[frame].error,
    );
    await page.getByLabel('Absolute error ×4', { exact: true }).uncheck();
    await page.getByLabel('ROI lens', { exact: true }).check();
    await page.getByLabel('Image zoom', { exact: true }).fill('1.5');
    await page.getByLabel('ROI X', { exact: true }).fill('0.6');
    await page.getByLabel('Comparison split', { exact: true }).fill('45');
    await capture(scene.scene.replace(':', '-') + '-images.png');
    assert.equal(requests.length, 0, 'Saved images fetched a PLY before the first 3D request');
    await tab('Explore 3D');
    const pair =
      Object.values(scene.models).reduce((n, r) => n + r.gaussians, 0) <= 1500000 &&
      Object.values(scene.models).reduce((n, r) => n + r.bytes, 0) <= 384 * 2 ** 20;
    await ready(pair ? 2 : 1);
    maximumContexts = Math.max(maximumContexts, await contexts());
    assert.ok((await contexts()) <= 2);
    for (const name of [
      'Reset camera',
      'Rotate object',
      'Save camera bookmark',
      'Export viewer screenshot',
      'Fullscreen',
      'Walk in scene · WASD',
      'Cancel loading',
      'Retry assets',
    ])
      await page.getByRole('button', { name, exact: true }).waitFor();
    await page.getByLabel('Point size', { exact: true }).waitFor();
    await page.getByLabel('Sync cameras', { exact: true }).waitFor();
    const canvases = page.locator('[data-testid="viewer"] canvas'),
      canvas = canvases.first();
    const sizes = await canvases.evaluateAll((cs) =>
      cs.map((c) => ({ width: c.width, height: c.height })),
    );
    assert.ok(sizes.every((s) => s.width * s.height <= 1280 * 720 + 2));
    await canvas.scrollIntoViewIfNeeded();
    await page.waitForTimeout(1200);
    const before = await canvas.getAttribute('data-render-count');
    await page.waitForTimeout(1000);
    assert.equal(
      await canvas.getAttribute('data-render-count'),
      before,
      'Idle viewer keeps drawing',
    );
    const box = await canvas.boundingBox();
    await page.mouse.move(box.x + box.width * 0.45, box.y + box.height * 0.5);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.5, { steps: 8 });
    await page.mouse.up();
    await page.waitForTimeout(500);
    const pose = await canvas.getAttribute('data-camera-pose');
    assert.ok(pose);
    if (pair)
      assert.equal(
        await canvases.last().getAttribute('data-camera-pose'),
        pose,
        'Paired orbit is not synchronized',
      );
    await page.getByRole('button', { name: 'Baseline · Splatfacto', exact: true }).click();
    await ready(1);
    assert.equal(
      await canvas.getAttribute('data-camera-pose'),
      pose,
      'Model switch loses the current camera',
    );
    const downloaded = requests.length;
    await page.getByLabel('Camera preset', { exact: true }).selectOption('1');
    await page.waitForTimeout(300);
    assert.equal(requests.length, downloaded, 'Camera preset re-downloads a PLY');
    await page.getByLabel('Grid / axes', { exact: true }).check();
    await page.getByLabel('Eval camera coverage', { exact: true }).check();
    await page.getByRole('button', { name: 'Save camera bookmark', exact: true }).click();
    await page.getByRole('button', { name: 'Reset camera', exact: true }).click();
    await capture(scene.scene.replace(':', '-') + '-3d.png');
    await tab('Benchmarks & architecture');
    await release();
    const plyBeforeBenchmark = requests.length;
    const table = page.getByRole('table', { name: 'Completed experiment metrics' });
    await table.waitFor();
    for (const model of ['baseline', 'upgrade']) {
      const row = table.locator('[data-evidence-row="' + model + '"]');
      for (const [key, digits] of [
        ['psnr', 4],
        ['ssim', 5],
        ['lpips', 5],
      ])
        assert.ok(
          (await row.innerText()).includes(scene.models[model].metrics[key].toFixed(digits)),
        );
    }
    assert.ok(
      (await table
        .locator('td')
        .first()
        .evaluate((e) => parseFloat(getComputedStyle(e).fontSize))) >= 14,
    );
    assert.ok(
      (await table
        .locator('thead th')
        .first()
        .evaluate((e) => parseFloat(getComputedStyle(e).fontSize))) >= 13,
    );
    await page.getByLabel('Benchmark scope', { exact: true }).selectOption('studies');
    const group = page.getByLabel('Evidence group', { exact: true });
    const values = await group.locator('option').evaluateAll((xs) => xs.map((x) => x.value));
    for (const value of values) {
      await group.selectOption(value);
      assert.ok((await table.locator('tbody tr').count()) > 0);
      assert.ok(!(await table.innerText()).includes('NaN'));
      if (value === 'seeds') {
        assert.equal(await table.locator('tbody tr').count(), 6);
        assert.ok((await table.innerText()).includes('seed 2026'));
      }
      if (value === 'teacher') {
        assert.equal(await table.locator('tbody tr').count(), 4);
        assert.ok((await table.innerText()).includes('30.2916'));
        assert.ok((await table.innerText()).includes('30.2981'));
      }
    }
    await group.selectOption('final');
    if (scene.scene === 'custom:tea_sets_2') {
      await page
        .getByText('Browser precision diagnosis · retained negative results', { exact: true })
        .click();
      const precision = page.getByRole('table', {
        name: 'Browser precision investigation',
        exact: true,
      });
      assert.equal(await precision.locator('tbody tr').count(), 8);
      assert.ok((await precision.innerText()).includes('gate-not-met'));
      for (let i = 0; i < catalog.visual_research.inspection_history.length; i++) {
        const r = catalog.visual_research.inspection_history[i],
          text = await precision.locator('tbody tr').nth(i).innerText();
        assert.ok(
          text.includes(r.mean_parity_db.toFixed(2)) &&
            text.includes(r.p95_frame_interval_ms.toFixed(2)),
        );
      }
      await page
        .getByText('Browser precision diagnosis · retained negative results', { exact: true })
        .click();
    }
    await page
      .getByRole('img', { name: 'Per-view upgrade minus baseline', exact: true })
      .locator('a')
      .nth(1)
      .click();
    await page.getByLabel('Held-out view', { exact: true }).waitFor();
    assert.equal(await page.getByLabel('Held-out view', { exact: true }).inputValue(), '1');
    assert.equal(
      await page.locator('img[alt="Upgrade · Improved-GS reconstruction"]').getAttribute('src'),
      scene.models.upgrade.frames[1].pred,
    );
    await tab('Benchmarks & architecture');
    await table.waitFor();
    await page.getByRole('button', { name: 'pipeline', exact: true }).click();
    await page
      .getByRole('img', { name: 'pipeline architecture diagram', exact: true })
      .locator('svg')
      .waitFor();
    await capture(scene.scene.replace(':', '-') + '-benchmark.png');
    assert.equal(requests.length, plyBeforeBenchmark, 'Benchmark fetched a PLY');
    await tab('Visual quality');
    await page
      .getByRole('heading', { name: 'Baseline and selected upgrade', exact: true })
      .waitFor();
    assert.equal(
      await page
        .getByRole('heading', { name: 'Baseline and selected upgrade', exact: true })
        .count(),
      1,
    );
    assert.equal(await page.locator('img[data-final-image]').count(), 3);
    assert.equal(await page.getByLabel('Final model', { exact: true }).inputValue(), 'upgrade');
    for (const edge of [3840, 7680]) {
      await page.getByLabel('Final output', { exact: true }).selectOption(String(edge));
      await allImages();
      assert.equal(await page.locator('img[data-final-image]').count(), 2);
    }
    await page.getByLabel('Final output', { exact: true }).selectOption('0');
    await allImages();
    await capture(scene.scene.replace(':', '-') + '-visual-quality.png');
    await tab('Image comparison');
    // The original baseline flow remains the paired N/S experience.
    await variant.selectOption('baseline');
    if (scene.scene === 'custom:tea_sets_2') {
      await page.waitForFunction(
        () =>
          [...document.querySelectorAll('[data-testid="viewer"] [role="status"]')].filter((e) =>
            /ready/.test(e.textContent),
          ).length === 2,
        null,
        { timeout: 120000 },
      );
      assert.ok(
        (await page.locator('[data-testid="viewer"]').innerText()).includes('Point cloud proxy'),
      );
      await capture('tea-original-baseline-3d.png');
    }
    await tab('Image comparison');
    await release();
    await allImages();
    assert.ok(
      await page
        .getByLabel('Left image', { exact: true })
        .locator('option[value="nerfacto"]')
        .count(),
    );
    results.push({
      scene: scene.scene,
      status: 'passed',
      controls: 'original-toolbar-and-image-controls-retained',
      preview: pair ? 'synchronized-pair' : 'one-model-memory-fallback',
      camera_preserved: true,
      benchmark_groups: values.length,
      native_metrics: 'exact-source-values',
      profiles: '4K/8K-loaded',
      canvas_sizes: sizes,
    });
    await variant.selectOption('compare');
    const next = scenes[(scenes.indexOf(scene) + 1) % scenes.length];
    await page.getByLabel('Dataset', { exact: true }).selectOption(next.scene);
    assert.equal(
      await page.getByLabel('Run set', { exact: true }).inputValue(),
      'selected-final:' + next.scene,
    );
    assert.equal(await variant.inputValue(), 'compare');
    await allImages();
    requests.length = 0;
  }
  await page.goto(job.url + '/?scene=room&tab=research');
  await page.getByLabel('Evidence group', { exact: true }).waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  await capture('benchmark-mobile.png');
  assert.ok(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
    'Mobile page overflows',
  );
  await page.getByRole('button', { name: 'Toggle theme', exact: true }).click();
  await capture('benchmark-mobile-dark.png');
  await page.goto(job.url + '/');
  await release();
  assert.equal(errors.length, 0, errors.join('\n'));
  await writeFile(
    path.join(job.output, 'browser-check.json'),
    JSON.stringify(
      {
        status: 'passed',
        scenes: results,
        page_errors: errors,
        maximum_contexts: maximumContexts,
        final_contexts: await contexts(),
        scope:
          'Built original-layout UI with actual saved images and PLY assets; not a new training run or unlimited memory certification.',
        checked_at: new Date().toISOString(),
      },
      null,
      2,
    ),
  );
} catch (e) {
  await page
    .screenshot({ path: path.join(job.output, 'failure.png'), fullPage: true })
    .catch(() => {});
  throw e;
} finally {
  await browser.close();
}
