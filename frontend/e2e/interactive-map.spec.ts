import { expect, test } from '@playwright/test';

const nodes = [
  { id: 'aadhaar', type: 'prereq', title: 'Have Aadhaar', detail: 'Aadhaar number of proprietor/partner for OTP.' },
  { id: 'pan', type: 'prereq', title: 'Have PAN', detail: 'PAN validated against Income Tax database.' },
  { id: 'udyam', type: 'action', title: 'Udyam Registration', detail: 'Free, paperless registration.', url: 'https://udyamregistration.gov.in/' },
  { id: 'gst', type: 'action', title: 'GST Registration', detail: 'GST registration with PAN.', fee: 'Rs 0' },
];
const edges = [['aadhaar', 'udyam'], ['pan', 'udyam'], ['pan', 'gst'], ['udyam', 'gst']];

function mapResponse(query = '') {
  const params = new URLSearchParams(query);
  const q = (params.get('q') || '').toLowerCase();
  const type = params.get('node_type') || '';
  const status = params.get('status') || '';
  const visible = nodes.filter((node) => {
    const nodeStatus = node.id === 'udyam' || node.id === 'gst' ? 'action' : 'ready';
    return (!type || node.type === type) && (!status || nodeStatus === status) && (!q || `${node.title} ${node.detail} ${node.fee || ''}`.toLowerCase().includes(q));
  });
  const ids = new Set(visible.map((node) => node.id));
  return {
    slug: 'udyam-register',
    title: 'Register a small business',
    city: 'Hyderabad',
    graph: { nodes: visible, edges: edges.filter(([from, to]) => ids.has(from) && ids.has(to)) },
    filters: { types: ['action', 'prereq'], statuses: ['action', 'ready'], total: nodes.length },
    sources: ['https://udyamregistration.gov.in/'],
  };
}

async function mockAuthenticatedApi(page: import('@playwright/test').Page) {
  await page.addInitScript(() => localStorage.setItem('civic_token', 'e2e-token'));
  await page.route('**/api/maps/udyam-register*', async (route) => {
    const url = new URL(route.request().url());
    await route.fulfill({ json: mapResponse(url.search) });
  });
  await page.route('**/api/me/progress/udyam-register', async (route) => {
    await route.fulfill({ json: { steps: ['aadhaar'] } });
  });
  await page.route('**/api/me/progress', async (route) => {
    if (route.request().method() === 'POST') await route.fulfill({ json: { ok: true } });
    else await route.continue();
  });
}

test('user can authenticate and reach the personalized dashboard shell', async ({ page }) => {
  await page.route('**/api/auth/login', async (route) => {
    await route.fulfill({ json: { token: 'e2e-auth-token', user_id: 7 } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Login' }).first().click();
  await page.getByLabel('Email').fill('citizen@example.com');
  await page.getByLabel('Password').fill('correct-horse-battery-staple');
  await page.getByRole('button', { name: 'Login' }).last().click();
  await expect(page.getByText('Your civic twin')).toBeVisible();
  await expect(page.evaluate(() => localStorage.getItem('civic_token'))).resolves.toBe('e2e-auth-token');
});

test('interactive map filters are sent to the backend and update visible nodes', async ({ page }) => {
  await mockAuthenticatedApi(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'Path Builder' }).click();
  await expect(page.getByText('VERIFIED CIVIC MAP')).toBeVisible();
  await expect(page.getByText('Have Aadhaar')).toBeVisible();
  await expect(page.getByText('Udyam Registration')).toBeVisible();

  await page.getByLabel('Filter by step type').selectOption('action');
  await expect(page.getByText('Udyam Registration')).toBeVisible();
  await expect(page.getByText('Have Aadhaar')).toHaveCount(0);
  await expect(page.getByText('Filters are synced with the API')).toBeVisible();

  await page.getByRole('button', { name: 'List' }).click();
  await expect(page.getByRole('heading', { name: 'GST Registration' })).toBeVisible();
});

test('personalized progress is visible and marking a step done updates the map', async ({ page }) => {
  await mockAuthenticatedApi(page);
  await page.route('**/api/me/dashboard', async (route) => {
    await route.fulfill({ json: { have: ['Aadhaar'], next_easiest: [], in_progress_maps: { 'udyam-register': 1 }, user: { name: 'Test Citizen' } } });
  });
  await page.route('**/api/me/brief', async (route) => {
    await route.fulfill({ json: { brief: 'Your next step is ready.', via: 'test' } });
  });
  await page.goto('/');
  await page.locator('.cv-nav-item').filter({ hasText: 'Civic Twin' }).click();
  await expect(page.getByText('Welcome back, Test Citizen')).toBeVisible();
  await expect(page.getByText('PERSONAL PROGRESS')).toBeVisible();
  await expect(page.getByText('1 of 4 steps completed')).toBeVisible();

  await page.getByRole('button', { name: 'Path Builder' }).click();
  await page.getByRole('button', { name: 'List' }).click();
  await page.getByText('Udyam Registration').click();
  await page.locator('.cv-map-detail').getByRole('button', { name: /Mark done/i }).click();
  await expect(page.locator('.cv-map-detail .cv-status', { hasText: 'Verified' })).toBeVisible();
});
