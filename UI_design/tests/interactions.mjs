import { chromium, expect } from '@playwright/test';
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const url = process.argv[2] || 'http://127.0.0.1:7016';
const out = new URL('../../artifacts/ui/qa/interactions/', import.meta.url);
await mkdir(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: 'C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe',
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
const errors = [],
  downloads = [];
page.on('pageerror', (error) => errors.push(error.message));
page.on('download', (download) =>
  downloads.push({
    name: download.suggestedFilename(),
    saved: download.saveAs(fileURLToPath(new URL(download.suggestedFilename(), out))),
  }),
);
const ready = () =>
  page.waitForFunction(
    () =>
      document.body.innerText.includes('Gaussian · ready') &&
      document.body.innerText.includes('points · proxy ready'),
    {},
    { timeout: 90000 },
  );
try {
  await page.addInitScript(() => localStorage.setItem('topic16-onboarded', '1'));
  await page.goto(url);
  await page.getByRole('button', { name: /Khám phá bộ trà/ }).click();
  await ready();
  await page.getByRole('button', { name: 'Export viewer screenshot', exact: true }).click();
  for (let i = 0; downloads.length < 2 && i < 50; i++) await page.waitForTimeout(100);
  assert.equal(downloads.length, 2, 'Screenshot and metadata should both download');
  await Promise.all(downloads.map((d) => d.saved));
  const metadata = JSON.parse(
    await readFile(new URL(downloads.find((d) => d.name.endsWith('.json')).name, out), 'utf8'),
  );
  assert.equal(metadata.scene, 'custom:tea_sets_2');
  assert.equal(metadata.mode, 'both');
  assert.ok(metadata.runs.nerfacto.checkpoint_sha256);
  const lost = await page
    .locator('canvas')
    .last()
    .evaluate((canvas) => {
      const extension = canvas.getContext('webgl2').getExtension('WEBGL_lose_context');
      extension?.loseContext();
      return !!extension;
    });
  assert.ok(lost);
  await page.getByText('Graphics context lost.', { exact: false }).waitFor();
  await page.getByRole('button', { name: 'Retry assets', exact: true }).click();
  await ready();
  await page.getByRole('button', { name: 'Save camera bookmark', exact: true }).click();
  const originalBookmark = await page.evaluate(() => JSON.parse(localStorage.getItem('topic16-bookmarks')).bookmarks[0]);
  await page.getByRole('combobox', { name: 'Dataset', exact: true }).selectOption('bonsai');
  await ready();
  await page.getByRole('button', { name: /Góc đã lưu/ }).click();
  await page.getByRole('button').filter({ hasText: originalBookmark.title }).filter({ hasText: originalBookmark.scene }).first().click();
  await ready();
  await expect(page.getByRole('combobox', { name: 'Dataset', exact: true })).toHaveValue('custom:tea_sets_2');
  await page.getByRole('button', { name: 'Close bookmarks', exact: true }).click();
  const canvasBounds = await page.locator('canvas').last().boundingBox();
  await page.mouse.move(canvasBounds.x + canvasBounds.width / 2, canvasBounds.y + canvasBounds.height / 2);
  await page.mouse.down();
  await page.mouse.move(canvasBounds.x + canvasBounds.width / 2 + 45, canvasBounds.y + canvasBounds.height / 2 + 20, { steps: 8 });
  await page.mouse.up();
  await page.getByRole('button', { name: 'Save camera bookmark', exact: true }).click();
  const movedCamera = await page.evaluate(() => JSON.parse(localStorage.getItem('topic16-bookmarks')).bookmarks.at(-1).camera);
  await page.getByRole('button', { name: 'N · Nerfacto', exact: true }).click();
  await page.waitForFunction(() => document.body.innerText.includes('points · proxy ready'));
  await page.getByRole('button', { name: 'Save camera bookmark', exact: true }).click();
  const retainedCamera = await page.evaluate(() => JSON.parse(localStorage.getItem('topic16-bookmarks')).bookmarks.at(-1).camera);
  movedCamera.camera_to_world.flat().forEach((n, i) => assert.ok(Math.abs(n - retainedCamera.camera_to_world.flat()[i]) < 1e-4));
  await page.getByRole('button', { name: 'Song song', exact: true }).click();
  await ready();
  await page.getByRole('button', { name: 'Art gallery', exact: false }).click();
  await page.getByRole('button', { name: 'Guided tour', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Stop tour', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await page.waitForTimeout(1000);
  await page.getByRole('button', { name: 'Stop tour', exact: true }).click();
  await page.getByRole('slider', { name: 'Walking speed' }).fill('2.3');
  await page.getByRole('button', { name: '3. Garden', exact: true }).click();
  await page.getByRole('button', { name: 'Open reconstruction' }).click();
  await ready();
  await page.getByRole('button', { name: 'Art gallery', exact: false }).click();
  await expect(page.getByRole('button', { name: '3. Garden', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await page.emulateMedia({ forcedColors: 'active', reducedMotion: 'reduce' });
  await page.screenshot({ path: fileURLToPath(new URL('gallery-forced-colors.png', out)) });
  await page.emulateMedia({ forcedColors: 'none', reducedMotion: 'no-preference' });
  const catalog = await (await fetch(url + '/api/catalog')).json();
  const room = catalog.scenes.find((d) => d.id === 'room');
  await page.goto(url + '/?report=1&scene=room&scope=room&metric=lpips');
  await page.locator('[aria-label="pipeline architecture diagram"] svg').waitFor();
  await page.emulateMedia({ media: 'print' });
  const text = await page.locator('body').innerText();
  assert.ok(text.includes('Filter: room') && text.includes('selected metric: lpips'));
  for (const method of Object.values(room.methods)) {
    assert.ok(text.includes(method.run_key));
    assert.ok(text.includes(method.config));
    assert.ok(text.includes(method.checkpoint_sha256));
    assert.ok(text.includes(method.split_hash));
  }
  await page.pdf({
    path: fileURLToPath(new URL('room-lpips-report.pdf', out)),
    format: 'A4',
    printBackground: true,
  });
  await page.screenshot({ path: fileURLToPath(new URL('print-sources.png', out)), fullPage: true });
  assert.deepEqual(errors, []);
  await writeFile(
    new URL('result.json', out),
    JSON.stringify(
      {
        status: 'passed',
        browser: await browser.version(),
        revision: catalog.revision,
        screenshotDownloads: downloads.map((d) => d.name),
      contextLossRecovered: true,
      crossSceneBookmarkAndMovedCameraRetained: true,
        tourControls: true,
        galleryReturn: true,
        printFilter: 'room/lpips',
        printExactSources: true,
        forcedColorsEmulated: true,
        errors,
      },
      null,
      2,
    ),
  );
  console.log('EXPORT / CONTEXT LOSS / GALLERY / PRINT SOURCES PASS');
} finally {
  await page.close();
  await browser.close();
}
