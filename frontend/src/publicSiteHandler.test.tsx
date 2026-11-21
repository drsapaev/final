import { describe, expect, it, vi } from 'vitest';
import { handlePublicSiteRequest } from './publicSiteHandler';
import { getPublicSiteBreadcrumbs } from './publicSitePage';
import nitroConfig from '../nitro.config';
import { PUBLIC_SITE_ROUTE_DEFINITIONS } from './routing/publicSiteRouteEntries';
import { resolvePublicSiteRoute } from './routing/publicSiteRouteEntries';

const assets = {
  pageStyles: ['/assets/public-site.css'],
  appEntry: '/assets/clinic-app.js',
  appStyles: ['/assets/clinic-app.css'],
};

describe('Nitro public-site route registration', () => {
  const handlers = nitroConfig.handlers ?? [];

  it('routes every public page directly so its HTTP status reaches the client', () => {
    expect(nitroConfig.serverEntry).toBe(false);
    for (const { path } of PUBLIC_SITE_ROUTE_DEFINITIONS) {
      expect(handlers).toContainEqual(expect.objectContaining({
        route: path,
        handler: './src/publicSiteHandler.tsx',
        format: 'web',
      }));
    }
  });

  it('keeps API and WebSocket paths closed on the Vercel origin', () => {
    const routes = handlers.map(({ route }) => route);
    expect(routes).toEqual(expect.arrayContaining(['/api', '/api/**', '/ws', '/ws/**']));
  });
});

function createFetch(handler: (url: URL, init?: RequestInit) => Response | Promise<Response>) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = input instanceof URL ? input : new URL(String(input));
    return handler(url, init);
  });
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('public-site SSR request handler', () => {
  it('renders a localized service detail and request-time SEO metadata', async () => {
    const fetchImpl = createFetch((url) => {
      if (url.pathname === '/api/v1/public-site/clinic') return jsonResponse({ logo_url: null });
      expect(url.origin).toBe('https://api.kosmed.test');
      expect(url.pathname).toBe('/api/v1/public-site/services/laser-care');
      expect(url.searchParams.get('locale')).toBe('ru');
      return jsonResponse({
        slug: 'laser-care',
        name: 'Лазерная терапия',
        description: 'Описание опубликованной услуги клиники.',
        price: '125000.00',
        currency: 'UZS',
        category: 'Дерматология',
      });
    });

    const response = await handlePublicSiteRequest(
      new Request('https://preview.kosmed.test/ru/services/laser-care'),
      {
        apiOrigin: 'https://api.kosmed.test',
        siteOrigin: 'https://www.kosmed.test',
        deploymentEnvironment: 'preview',
      },
      assets,
      fetchImpl,
    );
    const html = await response.text();

    expect(response.status).toBe(200);
    expect(response.headers.get('Cache-Control')).toBe('no-store');
    expect(response.headers.get('X-Robots-Tag')).toBe('noindex, nofollow');
    expect(response.headers.get('Content-Language')).toBe('ru');
    expect(html).toContain('<html lang="ru">');
    expect(html).toContain('<title>Лазерная терапия — Doktor KosMed Clinic</title>');
    expect(html).toContain('Описание опубликованной услуги клиники.');
    expect(html).not.toContain('Цена по запросу');
    expect(html).not.toContain('125000');
    expect(html).not.toContain('UZS');
    expect(html).toContain('href="https://www.kosmed.test/ru/services/laser-care"');
    expect(html).toContain('hreflang="uz-Latn" href="https://www.kosmed.test/services/laser-care"');
    expect(html).toContain('hreflang="x-default"');
    expect(html).toContain('/assets/public-site.css');
    expect(html).not.toContain('/assets/clinic-app.js');
    expect(html).not.toContain('Врачи, оказывающие услугу');
    expect(html).toContain('href="/ru/contacts">Связаться с клиникой</a>');
  });

  it.each([
    { locale: 'ru', prefix: '/ru', heading: 'Врачи, оказывающие услугу' },
    { locale: 'uz-Latn', prefix: '', heading: 'Ushbu xizmat bo‘yicha shifokorlar' },
  ])('renders links from a service to its published doctor profiles in $locale', async ({ locale, prefix, heading }) => {
    const doctors = [
      { slug: 'synthetic-doctor-a', name: 'SYNTHETIC Doctor A' },
      { slug: 'synthetic-doctor-b', name: 'SYNTHETIC Doctor B' },
    ];
    const fetchImpl = createFetch((url) => {
      if (url.pathname === '/api/v1/public-site/clinic') return jsonResponse({ logo_url: null });
      expect(url.pathname).toBe('/api/v1/public-site/services/synthetic-service');
      expect(url.searchParams.get('locale')).toBe(locale);
      return jsonResponse({
        slug: 'synthetic-service',
        name: 'SYNTHETIC Service',
        description: 'SYNTHETIC public service',
        price: '125000.00',
        currency: 'UZS',
        related_doctors: doctors,
      });
    });

    const response = await handlePublicSiteRequest(
      new Request(`https://preview.kosmed.test${prefix}/services/synthetic-service`),
      {
        apiOrigin: 'https://api.kosmed.test',
        siteOrigin: 'https://www.kosmed.test',
        deploymentEnvironment: 'preview',
      },
      assets,
      fetchImpl,
    );

    expect(response.status).toBe(200);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    const document = new DOMParser().parseFromString(await response.text(), 'text/html');
    const article = document.querySelector('main article');
    expect(article?.querySelector('section > h2')?.textContent).toBe(heading);
    expect(Array.from(article?.querySelectorAll('section > ul > li > a') ?? [], (link) => [
      link.getAttribute('href'), link.textContent,
    ])).toEqual(doctors.map(({ slug, name }) => [`${prefix}/doctors/${slug}`, name]));
    expect(article?.querySelector(`a[href="${prefix}/contacts"]`)).not.toBeNull();
    expect(article?.textContent).not.toContain('125000');
    expect(article?.textContent).not.toContain('UZS');
  });

  it.each(PUBLIC_SITE_ROUTE_DEFINITIONS)('renders the published clinic logo on $path and falls back when absent', async ({ path: routePath, locale }) => {
    const path = routePath.replace(':slug', 'synthetic');
    const home = locale === 'ru' ? '/ru' : '/';
    const apiOrigin = 'https://api.kosmed.test';
    const logoPath = `/api/v1/public-site/media/${'b'.repeat(64)}`;

    async function renderBrand(logoUrl: string | null) {
      const fetchImpl = createFetch((url, init) => {
        if (url.pathname === '/api/v1/public-site/clinic') {
          expect(init?.cache).toBe('no-store');
          return jsonResponse({ name: 'SYNTHETIC Clinic', logo_url: logoUrl });
        }
        switch (url.pathname) {
          case '/api/v1/public-site/doctors/synthetic':
            return jsonResponse({ slug: 'synthetic', name: 'SYNTHETIC Doctor', bio: 'SYNTHETIC bio' });
          case '/api/v1/public-site/services/synthetic':
            return jsonResponse({ slug: 'synthetic', name: 'SYNTHETIC Service', description: 'SYNTHETIC description' });
          case '/api/v1/public-site/doctors':
          case '/api/v1/public-site/services':
            return jsonResponse([]);
          default:
            return jsonResponse({}, 404);
        }
      });
      const response = await handlePublicSiteRequest(
        new Request(`https://preview.kosmed.test${path}`),
        { apiOrigin, siteOrigin: 'https://www.kosmed.test', deploymentEnvironment: 'preview' },
        assets,
        fetchImpl,
      );
      expect(response.status).toBe(200);
      const clinicReads = fetchImpl.mock.calls.filter(([url]) =>
        String(url) === apiOrigin + '/api/v1/public-site/clinic');
      expect(clinicReads).toHaveLength(1);
      const document = new DOMParser().parseFromString(await response.text(), 'text/html');
      return document.querySelector('header a.public-site__brand');
    }

    const brand = await renderBrand(logoPath);
    expect(brand?.getAttribute('href')).toBe(home);
    expect(brand?.textContent).toBe('Doktor KosMed Clinic');
    expect(brand?.querySelector('img')?.getAttribute('src')).toBe(apiOrigin + logoPath);
    expect(brand?.querySelector('img')?.getAttribute('alt')).toBe('');

    const fallback = await renderBrand(null);
    expect(fallback?.getAttribute('href')).toBe(home);
    expect(fallback?.querySelector('img')).toBeNull();
    expect(fallback?.querySelector('span[aria-hidden="true"]')?.textContent).toBe('K');
  });

  it('aborts a slow optional clinic request and keeps the localized price page', async () => {
    let logoSignal: AbortSignal | null | undefined;
    const fetchImpl = createFetch((url, init) => {
      if (url.pathname === '/api/v1/public-site/clinic') {
        const signal = init?.signal;
        if (!signal) throw new Error('Expected a bounded clinic request');
        logoSignal = signal;
        return new Promise<Response>((_resolve, reject) => {
          signal.addEventListener('abort', () => reject(signal.reason), { once: true });
        });
      }
      expect(url.pathname).toBe('/api/v1/public-site/services');
      return jsonResponse([]);
    });

    const response = await handlePublicSiteRequest(
      new Request('https://preview.kosmed.test/ru/prices'),
      { apiOrigin: 'https://api.kosmed.test', deploymentEnvironment: 'preview' },
      assets,
      fetchImpl,
    );
    const document = new DOMParser().parseFromString(await response.text(), 'text/html');

    expect(logoSignal?.aborted).toBe(true);
    expect(response.status).toBe(200);
    expect(document.querySelector('h1')?.textContent).toBe('Цены');
    expect(document.querySelector('header .public-site__brand-mark')?.textContent).toBe('K');
  }, 5_000);

  it('shows doctor specialty, full name, and persisted experience on the public profile', async () => {
    const fetchImpl = createFetch((url) => {
      if (url.pathname === '/api/v1/public-site/clinic') return jsonResponse({ logo_url: null });
      expect(url.pathname).toBe('/api/v1/public-site/doctors/dermatolog');
      return jsonResponse({
        slug: 'dermatolog',
        name: 'SYNTHETIC Doctor Name',
        specialty: 'Дерматология',
        experience_years: 18,
        professional_category: 'Высшая квалификационная категория',
        bio: 'SYNTHETIC verified doctor biography.',
        portrait_url: null,
      });
    });

    const response = await handlePublicSiteRequest(
      new Request('https://preview.kosmed.test/ru/doctors/dermatolog'),
      {
        apiOrigin: 'https://api.kosmed.test',
        siteOrigin: 'https://www.kosmed.test',
        deploymentEnvironment: 'preview',
      },
      assets,
      fetchImpl,
    );
    const html = await response.text();

    expect(response.status).toBe(200);
    expect(html).toContain('Дерматология — SYNTHETIC Doctor Name');
    expect(html).toContain('Стаж: 18 лет');
    expect(html).toContain('Высшая квалификационная категория');
    expect(html).toContain('SYNTHETIC verified doctor biography.');
  });

  it.each([
    { locale: 'uz-Latn', prefix: '' },
    { locale: 'ru', prefix: '/ru' },
  ])('renders published doctor portraits in the $locale catalog and profile', async ({ locale, prefix }) => {
    const portraitPath = `/api/v1/public-site/media/${'a'.repeat(64)}`;
    const apiOrigin = 'https://api.kosmed.test';
    const doctor = {
      slug: 'synthetic-with-portrait',
      name: 'SYNTHETIC Doctor With Portrait',
      bio: 'SYNTHETIC public biography.',
      portrait_url: portraitPath,
    };
    const textOnlyDoctor = {
      ...doctor,
      slug: 'synthetic-without-portrait',
      name: 'SYNTHETIC Doctor Without Portrait',
      portrait_url: null,
    };
    const fetchImpl = createFetch((url) => {
      if (url.pathname === '/api/v1/public-site/clinic') return jsonResponse({ logo_url: null });
      expect(url.searchParams.get('locale')).toBe(locale);
      if (url.pathname === '/api/v1/public-site/doctors') {
        return jsonResponse([doctor, textOnlyDoctor]);
      }
      const profile = [doctor, textOnlyDoctor].find(({ slug }) =>
        url.pathname === `/api/v1/public-site/doctors/${slug}`);
      return profile ? jsonResponse(profile) : jsonResponse({}, 404);
    });

    async function renderDoctors(path: string) {
      const response = await handlePublicSiteRequest(
        new Request(`https://preview.kosmed.test${prefix}${path}`),
        { apiOrigin, siteOrigin: 'https://www.kosmed.test', deploymentEnvironment: 'preview' },
        assets,
        fetchImpl,
      );
      expect(response.status).toBe(200);
      return new DOMParser().parseFromString(await response.text(), 'text/html');
    }

    const catalog = await renderDoctors('/doctors');
    expect(catalog.querySelectorAll('main img')).toHaveLength(1);
    const cardPortrait = catalog.querySelector('main img');
    expect(cardPortrait?.getAttribute('src')).toBe(apiOrigin + portraitPath);
    expect(cardPortrait?.getAttribute('alt')).toBe('');
    expect(cardPortrait?.getAttribute('loading')).toBe('lazy');
    expect(cardPortrait?.closest('li')?.textContent).toContain(doctor.name);
    expect(catalog.querySelector('main')?.textContent).toContain(textOnlyDoctor.name);

    const profile = await renderDoctors(`/doctors/${doctor.slug}`);
    const profilePortrait = profile.querySelector('main img');
    expect(profilePortrait?.getAttribute('src')).toBe(apiOrigin + portraitPath);
    expect(profilePortrait?.getAttribute('alt')).toBe('');
    expect(profilePortrait?.getAttribute('loading')).not.toBe('lazy');
    expect(profile.querySelector('main h1')?.textContent).toBe(doctor.name);

    const textOnlyProfile = await renderDoctors(`/doctors/${textOnlyDoctor.slug}`);
    expect(textOnlyProfile.querySelector('main img')).toBeNull();
    expect(textOnlyProfile.querySelector('main h1')?.textContent).toBe(textOnlyDoctor.name);
  });

  it('keeps live service prices on the prices page', async () => {
    const fetchImpl = createFetch((url) => {
      if (url.pathname === '/api/v1/public-site/clinic') return jsonResponse({ logo_url: null });
      expect(url.pathname).toBe('/api/v1/public-site/services');
      expect(url.searchParams.get('locale')).toBe('ru');
      return jsonResponse([
        {
          slug: 'consultation',
          name: 'SYNTHETIC консультация',
          description: 'SYNTHETIC description',
          price: '125000.00',
          currency: 'UZS',
          category: null,
        },
      ]);
    });

    const response = await handlePublicSiteRequest(
      new Request('https://preview.kosmed.test/ru/prices'),
      {
        apiOrigin: 'https://api.kosmed.test',
        siteOrigin: 'https://www.kosmed.test',
        deploymentEnvironment: 'preview',
      },
      assets,
      fetchImpl,
    );
    const html = await response.text();

    expect(response.status).toBe(200);
    expect(html).toContain('SYNTHETIC консультация');
    expect(html).toContain('UZS');
    expect(html).toContain('125');
  });

  it('renders the admin-managed clinic opening and closing times in localized contacts', async () => {
    const fetchImpl = createFetch((url) => {
      expect(url.pathname).toBe('/api/v1/public-site/clinic');
      return jsonResponse({
        name: 'Doktor KosMed Clinic',
        address: 'SYNTHETIC address',
        phone: null,
        email: null,
        logo_url: null,
        working_hours_start: '09:00:00',
        working_hours_end: '17:00:00',
      });
    });

    const response = await handlePublicSiteRequest(
      new Request('https://preview.kosmed.test/ru/contacts'),
      {
        apiOrigin: 'https://api.kosmed.test',
        siteOrigin: 'https://www.kosmed.test',
        deploymentEnvironment: 'preview',
      },
      assets,
      fetchImpl,
    );
    const html = await response.text();

    expect(response.status).toBe(200);
    expect(html).toContain('Понедельник–суббота');
    expect(html).toContain('09:00');
    expect(html).toContain('17:00');
    expect(html).toContain('Воскресенье — выходной');
  });

  it.each([
    {
      path: '/ru/services/laser-care',
      locale: 'ru',
      kind: 'service',
      slug: 'laser-care',
      homeLabel: 'Главная',
      homePath: '/ru',
      sectionLabel: 'Услуги',
      sectionPath: '/ru/services',
      pageName: 'Лазерная терапия',
    },
    {
      path: '/services/laser-care',
      locale: 'uz-Latn',
      kind: 'service',
      slug: 'laser-care',
      homeLabel: 'Bosh sahifa',
      homePath: '/',
      sectionLabel: 'Xizmatlar',
      sectionPath: '/services',
      pageName: 'Lazer terapiyasi',
    },
    {
      path: '/ru/doctors/dermatolog',
      locale: 'ru',
      kind: 'doctor',
      slug: 'dermatolog',
      homeLabel: 'Главная',
      homePath: '/ru',
      sectionLabel: 'Врачи',
      sectionPath: '/ru/doctors',
      pageName: 'Врач дерматолог',
    },
    {
      path: '/doctors/dermatolog',
      locale: 'uz-Latn',
      kind: 'doctor',
      slug: 'dermatolog',
      homeLabel: 'Bosh sahifa',
      homePath: '/',
      sectionLabel: 'Shifokorlar',
      sectionPath: '/doctors',
      pageName: 'Dermatolog shifokor',
    },
  ])('renders matching localized breadcrumbs and JSON-LD for $path', async (scenario) => {
    const { kind, locale, path, slug, pageName } = scenario;
    const apiPath = kind === 'service'
      ? `/api/v1/public-site/services/${slug}`
      : `/api/v1/public-site/doctors/${slug}`;
    const apiRecord = kind === 'service'
      ? { slug, name: pageName, description: 'Published service description.', price: null, currency: null }
      : { slug, name: pageName, bio: 'Published doctor biography.' };
    const fetchImpl = createFetch((url) => {
      if (url.pathname === '/api/v1/public-site/clinic') return jsonResponse({ logo_url: null });
      expect(url.pathname).toBe(apiPath);
      expect(url.searchParams.get('locale')).toBe(locale);
      return jsonResponse(apiRecord);
    });
    const response = await handlePublicSiteRequest(
      new Request(`https://preview.kosmed.test${path}`),
      {
        apiOrigin: 'https://api.kosmed.test',
        siteOrigin: 'https://www.kosmed.test',
        deploymentEnvironment: 'preview',
      },
      assets,
      fetchImpl,
    );
    const html = await response.text();
    const navigation = html.match(/<nav class="public-site__breadcrumbs"[\s\S]*?<\/nav>/);
    const jsonLdTag = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);

    expect(response.status).toBe(200);
    expect(navigation).not.toBeNull();
    expect(navigation?.[0]).toContain(`<a href="${scenario.homePath}">${scenario.homeLabel}</a>`);
    expect(navigation?.[0]).toContain(`<a href="${scenario.sectionPath}">${scenario.sectionLabel}</a>`);
    expect(navigation?.[0]).toContain(`<span aria-current="page">${pageName}</span>`);
    expect(jsonLdTag).not.toBeNull();
    if (!jsonLdTag) throw new Error('BreadcrumbList JSON-LD was not rendered.');

    const jsonLd = JSON.parse(jsonLdTag[1]) as {
      '@context': string;
      '@type': string;
      itemListElement: Array<{
        '@type': string;
        position: number;
        name: string;
        item: string;
      }>;
    };
    expect(jsonLd).toEqual({
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: scenario.homeLabel,
          item: new URL(scenario.homePath, 'https://www.kosmed.test').href,
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: scenario.sectionLabel,
          item: new URL(scenario.sectionPath, 'https://www.kosmed.test').href,
        },
        {
          '@type': 'ListItem',
          position: 3,
          name: pageName,
          item: new URL(path, 'https://www.kosmed.test').href,
        },
      ],
    });
  });

  it('omits breadcrumbs from home, hidden details, and their JSON-LD', async () => {
    const homeRoute = resolvePublicSiteRoute('/');
    const missingRoute = resolvePublicSiteRoute('/ru/services/hidden-service');
    expect(homeRoute).not.toBeNull();
    expect(missingRoute).not.toBeNull();
    if (!homeRoute || !missingRoute) throw new Error('Expected public routes to resolve.');
    expect(getPublicSiteBreadcrumbs(homeRoute, {})).toEqual([]);
    expect(getPublicSiteBreadcrumbs(missingRoute, {})).toEqual([]);

    const fetchImpl = createFetch(() => jsonResponse({ detail: { code: 'public_content_not_found' } }, 404));
    const response = await handlePublicSiteRequest(
      new Request('https://preview.kosmed.test/ru/services/hidden-service'),
      { apiOrigin: 'https://api.kosmed.test', deploymentEnvironment: 'preview' },
      assets,
      fetchImpl,
    );
    const html = await response.text();

    expect(response.status).toBe(404);
    expect(html).not.toContain('public-site__breadcrumbs');
    expect(html).not.toContain('BreadcrumbList');
  });

  it('escapes untrusted catalog text inside the JSON-LD script element', async () => {
    const unsafeName = '</script><script>alert(1)</script> &';
    const fetchImpl = createFetch(() => jsonResponse({
      slug: 'unsafe-name',
      name: unsafeName,
      description: 'Published service description.',
      price: null,
      currency: null,
    }));
    const response = await handlePublicSiteRequest(
      new Request('https://preview.kosmed.test/ru/services/unsafe-name'),
      { apiOrigin: 'https://api.kosmed.test', deploymentEnvironment: 'preview' },
      assets,
      fetchImpl,
    );
    const html = await response.text();
    const jsonLdTag = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);

    expect(response.status).toBe(200);
    expect(html).not.toContain('</script><script>alert(1)</script>');
    expect(html).toContain('&lt;/script&gt;&lt;script&gt;alert(1)&lt;/script&gt; &amp;');
    expect(html).toContain('\\u003c/script\\u003e\\u003cscript\\u003ealert(1)\\u003c/script\\u003e \\u0026');
    expect(jsonLdTag).not.toBeNull();
    if (!jsonLdTag) throw new Error('BreadcrumbList JSON-LD was not rendered.');
    const jsonLd = JSON.parse(jsonLdTag[1]) as {
      itemListElement: Array<{ name: string }>;
    };
    expect(jsonLd.itemListElement[jsonLd.itemListElement.length - 1]?.name).toBe(unsafeName);
  });

  it('returns a generic 503 and never renders prior page data when the API fails', async () => {
    const fetchImpl = createFetch(() => new Response('private upstream error', { status: 500 }));
    const response = await handlePublicSiteRequest(
      new Request('https://preview.kosmed.test/ru/services'),
      { apiOrigin: 'https://api.kosmed.test', deploymentEnvironment: 'preview' },
      assets,
      fetchImpl,
    );
    const html = await response.text();

    expect(response.status).toBe(503);
    expect(response.headers.get('Cache-Control')).toBe('no-store');
    expect(response.headers.get('X-Robots-Tag')).toBe('noindex, nofollow');
    expect(html).toContain('Не удалось загрузить актуальную информацию клиники.');
    expect(html).not.toContain('private upstream error');
    expect(html).not.toContain('old published card');
  });

  it('returns a public 404 for a hidden or unknown detail slug', async () => {
    const fetchImpl = createFetch(() => jsonResponse({ detail: { code: 'public_content_not_found' } }, 404));
    const response = await handlePublicSiteRequest(
      new Request('https://preview.kosmed.test/ru/services/hidden-service'),
      { apiOrigin: 'https://api.kosmed.test', deploymentEnvironment: 'preview' },
      assets,
      fetchImpl,
    );
    const html = await response.text();

    expect(response.status).toBe(404);
    expect(response.headers.get('Cache-Control')).toBe('no-store');
    expect(response.headers.get('X-Robots-Tag')).toBe('noindex, nofollow');
    expect(html).toContain('Услуга не найдена или больше не опубликована.');
    expect(html).not.toContain('public_content_not_found');
  });

  it('generates a no-store sitemap from published services and doctors in both locales', async () => {
    const fetchImpl = createFetch((url) => {
      const locale = url.searchParams.get('locale');
      if (url.pathname.endsWith('/services')) {
        return jsonResponse([{
          slug: 'skin-care',
          name: locale === 'ru' ? 'Уход за кожей' : 'Teri parvarishi',
          description: 'Published text',
          price: null,
          currency: null,
        }]);
      }
      return jsonResponse([{
        slug: 'dermatolog',
        name: locale === 'ru' ? 'Врач дерматолог' : 'Dermatolog shifokor',
        bio: 'Published bio',
      }]);
    });
    const response = await handlePublicSiteRequest(
      new Request('https://preview.kosmed.test/sitemap.xml'),
      { apiOrigin: 'https://api.kosmed.test', deploymentEnvironment: 'preview' },
      assets,
      fetchImpl,
    );
    const xml = await response.text();

    expect(response.status).toBe(200);
    expect(response.headers.get('Content-Type')).toContain('application/xml');
    expect(response.headers.get('Cache-Control')).toBe('no-store');
    expect(response.headers.get('X-Robots-Tag')).toBe('noindex, nofollow');
    expect(xml).toContain('https://preview.kosmed.test/');
    expect(xml).toContain('https://preview.kosmed.test/ru/services/skin-care');
    expect(xml).toContain('https://preview.kosmed.test/doctors/dermatolog');
    expect(xml).toContain('hreflang="x-default"');
    expect(xml).not.toContain('queue');
    expect(fetchImpl).toHaveBeenCalledTimes(4);
  });

  it('keeps Clinic OS routes on the existing SPA shell without public API calls', async () => {
    const fetchImpl = createFetch(() => {
      throw new Error('must not fetch for app routes');
    });
    const appPaths = [
      '/login',
      '/registrar',
      '/registrar/welcome',
      '/registrar/queue',
      '/queue/join',
      '/q/SYNTHETIC-CODE',
      '/confirm-visit',
      '/clinical/appointments',
      '/cashier',
      '/admin',
    ];

    for (const pathname of appPaths) {
      const response = await handlePublicSiteRequest(
        new Request(`https://preview.kosmed.test${pathname}`),
        { apiOrigin: 'https://api.kosmed.test', deploymentEnvironment: 'preview' },
        assets,
        fetchImpl,
      );
      const html = await response.text();

      expect(response.status, pathname).toBe(200);
      expect(html, pathname).toContain('Clinic OS');
      expect(html, pathname).toContain('id="root"');
      expect(html, pathname).toContain('/assets/clinic-app.js');
      expect(html, pathname).not.toContain('id="public-site-root"');
    }

    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it('does not serve the Clinic OS shell for the bare API base path', async () => {
    const fetchImpl = createFetch(() => {
      throw new Error('API paths must not fetch public catalog data');
    });
    const response = await handlePublicSiteRequest(
      new Request('https://preview.kosmed.test/api'),
      { apiOrigin: 'https://api.kosmed.test', deploymentEnvironment: 'preview' },
      assets,
      fetchImpl,
    );

    expect(response.status).toBe(404);
    expect(response.headers.get('Cache-Control')).toBe('no-store');
    expect(await response.text()).toBe('');
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it('disallows indexing on preview robots without needing the API', async () => {
    const fetchImpl = createFetch(() => {
      throw new Error('robots.txt does not depend on the API');
    });
    const response = await handlePublicSiteRequest(
      new Request('https://preview.kosmed.test/robots.txt'),
      { deploymentEnvironment: 'preview' },
      assets,
      fetchImpl,
    );

    expect(response.status).toBe(200);
    expect(await response.text()).toContain('Disallow: /');
    expect(response.headers.get('Cache-Control')).toBe('no-store');
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
