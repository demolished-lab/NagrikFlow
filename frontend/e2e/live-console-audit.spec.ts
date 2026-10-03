import { mkdir } from 'node:fs/promises';
import { expect, test } from '@playwright/test';

// Live audit: NO route mocks — every page talks to the real backend through
// the vite /api proxy. Fails on any page error, console error, HTTP 5xx or
// hard network failure; warnings are printed for review.
const benign = /favicon|__vite_ping|WebSocket|HMR|React DevTools|ERR_ABORTED|web-vitals|jsdelivr/i;

test('live end-to-end UI audit: real backend, zero errors', async ({ page }, testInfo) => {
  test.skip(process.env.LIVE_E2E !== '1', 'Set LIVE_E2E=1 with a local backend to run this live audit.');
  // Real 5-source CDX builds measured at ~8.3 min wall time (job 16: 8m18s),
  // so the terminal-state wait needs real margin over that.
  test.setTimeout(900_000);
  const shotDir = testInfo.outputPath();
  await mkdir(shotDir, { recursive: true });
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
  await page.screenshot({ path: `${shotDir}/01-home.png`, fullPage: true });

  // 2. real build through the concierge form (~5 min live)
  await page.getByLabel('Describe your civic task').fill('udyam registration');
  await page.getByLabel('City').fill('Pune');
  await page.getByLabel('State').fill('MH');
  await page.getByRole('button', { name: /Build my pathway/ }).click();
  await expect(page.locator('.cv-build-status')).toBeVisible({ timeout: 15_000 });
  const doneState = page.getByText(/awaiting source review|Your reviewed pathway is ready|We couldn.t build/);
  await expect(doneState).toBeVisible({ timeout: 720_000 });
  await page.screenshot({ path: `${shotDir}/02-build-done.png`, fullPage: true });

  // 3. pathways list
  await page.goto('/#/pathways');
  await expect(page.getByRole('heading', { name: 'My pathways' })).toBeVisible();
  await page.screenshot({ path: `${shotDir}/03-pathways.png`, fullPage: true });

  // 4. roadmap draft: the review banner is structural for unverified maps;
  //    source warnings appear only when a source degraded (5/5 OK on a
  //    healthy network) — log them for review instead of hard-asserting.
  await page.getByRole('button', { name: 'Open pathway' }).first().click();
  await expect(page.getByText('DRAFT PATHWAY')).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByText('This pathway is awaiting source review.'),
  ).toBeVisible({ timeout: 30_000 });
  const roadWarn = page.getByText('Some sources for this pathway need your attention.');
  if (await roadWarn.count()) console.log('ROADMAP_WARNINGS=' + await roadWarn.innerText());
  await page.screenshot({ path: `${shotDir}/04-roadmap-draft.png`, fullPage: true });

  // 5. packet must render from the real backend; warnings conditional as above
  await page.getByRole('button', { name: 'Load packet' }).click();
  await expect(page.locator('.cv-packet-body')).toBeVisible({ timeout: 60_000 });
  const packetWarn = page.getByText('Source warnings for this packet.');
  if (await packetWarn.count()) console.log('PACKET_WARNINGS=' + await packetWarn.innerText());
  await page.screenshot({ path: `${shotDir}/05-packet.png`, fullPage: true });

  // 6. documents + help surfaces
  await page.goto('/#/documents');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${shotDir}/06-documents.png`, fullPage: true });
  await page.goto('/#/help');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${shotDir}/07-help.png`, fullPage: true });

  console.log('AUDIT_HARD=' + JSON.stringify(hard, null, 2));
  console.log('AUDIT_SOFT=' + JSON.stringify(soft, null, 2));
  expect(hard).toEqual([]);
});
