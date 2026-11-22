import { readFileSync } from 'node:fs';
import { URL as NodeURL } from 'node:url';
import { runInNewContext } from 'node:vm';
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

const DETAIL_ENTITY_TYPE = /"@type"\s*:\s*"(?:ProfilePage|Service)"/;
const MEDIA_FALLBACK_SCRIPT = 'script[src="/public-site-media-fallback.js"]';

function readStructuredData(document: Document): Record<string, unknown>[] {
  return Array.from(document.querySelectorAll('head script[type="application/ld+json"]'), (tag) =>
    JSON.parse(tag.textContent ?? '') as Record<string, unknown>);
}

function expectUnavailablePage(response: Response, locale: string) {
  expect(response.status).toBe(503);
  expect(response.headers.get('Cache-Control')).toBe('no-store');
  expect(response.headers.get('X-Robots-Tag')).toBe('noindex, nofollow');
  expect(response.headers.get('Content-Type')).toBe('text/html; charset=utf-8');
  expect(response.headers.get('Content-Language')).toBe(locale);
}

it('marks already broken and newly failed public-site images as unavailable', () => {
  const page = new DOMParser().parseFromString(
    '<div class="public-site">' +
      '<img src="/broken-logo.png" data-public-site-image>' +
      '<img src="/healthy-logo.png" data-public-site-image>' +
      '<img src="/pending-portrait.png" data-public-site-image>' +
      '</div>' +
      '<img src="/unrelated.png" data-public-site-image>',
    'text/html',
  );
  const [broken, healthy, pending, unrelated] = page.querySelectorAll('img');
  Object.defineProperties(broken, { complete: { value: true }, naturalWidth: { value: 0 } });
  Object.defineProperties(healthy, { complete: { value: true }, naturalWidth: { value: 2 } });
  Object.defineProperties(pending, { complete: { value: false }, naturalWidth: { value: 0 } });
  Object.defineProperties(unrelated, { complete: { value: true }, naturalWidth: { value: 0 } });

  const script = readFileSync(new NodeURL('../public/public-site-media-fallback.js', import.meta.url), 'utf8');
  runInNewContext(script, { document: page, HTMLImageElement });
  page.dispatchEvent(new Event('DOMContentLoaded'));

  expect(broken.dataset.publicSiteImage).toBe('unavailable');
  expect(healthy.dataset.publicSiteImage).toBe('');
  expect(pending.dataset.publicSiteImage).toBe('');
  expect(unrelated.dataset.publicSiteImage).toBe('');

  pending.dispatchEvent(new Event('error'));
  unrelated.dispatchEvent(new Event('error'));

  expect(pending.dataset.publicSiteImage).toBe('unavailable');
  expect(unrelated.dataset.publicSiteImage).toBe('');
});

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

  it.each(PUBLIC_SITE_ROUTE_DEFINITIONS)('renders the published clinic logo on $path and falls back when absent', async ({ path: routePath, locale, kind }) => {
    const path = routePath.replace(':slug', 'synthetic');
    const home = locale === 'ru' ? '/ru' : '/';
    const apiOrigin = 'https://api.kosmed.test';
    const logoPath = `/api/v1/public-site/media/${'b'.repeat(64)}`;

    async function renderBrand(logoUrl: string | null) {
      const fetchImpl = createFetch((url, init) => {
        if (url.pathname === '/api/v1/public-site/clinic') {
          expect(init?.cache).toBe('no-store');
          return jsonResponse({ name: 'SYNTHETIC Clinic', address: 'SYNTHETIC address', logo_url: logoUrl });
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
      const html = await response.text();
      if (kind !== 'contacts') expect(html).not.toContain('MedicalClinic');
      if (kind !== 'doctor' && kind !== 'service') expect(html).not.toMatch(DETAIL_ENTITY_TYPE);
      return new DOMParser().parseFromString(html, 'text/html');
    }

    const brandedPage = await renderBrand(logoPath);
    const brand = brandedPage.querySelector('header a.public-site__brand');
    const logo = brand?.querySelector('img');
    expect(brand?.getAttribute('href')).toBe(home);
    expect(brand?.querySelector('span:not([aria-hidden])')?.textContent).toBe('Doktor KosMed Clinic');
    expect(logo?.getAttribute('src')).toBe(apiOrigin + logoPath);
    expect(logo?.getAttribute('alt')).toBe('');
    expect(logo?.getAttribute('width')).toBe('38');
    expect(logo?.getAttribute('height')).toBe('38');
    expect(logo?.getAttribute('data-public-site-image')).toBe('');
    expect(logo?.nextElementSibling?.getAttribute('aria-hidden')).toBe('true');
    expect(logo?.nextElementSibling?.textContent).toBe('K');
    expect(brandedPage.querySelectorAll(MEDIA_FALLBACK_SCRIPT)).toHaveLength(1);
    expect(brandedPage.querySelector(MEDIA_FALLBACK_SCRIPT)?.hasAttribute('async')).toBe(true);

    const fallbackPage = await renderBrand(null);
    const fallback = fallbackPage.querySelector('header a.public-site__brand');
    expect(fallback?.getAttribute('href')).toBe(home);
    expect(fallback?.querySelector('img')).toBeNull();
    expect(fallback?.querySelector('span[aria-hidden="true"]')?.textContent).toBe('K');
    expect(fallbackPage.querySelector(MEDIA_FALLBACK_SCRIPT)).toBeNull();
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
    const logoPath = `/api/v1/public-site/media/${'b'.repeat(64)}`;
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
    async function renderDoctors(path: string, logoUrl: string | null = null) {
      const fetchImpl = createFetch((url) => {
        if (url.pathname === '/api/v1/public-site/clinic') return jsonResponse({ logo_url: logoUrl });
        expect(url.searchParams.get('locale')).toBe(locale);
        if (url.pathname === '/api/v1/public-site/doctors') {
          return jsonResponse([doctor, textOnlyDoctor]);
        }
        const profile = [doctor, textOnlyDoctor].find(({ slug }) =>
          url.pathname === `/api/v1/public-site/doctors/${slug}`);
        return profile ? jsonResponse(profile) : jsonResponse({}, 404);
      });
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
    expect(cardPortrait?.getAttribute('width')).toBe('80');
    expect(cardPortrait?.getAttribute('height')).toBe('80');
    expect(cardPortrait?.getAttribute('data-public-site-image')).toBe('');
    expect(catalog.querySelectorAll(MEDIA_FALLBACK_SCRIPT)).toHaveLength(1);
    expect(cardPortrait?.closest('li')?.textContent).toContain(doctor.name);
    expect(catalog.querySelector('main')?.textContent).toContain(textOnlyDoctor.name);

    const profile = await renderDoctors(`/doctors/${doctor.slug}`, logoPath);
    const profilePortrait = profile.querySelector('main img');
    expect(profilePortrait?.getAttribute('src')).toBe(apiOrigin + portraitPath);
    expect(profilePortrait?.getAttribute('alt')).toBe('');
    expect(profilePortrait?.getAttribute('loading')).not.toBe('lazy');
    expect(profilePortrait?.getAttribute('fetchpriority')).toBe('high');
    expect(profilePortrait?.getAttribute('width')).toBe('160');
    expect(profilePortrait?.getAttribute('height')).toBe('160');
    expect(profilePortrait?.getAttribute('data-public-site-image')).toBe('');
    expect(profile.querySelectorAll('img[data-public-site-image]')).toHaveLength(2);
    expect(profile.querySelectorAll(MEDIA_FALLBACK_SCRIPT)).toHaveLength(1);
    expect(profile.querySelector('main h1')?.textContent).toBe(doctor.name);

    const textOnlyProfile = await renderDoctors(`/doctors/${textOnlyDoctor.slug}`);
    expect(textOnlyProfile.querySelector('main img')).toBeNull();
    expect(textOnlyProfile.querySelector('img[data-public-site-image]')).toBeNull();
    expect(textOnlyProfile.querySelector(MEDIA_FALLBACK_SCRIPT)).toBeNull();
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

  describe('MedicalClinic structured data', () => {
    const fixture = {
      name: 'SYNTHETIC Clinic',
      address: 'SYNTHETIC address',
      phone: '+000 (00) 000-000',
      email: 'clinic+synthetic@example.test',
      logo_url: null,
      working_hours_start: '09:00:00',
      working_hours_end: '17:00:00',
    };

    function requestContacts(path: string, fetchImpl: ReturnType<typeof createFetch>) {
      return handlePublicSiteRequest(
        new Request(`https://preview.kosmed.test${path}`),
        {
          apiOrigin: 'https://api.kosmed.test',
          siteOrigin: 'https://www.kosmed.test',
          deploymentEnvironment: 'preview',
        },
        assets,
        fetchImpl,
      );
    }

    it.each([
      {
        path: '/contacts',
        locale: 'uz-Latn',
        workingDays: 'Dushanba–shanba',
        sundayClosed: 'Yakshanba — dam olish kuni',
      },
      {
        path: '/ru/contacts',
        locale: 'ru',
        workingDays: 'Понедельник–суббота',
        sundayClosed: 'Воскресенье — выходной',
      },
    ])('matches rendered contacts and the canonical clinic identity on $path', async ({ path, locale, workingDays, sundayClosed }) => {
      const fetchImpl = createFetch((url) => {
        expect(url.href).toBe('https://api.kosmed.test/api/v1/public-site/clinic');
        return jsonResponse(fixture);
      });

      const response = await requestContacts(path, fetchImpl);
      const document = new DOMParser().parseFromString(await response.text(), 'text/html');
      const contactText = document.querySelector('address')?.textContent;
      const structuredData = readStructuredData(document);

      expect(response.status).toBe(200);
      expect(response.headers.get('Cache-Control')).toBe('no-store');
      expect(response.headers.get('X-Robots-Tag')).toBe('noindex, nofollow');
      expect(response.headers.get('Content-Language')).toBe(locale);
      expect(document.querySelector('footer')?.textContent).toContain(fixture.name);
      expect(contactText).toContain(fixture.address);
      expect(contactText).toContain(fixture.phone);
      expect(contactText).toContain(fixture.email);
      expect(contactText).toContain(workingDays);
      expect(contactText).toContain('09:00–17:00');
      expect(contactText).toContain(sundayClosed);
      expect(structuredData).toContainEqual(expect.objectContaining({ '@type': 'BreadcrumbList' }));
      expect(structuredData.filter((record) => record['@type'] === 'MedicalClinic')).toEqual([{
        '@context': 'https://schema.org',
        '@type': 'MedicalClinic',
        '@id': 'https://www.kosmed.test/#clinic',
        url: 'https://www.kosmed.test/',
        name: fixture.name,
        address: fixture.address,
        telephone: '+00000000000',
        email: fixture.email,
        openingHoursSpecification: {
          '@type': 'OpeningHoursSpecification',
          dayOfWeek: [
            'https://schema.org/Monday',
            'https://schema.org/Tuesday',
            'https://schema.org/Wednesday',
            'https://schema.org/Thursday',
            'https://schema.org/Friday',
            'https://schema.org/Saturday',
          ],
          opens: '09:00:00',
          closes: '17:00:00',
        },
      }]);
      expect(fetchImpl).toHaveBeenCalledOnce();
    });

    it('uses current clinic hours on every uncached request', async () => {
      const clinic = { ...fixture };
      const fetchImpl = createFetch((_url, init) => {
        expect(init?.cache).toBe('no-store');
        return jsonResponse(clinic);
      });

      const original = await requestContacts('/contacts', fetchImpl);
      const originalDocument = new DOMParser().parseFromString(await original.text(), 'text/html');
      expect(originalDocument.querySelector('address')?.textContent).toContain('09:00–17:00');
      clinic.working_hours_start = '08:30:00';
      clinic.working_hours_end = '16:15:00';
      const updated = await requestContacts('/contacts', fetchImpl);
      const document = new DOMParser().parseFromString(await updated.text(), 'text/html');

      expect(updated.headers.get('Cache-Control')).toBe('no-store');
      expect(document.querySelector('address')?.textContent).toContain('08:30–16:15');
      expect(readStructuredData(document)).toContainEqual(expect.objectContaining({
        '@type': 'MedicalClinic',
        openingHoursSpecification: expect.objectContaining({ opens: '08:30:00', closes: '16:15:00' }),
      }));
      expect(fetchImpl).toHaveBeenCalledTimes(2);
    });

    it.each([
      { label: 'out-of-range hours', start: '99:00:00', end: '17:00:00' },
      { label: 'a missing closing time', start: '09:00:00', end: null },
      { label: 'reversed hours', start: '18:00:00', end: '09:00:00' },
    ])('omits invalid contacts and $label while retaining the published address', async ({ start, end }) => {
      const response = await requestContacts('/ru/contacts', createFetch(() => jsonResponse({
        ...fixture,
        phone: 'SYNTHETIC invalid phone',
        email: 'SYNTHETIC invalid email',
        working_hours_start: start,
        working_hours_end: end,
      })));
      const document = new DOMParser().parseFromString(await response.text(), 'text/html');

      expect(response.status).toBe(200);
      expect(document.querySelector('address')?.textContent).toContain(fixture.address);
      expect(document.querySelector('address')?.textContent).not.toContain('SYNTHETIC invalid');
      expect(document.querySelector('address')?.textContent).not.toContain('Понедельник–суббота');
      expect(readStructuredData(document).filter((record) => record['@type'] === 'MedicalClinic')).toEqual([{
        '@context': 'https://schema.org',
        '@type': 'MedicalClinic',
        '@id': 'https://www.kosmed.test/#clinic',
        url: 'https://www.kosmed.test/',
        name: fixture.name,
        address: fixture.address,
      }]);
    });

    it.each([
      { label: 'has no published name', clinic: { ...fixture, name: null } },
      { label: 'has no publishable contact information or hours', clinic: { name: fixture.name } },
    ])('omits the entity when the clinic $label', async ({ clinic }) => {
      const response = await requestContacts('/contacts', createFetch(() => jsonResponse(clinic)));
      const document = new DOMParser().parseFromString(await response.text(), 'text/html');

      expect(response.status).toBe(200);
      expect(document.querySelector('main')).not.toBeNull();
      expect(readStructuredData(document)).not.toContainEqual(expect.objectContaining({ '@type': 'MedicalClinic' }));
    });

    it('preserves published contact text without letting it close the JSON-LD script', async () => {
      const address = 'SYNTHETIC </script> <address> &';
      const response = await requestContacts('/contacts', createFetch(() => jsonResponse({ ...fixture, address })));
      const html = await response.text();
      const document = new DOMParser().parseFromString(html, 'text/html');

      expect(response.status).toBe(200);
      expect(html).not.toContain(address);
      expect(document.querySelector('address')?.textContent).toContain(address);
      expect(readStructuredData(document)).toContainEqual(expect.objectContaining({ '@type': 'MedicalClinic', address }));
    });
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
      pageDescription: 'SYNTHETIC описание опубликованной услуги.',
      category: 'SYNTHETIC категория',
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
      pageDescription: 'SYNTHETIC e’lon qilingan xizmat tavsifi.',
      category: null,
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
      pageName: 'SYNTHETIC Doctor',
      pageDescription: 'SYNTHETIC биография врача.',
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
      pageName: 'SYNTHETIC Doctor',
      pageDescription: 'SYNTHETIC shifokor tarjimai holi.',
    },
  ])('renders localized breadcrumbs and published detail structured data for $path', async (scenario) => {
    const { kind, locale, path, slug, pageName, pageDescription, category } = scenario;
    const apiPath = kind === 'service'
      ? `/api/v1/public-site/services/${slug}`
      : `/api/v1/public-site/doctors/${slug}`;
    const apiRecord = kind === 'service'
      ? {
        slug,
        name: pageName,
        description: pageDescription,
        category,
        price: '125000.00',
        currency: 'UZS',
        related_doctors: [{ slug: 'synthetic-doctor', name: 'SYNTHETIC Related Doctor' }],
      }
      : {
        slug,
        name: pageName,
        bio: pageDescription,
        specialty: locale === 'ru' ? 'Дерматология' : 'Dermatologiya',
        experience_years: 10,
        professional_category: 'SYNTHETIC Qualification',
        portrait_url: `/api/v1/public-site/media/${'b'.repeat(64)}`,
      };
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
    const document = new DOMParser().parseFromString(html, 'text/html');
    const structuredData = readStructuredData(document);
    const canonical = `https://www.kosmed.test${path}`;

    expect(response.status).toBe(200);
    expect(response.headers.get('Content-Language')).toBe(locale);
    expect(response.headers.get('Cache-Control')).toBe('no-store');
    expect(response.headers.get('X-Robots-Tag')).toBe('noindex, nofollow');
    expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(canonical);
    expect(document.querySelector('article h1')?.textContent).toContain(pageName);
    expect(document.querySelector('article')?.textContent).toContain(pageDescription);
    expect(navigation).not.toBeNull();
    expect(navigation?.[0]).toContain(`<a href="${scenario.homePath}">${scenario.homeLabel}</a>`);
    expect(navigation?.[0]).toContain(`<a href="${scenario.sectionPath}">${scenario.sectionLabel}</a>`);
    expect(navigation?.[0]).toContain(`<span aria-current="page">${pageName}</span>`);
    expect(structuredData.find((record) => record['@type'] === 'BreadcrumbList')).toEqual({
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
          item: canonical,
        },
      ],
    });
    const expectedEntity = kind === 'service' ? {
      '@context': 'https://schema.org',
      '@type': 'Service',
      '@id': `https://www.kosmed.test/services/${slug}#service`,
      url: canonical,
      name: pageName,
      description: pageDescription,
      ...(category ? { category } : {}),
    } : {
      '@context': 'https://schema.org',
      '@type': 'ProfilePage',
      url: canonical,
      mainEntity: {
        '@type': 'Person',
        '@id': `https://www.kosmed.test/doctors/${slug}#doctor`,
        name: pageName,
        description: pageDescription,
      },
    };
    expect(structuredData.filter((record) => record['@type'] !== 'BreadcrumbList')).toEqual([expectedEntity]);
    if (category) expect(document.querySelector('article .public-site__eyebrow')?.textContent).toBe(category);
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
    const unsafeDescription = 'SYNTHETIC description </script> &';
    const fetchImpl = createFetch(() => jsonResponse({
      slug: 'unsafe-name',
      name: unsafeName,
      description: unsafeDescription,
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

    const document = new DOMParser().parseFromString(html, 'text/html');
    const service = readStructuredData(document).find((record) => record['@type'] === 'Service');
    expect(html).not.toContain(unsafeDescription);
    expect(service).toMatchObject({ name: unsafeName, description: unsafeDescription });
    expect(service).not.toHaveProperty('category');
  });

  const errorCopy = {
    ru: {
      title: 'Страница временно недоступна — Doktor KosMed Clinic',
      message: 'Не удалось загрузить актуальную информацию клиники.',
      navigation: 'Навигация сайта',
      retry: 'Повторить',
      skip: 'Перейти к основному содержимому',
    },
    'uz-Latn': {
      title: 'Sahifa vaqtincha ochilmayapti — Doktor KosMed Clinic',
      message: 'Klinikaning dolzarb ma’lumotlarini yuklab bo‘lmadi.',
      navigation: 'Sayt navigatsiyasi',
      retry: 'Qayta urinish',
      skip: 'Asosiy mazmunga o‘tish',
    },
  } as const;

  it.each([
    { path: '/services', locale: 'ru' },
    { path: '/contacts', locale: 'ru' },
    { path: '/services/synthetic-service', locale: 'ru' },
    { path: '/doctors/synthetic-doctor', locale: 'ru' },
    { path: '/doctors/synthetic-doctor', locale: 'uz-Latn' },
  ] as const)('returns the localized recovery view for $locale $path failures', async ({ path, locale }) => {
    const fetchImpl = createFetch(() => new Response('private upstream error: old published card', { status: 500 }));
    const prefix = locale === 'ru' ? '/ru' : '';
    const alternatePrefix = locale === 'ru' ? '' : '/ru';
    const copy = errorCopy[locale];
    const response = await handlePublicSiteRequest(
      new Request(`https://www.kosmed.test${prefix}${path}?ref=synthetic-incidental-query`),
      { apiOrigin: 'https://api.kosmed.test', deploymentEnvironment: 'production' },
      assets,
      fetchImpl,
    );
    const html = await response.text();
    const document = new DOMParser().parseFromString(html, 'text/html');

    expectUnavailablePage(response, locale);
    expect(document.documentElement.lang).toBe(locale);
    expect(document.title).toBe(copy.title);
    expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('noindex,nofollow');
    expect(document.querySelector('link[rel="canonical"], script')).toBeNull();
    const nav = document.querySelector('header > nav');
    expect(nav?.getAttribute('aria-label')).toBe(copy.navigation);
    expect(nav?.querySelector(`a[href="${prefix}/contacts"]`)).not.toBeNull();
    expect(document.querySelector('header .public-site__language')?.getAttribute('href')).toBe(alternatePrefix + path);
    expect(document.querySelector('a[href="#main-content"]')?.textContent).toBe(copy.skip);
    const main = document.querySelector('main#main-content');
    expect(main?.getAttribute('tabindex')).toBe('-1');
    const error = main?.querySelector('[role="alert"]');
    expect(error?.querySelector('h1')?.textContent).toBe(copy.message);
    const retry = error?.querySelector('a');
    expect(retry?.textContent).toBe(copy.retry);
    expect(retry?.getAttribute('href')).toBe(prefix + path);
    expect(html).not.toContain('synthetic-incidental-query');
    expect(html).not.toContain('private upstream error');
    expect(html).not.toContain('old published card');
  });

  it('returns the 503 headers and an empty body for HEAD', async () => {
    const response = await handlePublicSiteRequest(
      new Request('https://www.kosmed.test/ru/services/synthetic-service', { method: 'HEAD' }),
      { apiOrigin: 'https://api.kosmed.test', deploymentEnvironment: 'production' },
      assets,
      createFetch(() => new Response(null, { status: 500 })),
    );

    expectUnavailablePage(response, 'ru');
    expect(await response.text()).toBe('');
  });

  it('keeps the localized retry link when the configured canonical origin is invalid', async () => {
    const fetchImpl = createFetch(() => jsonResponse({}));
    const response = await handlePublicSiteRequest(
      new Request('https://www.kosmed.test/doctors/synthetic-doctor?ref=synthetic-incidental-query'),
      {
        apiOrigin: 'https://api.kosmed.test',
        siteOrigin: 'ftp://invalid-canonical-origin.test',
        deploymentEnvironment: 'production',
      },
      assets,
      fetchImpl,
    );
    const html = await response.text();
    const document = new DOMParser().parseFromString(html, 'text/html');

    expectUnavailablePage(response, 'uz-Latn');
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(document.title).toBe(errorCopy['uz-Latn'].title);
    expect(document.querySelector('link[rel="canonical"], script')).toBeNull();
    expect(document.querySelector('main [role="alert"] a')?.getAttribute('href')).toBe('/doctors/synthetic-doctor');
    expect(html).not.toContain('invalid-canonical-origin.test');
  });

  it('retries the same localized detail after the synthetic API recovers', async () => {
    const path = '/ru/services/synthetic-service';
    const requestUrl = `https://www.kosmed.test${path}?ref=synthetic-incidental-query`;
    const config = { apiOrigin: 'https://api.kosmed.test', deploymentEnvironment: 'production' };
    const serviceName = 'Синтетическая услуга восстановлена';
    let apiReady = false;
    const fetchImpl = createFetch((url) => {
      if (url.pathname === '/api/v1/public-site/clinic') return jsonResponse({ logo_url: null });
      expect(url.pathname).toBe('/api/v1/public-site/services/synthetic-service');
      expect(url.search).toBe('?locale=ru');
      return apiReady
        ? jsonResponse({ slug: 'synthetic-service', name: serviceName, description: 'SYNTHETIC service', price: null })
        : new Response(null, { status: 500 });
    });

    const failed = await handlePublicSiteRequest(new Request(requestUrl), config, assets, fetchImpl);
    expectUnavailablePage(failed, 'ru');
    const errorDocument = new DOMParser().parseFromString(await failed.text(), 'text/html');
    const retry = errorDocument.querySelector('main [role="alert"] a')?.getAttribute('href');
    expect(retry).toBe(path);
    if (!retry) throw new Error('The retry link is missing.');

    apiReady = true;
    const recovered = await handlePublicSiteRequest(new Request(new URL(retry, requestUrl)), config, assets, fetchImpl);
    const document = new DOMParser().parseFromString(await recovered.text(), 'text/html');
    expect(recovered.status).toBe(200);
    expect(recovered.headers.get('Cache-Control')).toBe('no-store');
    expect(recovered.headers.get('X-Robots-Tag')).toBeNull();
    expect(document.querySelector('main h1')?.textContent).toBe(serviceName);
    expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(`https://www.kosmed.test${path}`);
  });

  it.each([
    { path: '/ru/services/hidden-service', message: 'Услуга не найдена или больше не опубликована.' },
    { path: '/ru/doctors/hidden-doctor', message: 'Врач не найден или профиль больше не опубликован.' },
  ])('returns a public 404 without structured detail data for $path', async ({ path, message }) => {
    const fetchImpl = createFetch(() => jsonResponse({ detail: { code: 'public_content_not_found' } }, 404));
    const response = await handlePublicSiteRequest(
      new Request(`https://preview.kosmed.test${path}`),
      { apiOrigin: 'https://api.kosmed.test', deploymentEnvironment: 'preview' },
      assets,
      fetchImpl,
    );
    const html = await response.text();

    expect(response.status).toBe(404);
    expect(response.headers.get('Cache-Control')).toBe('no-store');
    expect(response.headers.get('X-Robots-Tag')).toBe('noindex, nofollow');
    expect(html).toContain(message);
    expect(html).not.toContain('public_content_not_found');
    expect(html).not.toContain('MedicalClinic');
    expect(html).not.toMatch(DETAIL_ENTITY_TYPE);
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
      expect(html, pathname).not.toContain('MedicalClinic');
      expect(html, pathname).not.toMatch(DETAIL_ENTITY_TYPE);
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
