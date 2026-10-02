import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const url = process.argv[2] || 'http://127.0.0.1:7016';
const out = new URL('../../artifacts/ui/qa/browser/', import.meta.url);
await mkdir(out, { recursive: true });
const browsers = {
  brave: 'C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe',
  chrome: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  edge: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
};
const records = [];
for (const [name, executablePath] of Object.entries(browsers)) {
  const browser = await chromium.launch({ executablePath, headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  const page = await context.newPage();
  await page.addInitScript(() => {
    window.__workerNames = new Set();
    const original = Worker.prototype.postMessage;
    Worker.prototype.postMessage = function (message, ...rest) {
      if (message?.name) window.__workerNames.add(message.name);
      return original.call(this, message, ...rest);
    };
  });
  const errors = [],
    workers = [];
  page.on(
    'pageerror',
    (e) => (
      errors.push({ message: e.message, stack: e.stack, time: Date.now() }),
      console.log('PAGE ERROR', e.message, e.stack)
    ),
  );
  page.on('worker', (w) => workers.push(w.url()));
  try {
    await page.goto(url);
    await page.getByRole('button', { name: 'Bỏ qua', exact: true }).click();
    await page.screenshot({ path: fileURLToPath(new URL(name + '-collection.png', out)) });
    const axe = await new AxeBuilder({ page }).analyze();
    if (axe.violations.length)
      console.log(
        name,
        'AXE',
        JSON.stringify(
          axe.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })),
        ),
      );
    await page.getByRole('button', { name: /Khám phá bộ trà/ }).click();
    await page.waitForFunction(
      () =>
        document.body.innerText.includes('Gaussian · ready') &&
        document.body.innerText.includes('points · proxy ready'),
      {},
      { timeout: 90000 },
    );
    await page.waitForTimeout(1500);
    const workerNames = await page.evaluate(() => [...window.__workerNames]);
    if (!workerNames.includes('loadPackedSplats'))
      throw new Error('Gaussian decode was not observed in a worker');
    await page.screenshot({ path: fileURLToPath(new URL(name + '-tea-dual.png', out)) });
    await page.getByRole('button', { name: 'Save camera bookmark', exact: true }).click();
    const saved = await page.evaluate(() =>
      JSON.parse(localStorage.getItem('topic16-bookmarks')).bookmarks.at(-1),
    );
    console.log('CAMERA', JSON.stringify(saved.camera.camera_to_world));
    const snapshotCamera = async () => {
      await page.getByRole('button', { name: 'Save camera bookmark', exact: true }).click();
      return page.evaluate(
        () => JSON.parse(localStorage.getItem('topic16-bookmarks')).bookmarks.at(-1).camera,
      );
    };
    // Verify actual non-default pose survives disposing and recreating panes.
    const canvas = page.locator('canvas').last();
    await canvas.hover();
    await page.mouse.move(1050, 430);
    await page.mouse.down();
    await page.mouse.move(1090, 450, { steps: 8 });
    await page.mouse.up();
    await page.mouse.wheel(0, -100);
    await page.waitForTimeout(500);
    const moved = await snapshotCamera();
    for (const mode of ['N · Nerfacto', 'S · Splatfacto', 'Song song']) {
      await page.getByRole('button', { name: mode, exact: true }).click();
      await page.waitForFunction(
        (mode) => {
          const text = document.body.innerText;
          return (
            (mode === 'S · Splatfacto' || text.includes('points · proxy ready')) &&
            (mode === 'N · Nerfacto' || text.includes('Gaussian · ready'))
          );
        },
        mode,
        { timeout: 90000 },
      );
      const restored = await snapshotCamera();
      moved.camera_to_world
        .flat()
        .forEach((n, i) =>
          assert.ok(Math.abs(n - restored.camera_to_world.flat()[i]) < 1e-4, `Pose drift: ${mode}`),
        );
    }
    await page.getByRole('checkbox', { name: 'Sync cameras' }).uncheck();
    await page.getByRole('checkbox', { name: 'Sync cameras' }).check();
    await page.getByRole('slider', { name: 'Point size' }).fill('0.004');
    const workspaceAxe = await new AxeBuilder({ page }).analyze();
    assert.equal(workspaceAxe.violations.length, 0, JSON.stringify(workspaceAxe.violations));
    await page.getByRole('button', { name: 'Reset camera', exact: true }).click();
    const gpu = await page
      .locator('canvas')
      .last()
      .evaluate((c) => {
        const gl = c.getContext('webgl2');
        const ext = gl?.getExtension('WEBGL_debug_renderer_info');
        return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : null;
      });
    if (name === 'brave') {
      for (const scene of ['bonsai', 'garden', 'room', 'poster']) {
        if (scene === 'garden') {
          await page.route('**/api/assets/*', async (route) => {
            await new Promise((resolve) => setTimeout(resolve, 1500));
            await route.continue().catch(() => {});
          });
        }
        await page.getByRole('combobox', { name: 'Dataset', exact: true }).selectOption(scene);
        if (scene === 'garden') {
          await page.waitForFunction(() => document.body.innerText.includes('Downloading'));
          await page.getByRole('button', { name: 'Cancel loading', exact: true }).click();
          await page.waitForFunction(() => document.body.innerText.includes('Cancelled'));
          await page.unroute('**/api/assets/*');
          await page.getByRole('button', { name: 'Retry assets', exact: true }).click();
        }
        await page.waitForFunction(
          () =>
            document.body.innerText.includes('Gaussian · ready') &&
            document.body.innerText.includes('points · proxy ready'),
          {},
          { timeout: 90000 },
        );
        await page.waitForTimeout(400);
        await page.screenshot({
          path: fileURLToPath(new URL(name + '-' + scene + '-dual.png', out)),
        });
        console.log('REAL SCENE', scene, 'ready');
      }
      await page
        .getByRole('combobox', { name: 'Dataset', exact: true })
        .selectOption('custom:tea_sets_2');
      await page.waitForFunction(() => document.body.innerText.includes('Gaussian · ready'));
      await page.getByRole('button', { name: 'So sánh ảnh', exact: true }).click();
      await page.locator('img').first().waitFor();
      await page.getByRole('slider', { name: 'Comparison split' }).fill('63');
      await page.screenshot({ path: fileURLToPath(new URL('brave-images.png', out)) });
      await page.getByRole('button', { name: 'Benchmark & kiến trúc', exact: true }).click();
      await page
        .locator('[aria-label="pipeline architecture diagram"] svg')
        .waitFor({ timeout: 60000 });
      for (const diagram of ['nerfacto', 'splatfacto', 'pipeline']) {
        await page.getByRole('button', { name: diagram, exact: true }).click();
        await page.locator(`[aria-label="${diagram} architecture diagram"] svg`).waitFor();
      }
      await page.getByRole('slider', { name: 'Diagram zoom' }).fill('1.2');
      const svgDownload = page.waitForEvent('download');
      await page.getByRole('button', { name: 'Export SVG' }).click();
      await (await svgDownload).saveAs(fileURLToPath(new URL('pipeline-architecture.svg', out)));
      const reportPage = page.waitForEvent('popup');
      await page.getByRole('button', { name: 'Print / save PDF', exact: true }).click();
      const report = await reportPage;
      await report.locator('table').waitFor();
      await report.locator('[aria-label="pipeline architecture diagram"] svg').waitFor();
      await report.pdf({
        path: fileURLToPath(new URL('research-report.pdf', out)),
        format: 'A4',
        printBackground: true,
      });
      await report.close();
      await page.screenshot({
        path: fileURLToPath(new URL('brave-research.png', out)),
        fullPage: true,
      });
      await page.getByRole('button', { name: 'Art gallery', exact: false }).click();
      await page.locator('canvas').waitFor();
      await page.waitForTimeout(1500);
      await page.keyboard.press('KeyW');
      await page.getByRole('slider', { name: 'Walking speed' }).fill('2.2');
      await page.getByRole('button', { name: '3. Garden', exact: true }).click();
      await page.screenshot({ path: fileURLToPath(new URL('brave-gallery.png', out)) });
      await page.getByRole('button', { name: 'Open reconstruction' }).click();
      await page.waitForFunction(() => document.body.innerText.includes('Gaussian · ready'));
      await page.setViewportSize({ width: 390, height: 844 });
      await page.screenshot({ path: fileURLToPath(new URL('brave-mobile.png', out)) });
    }
    if (errors.length) throw new Error(errors.join('\n'));
    records.push({
      workerNames,
      browser: name,
      version: await browser.version(),
      gpu,
      workers: workers.length,
      axe: axe.violations,
      workspaceAxe: workspaceAxe.violations,
      modeCameraRetention: true,
      errors,
    });
    console.log(name, 'PASS', gpu);
  } finally {
    await context.close();
    await browser.close();
  }
}
await writeFile(new URL('results.json', out), JSON.stringify(records, null, 2));
