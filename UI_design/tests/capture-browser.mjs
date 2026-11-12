// Real local artifact QA. Screenshots never substitute for study validation.
import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { mkdir, writeFile } from 'node:fs/promises';
const url = process.argv[2] || 'http://127.0.0.1:7016';
const output = new URL('../../upgrade/reports/qa/browser/', import.meta.url);
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  headless: true,
  args: ['--disable-gpu'],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } }),
  errors = [];
page.on('pageerror', (error) => errors.push(error.message));
try {
  const response = await page.request.get(url + '/api/catalog'),
    catalog = await response.json();
  const scene =
    catalog.scenes.find((s) => s.run_sets?.some((r) => r.variant === 'upgrade')) ||
    catalog.scenes[0];
  assert.ok(catalog.upgrade.runs.every((r) => r.budget >= 10000 && r.tier !== 'smoke'));
  const baseline = scene.run_sets.find((r) => r.variant === 'baseline');
  assert.ok(baseline.methods.nerfacto.asset && baseline.methods.splatfacto.asset);
  const upgrade =
    scene.run_sets?.find((r) => r.variant === 'upgrade' && r.budget === 10000) ||
    scene.run_sets?.find((r) => r.variant === 'upgrade');
  await page.addInitScript(() => localStorage.setItem('topic16-onboarded', '1'));
  await page.goto(url + '/?scene=' + encodeURIComponent(scene.id) + '&tab=images');
  await page.getByLabel('Variant', { exact: true }).waitFor();
  assert.equal(await page.getByLabel('Variant', { exact: true }).inputValue(), 'baseline');
  await page.getByLabel('Variant', { exact: true }).selectOption('upgrade');
  const automaticallySelected = await page.getByLabel('Run set', { exact: true }).inputValue();
  const selected = scene.run_sets.find((r) => r.id === automaticallySelected);
  assert.ok(selected.budget >= 10000 && selected.tier !== 'smoke');
  assert.equal(
    await page.getByLabel('Run set').locator('option').filter({ hasText: '10 steps' }).count(),
    0,
  );
  await page.goto(
    url +
      '/?scene=' +
      encodeURIComponent(scene.id) +
      '&tab=images' +
      (upgrade ? '&runSet=' + upgrade.id : ''),
  );
  await page.getByLabel('Image source', { exact: true }).waitFor();
  if (upgrade) {
    assert.equal(await page.getByLabel('Variant', { exact: true }).inputValue(), 'upgrade');
    await page.getByLabel('Variant', { exact: true }).selectOption('compare');
    await page.getByText('Compare the same method', { exact: false }).waitFor();
    await page.getByLabel('Compare the same method').selectOption('splatfacto');
    assert.equal(await page.getByLabel('Left image', { exact: true }).inputValue(), 'nerfacto');
    assert.equal(
      await page.getByLabel('Right image', { exact: true }).locator('option:checked').innerText(),
      'Upgrade · splatfacto',
    );
    await page.getByLabel('Right image', { exact: true }).selectOption('splatfacto');
    await page.screenshot({
      path: fileURLToPath(new URL('baseline-upgrade-images.png', output)),
      fullPage: true,
    });
  }
  await page
    .getByRole('button', { name: /Benchmark & kiến trúc|Benchmarks & architecture/ })
    .click();
  await page.getByRole('region', { name: 'Measured research results' }).waitFor();
  assert.equal(
    await page.locator('svg[aria-label="Measured quality versus training minutes"]').count(),
    1,
  );
  assert.equal(await page.locator('table').count(), 1);
  await page.getByLabel('Benchmark scope').selectOption('conditions');
  await page.getByText('Capture audit · quan sát train', { exact: true }).click();
  assert.ok((await page.locator('img[alt^="Train view"]').count()) <= 12);
  await page.getByText('Dự báo chất lượng · trạng thái bằng chứng', { exact: true }).click();
  await page
    .getByText(/insufficient-evidence/)
    .first()
    .waitFor();
  const coverage = page.locator('img[alt$="camera coverage"]');
  await coverage.scrollIntoViewIfNeeded();
  await page.waitForFunction(() =>
    [...document.querySelectorAll('img[alt$="camera coverage"]')].every(
      (image) => image.complete && image.naturalWidth > 0,
    ),
  );
  const firstPreview = page.locator('img[alt^="Train view"]').first();
  await firstPreview.scrollIntoViewIfNeeded();
  await page.waitForFunction(() =>
    [...document.querySelectorAll('img[alt^="Train view"]')].every(
      (image) => image.complete && image.naturalWidth > 0,
    ),
  );
  await page.getByRole('img', { name: 'pipeline architecture diagram' }).locator('svg').waitFor();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: fileURLToPath(new URL('capture-intelligence.png', output)),
    fullPage: true,
  });
  assert.deepEqual(errors, []);
  const result = {
    status: 'passed',
    url,
    revision: catalog.revision,
    scene: scene.id,
    upgrade_pair: !!upgrade,
    run_set: upgrade?.id,
    budget: upgrade?.budget,
    automatic_upgrade_budget: selected.budget,
    smoke_hidden: true,
    single_benchmark: true,
    baseline_paired_3d_preserved: true,
    completed_study_runs: catalog.upgrade?.runs.filter((r) => r.study === 'tea60-v1').length || 0,
    page_errors: errors,
  };
  await writeFile(new URL('result.json', output), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
