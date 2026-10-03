import { expect, test } from '@playwright/test';

test('pathway generation exposes staged background activity', async ({ page }) => {
  let polls = 0;
  await page.addInitScript(() => localStorage.setItem('civic_token', 'activity-token'));
  await page.route('**/api/me/profile', async (route) => route.fulfill({
    json: { id: 1, email: 'citizen@example.com', name: 'Test Citizen', role: 'citizen', city: 'Pune', state: 'Maharashtra' },
  }));
  await page.route('**/api/me/pathways', async (route) => route.fulfill({ json: [] }));
  await page.route('**/api/build-task', async (route) => route.fulfill({ json: { job_id: 17, slug: 'water-connection' } }));
  await page.route('**/api/jobs/17', async (route) => {
    polls += 1;
    await route.fulfill({ json: polls < 3 ? { status: 'running' } : { status: 'done', result: { slug: 'water-connection' } } });
  });
  await page.route('**/api/task/water-connection', async (route) => route.fulfill({
    json: { slug: 'water-connection', title: 'Get a water connection', graph: { nodes: [], edges: [] }, verified: false },
  }));

  await page.goto('/');
  await page.getByLabel('Describe your civic task').fill('Get a water connection');
  await page.getByRole('button', { name: /Build my pathway/ }).click();

  const activity = page.getByRole('region', { name: 'Live pathway activity' });
  await expect(activity).toBeVisible();
  await expect(activity).toContainText('Task received');
  await expect(activity).toContainText('Finding official sources');
  await expect(activity).toContainText('Cross-checking requirements');
  await expect(page.getByRole('status')).toContainText('Putting your pathway together');
  await expect(page.getByText('Your pathway was built and is awaiting source review.')).toBeVisible({ timeout: 10000 });
});
