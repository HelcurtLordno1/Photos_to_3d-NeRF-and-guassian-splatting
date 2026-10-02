import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: 'tests/e2e',
  use: {
    baseURL: 'http://127.0.0.1:7019',
    launchOptions: { executablePath: process.env.TOPIC16_TEST_BROWSER },
  },
  webServer: {
    command: process.env.TOPIC16_TEST_PYTHON
      ? `"${process.env.TOPIC16_TEST_PYTHON}" tests/fixture_api.py`
      : 'python tests/fixture_api.py',
    url: 'http://127.0.0.1:7019/api/health',
    reuseExistingServer: false,
  },
  reporter: [['list'], ['html', { open: 'never' }]],
});
