import { expect, test, type APIRequestContext, type Browser, type Locator, type Page, type Request } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const VITE_ORIGIN = 'http://localhost:5173';
const PUBLIC_SITE_ORIGINS = [
  { name: 'Vite', origin: VITE_ORIGIN },
  { name: 'Nitro', origin: 'http://127.0.0.1:5278' },
] as const;
const FIXTURE_ORIGIN = 'http://127.0.0.1:' + Number(process.env.PUBLIC_SITE_FIXTURE_PORT || 5279);
const PUBLIC_SITE_BRAND = 'Doktor KosMed Clinic';

const LOCALES = [
  {
    lang: 'uz-Latn',
    prefix: '',
    skipLink: 'Asosiy mazmunga o‘tish',
    navigation: 'Sayt navigatsiyasi',
    languageSwitch: 'RU — Rus tiliga o‘tish',
    doctorName: 'Sintetik sinov profili',
    homeTitle: `${PUBLIC_SITE_BRAND} — xizmatlar va shifokorlar`,
    errorTitle: `Sahifa vaqtincha ochilmayapti — ${PUBLIC_SITE_BRAND}`,
  },
  {
    lang: 'ru',
    prefix: '/ru',
    skipLink: 'Перейти к основному содержимому',
    navigation: 'Навигация сайта',
    languageSwitch: 'O‘Z — Перейти на узбекский',
    doctorName: 'Синтетический тестовый профиль',
    homeTitle: `${PUBLIC_SITE_BRAND} — услуги и врачи`,
    errorTitle: `Страница временно недоступна — ${PUBLIC_SITE_BRAND}`,
  },
] as const;
type Locale = (typeof LOCALES)[number];

const SERVICE_TITLES = { 'uz-Latn': 'Xizmatlar', ru: 'Услуги' } as const;

const PAGES = [
  { path: '', titles: { 'uz-Latn': 'SYNTHETIC QA CLINIC', ru: 'SYNTHETIC QA CLINIC' } },
  { path: '/services', titles: SERVICE_TITLES },
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
const CATALOG_FILTER_ASSET = '/public-site-catalog-filter.js';
const PRIVATE_SEARCH_PROBE = 'synthetic-private-qa-741e';
const CATALOG_COPY = {
  'uz-Latn': {
    service: { search: 'Xizmatlarni qidirish', group: 'Toifa', firstGroup: 'Sinov toifasi' },
    doctor: { search: 'Shifokorlarni qidirish', group: 'Mutaxassisligi', firstGroup: 'Sinov mutaxassisligi' },
    all: 'Barchasi',
    reset: 'Filtrlarni tozalash',
    resultPrefix: 'Natijalar',
    noResults: 'Hech narsa topilmadi.',
    query: '  O\'RIK  ',
  },
  ru: {
    service: { search: 'Поиск услуг', group: 'Категория', firstGroup: 'Тестовая категория' },
    doctor: { search: 'Поиск врачей', group: 'Специализация', firstGroup: 'Тестовая специализация' },
    all: 'Все',
    reset: 'Сбросить фильтры',
    resultPrefix: 'Найдено',
    noResults: 'Ничего не найдено.',
    query: '  ЕЛКА  ',
  },
} as const;

const CATALOG_DETAILS = {
  service: [
    '/services/synthetic-service',
    '/services/synthetic-service-match',
    '/services/synthetic-service-other',
    '/services/synthetic-service-no-category',
  ],
  doctor: [
    '/doctors/synthetic-profile',
    '/doctors/synthetic-profile-match',
    '/doctors/synthetic-profile-other',
    '/doctors/synthetic-profile-no-specialty',
  ],
} as const;
type CatalogKind = keyof typeof CATALOG_DETAILS;

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
  {
    beforeCatalogResponse,
    beforePublicFailure,
  }: {
    beforeCatalogResponse?: () => Promise<void>;
    beforePublicFailure?: () => Promise<void>;
  } = {},
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
      if (beforePublicFailure) {
        await beforePublicFailure();
        await route.fulfill(jsonResponse({ detail: 'synthetic upstream unavailable' }, 503));
        return;
      }
      if (pathname === '/api/v1/public-site/services' && beforeCatalogResponse) {
        await beforeCatalogResponse();
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

async function assertMobileServiceNavigation(page: Page, locale: Locale, skipLink: Locator) {
  const header = page.locator('.public-site__header');
  const brand = header.getByRole('link', { name: PUBLIC_SITE_BRAND, exact: true });
  const language = header.getByRole('link', { name: locale.languageSwitch, exact: true });
  const menu = header.locator('.public-site__mobile-menu summary');
  const navigation = header.getByRole('navigation', { name: locale.navigation, exact: true });

  for (const target of [brand, language, menu]) {
    await page.keyboard.press('Tab');
    await expect(target).toBeFocused();
  }
  await page.keyboard.press('Enter');
  await expect(navigation).toBeVisible();

  const menuLinks = await navigation.getByRole('link').all();
  expect(menuLinks.length).toBeGreaterThan(0);
  const main = page.getByRole('main');
  const breadcrumbsHome = main.locator('.public-site__breadcrumbs a').first();
  const search = main.getByRole('searchbox', { name: CATALOG_COPY[locale.lang].service.search, exact: true });
  const firstService = main.locator('a.public-site__list-title').first();
  const catalogTabStops = [
    breadcrumbsHome,
    search,
    main.getByRole('combobox', { name: CATALOG_COPY[locale.lang].service.group, exact: true }),
    main.getByRole('button', { name: CATALOG_COPY[locale.lang].reset, exact: true }),
    firstService,
  ];
  for (const target of [...menuLinks, ...catalogTabStops]) {
    await page.keyboard.press('Tab');
    await expect(target).toBeFocused();
    if (target === search || target === firstService) {
      await expect(target).toBeInViewport();
      await expect.poll(() => target.evaluate((element) =>
        Array.from(element.getClientRects()).every((rect) =>
          element.contains(document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2))),
      ), { message: 'the open menu should not cover the focused catalog item' }).toBe(true);
    }
  }
  await expect(navigation).toBeVisible();

  const reverseTabStops = [...menuLinks, ...catalogTabStops.slice(0, -1)].reverse();
  for (const target of [...reverseTabStops, menu]) {
    await page.keyboard.press('Shift+Tab');
    await expect(target).toBeFocused();
  }
  await page.keyboard.press('Enter');
  await expect(navigation).toBeHidden();
  for (const target of [language, brand, skipLink]) {
    await page.keyboard.press('Shift+Tab');
    await expect(target).toBeFocused();
  }
}

async function assertEnlargedDesktopNavigation(page: Page, locale: Locale) {
  const header = page.locator('.public-site__header');
  const navigation = header.getByRole('navigation', { name: locale.navigation, exact: true });
  const navLinks = navigation.getByRole('link');
  const headerLinks = header.getByRole('link');
  const skipLink = page.getByRole('link', { name: locale.skipLink, exact: true });
  const brand = header.getByRole('link', { name: PUBLIC_SITE_BRAND, exact: true });
  const language = header.getByRole('link', { name: locale.languageSwitch, exact: true });

  await expect(navLinks).toHaveCount(5);
  await expect(headerLinks).toHaveCount(7);
  // Simulate enlarged header text while preserving the page's viewport, spacing and breakpoint.
  const enlarged = await headerLinks.evaluateAll((elements) => {
    const links = elements as HTMLAnchorElement[];
    const sizes = links.map((link) => Number.parseFloat(getComputedStyle(link).fontSize));
    links.forEach((link, index) => {
      link.style.fontSize = `${sizes[index] * 2}px`;
    });
    return links.every((link, index) =>
      Math.abs(Number.parseFloat(getComputedStyle(link).fontSize) - sizes[index] * 2) < 0.1);
  });
  expect(enlarged, 'the computed font size of each header link should double').toBe(true);

  await expect.poll(() => page.evaluate(() => {
    const { scrollWidth, clientWidth } = document.documentElement;
    return scrollWidth - clientWidth;
  }), { message: 'the enlarged header should not cause horizontal overflow' }).toBeLessThanOrEqual(1);

  for (const target of [skipLink, brand, ...await navLinks.all(), language]) {
    await page.keyboard.press('Tab');
    await expect(target).toBeFocused();
    await expect(target).toBeInViewport({ ratio: 1 });
    // Overflow clipping can hide a label even when the document has no horizontal scrollbar.
    await expect.poll(() => target.evaluate((element) => {
      const box = element.getBoundingClientRect();
      const range = document.createRange();
      range.selectNodeContents(element);
      const { clientWidth } = document.documentElement;
      return {
        focusVisible: element.matches(':focus-visible'),
        centerExposed: element.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2)),
        textFits: Array.from(range.getClientRects()).every((rect) => rect.left >= -1 && rect.right <= clientWidth + 1),
      };
    }), { message: 'the focused navigation target and its text should remain exposed' }).toEqual({
      focusVisible: true,
      centerExposed: true,
      textFits: true,
    });
  }
}

async function assertSkipNavigation(page: Page, locale: Locale, checkMobileServiceNavigation = false) {
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
  if (checkMobileServiceNavigation) {
    await assertMobileServiceNavigation(page, locale, skipLink);
  }
  await expect(skipLink).toBeInViewport();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#main-content$/);
  await expect(main).toBeFocused();

  if (checkMobileServiceNavigation) return;

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

async function assertVisibleCatalogLinks(catalog: Locator, paths: readonly string[]) {
  const links = catalog.locator('[data-catalog-item]:visible a.public-site__list-title');
  await expect.poll(() => links.evaluateAll((elements) => elements.map((element) => element.getAttribute('href'))))
    .toEqual(paths);
}

async function assertCatalogFilter(page: Page, locale: Locale, kind: CatalogKind) {
  const catalog = page.locator('public-site-catalog-filter');
  const controls = catalog.getByRole('search');
  const copy = CATALOG_COPY[locale.lang];
  const search = controls.getByRole('searchbox', { name: copy[kind].search, exact: true });
  const group = controls.getByRole('combobox', { name: copy[kind].group, exact: true });
  const status = catalog.locator('.public-site__catalog-status');
  const reset = controls.getByRole('button', { name: copy.reset, exact: true });
  const paths = CATALOG_DETAILS[kind].map((path) => locale.prefix + path);

  await expect(search).toBeVisible();
  await expect(group.locator('option:checked')).toHaveText(copy.all);
  await assertVisibleCatalogLinks(catalog, paths);
  await expect(status).toHaveText(`${copy.resultPrefix} 4`);

  let sentQuery = false;
  let fetchedCatalog = false;
  const recordRequest = (request: Request) => {
    const url = new URL(request.url());
    if (url.href.toLowerCase().includes(PRIVATE_SEARCH_PROBE)
      || request.postData()?.toLowerCase().includes(PRIVATE_SEARCH_PROBE)) sentQuery = true;
    if (url.pathname.startsWith('/api/v1/public-site/')) fetchedCatalog = true;
  };
  const initialUrl = page.url();
  page.on('request', recordRequest);
  try {
    await group.selectOption({ label: copy[kind].firstGroup });
    await assertVisibleCatalogLinks(catalog, paths.slice(0, 2));
    await expect(status).toHaveText(`${copy.resultPrefix} 2`);

    await search.fill(copy.query);
    await assertVisibleCatalogLinks(catalog, [paths[1]]);
    await expect(status).toHaveText(`${copy.resultPrefix} 1`);

    await group.selectOption({ label: copy.all });
    await assertVisibleCatalogLinks(catalog, paths.slice(1, 3));
    if (locale.lang === 'uz-Latn') {
      await search.fill('O’RIK');
      await assertVisibleCatalogLinks(catalog, paths.slice(1, 3));
    }
    await expect(page).toHaveURL(initialUrl);

    await group.selectOption({ label: copy[kind].firstGroup });
    await search.fill(PRIVATE_SEARCH_PROBE);
    await search.press('Enter');
    await assertVisibleCatalogLinks(catalog, []);
    await expect(status).toHaveText(`${copy.resultPrefix} 0`);
    await expect(catalog.getByText(copy.noResults, { exact: true })).toBeVisible();
    await expect(catalog.locator(`a[href="${locale.prefix}/contacts"]`)).toBeVisible();
    await expect(page).toHaveURL(initialUrl);
    const storedQuery = await page.evaluate((probe) => {
      const storageHasProbe = [localStorage, sessionStorage].some((storage) =>
        Object.entries(storage).some(([key, value]) =>
          key.toLowerCase().includes(probe) || String(value).toLowerCase().includes(probe)));
      return storageHasProbe || document.cookie.toLowerCase().includes(probe);
    }, PRIVATE_SEARCH_PROBE);
    expect(storedQuery, 'the synthetic search term must remain out of browser storage').toBe(false);

    await reset.click();
    await expect(search).toBeFocused();
    await expect(search).toHaveValue('');
    await expect(group.locator('option:checked')).toHaveText(copy.all);
    await assertVisibleCatalogLinks(catalog, paths);
    await expect(status).toHaveText(`${copy.resultPrefix} 4`);
    await expect(catalog.getByText(copy.noResults, { exact: true })).toBeHidden();
    await expect(page).toHaveURL(initialUrl);
    expect(sentQuery, 'the synthetic search term must remain out of requests').toBe(false);
    expect(fetchedCatalog, 'filtering must use the catalog already on the page').toBe(false);
  } finally {
    page.off('request', recordRequest);
  }
}

async function assertCatalogFallback(page: Page, browser: Browser, request: APIRequestContext) {
  await test.step('Vite keeps the complete linked catalog when the filter asset is blocked', async () => {
    const assetUrl = VITE_ORIGIN + CATALOG_FILTER_ASSET;
    let blockedAsset = false;
    await page.route(assetUrl, (route) => {
      blockedAsset = true;
      return route.abort('blockedbyclient');
    });
    try {
      await page.goto(VITE_ORIGIN + '/ru/services');
      const catalog = page.locator('public-site-catalog-filter');
      await assertVisibleCatalogLinks(catalog, CATALOG_DETAILS.service.map((path) => '/ru' + path));
      await expect(catalog.getByRole('search', { includeHidden: true })).toBeHidden();
      await expect.poll(() => blockedAsset).toBe(true);
    } finally {
      await page.unroute(assetUrl);
    }
  });

  await test.step('Nitro serves the built enhancement asset and works with JavaScript disabled', async () => {
    const nitroOrigin = PUBLIC_SITE_ORIGINS[1].origin;
    const asset = await request.head(nitroOrigin + CATALOG_FILTER_ASSET, { maxRedirects: 0, timeout: 5000 });
    expect(asset.ok()).toBe(true);
    expect(asset.headers()['content-type']).toContain('javascript');
    expect(asset.headers()['cache-control']).toBe('no-store');

    const noScriptPage = await browser.newPage({ javaScriptEnabled: false, viewport: { width: 320, height: 900 } });
    try {
      await installSyntheticApi(noScriptPage, request);
      await noScriptPage.goto(nitroOrigin + '/doctors');
      const catalog = noScriptPage.locator('public-site-catalog-filter');
      await assertVisibleCatalogLinks(catalog, CATALOG_DETAILS.doctor);
      await expect(catalog.getByRole('search', { includeHidden: true })).toBeHidden();
    } finally {
      await noScriptPage.close();
    }
  });
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
          await expect(page.locator('.public-site__language')).toHaveAccessibleName(locale.languageSwitch);
          const pageName = path === '/doctors/synthetic-profile' ? locale.doctorName : titles[locale.lang];
          await expect(page).toHaveTitle(path === '' ? locale.homeTitle : `${pageName} — ${PUBLIC_SITE_BRAND}`);

          if (path === '/services/synthetic-service') {
            await expect(main.getByRole('link', { name: locale.doctorName, exact: true }))
              .toHaveAttribute('href', locale.prefix + '/doctors/synthetic-profile');
          }

          const isCatalog = path === '/services' || path === '/prices' || path === '/doctors';
          if (isCatalog) {
            await expect(main.getByRole('search')).toBeVisible();
          }

          await expect.poll(() => page.evaluate(() => {
            const { scrollWidth, clientWidth } = document.documentElement;
            return scrollWidth - clientWidth;
          }), { message: 'the public page should fit the viewport width' }).toBeLessThanOrEqual(1);

          await assertSkipNavigation(page, locale, width === 320 && path === '/services');

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

          if (width === 320 && isCatalog) {
            await assertCatalogFilter(page, locale, path === '/doctors' ? 'doctor' : 'service');
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

async function solidContrastRatio(target: Locator, kind: 'text' | 'outline') {
  return target.evaluate((element, kind) => {
    const canvas = document.createElement('canvas');
    canvas.width = 1;
    canvas.height = 1;
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Unable to sample the control colors');

    const style = getComputedStyle(element);
    if (kind === 'outline' && (style.outlineStyle === 'none' || parseFloat(style.outlineWidth) === 0)) return 0;
    const backgrounds: string[] = [];
    for (let node = kind === 'text' ? element : element.parentElement; node; node = node.parentElement) {
      backgrounds.push(getComputedStyle(node).backgroundColor);
      if (node.classList.contains('public-site')) break;
    }
    for (const color of backgrounds.reverse()) {
      context.fillStyle = color;
      context.fillRect(0, 0, 1, 1);
    }
    const background = context.getImageData(0, 0, 1, 1).data;
    if (background[3] !== 255) throw new Error('Expected a solid public-site background');

    context.fillStyle = kind === 'text' ? style.color : style.outlineColor;
    context.fillRect(0, 0, 1, 1);
    const foreground = context.getImageData(0, 0, 1, 1).data;
    const luminance = (pixel: Uint8ClampedArray) => {
      const [r, g, b] = Array.from(pixel.slice(0, 3), (value) => {
        const channel = value / 255;
        return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const foregroundLight = luminance(foreground);
    const backgroundLight = luminance(background);
    return (Math.max(foregroundLight, backgroundLight) + 0.05) /
      (Math.min(foregroundLight, backgroundLight) + 0.05);
  }, kind);
}

test.describe('public-site accessibility', () => {
  test('Vite dark public navigation preserves hover and keyboard focus contrast', async ({ page, request }) => {
    test.setTimeout(60_000);
    await page.emulateMedia({ colorScheme: 'dark', forcedColors: 'none' });
    await page.addInitScript((origin) => {
      if (location.origin === origin) localStorage.setItem('colorScheme', 'dark');
    }, VITE_ORIGIN);
    await installSyntheticApi(page, request);

    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 });
      for (const locale of LOCALES) {
        await test.step(`${locale.lang} at ${width}px`, async () => {
          await page.goto(VITE_ORIGIN + locale.prefix + '/services');
          const root = page.locator('html');
          await expect(root).toHaveAttribute('data-theme', 'dark');
          await expect(page.getByRole('heading', { level: 1, name: SERVICE_TITLES[locale.lang] })).toBeVisible();

          const skip = page.getByRole('link', { name: locale.skipLink, exact: true });
          const header = page.locator('.public-site__header');
          await page.keyboard.press('Tab');
          await expect(skip).toBeFocused();
          await expect.poll(() => solidContrastRatio(skip, 'outline')).toBeGreaterThanOrEqual(3);
          await page.keyboard.press('Tab');
          await expect(header.getByRole('link', { name: PUBLIC_SITE_BRAND, exact: true })).toBeFocused();

          if (width === 390) {
            await page.keyboard.press('Tab');
            await expect(header.getByRole('link', { name: locale.languageSwitch, exact: true })).toBeFocused();
            await page.keyboard.press('Tab');
            await expect(header.locator('.public-site__mobile-menu summary')).toBeFocused();
            await page.keyboard.press('Enter');
          }

          const navigation = header.getByRole('navigation', { name: locale.navigation, exact: true });
          const link = navigation.getByRole('link').first();
          await page.keyboard.press('Tab');
          await expect(link).toBeFocused();
          await expect.poll(() => solidContrastRatio(link, 'outline')).toBeGreaterThanOrEqual(3);
          await link.hover();
          await expect.poll(() => solidContrastRatio(link, 'text')).toBeGreaterThanOrEqual(4.5);
          await expect(link).toHaveCSS('text-decoration-line', 'underline');
        });
      }
    }

    await navigateInApp(page, '/login');
    await expect(page.locator('input[autocomplete="username"]')).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await expect(page.locator('html.public-site-document')).toHaveCount(0);
  });

  test('the localized Vite and Nitro catalog passes keyboard and Axe checks at 320px', async ({ page, browser, request }) => {
    test.setTimeout(120_000);
    await assertLocalizedCatalog(page, request, 320);
    await assertCatalogFallback(page, browser, request);
  });

  test('the localized Vite and Nitro catalog passes keyboard and Axe checks at 1440px', async ({ page, request }) => {
    test.setTimeout(120_000);
    await assertLocalizedCatalog(page, request, 1440);
  });

  for (const locale of LOCALES) {
    test(`the desktop header fits doubled ${locale.lang} text at 960px in Vite and Nitro`, async ({ page, request }) => {
      await page.setViewportSize({ width: 960, height: 900 });
      await installSyntheticApi(page, request);

      for (const runtime of PUBLIC_SITE_ORIGINS) {
        await test.step(runtime.name, async () => {
          await page.goto(runtime.origin + locale.prefix + '/services');
          const main = page.getByRole('main');
          await expect(main.getByRole('heading', { name: SERVICE_TITLES[locale.lang], level: 1, exact: true }))
            .toBeVisible();
          await expect(page.locator('html')).toHaveAttribute('lang', locale.lang);
          await assertEnlargedDesktopNavigation(page, locale);
        });
      }
    });
  }

  for (const locale of LOCALES) {
    test(`the Vite skip link keeps focus when the ${locale.lang} catalog loads`, async ({ page, request }) => {
      let releaseCatalog!: () => void;
      const holdCatalog = new Promise<void>((resolve) => { releaseCatalog = resolve; });
      const path = VITE_ORIGIN + locale.prefix + '/services';
      const main = page.getByRole('main');
      const skipLink = page.getByRole('link', { name: locale.skipLink, exact: true });

      try {
        await installSyntheticApi(page, request, { beforeCatalogResponse: () => holdCatalog });
        await Promise.all([
          page.waitForRequest((candidate) => new URL(candidate.url()).pathname === '/api/v1/public-site/services'),
          page.goto(path, { waitUntil: 'domcontentloaded' }),
        ]);
        await expect(main).toHaveAttribute('aria-busy', 'true');
        await page.keyboard.press('Tab');
        await expect(skipLink).toBeFocused();
        await page.keyboard.press('Enter');
        await expect(page).toHaveURL(path + '#main-content');
        await expect(main).toBeFocused();
        const loadingMain = await main.elementHandle();

        releaseCatalog();
        await expect(main.getByRole('heading', { level: 1, name: SERVICE_TITLES[locale.lang], exact: true })).toBeVisible();
        await expect(main).not.toHaveAttribute('aria-busy', 'true');
        await expect(page).toHaveURL(path + '#main-content');
        await expect(main).toBeFocused();
        expect(await loadingMain.evaluate((element) => element === document.activeElement)).toBe(true);

        await page.keyboard.press('Tab');
        await expect(main.locator('.public-site__breadcrumbs a').first()).toBeFocused();
      } finally {
        releaseCatalog();
      }
    });
  }

  test('the Vite error state uses the public locale and restores the app language on exit', async ({ page, request }) => {
    let allowPublicFailure = Promise.resolve();
    await installSyntheticApi(page, request, { beforePublicFailure: () => allowPublicFailure });
    await page.goto(VITE_ORIGIN + '/login');
    const login = page.locator('input[autocomplete="username"]');
    const body = page.locator('body');
    await expect(login).toBeVisible();
    await expect(page).toHaveTitle('Clinic OS');
    const appOverflowX = await body.evaluate((element) => getComputedStyle(element).overflowX);

    await page.evaluate(() => {
      document.documentElement.lang = 'fr';
      document.documentElement.dataset.localeTest = 'same-document';
    });
    for (const { locale, pendingName, errorMessage } of [
      { locale: LOCALES[1], pendingName: 'Услуги', errorMessage: 'Не удалось загрузить актуальную информацию клиники.' },
      { locale: LOCALES[0], pendingName: 'Xizmatlar', errorMessage: 'Klinikaning dolzarb ma’lumotlarini yuklab bo‘lmadi.' },
    ]) {
      let releasePublicFailure!: () => void;
      allowPublicFailure = new Promise<void>((resolve) => { releasePublicFailure = resolve; });
      try {
        await navigateInApp(page, locale.prefix + '/services');
        await expect(page.getByRole('main')).toHaveAttribute('aria-busy', 'true');
        await expect(page).toHaveTitle(`${pendingName} — ${PUBLIC_SITE_BRAND}`);
      } finally {
        releasePublicFailure();
      }

      await expect(page.getByRole('alert')).toContainText(errorMessage);
      await expect(page.locator('html')).toHaveAttribute('lang', locale.lang);
      await expect(page).toHaveTitle(locale.errorTitle);
      await expect(body).toHaveCSS('overflow-x', 'clip');
      if (locale.lang === 'ru') {
        await assertSkipNavigation(page, locale);
        await assertNoAxeViolations(page);
      }
    }

    await navigateInApp(page, '/login');
    await expect(login).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('lang', 'fr');
    await expect(page.locator('html')).toHaveAttribute('data-locale-test', 'same-document');
    await expect(page).toHaveTitle('Clinic OS');
    await expect(body).toHaveCSS('overflow-x', appOverflowX);
  });
});
