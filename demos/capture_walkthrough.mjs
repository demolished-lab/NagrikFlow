import { createRequire } from 'node:module';
import { mkdirSync, renameSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const requireFrontend = createRequire(fileURLToPath(new URL('../frontend/package.json', import.meta.url)));
const { chromium } = requireFrontend('@playwright/test');

const demoDir = fileURLToPath(new URL('.', import.meta.url));
const rawDir = join(demoDir, 'raw');
const output = join(rawDir, 'civic-pathfinder-walkthrough.webm');
const width = 1600;
const height = 900;
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

mkdirSync(rawDir, { recursive: true });
rmSync(output, { force: true });
const browser = await chromium.launch({
  headless: false,
  executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium',
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-background-timer-throttling'],
});
const context = await browser.newContext({
  viewport: { width, height },
  deviceScaleFactor: 1,
  recordVideo: { dir: rawDir, size: { width, height } },
});
const page = await context.newPage();
page.setDefaultTimeout(12000);

// Recordly-inspired cursor polish: a small, readable focus ring follows only
// the demonstrator's real pointer; it does not alter the app or its source.
await page.addInitScript(() => {
  document.addEventListener('DOMContentLoaded', () => {
    const cursor = document.createElement('div');
    cursor.id = 'demo-focus-cursor';
    cursor.setAttribute('aria-hidden', 'true');
    document.body.append(cursor);
    const style = document.createElement('style');
    style.textContent = `
      *, *::before, *::after { cursor: none !important; }
      #demo-focus-cursor { position: fixed; top: 0; left: 0; z-index: 2147483647; width: 23px; height: 23px; margin: -11px 0 0 -11px; border: 2px solid rgba(255,255,255,.98); border-radius: 50%; box-shadow: 0 1px 6px rgba(9,30,42,.55), 0 0 0 2px rgba(27,122,104,.86); background: rgba(27,122,104,.16); pointer-events: none; transform: translate(-100px,-100px); transition: transform 85ms ease-out, scale 120ms ease; }
      #demo-focus-cursor.is-down { scale: .78; background: rgba(27,122,104,.42); }
    `;
    document.head.append(style);
    window.addEventListener('mousemove', (event) => {
      cursor.style.transform = `translate(${event.clientX}px, ${event.clientY}px)`;
    }, { passive: true });
    window.addEventListener('mousedown', () => cursor.classList.add('is-down'));
    window.addEventListener('mouseup', () => cursor.classList.remove('is-down'));
  }, { once: true });
});

const step = async (label, ms = 1600) => {
  console.log(`capture: ${label}`);
  await pause(ms);
};

try {
  await page.goto(process.env.DEMO_URL || 'http://127.0.0.1:5173', { waitUntil: 'networkidle' });
  await page.locator('.cv-public-shell').waitFor();
  await step('public service navigator', 3500);

  await page.getByLabel('Describe your civic task').fill('Register a small business');
  await page.getByLabel('City').fill('Hyderabad');
  await page.getByLabel('State').fill('Telangana');
  await page.getByLabel('Type of service').selectOption({ label: 'Business & Trade' });
  await step('describe the goal and location', 2800);

  await page.locator('form.cv-public-composer').getByRole('button', { name: /Build my pathway/ }).click();
  await page.locator('.cv-auth-card').waitFor();
  await step('sign in to keep progress together', 2300);
  await page.getByLabel('Email').fill(process.env.DEMO_EMAIL || 'rani@example.in');
  await page.getByLabel('Password').fill(process.env.DEMO_PASSWORD || 'secret1234');
  await page.getByRole('button', { name: /^Login$/i }).click();
  await page.locator('.cv-app-layout').waitFor();
  await page.locator('.cv-recent-pathway-card').waitFor();
  await step('saved pathway and progress', 5500);

  await page.locator('.cv-recent-pathway-footer').getByRole('button', { name: /Open pathway/ }).click();
  await page.locator('.cv-roadmap-view').waitFor();
  await step('reviewed steps and source links', 5000);
  await page.getByRole('button', { name: /Map/ }).click();
  await page.locator('.cv-interactive-map').waitFor();
  await step('dependency map', 7000);

  await page.getByRole('button', { name: 'Documents', exact: true }).click();
  await page.locator('.cv-dashboard-view').waitFor();
  await page.locator('.cv-dashboard-grid').scrollIntoViewIfNeeded();
  await step('documents and easier next steps', 7000);
  // Hold a clean, readable final screen for the outro transition.
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
  await step('dashboard close', 4000);
} finally {
  await page.close();
  const clip = await page.video().path();
  await context.close();
  await browser.close();
  renameSync(clip, output);
  console.log(`saved: ${output}`);
}
