import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFile } from 'node:fs/promises';
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('topic16-onboarded', '1'));
  await page.goto('/');
});
test('collection selection, saved comparison and exact metric table', async ({ page }) => {
  await expect(page.getByRole('heading', { name: 'Một bộ ảnh. Hai cách nhìn.' })).toBeVisible();
  await page.getByRole('button', { name: /Bonsai Synthetic CI fixture/ }).click();
  await expect(page.getByRole('combobox', { name: 'Dataset', exact: true })).toHaveValue('bonsai');
  await page.getByRole('button', { name: 'So sánh ảnh', exact: true }).click();
  await page.getByRole('slider', { name: 'Comparison split' }).fill('70');
  await expect(page.getByRole('img', { name: 'gt reconstruction' })).toBeVisible();
  await page.getByRole('checkbox', { name: 'ROI lens' }).check();
  await page.getByRole('slider', { name: 'ROI X', exact: true }).fill('0.7');
  await page.getByRole('button', { name: 'Benchmark & kiến trúc', exact: true }).click();
  await expect(page.locator('table')).toContainText('20.00');
  await expect(page.locator('[aria-label="pipeline architecture diagram"] svg')).toBeVisible();
});
test('onboarding, language, theme and keyboard-friendly gallery fallback', async ({ page }) => {
  await page.getByRole('button', { name: 'Help', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await page.getByRole('combobox', { name: 'Language' }).selectOption('en');
  await expect(page.getByRole('button', { name: 'Collection', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Toggle theme', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByRole('button', { name: 'Art gallery' }).click();
  await expect(page.getByRole('button', { name: '3. Garden', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '3. Garden', exact: true }).click();
  await page.getByRole('button', { name: 'Open reconstruction' }).click();
  await expect(page.getByRole('combobox', { name: 'Dataset', exact: true })).toHaveValue('garden');
});
test('collection has no automated accessibility violations', async ({ page }) => {
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
test('bookmark backup can be imported, merged and replaced', async ({ page }) => {
  await page.getByRole('button', { name: /Khám phá bộ trà/ }).click();
  await page.getByRole('button', { name: 'Save camera bookmark', exact: true }).click();
  await page.getByRole('button', { name: /Góc đã lưu/ }).click();
  const backup = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Backup JSON' }).click();
  const raw = await readFile(await (await backup).path(), 'utf8');
  expect(JSON.parse(raw).bookmarks).toHaveLength(1);
  const upload = page.getByLabel('Import JSON');
  await upload.setInputFiles({
    name: 'backup.json',
    mimeType: 'application/json',
    buffer: Buffer.from(raw),
  });
  await expect(page.getByText('Preview: 1 bookmarks', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Merge', exact: true }).click();
  await expect(page.getByRole('button', { name: /Góc đã lưu/ })).toContainText('(1)');
  await upload.setInputFiles({
    name: 'empty.json',
    mimeType: 'application/json',
    buffer: Buffer.from('{"schema_version":1,"bookmarks":[]}'),
  });
  await page.getByRole('button', { name: 'Replace', exact: true }).click();
  await expect(page.getByRole('button', { name: /Góc đã lưu/ })).toContainText('(0)');
  await upload.setInputFiles({
    name: 'invalid.json',
    mimeType: 'application/json',
    buffer: Buffer.from('{"schema_version":2,"bookmarks":[]}'),
  });
  await expect(
    page.getByRole('status').filter({ hasText: 'Unsupported bookmark backup' }),
  ).toBeVisible();
});
test('switching scene during a delayed submission cannot apply a stale pair', async ({ page }) => {
  // CPU network fixture: exercise the submission race without claiming CUDA QA.
  let submitted;
  let cancelled = false;
  await page.route('**/api/readiness', (route) => route.fulfill({ json: { state: 'ready' } }));
  await page.route('**/api/lease', (route) => route.fulfill({ json: { token: 'fixture-owner' } }));
  await page.route('**/api/jobs', async (route) => {
    const request = route.request().postDataJSON();
    submitted = { ...request, id: 'delayed-fixture-job', status: 'queued' };
    await new Promise((resolve) => setTimeout(resolve, 500));
    await route.fulfill({ status: 202, json: submitted });
  });
  await page.route('**/api/jobs/delayed-fixture-job/cancel', (route) => {
    cancelled = true;
    return route.fulfill({ json: { cancelled: true } });
  });
  await page.route('**/api/jobs/delayed-fixture-job', (route) =>
    route.fulfill({ json: { ...submitted, status: 'cancelled' } }),
  );
  await page.reload();
  await page.getByRole('button', { name: /Khám phá bộ trà/ }).click();
  const submission = page.waitForRequest(
    (r) => r.url().endsWith('/api/jobs') && r.method() === 'POST',
  );
  await expect(page.getByRole('button', { name: 'Render ảnh model', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Render ảnh model', exact: true }).click();
  await submission;
  await page.getByRole('combobox', { name: 'Dataset', exact: true }).selectOption('bonsai');
  await expect.poll(() => cancelled).toBe(true);
  await expect(page.getByRole('combobox', { name: 'Dataset', exact: true })).toHaveValue('bonsai');
  await expect(page.getByRole('combobox', { name: 'Image source', exact: true })).toHaveCount(0);
});
