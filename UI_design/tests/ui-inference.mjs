import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
const url = process.argv[2] || 'http://127.0.0.1:7016';
const out = new URL('../../artifacts/ui/qa/ui-inference/', import.meta.url);
await mkdir(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: 'C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe',
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
const errors = [];
page.on('pageerror', (e) => errors.push({ message: e.message, stack: e.stack }));
try {
  await page.addInitScript(() => localStorage.setItem('topic16-onboarded', '1'));
  await page.goto(url);
  await page.getByRole('button', { name: /Khám phá bộ trà/ }).click();
  await page.waitForFunction(
    () =>
      document.body.innerText.includes('Gaussian · ready') &&
      document.body.innerText.includes('points · proxy ready'),
  );
  await page.waitForTimeout(1000);
  await page.getByRole('combobox', { name: 'Render resolution' }).selectOption('320');
  const requestPromise = page.waitForRequest(
    (r) => r.url().endsWith('/api/jobs') && r.method() === 'POST',
  );
  await page.getByRole('button', { name: 'Render ảnh model', exact: true }).click();
  const request = (await requestPromise).postDataJSON();
  await page.waitForFunction(
    () =>
      document.querySelector('[aria-label="Image source"]') ||
      document.body.innerText.includes('FAILED ·'),
    {},
    { timeout: 240000 },
  );
  if ((await page.locator('[aria-label="Image source"]').count()) === 0)
    throw new Error(await page.locator('[role="status"]').allTextContents());
  await page.waitForFunction(
    () => document.querySelector('[aria-label="Image source"]')?.value === 'live',
  );
  await page
    .locator('img')
    .first()
    .evaluate(async (img) => {
      if (!img.complete)
        await new Promise((r, j) => {
          img.onload = r;
          img.onerror = j;
        });
    });
  await page.screenshot({ path: fileURLToPath(new URL('pair.png', out)) });
  const singles = [];
  for (const [label, method] of [
    ['N · Nerfacto', 'nerfacto'],
    ['S · Splatfacto', 'splatfacto'],
  ]) {
    await page.getByRole('button', { name: 'Khám phá 3D', exact: true }).click();
    await page.getByRole('button', { name: label, exact: true }).click();
    await page.waitForFunction(
      (method) =>
        document.body.innerText.includes(
          method === 'nerfacto' ? 'points · proxy ready' : 'Gaussian · ready',
        ),
      method,
      { timeout: 90000 },
    );
    const createdResponse = page.waitForResponse(
      (r) => r.url().endsWith('/api/jobs') && r.request().method() === 'POST',
    );
    await page.getByRole('button', { name: 'Render ảnh model', exact: true }).click();
    const created = await (await createdResponse).json();
    assert.deepEqual(created.methods, [method]);
    await page.waitForFunction(
      () =>
        document.querySelector('[aria-label="Image source"]') ||
        document.body.innerText.includes('FAILED ·'),
      {},
      { timeout: 240000 },
    );
    await page.waitForFunction(
      () => document.querySelector('[aria-label="Image source"]')?.value === 'live',
    );
    assert.equal(await page.locator('[aria-label="Image source"]').inputValue(), 'live');
    const completed = await (await fetch(url + '/api/jobs/' + created.id)).json();
    assert.equal(completed.status, 'succeeded', completed.error);
    assert.deepEqual(Object.keys(completed.results), [method]);
    singles.push(completed);
    await page.screenshot({ path: fileURLToPath(new URL(method + '-single.png', out)) });
  }
  if (errors.length) throw new Error(JSON.stringify(errors));
  await writeFile(
    new URL('result.json', out),
    JSON.stringify(
      { status: 'passed', request, singles, errors, browser: await browser.version() },
      null,
      2,
    ),
  );
  console.log('UI PAIRED + BOTH SINGLE-MODEL INFERENCE PASS');
} finally {
  await page.close();
  await browser.close();
}
