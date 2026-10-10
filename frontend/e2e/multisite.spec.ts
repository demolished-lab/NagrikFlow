import { expect, test, type Page, type Route } from '@playwright/test';

const slug = 'small-business-registration';
const title = 'Small Business Registration';

const steps = [
  {
    id: 'name', type: 'action', title: 'Choose a business name',
    detail: 'Check availability before you submit the application.',
    url: 'https://www.mca.gov.in/', fee: 'No fee',
  },
  {
    id: 'udyam', type: 'action', title: 'Apply for Udyam registration',
    detail: 'Register an eligible micro, small, or medium enterprise.',
    url: 'https://udyamregistration.gov.in/',
  },
];

const mapPayload = {
  slug,
  title,
  city: 'Pune',
  state: 'Maharashtra',
  service_type: 'Business',
  verified: true,
  graph: { nodes: steps, edges: [['name', 'udyam']] },
  filters: { types: ['action'], statuses: ['ready', 'verified'], total: steps.length },
  sources: [
    { url: 'https://www.mca.gov.in/', ok: true },
    { url: 'https://udyamregistration.gov.in/', ok: true },
  ],
};

const pathway = {
  job_id: 41,
  slug,
  title,
  city: 'Pune',
  state: 'Maharashtra',
  created_at: '2026-10-03T12:00:00Z',
  status: 'verified',
  verified: true,
  steps: steps.length,
  completed: 0,
  completed_steps: [],
  steps_preview: steps,
  sources: mapPayload.sources,
};

async function installApiMocks(page: Page, role: 'user' | 'admin' = 'user', errorMetrics = false) {
  const completed = new Set<string>();
  const unhandled: string[] = [];

  await page.addInitScript(() => localStorage.setItem('civic_token', 'e2e-test-token'));
  await page.route('**/api/**', async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, '');
    const method = request.method();
    const json = (body: unknown, status = 200) => route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });

    if (method === 'GET' && path === '/me/profile') {
      return json({ email: 'asha@example.test', name: 'Asha Rao', role, city: 'Pune', state: 'Maharashtra' });
    }
    if (method === 'GET' && path === '/me/pathways') {
      return json([{ ...pathway, completed: completed.size, completed_steps: [...completed] }]);
    }
    if (method === 'GET' && path === '/me/dashboard') {
      return json({
        user: { name: 'Asha Rao' },
        have: ['PAN Card'],
        in_progress_maps: { [slug]: completed.size },
        next_easiest: [{ get: 'Apply for Udyam registration', effort: 'Easy', why: 'Your business details are ready.' }],
      });
    }
    if (method === 'GET' && path === '/me/brief') {
      return json({ brief: 'Your business registration steps are ready to review.', via: 'test fixture' });
    }
    if (method === 'GET' && path === '/me/notifications') {
      return json({ notifications: [], unread: 0 });
    }
    if (method === 'GET' && path === `/me/progress/${slug}`) {
      return json({ steps: [...completed] });
    }
    if (method === 'GET' && path === `/me/milestones/${slug}`) {
      return json({ milestones: [] });
    }
    if (method === 'GET' && path === `/maps/${slug}`) {
      return json({ ...mapPayload, graph: { ...mapPayload.graph, nodes: steps.filter((step) => !url.searchParams.get('q') || step.title.toLowerCase().includes(url.searchParams.get('q')!.toLowerCase())) } });
    }
    if (method === 'POST' && path === '/me/progress') {
      const body = request.postDataJSON() as { step_id?: string };
      if (body.step_id) completed.add(body.step_id);
      return json({ ok: true, steps: [...completed] });
    }
    if (method === 'POST' && path === '/build-task') {
      return json({ job_id: 41, slug });
    }
    if (method === 'GET' && path === '/jobs/41') {
      return json({ status: 'done', result: { slug } });
    }
    if (method === 'GET' && path === `/task/${slug}`) {
      return json(mapPayload);
    }
    if (method === 'GET' && path === '/admin/maps') {
      return json([{
        slug, title, steps: steps.length, verified: true,
        hash: 'e2e-source-hash', checked: '2026-10-03T12:00:00Z',
        sources: mapPayload.sources,
      }]);
    }
    if (method === 'GET' && path === '/admin/metrics') {
      return json({
        '/me/profile': { hits: 4, errors: 0, avg_ms: 18.4 },
        '/build-task': { hits: 2, errors: errorMetrics ? 1 : 0, avg_ms: 142.7 },
        '/jobs/*': { hits: 5, errors: 0, avg_ms: 9.2 },
      });
    }
    if (method === 'POST' && path === `/admin/maps/${slug}/verify`) {
      return json({ ok: true, verified: Boolean(request.postDataJSON().verified) });
    }
    if (method === 'POST' && path === '/admin/jobs/recheck') {
      return json({ job_id: 42 });
    }
    if (method === 'GET' && path === '/admin/jobs/42') {
      return json({ status: 'done', result: { maps: [] } });
    }

    unhandled.push(`${method} ${path}`);
    return json({ detail: `Unhandled E2E API request: ${method} ${path}` }, 404);
  });

  return unhandled;
}

test('guest task entry preserves location context and asks for sign-in before building', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'What do you need to get done?' })).toBeVisible();

  await page.getByRole('textbox', { name: 'Describe your civic task' }).fill('Register a small business');
  await page.getByRole('textbox', { name: 'City' }).fill('Pune');
  await page.getByRole('textbox', { name: 'State' }).fill('Maharashtra');
  await page.getByRole('combobox', { name: 'Type of service' }).selectOption({ label: 'Business & Trade' });
  await page.locator('.cv-public-build').click();

  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible();
  const saved = await page.evaluate(() => ({
    task: sessionStorage.getItem('civic_task_prefill'),
    location: JSON.parse(sessionStorage.getItem('civic_location_prefill') || '{}'),
  }));
  expect(saved).toEqual({
    task: 'Register a small business',
    location: { city: 'Pune', state: 'Maharashtra', serviceType: 'Business & Trade' },
  });
});

test('registration view presents required identity and secure account fields', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Register', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'A clearer path starts here.' })).toBeVisible();
  await expect(page.getByLabel('Name')).toBeVisible();
  await expect(page.getByLabel('Email')).toHaveAttribute('type', 'email');
  await expect(page.getByLabel('Password')).toHaveAttribute('minlength', '8');
  await expect(page.getByRole('link', { name: /Udyam Registration Portal/ })).toHaveAttribute('href', 'https://udyamregistration.gov.in/');
});

test('citizen can build a pathway, inspect steps and official sources, save progress, and open the dashboard', async ({ page }) => {
  const unhandled = await installApiMocks(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'What do you need to get done?' })).toBeVisible();

  await page.getByRole('textbox', { name: 'Describe your civic task' }).fill('Register a small business');
  await page.getByRole('button', { name: /Build my pathway/ }).click();
  await expect(page.getByRole('button', { name: /Preview pathway/ })).toBeVisible();
  await page.getByRole('button', { name: /Preview pathway/ }).click();

  await expect(page.getByRole('heading', { name: title })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Pathway steps' })).toContainText('Choose a business name');
  await expect(page.getByRole('link', { name: 'Official source ↗' }).first()).toHaveAttribute('href', 'https://www.mca.gov.in/');
  await page.getByRole('button', { name: /Map/ }).click();
  await expect(page.getByRole('region', { name: 'Interactive civic procedure map' })).toBeVisible();
  await page.getByTestId('rf__node-name').locator('.cv-flow-node').click();
  const stepDetails = page.getByRole('complementary', { name: 'Step details' });
  await expect(stepDetails).toContainText('Check availability before you submit the application.');
  await expect(stepDetails.getByRole('link', { name: /Open official site/ })).toHaveAttribute('href', 'https://www.mca.gov.in/');
  await stepDetails.getByRole('button', { name: 'Mark complete' }).click();
  await expect(stepDetails.getByText('Complete')).toBeVisible();
  await page.getByRole('button', { name: /List/ }).click();
  await page.getByRole('button', { name: 'Mark complete' }).first().click();
  await expect(page.locator('.cv-filtered-step').first().getByText('Complete')).toBeVisible();
  await expect.poll(() => unhandled).toEqual([]);

  await page.getByRole('button', { name: 'Documents', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Welcome back, Asha Rao' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'What you hold' })).toBeVisible();
  await expect(page.getByText('PAN Card')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Easiest next wins' })).toBeVisible();
});

test('administrator can inspect source freshness and trigger a source recheck', async ({ page }) => {
  const unhandled = await installApiMocks(page, 'admin');
  await page.goto('/#/admin');

  await expect(page.getByRole('heading', { name: 'Pathway verification desk' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Pathway review' })).toBeVisible();
  await expect(page.getByText('e2e-source-hash')).toBeVisible();
  await expect(page.getByText('https://udyamregistration.gov.in/')).toBeVisible();
  await page.getByRole('button', { name: 'Recheck source', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('No changes found');
  expect(unhandled).toEqual([]);
});

test('administrator can inspect frontend and backend performance metrics', async ({ page }) => {
  const unhandled = await installApiMocks(page, 'admin');
  await page.goto('/#/performance');
  await expect(page.getByRole('heading', { name: 'Performance monitoring' })).toBeVisible();
  await expect(page.getByText('Page load')).toBeVisible();
  await expect(page.getByText('Backend route health')).toBeVisible();
  await expect(page.getByText('/build-task')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Refresh metrics' })).toBeVisible();
  expect(unhandled).toEqual([]);
});

test('performance dashboard triggers an error-rate alert and exports a JSON report', async ({ page }) => {
  const unhandled = await installApiMocks(page, 'admin', true);
  await page.goto('/#/performance');
  await expect(page.getByRole('alert')).toContainText('API error-rate alert triggered');
  await expect(page.getByText('Alert active')).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export JSON' }).click();
  expect((await download).suggestedFilename()).toMatch(/^nagrikflow-performance-.*\.json$/);
  await page.getByRole('button', { name: 'Acknowledge' }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect(unhandled).toEqual([]);
});

test('authenticated NagrikFlow shell exposes service discovery and the reference showcase', async ({ page }) => {
  const unhandled = await installApiMocks(page);
  await page.goto('/#/search');
  await expect(page.getByRole('button', { name: 'NagrikFlow home' })).toBeVisible();
  await expect(page.getByRole('heading', { name: /We found .* result/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /View path for/ }).first()).toBeVisible();
  await page.goto('/#/showcase');
  await expect(page.getByRole('heading', { name: 'Mobile Responsive Views' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Key UI Components' })).toBeVisible();
  expect(await page.locator('body').innerText()).not.toContain('Civic Path Navigator');
  expect(unhandled).toEqual([]);
});

test('mobile home view stays within the viewport and keeps navigation usable', async ({ page }) => {
  await installApiMocks(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'What do you need to get done?' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible();
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport + 1);
});
