import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const VITE_ORIGIN = 'http://localhost:5173';
const PUBLIC_SITE_ORIGINS = [
  { name: 'Vite', origin: VITE_ORIGIN },
  { name: 'Nitro', origin: 'http://127.0.0.1:5278' },
] as const;
const FIXTURE_ORIGIN = 'http://127.0.0.1:' + Number(process.env.PUBLIC_SITE_FIXTURE_PORT || 5279);

const LOCALES = [
  {
    lang: 'uz-Latn',
    prefix: '',
    skipLink: 'Asosiy mazmunga o‘tish',
    navigation: 'Sayt navigatsiyasi',
    doctorName: 'Sintetik sinov profili',
  },
  {
    lang: 'ru',
    prefix: '/ru',
    skipLink: 'Перейти к основному содержимому',
    navigation: 'Навигация сайта',
    doctorName: 'Синтетический тестовый профиль',
  },
] as const;
type Locale = (typeof LOCALES)[number];

const PAGES = [
  { path: '', titles: { 'uz-Latn': 'SYNTHETIC QA CLINIC', ru: 'SYNTHETIC QA CLINIC' } },
  { path: '/services', titles: { 'uz-Latn': 'Xizmatlar', ru: 'Услуги' } },
  {
    path: '/services/synthetic-service',
    titles: { 'uz-Latn': 'Sintetik sinov xizmati', ru: 'Синтетическая тестовая услуга' },
  },
  { path: '/doctors', titles: { 'uz-Latn': 'Shifokorlar', ru: 'Врачи' } },
  {
    path: '/doctors/synthetic-profile',
    titles: {
      'uz-Latn': 'Sinov mutaxassisligi — Sintetik sinov profili',
      ru: 'Тестовая специализация — Синтетический тестовый профиль',
    },
  },
  { path: '/prices', titles: { 'uz-Latn': 'Narxlar', ru: 'Цены' } },
  { path: '/contacts', titles: { 'uz-Latn': 'Kontaktlar', ru: 'Контакты' } },
] as const;

const AXE_WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

function jsonResponse(body: unknown, status = 200) {
  return {
    status,
    contentType: 'application/json; charset=utf-8',
    body: JSON.stringify(body),
  };
}

async function installSyntheticApi(
  page: Page,
  request: APIRequestContext,
  failPublicContent = false,
) {
  await page.routeWebSocket('**/*', (socket) => socket.close());
  await page.route('**/*', (route) => {
    const { origin } = new URL(route.request().url());
    return PUBLIC_SITE_ORIGINS.some((runtime) => runtime.origin === origin)
      ? route.continue()
      : route.abort('blockedbyclient');
  });

  // Serve both clients from the same loopback catalog. Do not forward request
  // headers or credentials from the browser to the fixture server.
  await page.route('**/api/v1/**', async (route) => {
    const { pathname, search } = new URL(route.request().url());

    if (pathname.endsWith('/setup/status')) {
      await route.fulfill(jsonResponse({ initialized: true }));
      return;
    }

    if (pathname.endsWith('/auth/me')) {
      await route.fulfill(jsonResponse({ detail: 'synthetic unauthenticated request' }, 401));
      return;
    }

    if (pathname.startsWith('/api/v1/public-site/')) {
      if (failPublicContent) {
        await route.fulfill(jsonResponse({ detail: 'synthetic upstream unavailable' }, 503));
        return;
      }

      const fixtureUrl = new URL(FIXTURE_ORIGIN);
      fixtureUrl.pathname = pathname;
      fixtureUrl.search = search;
      const fixture = await request.get(fixtureUrl.toString(), { maxRedirects: 0, timeout: 5000 });
      await route.fulfill({
        status: fixture.status(),
        contentType: 'application/json; charset=utf-8',
        body: await fixture.text(),
      });
      return;
    }

    await route.fulfill(jsonResponse({ detail: 'synthetic endpoint not found' }, 404));
  });
}

async function assertSkipNavigation(page: Page, locale: Locale) {
  const skipLink = page.getByRole('link', { name: locale.skipLink, exact: true });
  const navigation = page.getByRole('navigation', { name: locale.navigation, exact: true });
  const main = page.getByRole('main');

  await expect(main).toHaveCount(1);
  await expect(skipLink).toHaveCount(1);
  const accessibleTree = await page.locator('body').ariaSnapshot();
  const skipPosition = accessibleTree.indexOf(`link "${locale.skipLink}"`);
  const mainPosition = accessibleTree.indexOf('main:');
  expect(skipPosition, 'the skip link should appear in the accessibility tree').toBeGreaterThanOrEqual(0);
  expect(mainPosition, 'the main landmark should appear after the skip link').toBeGreaterThan(skipPosition);

  await page.keyboard.press('Tab');
  await expect(skipLink).toBeFocused();
  await expect(skipLink).toBeInViewport();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#main-content$/);
  await expect(main).toBeFocused();

  const mobileMenu = page.locator('.public-site__mobile-menu summary');
  if (await mobileMenu.isVisible()) {
    await mobileMenu.focus();
    await page.keyboard.press('Enter');
    await expect(navigation).toBeVisible();
    await page.keyboard.press('Enter');
    await expect(navigation).toBeHidden();
  } else {
    await expect(navigation).toBeVisible();
  }
}

async function assertNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(AXE_WCAG_TAGS).analyze();
  const violations = results.violations.map(({ id, impact, help, nodes }) => ({
    id,
    impact,
    help,
    nodes: nodes.map(({ target, failureSummary }) => ({ target, failureSummary })),
  }));

  expect(violations).toEqual([]);
}

async function assertLocalizedCatalog(page: Page, request: APIRequestContext, width: number) {
  await page.setViewportSize({ width, height: 900 });
  await installSyntheticApi(page, request);

  for (const runtime of PUBLIC_SITE_ORIGINS) {
    for (const locale of LOCALES) {
      for (const { path, titles } of PAGES) {
        const url = new URL(locale.prefix + path || '/', runtime.origin);
        await test.step(`${runtime.name} ${locale.lang} ${url.pathname}`, async () => {
          await page.goto(url.toString());
          const main = page.getByRole('main');
          await expect(main.getByRole('heading', { level: 1 })).toHaveText(titles[locale.lang]);
          await expect(page.locator('html')).toHaveAttribute('lang', locale.lang);

          if (path === '/services/synthetic-service') {
            await expect(main.getByRole('link', { name: locale.doctorName, exact: true }))
              .toHaveAttribute('href', locale.prefix + '/doctors/synthetic-profile');
          }

          await expect.poll(() => page.evaluate(() => {
            const { scrollWidth, clientWidth } = document.documentElement;
            return scrollWidth - clientWidth;
          }), { message: 'the public page should fit the viewport width' }).toBeLessThanOrEqual(1);

          await assertSkipNavigation(page, locale);

          if (runtime.origin === VITE_ORIGIN && path === '') {
            const scroll = await page.evaluate(() => {
              const originalY = window.scrollY;
              window.scrollTo({ top: 0, behavior: 'instant' });
              const startY = window.scrollY;
              window.scrollTo({ top: 100, behavior: 'instant' });
              const documentMovement = window.scrollY - startY;
              const bodyOffset = document.body.scrollTop;
              window.scrollTo({ top: originalY, behavior: 'instant' });
              return { documentMovement, bodyOffset };
            });
            expect(scroll.documentMovement, 'the home page should scroll the document').toBeGreaterThan(0);
            expect(scroll.bodyOffset, 'the body should not scroll independently').toBe(0);
          }

          await assertNoAxeViolations(page);
        });
      }
    }
  }
}

async function navigateInApp(page: Page, path: string) {
  await page.evaluate((pathname) => {
    // Use the SPA's history listener so a document reload cannot mask cleanup.
    window.history.pushState(window.history.state, '', pathname);
    window.dispatchEvent(new PopStateEvent('popstate', { state: window.history.state }));
  }, path);
}

test.describe('public-site accessibility', () => {
  test('the localized Vite and Nitro catalog passes keyboard and Axe checks at 320px', async ({ page, request }) => {
    test.setTimeout(120_000);
    await assertLocalizedCatalog(page, request, 320);
  });

  test('the localized Vite and Nitro catalog passes keyboard and Axe checks at 1440px', async ({ page, request }) => {
    test.setTimeout(120_000);
    await assertLocalizedCatalog(page, request, 1440);
  });

  test('the Vite error state uses the public locale and restores the app language on exit', async ({ page, request }) => {
    await installSyntheticApi(page, request, true);
    await page.goto(VITE_ORIGIN + '/login');
    const login = page.locator('input[autocomplete="username"]');
    const body = page.locator('body');
    await expect(login).toBeVisible();
    const appOverflowX = await body.evaluate((element) => getComputedStyle(element).overflowX);

    await page.evaluate(() => {
      document.documentElement.lang = 'fr';
      document.documentElement.dataset.localeTest = 'same-document';
    });
    await navigateInApp(page, '/ru/services');

    await expect(page.getByRole('alert')).toContainText('Не удалось загрузить актуальную информацию клиники.');
    await expect(page.locator('html')).toHaveAttribute('lang', 'ru');
    await expect(body).toHaveCSS('overflow-x', 'clip');
    await assertSkipNavigation(page, LOCALES[1]);
    await assertNoAxeViolations(page);

    await navigateInApp(page, '/services');
    await expect(page.getByRole('alert')).toContainText('Klinikaning dolzarb ma’lumotlarini yuklab bo‘lmadi.');
    await expect(page.locator('html')).toHaveAttribute('lang', 'uz-Latn');
    await expect(body).toHaveCSS('overflow-x', 'clip');

    await navigateInApp(page, '/login');
    await expect(login).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('lang', 'fr');
    await expect(page.locator('html')).toHaveAttribute('data-locale-test', 'same-document');
    await expect(body).toHaveCSS('overflow-x', appOverflowX);
  });
});
