import { describe, expect, it, vi } from 'vitest';
import { handlePublicSiteRequest } from './publicSiteHandler';
import type { PublicSiteFetch } from './publicSiteApi';
import nitroConfig from '../nitro.config';
import { PUBLIC_SITE_ROUTE_DEFINITIONS } from './routing/publicSiteRouteEntries';

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

function createFetch(handler: (url: URL) => Response | Promise<Response>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = input instanceof URL ? input : new URL(String(input));
    return handler(url);
  });
  return fetchMock as unknown as PublicSiteFetch;
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
      expect(url.origin).toBe('https://api.kosmed.test');
      expect(url.pathname).toBe('/api/v1/public-site/services/laser-care');
      expect(url.searchParams.get('locale')).toBe('ru');
      return jsonResponse({
        slug: 'laser-care',
        name: 'Лазерная терапия',
        description: 'Описание опубликованной услуги клиники.',
        price: null,
        currency: null,
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
    expect(html).toContain('Цена по запросу');
    expect(html).toContain('href="https://www.kosmed.test/ru/services/laser-care"');
    expect(html).toContain('hreflang="uz-Latn" href="https://www.kosmed.test/services/laser-care"');
    expect(html).toContain('hreflang="x-default"');
    expect(html).toContain('/assets/public-site.css');
    expect(html).not.toContain('/assets/clinic-app.js');
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
    const response = await handlePublicSiteRequest(
      new Request('https://preview.kosmed.test/login'),
      { apiOrigin: 'https://api.kosmed.test', deploymentEnvironment: 'preview' },
      assets,
      fetchImpl,
    );
    const html = await response.text();

    expect(response.status).toBe(200);
    expect(html).toContain('Clinic OS');
    expect(html).toContain('id="root"');
    expect(html).toContain('/assets/clinic-app.js');
    expect(html).not.toContain('id="public-site-root"');
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
