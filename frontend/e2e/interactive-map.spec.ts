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
    state: 'Telangana',
    graph: { nodes: visible, edges: edges.filter(([from, to]) => ids.has(from) && ids.has(to)) },
    filters: { types: ['action', 'prereq'], statuses: ['action', 'ready'], total: nodes.length },
    sources: ['https://udyamregistration.gov.in/'],
    verified: true,
  };
}

const savedPathway = {
  job_id: 21,
  slug: 'udyam-register',
  title: 'Register a small business',
  city: 'Hyderabad',
  state: 'Telangana',
  status: 'verified',
  verified: true,
  steps: 4,
  completed: 1,
  completed_steps: ['aadhaar'],
  steps_preview: nodes.slice(0, 4).map(({ id, title, detail, url, type }) => ({ id, title, detail, url, type })),
  sources: ['https://udyamregistration.gov.in/'],
  created_at: '2026-09-27T08:00:00Z',
};

async function mockAuthenticatedApi(page: import('@playwright/test').Page) {
  await page.addInitScript(() => localStorage.setItem('civic_token', 'e2e-token'));
  await page.route('**/api/me/profile', async (route) => {
    await route.fulfill({ json: { id: 7, email: 'citizen@example.com', name: 'Test Citizen', city: 'Hyderabad', state: 'Telangana', role: 'citizen' } });
  });
  await page.route('**/api/me/pathways', async (route) => {
    await route.fulfill({ json: [savedPathway] });
  });
  await page.route('**/api/maps/udyam-register*', async (route) => {
    const url = new URL(route.request().url());
    await route.fulfill({ json: mapResponse(url.search) });
  });
  await page.route('**/api/me/progress/udyam-register', async (route) => {
    await route.fulfill({ json: { steps: ['aadhaar'] } });
  });
  await page.route('**/api/me/milestones/udyam-register', async (route) => {
    await route.fulfill({ json: { milestones: [{ step_id: 'aadhaar', title: 'Have Aadhaar', due_at: '2026-10-01T00:00:00Z', days_left: 4, status: 'active' }] } });
  });
  await page.route('**/api/me/notifications', async (route) => {
    await route.fulfill({ json: { notifications: [], unread: 0 } });
  });
  await page.route('**/api/me/progress', async (route) => {
    if (route.request().method() === 'POST') await route.fulfill({ json: { ok: true } });
    else await route.continue();
  });
}

test('public root presents the concierge reference and preserves task and location through sign-in', async ({ page }) => {
  await page.route('**/api/auth/login', async (route) => {
    await route.fulfill({ json: { token: 'e2e-auth-token', user_id: 7 } });
  });
  await page.route('**/api/me/profile', async (route) => {
    await route.fulfill({ json: { id: 7, email: 'citizen@example.com', name: 'Test Citizen', city: 'Hyderabad', state: 'Telangana', role: 'citizen' } });
  });
  await page.route('**/api/me/pathways', async (route) => route.fulfill({ json: [] }));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'What do you need to get done?' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Example pathway' })).toBeVisible();
  await expect(page.getByText('Preview only')).toBeVisible();
  await page.getByLabel('Describe your civic task').fill('Get a water connection');
  await page.getByLabel('City').fill('Pune');
  await page.getByLabel('State').fill('Maharashtra');
  await page.getByRole('button', { name: 'Build my pathway' }).first().click();
  await expect(page.getByLabel('Email')).toBeVisible();
  await page.getByLabel('Email').fill('citizen@example.com');
  await page.getByLabel('Password').fill('correct-horse-battery-staple');
  await page.getByRole('button', { name: 'Login' }).last().click();
  await expect(page.getByRole('heading', { name: 'What do you need to get done?' })).toBeVisible();
  await expect(page.getByLabel('Describe your civic task')).toHaveValue('Get a water connection');
  await expect(page.getByLabel('City')).toHaveValue('Pune');
  await expect(page.getByLabel('State')).toHaveValue('Maharashtra');
  await expect(page.evaluate(() => localStorage.getItem('civic_token'))).resolves.toBe('e2e-auth-token');
});

test('register shortcut opens account registration mode', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Register' }).first().click();
  await expect(page.getByLabel('Name')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Register' }).last()).toBeVisible();
});

test('login and registration share the concierge shell and fit a mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Login' }).first().click();
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Official service links' })).toBeVisible();
  await expect(page.locator('.cv-auth-shell')).toHaveCount(1);
  const dimensions = await page.evaluate(() => ({ viewport: document.documentElement.clientWidth, page: document.documentElement.scrollWidth }));
  expect(dimensions.page).toBeLessThanOrEqual(dimensions.viewport);
  await page.getByRole('button', { name: 'Back to services' }).click();
  await expect(page.getByRole('heading', { name: 'What do you need to get done?' })).toBeVisible();
  await page.getByRole('button', { name: 'Register' }).first().click();
  await expect(page.getByRole('heading', { name: 'A clearer path starts here.' })).toBeVisible();
  await expect(page.getByLabel('City')).toBeVisible();
});

test('user can authenticate and reach the personalized concierge home', async ({ page }) => {
  await page.route('**/api/auth/login', async (route) => {
    await route.fulfill({ json: { token: 'e2e-auth-token', user_id: 7 } });
  });
  await page.route('**/api/me/profile', async (route) => {
    await route.fulfill({ json: { id: 7, email: 'citizen@example.com', name: 'Test Citizen', city: 'Hyderabad', state: 'Telangana', role: 'citizen' } });
  });
  await page.route('**/api/me/pathways', async (route) => route.fulfill({ json: [] }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Login' }).first().click();
  await page.getByLabel('Email').fill('citizen@example.com');
  await page.getByLabel('Password').fill('correct-horse-battery-staple');
  await page.getByRole('button', { name: 'Login' }).last().click();
  await expect(page.getByRole('heading', { name: 'What do you need to get done?' })).toBeVisible();
  await expect(page.getByLabel('Describe your civic task')).toBeVisible();
  await expect(page.getByLabel('City')).toHaveValue('Hyderabad');
  await expect(page.evaluate(() => localStorage.getItem('civic_token'))).resolves.toBe('e2e-auth-token');
});

test('My pathways lists saved server data and opens its roadmap', async ({ page }) => {
  await mockAuthenticatedApi(page);
  await page.goto('/#/pathways');
  await expect(page.getByRole('heading', { name: 'My pathways' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Register a small business' })).toBeVisible();
  await expect(page.getByText('Reviewed and ready')).toBeVisible();
  await page.getByRole('button', { name: 'Open pathway' }).click();
  await expect(page.getByText('REVIEWED CIVIC PATHWAY')).toBeVisible();
});

test('pathway map filters are sent to the backend and update visible steps', async ({ page }) => {
  await mockAuthenticatedApi(page);
  await page.goto('/#/roadmap/udyam-register');
  await expect(page.getByText('REVIEWED CIVIC PATHWAY')).toBeVisible();
  await expect(page.getByText('Have Aadhaar')).toBeVisible();
  await expect(page.getByText('Udyam Registration')).toBeVisible();

  await page.getByLabel('Filter by step type').selectOption('action');
  await expect(page.getByText('Udyam Registration')).toBeVisible();
  await expect(page.getByText('Have Aadhaar')).toHaveCount(0);
  await expect(page.getByText('Filters are synced with the API')).toBeVisible();

  await page.locator('.cv-view-toggle button').nth(1).click();
  await expect(page.getByRole('button', { name: /Map/ })).toBeVisible();
});

test('saved pathway progress and documents dashboard remain connected', async ({ page }) => {
  await mockAuthenticatedApi(page);
  await page.route('**/api/me/dashboard', async (route) => {
    await route.fulfill({ json: { have: ['Aadhaar'], next_easiest: [], in_progress_maps: { 'udyam-register': 1 }, user: { name: 'Test Citizen' } } });
  });
  await page.route('**/api/me/brief', async (route) => {
    await route.fulfill({ json: { brief: 'Your next step is ready.', via: 'test' } });
  });
  await page.goto('/#/documents');
  await expect(page.getByText('Welcome back, Test Citizen')).toBeVisible();
  await expect(page.getByText('PERSONAL PROGRESS')).toBeVisible();
  await expect(page.getByText('1 of 4 steps completed')).toBeVisible();

  await page.goto('/#/roadmap/udyam-register');
  const udyamStep = page.locator('.cv-filtered-step').filter({ hasText: 'Udyam Registration' });
  await udyamStep.getByRole('button', { name: 'Mark complete' }).click();
  await expect(udyamStep.getByText('Complete')).toBeVisible();
});

test('task build result is reflected from the saved API pathway and review status', async ({ page }) => {
  await mockAuthenticatedApi(page);
  let submitted: any = null;
  await page.route('**/api/build-task', async (route) => {
    submitted = route.request().postDataJSON();
    await route.fulfill({ json: { job_id: 101, slug: 'new-water-connection' } });
  });
  await page.route('**/api/jobs/101', async (route) => {
    await route.fulfill({ json: { status: 'done', result: { slug: 'new-water-connection' } } });
  });
  await page.route('**/api/task/new-water-connection', async (route) => {
    await route.fulfill({ json: { slug: 'new-water-connection', title: 'Get a water connection', city: 'Pune', state: 'Maharashtra', graph: { nodes, edges }, sources: ['https://example.gov.in'], verified: false } });
  });
  await page.route('**/api/maps/new-water-connection*', async (route) => {
    await route.fulfill({ json: { slug: 'new-water-connection', title: 'Get a water connection', city: 'Pune', state: 'Maharashtra', graph: { nodes, edges }, filters: { types: ['action', 'prereq'], statuses: ['action', 'ready'], total: nodes.length }, sources: ['https://example.gov.in'], verified: false } });
  });
  await page.route('**/api/me/progress/new-water-connection', async (route) => {
    await route.fulfill({ json: { steps: [] } });
  });
  await page.route('**/api/me/pathways', async (route) => {
    await route.fulfill({ json: [{ ...savedPathway, slug: 'new-water-connection', title: 'Get a water connection', city: 'Pune', state: 'Maharashtra', status: 'review_required', verified: false }] });
  });

  await page.goto('/');
  await page.getByLabel('Describe your civic task').fill('Get a water connection');
  await page.getByLabel('City').fill('Pune');
  await page.getByLabel('State').fill('Maharashtra');
  await page.getByRole('button', { name: 'Build my pathway' }).click();
  await expect(page.getByText('Your pathway was built and is awaiting source review.')).toBeVisible({ timeout: 10000 });
  expect(submitted).toMatchObject({ task: 'Get a water connection', city: 'Pune', state: 'Maharashtra' });
  await page.getByRole('button', { name: 'Preview pathway' }).click();
  await expect(page.getByText('DRAFT PATHWAY')).toBeVisible();
  await expect(page.getByText('This pathway is awaiting source review.')).toBeVisible();
});
