import { expect, test } from '@playwright/test';

// Live audit: NO route mocks — every page talks to the real backend through
// the vite /api proxy. Fails on any page error, console error, HTTP 5xx or
// hard network failure; warnings are printed for review.
const SHOT_DIR = 'C:\\Users\\Raja\\AppData\\Local\\Temp\\opencode\\ui-audit';
const benign = /favicon|__vite_ping|WebSocket|HMR|React DevTools|ERR_ABORTED|web-vitals|jsdelivr/i;

test('live end-to-end UI audit: real backend, zero errors', async ({ page }) => {
  test.setTimeout(600_000);
  const hard: string[] = [];
  const soft: string[] = [];

  page.on('console', (msg) => {
    const where = msg.location()?.url || '';
    if (msg.type() === 'error' && !benign.test(msg.text()) && !benign.test(where)) {
      hard.push(`console.error: ${msg.text()} @ ${where}`);
    }
    if (msg.type() === 'warning' && !benign.test(msg.text())) soft.push(`console.warning: ${msg.text()}`);
  });
  page.on('pageerror', (err) => hard.push(`pageerror: ${err.message}`));
  page.on('response', (res) => {
    if (res.status() >= 500) hard.push(`HTTP ${res.status()}: ${res.url()}`);
    if (res.status() === 404 && !benign.test(res.url())) soft.push(`HTTP 404: ${res.url()}`);
  });
  page.on('requestfailed', (req) => {
    const why = req.failure()?.errorText || '';
    if (!benign.test(req.url()) && !benign.test(why)) hard.push(`requestfailed: ${req.url()} ${why}`);
  });

  // 1. register through the real form
  const email = `audit${Date.now()}@t.co`;
  await page.goto('/');
  await page.getByRole('button', { name: 'Register' }).first().click();
  await page.getByLabel('Name').fill('UI Audit');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill('pw123456');
  await page.getByLabel('City').fill('Pune');
  await page.getByLabel('State').fill('MH');
  await page.getByRole('button', { name: 'Register' }).last().click();
  await expect(page.getByLabel('Describe your civic task')).toBeVisible({ timeout: 20_000 });
  await page.screenshot({ path: `${SHOT_DIR}/01-home.png`, fullPage: true });

  // 2. real build through the concierge form (~5 min live)
  await page.getByLabel('Describe your civic task').fill('udyam registration');
  await page.getByLabel('City').fill('Pune');
  await page.getByLabel('State').fill('MH');
  await page.getByRole('button', { name: /Build my pathway/ }).click();
  await expect(page.locator('.cv-build-status')).toBeVisible({ timeout: 15_000 });
  const doneState = page.getByText(/awaiting source review|Your reviewed pathway is ready|We couldn.t build/);
  await expect(doneState).toBeVisible({ timeout: 480_000 });
  await page.screenshot({ path: `${SHOT_DIR}/02-build-done.png`, fullPage: true });

  // 3. pathways list
  await page.goto('/#/pathways');
  await expect(page.getByRole('heading', { name: 'My pathways' })).toBeVisible();
  await page.screenshot({ path: `${SHOT_DIR}/03-pathways.png`, fullPage: true });

  // 4. roadmap draft: warnings banner must be visible to the citizen
  await page.getByRole('button', { name: 'Open pathway' }).first().click();
  await expect(page.getByText('DRAFT PATHWAY')).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByText('Some sources for this pathway need your attention.'),
  ).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: `${SHOT_DIR}/04-roadmap-warnings.png`, fullPage: true });

  // 5. packet: source warnings must surface here too
  await page.getByRole('button', { name: 'Load packet' }).click();
  await expect(page.getByText('Source warnings for this packet.')).toBeVisible({ timeout: 60_000 });
  await page.screenshot({ path: `${SHOT_DIR}/05-packet-warnings.png`, fullPage: true });

  // 6. documents + help surfaces
  await page.goto('/#/documents');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${SHOT_DIR}/06-documents.png`, fullPage: true });
  await page.goto('/#/help');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${SHOT_DIR}/07-help.png`, fullPage: true });

  console.log('AUDIT_HARD=' + JSON.stringify(hard, null, 2));
  console.log('AUDIT_SOFT=' + JSON.stringify(soft, null, 2));
  expect(hard).toEqual([]);
});
