import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const PUBLIC_SITE_ORIGINS = [
  { name: 'Vite', origin: 'http://localhost:5173', mockApi: true },
  { name: 'Nitro', origin: 'http://127.0.0.1:5278', mockApi: false },
] as const;

const LOCALIZED_SERVICE_ROUTES = [
  {
    name: 'Uzbek',
    path: '/services',
    skipLink: 'Asosiy mazmunga o‘tish',
    navigation: 'Sayt navigatsiyasi',
  },
  {
    name: 'Russian',
    path: '/ru/services',
    skipLink: 'Перейти к основному содержимому',
    navigation: 'Навигация сайта',
  },
] as const;

const AXE_WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

function jsonResponse(body: unknown) {
  return {
    status: 200,
    contentType: 'application/json; charset=utf-8',
    body: JSON.stringify(body),
  };
}

async function installSyntheticApi(page: Page, failPublicContent = false) {
  await page.routeWebSocket('**/*', (socket) => socket.close());
  await page.route('**/api/v1/**', async (route) => {
    const { pathname } = new URL(route.request().url());

    if (pathname.endsWith('/setup/status')) {
      await route.fulfill(jsonResponse({ initialized: true }));
      return;
    }

    if (pathname.endsWith('/auth/me')) {
      await route.fulfill({
        status: 401,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({ detail: 'synthetic unauthenticated request' }),
      });
      return;
    }

    if (pathname.includes('/api/v1/public-site/')) {
      if (failPublicContent) {
        await route.fulfill({
          status: 503,
          contentType: 'application/json; charset=utf-8',
          body: JSON.stringify({ detail: 'synthetic upstream unavailable' }),
        });
        return;
      }

      if (pathname.endsWith('/clinic')) {
        await route.fulfill(jsonResponse({
          name: 'SYNTHETIC QA CLINIC',
          address: null,
          phone: null,
          email: null,
        }));
        return;
      }

      if (pathname.endsWith('/services')) {
        const isRussian = new URL(route.request().url()).searchParams.get('locale') === 'ru';
        await route.fulfill(jsonResponse([{
          slug: 'synthetic-service',
          name: isRussian ? 'Синтетическая тестовая услуга' : 'Sintetik sinov xizmati',
          description: isRussian
            ? 'Синтетические данные для проверки доступности сайта.'
            : 'Saytga kirish imkoniyatini tekshirish uchun sintetik ma’lumot.',
          price: null,
          currency: null,
          category: isRussian ? 'Тестовая категория' : 'Sinov toifasi',
        }]));
        return;
      }

      if (pathname.endsWith('/doctors')) {
        await route.fulfill(jsonResponse([]));
        return;
      }

      if (pathname.endsWith('/categories')) {
        const isRussian = new URL(route.request().url()).searchParams.get('locale') === 'ru';
        await route.fulfill(jsonResponse([{ name: isRussian ? 'Тестовая категория' : 'Sinov toifasi' }]));
        return;
      }
    }

    await route.fulfill({
      status: 404,
      contentType: 'application/json; charset=utf-8',
      body: JSON.stringify({ detail: 'synthetic endpoint not found' }),
    });
  });
}

async function assertSkipNavigation(
  page: Page,
  expected: (typeof LOCALIZED_SERVICE_ROUTES)[number],
) {
  const skipLink = page.getByRole('link', { name: expected.skipLink, exact: true });
  const navigation = page.getByRole('navigation', { name: expected.navigation, exact: true });
  const main = page.getByRole('main');

  await expect(skipLink).toHaveCount(1);
  if (await navigation.count() === 0) {
    const mobileMenu = page.locator('.public-site__mobile-menu summary');
    await expect(mobileMenu).toBeVisible();
    await mobileMenu.click();
    await expect(navigation).toHaveCount(1);
    await page.reload();
    await expect(main).toBeVisible();
  } else {
    await expect(navigation).toHaveCount(1);
  }
  await expect(main).toHaveCount(1);

  const accessibleTree = await page.locator('body').ariaSnapshot();
  const skipPosition = accessibleTree.indexOf(`link "${expected.skipLink}"`);
  const mainPosition = accessibleTree.indexOf('main:');
  expect(skipPosition, 'the skip link should appear in the accessibility tree').toBeGreaterThanOrEqual(0);
  expect(mainPosition, 'the main landmark should appear in the accessibility tree').toBeGreaterThan(skipPosition);

  await page.keyboard.press('Tab');
  await expect(skipLink).toBeFocused();
  await expect(skipLink).toBeInViewport();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#main-content$/);
  await expect(main).toBeFocused();
}

async function assertNoAxeViolations(page: Page, label: string) {
  const results = await new AxeBuilder({ page }).withTags(AXE_WCAG_TAGS).analyze();
  const violations = results.violations.map(({ id, impact, help, nodes }) => ({
    id,
    impact,
    help,
    nodes: nodes.map(({ target, failureSummary }) => ({ target, failureSummary })),
  }));

  expect(violations, `${label}: Axe violations\n${JSON.stringify(violations, null, 2)}`).toEqual([]);
}

test.describe('public-site accessibility', () => {
  test('keyboard skip navigation and accessible landmarks work in Vite and Nitro in both locales', async ({ page }) => {
    for (const runtime of PUBLIC_SITE_ORIGINS) {
      if (runtime.mockApi) await installSyntheticApi(page);

      for (const route of LOCALIZED_SERVICE_ROUTES) {
        await page.goto(new URL(route.path, runtime.origin).toString());
        await expect(page.getByRole('main')).toBeVisible();
        await expect(page.getByRole('heading', { name: /xizmatlar|услуг/i })).toBeVisible();
        await assertSkipNavigation(page, route);
      }
    }
  });

  test('Axe WCAG A/AA scans pass on localized public catalog pages in Vite and Nitro', async ({ page }) => {
    for (const runtime of PUBLIC_SITE_ORIGINS) {
      if (runtime.mockApi) await installSyntheticApi(page);

      for (const route of LOCALIZED_SERVICE_ROUTES) {
        const label = `${runtime.name} ${route.name} ${route.path}`;
        await page.goto(new URL(route.path, runtime.origin).toString());
        await expect(page.getByRole('main')).toBeVisible();
        await expect(page.getByRole('heading', { name: /xizmatlar|услуг/i })).toBeVisible();

        await assertNoAxeViolations(page, label);
      }
    }
  });

  test('localized Vite error state keeps the keyboard bypass and has no Axe WCAG A/AA violations', async ({ page }) => {
    await installSyntheticApi(page, true);
    await page.goto('http://localhost:5173/ru/services');

    await expect(page.getByRole('alert')).toContainText('Не удалось загрузить актуальную информацию клиники.');
    await assertSkipNavigation(page, LOCALIZED_SERVICE_ROUTES[1]);

    await assertNoAxeViolations(page, 'Vite Russian error state');
  });
});
