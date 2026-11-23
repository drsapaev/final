import { renderToString } from 'react-dom/server';
import {
  getPublicSitePath,
  PUBLIC_SITE_ROUTE_DEFINITIONS,
  resolvePublicSiteRoute,
  type PublicSiteLocale,
  type PublicSitePageKind,
  type PublicSiteRouteMatch,
} from './routing/publicSiteRouteEntries';
import {
  createPublicSiteApi,
  PublicSiteApiError,
  type PublicSiteApi,
  type PublicSiteClinic,
  type PublicSiteDoctor,
  type PublicSiteFetch,
  type PublicSiteService,
} from './publicSiteApi';
import { loadPublicSitePageData, type PublicSitePageData } from './publicSiteData';
import { getPublicSitePageMetadata, PUBLIC_SITE_ERROR_TITLES } from './publicSiteMetadata';
import {
  getPublicClinicContacts,
  getPublicSiteBreadcrumbs,
  PublicSitePage,
  PublicSiteRequestState,
} from './publicSitePage';

export interface PublicSiteRuntimeConfig {
  apiOrigin?: string;
  siteOrigin?: string;
  deploymentEnvironment?: string;
}

export interface PublicSiteAssets {
  pageStyles: string[];
  appEntry: string;
  appStyles: string[];
  pageStyleText?: string;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    '\x27': '&#39;',
  })[char] ?? char);
}

function safeOrigin(value: string, allowLocalHttp = false): string | null {
  try {
    const url = new URL(value);
    const isLocal = url.hostname === 'localhost' || url.hostname === '127.0.0.1';
    if ((url.protocol !== 'https:' && !(allowLocalHttp && isLocal && url.protocol === 'http:')) ||
        url.username || url.password || url.search || url.hash || url.pathname !== '/') {
      return null;
    }
    return url.origin;
  } catch {
    return null;
  }
}

function canonicalOrigin(request: Request, configuredOrigin?: string): string | null {
  if (configuredOrigin) return safeOrigin(configuredOrigin, true);
  return safeOrigin(new URL(request.url).origin, true);
}

function renderJsonLd(value: unknown): string {
  const json = JSON.stringify(value)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/&/g, '\\u0026')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029');
  return `<script type="application/ld+json">${json}</script>`;
}

function renderMedicalClinicJsonLd(clinic: PublicSiteClinic | undefined, origin: string): string {
  const name = clinic?.name?.trim();
  if (!clinic || !name) return '';

  const { address, telHref, mailtoHref, hours } = getPublicClinicContacts(clinic);
  if (!address && !telHref && !mailtoHref && !hours) return '';

  const openingHoursSpecification = hours && {
    '@type': 'OpeningHoursSpecification',
    dayOfWeek: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
      .map((day) => `https://schema.org/${day}`),
    opens: `${hours.start}:00`,
    closes: `${hours.end}:00`,
  };

  return renderJsonLd({
    '@context': 'https://schema.org',
    '@type': 'MedicalClinic',
    '@id': `${origin}/#clinic`,
    url: `${origin}/`,
    name,
    address,
    telephone: telHref?.slice('tel:'.length),
    email: mailtoHref ? clinic.email?.trim() : undefined,
    openingHoursSpecification,
  });
}

function pagePath(route: PublicSiteRouteMatch, locale: PublicSiteLocale): string {
  return getPublicSitePath(route.kind, locale, route.slug);
}

function renderDetailJsonLd(
  route: PublicSiteRouteMatch,
  data: PublicSitePageData,
  origin: string,
  canonical: string,
): string {
  if (route.kind === 'doctor' && data.doctor) {
    const { name, bio } = data.doctor;
    return renderJsonLd({
      '@context': 'https://schema.org',
      '@type': 'ProfilePage',
      url: canonical,
      mainEntity: {
        '@type': 'Person',
        '@id': new URL(`${pagePath(route, 'uz-Latn')}#doctor`, origin).href,
        name,
        description: bio,
      },
    });
  }

  if (route.kind === 'service' && data.service) {
    const { name, description, category } = data.service;
    return renderJsonLd({
      '@context': 'https://schema.org',
      '@type': 'Service',
      '@id': new URL(`${pagePath(route, 'uz-Latn')}#service`, origin).href,
      url: canonical,
      name,
      description,
      category: category ?? undefined,
    });
  }

  return '';
}

function renderPublicDocument(
  route: PublicSiteRouteMatch,
  data: PublicSitePageData,
  origin: string,
  styles: string[],
  pageStyleText?: string,
): string {
  const meta = getPublicSitePageMetadata(route, data);
  const canonical = new URL(pagePath(route, route.locale), origin).href;
  const alternateUz = new URL(pagePath(route, 'uz-Latn'), origin).href;
  const alternateRu = new URL(pagePath(route, 'ru'), origin).href;
  const breadcrumbs = getPublicSiteBreadcrumbs(route, data);
  const breadcrumbJsonLd = breadcrumbs.length > 0
    ? renderJsonLd({
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: breadcrumbs.map((item, index) => ({
        '@type': 'ListItem',
        position: index + 1,
        name: item.name,
        item: new URL(item.path, origin).href,
      })),
    })
    : '';
  const entityJsonLd = route.kind === 'contacts'
    ? renderMedicalClinicJsonLd(data.clinic, origin)
    : renderDetailJsonLd(route, data, origin, canonical);
  const body = renderToString(<PublicSitePage route={route} data={data} />);
  const css = renderPageStyles(styles, pageStyleText);

  return `<!doctype html><html lang="${escapeHtml(route.locale)}"><head>` +
    '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' +
    `<title>${escapeHtml(meta.title)}</title>` +
    `<meta name="description" content="${escapeHtml(meta.description)}">` +
    `<link rel="canonical" href="${escapeHtml(canonical)}">` +
    `<link rel="alternate" hreflang="uz-Latn" href="${escapeHtml(alternateUz)}">` +
    `<link rel="alternate" hreflang="ru" href="${escapeHtml(alternateRu)}">` +
    `<link rel="alternate" hreflang="x-default" href="${escapeHtml(alternateUz)}">` +
    `<meta property="og:title" content="${escapeHtml(meta.title)}">` +
    `<meta property="og:description" content="${escapeHtml(meta.description)}">` +
    `<meta property="og:type" content="website"><meta property="og:url" content="${escapeHtml(canonical)}">` +
    `<meta property="og:locale" content="${route.locale === 'ru' ? 'ru_RU' : 'uz_UZ'}">` +
    `<meta name="twitter:card" content="summary">${breadcrumbJsonLd}${entityJsonLd}${css}</head>` +
    `<body><div id="public-site-root">${body}</div></body></html>`;
}

function renderAppShell(assets: PublicSiteAssets): string {
  const css = assets.appStyles.map((href) => `<link rel="stylesheet" href="${escapeHtml(href)}">`).join('');
  return '<!doctype html><html lang="en"><head>' +
    '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' +
    '<meta name="robots" content="noindex,nofollow">' +
    '<meta name="application-name" content="Clinic OS">' +
    '<link rel="manifest" href="/manifest.json"><link rel="icon" href="/brand/logo-mark.svg">' +
    '<title>Clinic OS</title>' + css +
    `</head><body><div id="root"></div><script type="module" src="${escapeHtml(assets.appEntry)}"></script></body></html>`;
}

function responseHeaders(contentType: string, noIndex: boolean): Headers {
  const headers = new Headers({
    'Cache-Control': 'no-store',
    'Content-Type': contentType,
    'X-Content-Type-Options': 'nosniff',
  });
  if (noIndex) headers.set('X-Robots-Tag', 'noindex, nofollow');
  return headers;
}

function htmlResponse(
  body: string,
  status: number,
  locale: PublicSiteLocale,
  noIndex: boolean,
  method: string,
): Response {
  const headers = responseHeaders('text/html; charset=utf-8', noIndex);
  headers.set('Content-Language', locale);
  return new Response(method === 'HEAD' ? null : body, { status, headers });
}

function xmlEscape(value: string): string {
  return value.replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    '\x27': '&apos;',
  })[char] ?? char);
}

function buildSitemap(
  origin: string,
  services: Record<PublicSiteLocale, PublicSiteService[]>,
  doctors: Record<PublicSiteLocale, PublicSiteDoctor[]>,
): string {
  const urls = new Map<string, Map<PublicSiteLocale, string>>();
  const addPair = (kind: PublicSitePageKind, slug?: string) => {
    const byLocale = new Map<PublicSiteLocale, string>();
    for (const locale of ['uz-Latn', 'ru'] as const) {
      byLocale.set(locale, new URL(getPublicSitePath(kind, locale, slug), origin).href);
    }
    urls.set(`${kind}:${slug ?? ''}`, byLocale);
  };

  for (const route of PUBLIC_SITE_ROUTE_DEFINITIONS) {
    if (route.kind !== 'service' && route.kind !== 'doctor') addPair(route.kind);
  }

  const addPublishedSlugs = <T extends { slug: string }>(
    kind: 'service' | 'doctor',
    entries: Record<PublicSiteLocale, T[]>,
  ) => {
    const allSlugs = new Set([...entries['uz-Latn'], ...entries.ru].map((entry) => entry.slug));
    for (const slug of allSlugs) {
      const byLocale = new Map<PublicSiteLocale, string>();
      for (const locale of ['uz-Latn', 'ru'] as const) {
        if (entries[locale].some((entry) => entry.slug === slug)) {
          byLocale.set(locale, new URL(getPublicSitePath(kind, locale, slug), origin).href);
        }
      }
      urls.set(`${kind}:${slug}`, byLocale);
    }
  };
  addPublishedSlugs('service', services);
  addPublishedSlugs('doctor', doctors);

  const records = [...urls.values()].flatMap((byLocale) => {
    const alternates = [...byLocale.entries()].map(([locale, href]) =>
      `<xhtml:link rel="alternate" hreflang="${locale}" href="${xmlEscape(href)}"/>`,
    ).join('');
    const defaultHref = byLocale.get('uz-Latn');
    const xDefault = defaultHref
      ? `<xhtml:link rel="alternate" hreflang="x-default" href="${xmlEscape(defaultHref)}"/>`
      : '';
    return [...byLocale.values()].map((href) =>
      `<url><loc>${xmlEscape(href)}</loc>${alternates}${xDefault}</url>`,
    );
  }).join('');

  return '<?xml version="1.0" encoding="UTF-8"?>' +
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">' +
    records + '</urlset>';
}

async function renderSitemap(api: PublicSiteApi, origin: string): Promise<string> {
  const [uzServices, ruServices, uzDoctors, ruDoctors] = await Promise.all([
    api.listServices('uz-Latn'),
    api.listServices('ru'),
    api.listDoctors('uz-Latn'),
    api.listDoctors('ru'),
  ]);
  return buildSitemap(origin, {
    'uz-Latn': uzServices,
    ru: ruServices,
  }, {
    'uz-Latn': uzDoctors,
    ru: ruDoctors,
  });
}

export async function handlePublicSiteRequest(
  request: Request,
  config: PublicSiteRuntimeConfig,
  assets: PublicSiteAssets,
  fetchImpl?: PublicSiteFetch,
): Promise<Response> {
  const url = new URL(request.url);
  const noIndex = config.deploymentEnvironment !== 'production';
  const localeHint: PublicSiteLocale = url.pathname === '/ru' || url.pathname.startsWith('/ru/') ? 'ru' : 'uz-Latn';

  if (request.method !== 'GET' && request.method !== 'HEAD') {
    return new Response('Method not allowed', {
      status: 405,
      headers: { Allow: 'GET, HEAD', 'Cache-Control': 'no-store' },
    });
  }

  if (url.pathname === '/api' || url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws')) {
    return new Response(null, { status: 404, headers: { 'Cache-Control': 'no-store' } });
  }

  const origin = canonicalOrigin(request, config.siteOrigin);
  if (url.pathname === '/robots.txt') {
    const robots = noIndex
      ? 'User-agent: *\nDisallow: /\n'
      : `User-agent: *\nAllow: /\n${origin ? `Sitemap: ${origin}/sitemap.xml\n` : ''}`;
    const headers = responseHeaders('text/plain; charset=utf-8', noIndex);
    return new Response(request.method === 'HEAD' ? null : robots, { status: 200, headers });
  }

  if (url.pathname === '/sitemap.xml') {
    if (!origin || !config.apiOrigin) {
      return new Response(request.method === 'HEAD' ? null : 'Sitemap is temporarily unavailable', {
        status: 503,
        headers: responseHeaders('application/xml; charset=utf-8', true),
      });
    }
    try {
      const api = createPublicSiteApi(config.apiOrigin, fetchImpl);
      const sitemap = await renderSitemap(api, origin);
      const headers = responseHeaders('application/xml; charset=utf-8', noIndex);
      return new Response(request.method === 'HEAD' ? null : sitemap, { status: 200, headers });
    } catch {
      return new Response(request.method === 'HEAD' ? null : 'Sitemap is temporarily unavailable', {
        status: 503,
        headers: responseHeaders('text/plain; charset=utf-8', true),
      });
    }
  }

  const route = resolvePublicSiteRoute(url.pathname);
  if (!route) {
    return htmlResponse(renderAppShell(assets), 200, localeHint, true, request.method);
  }
  if (!origin) return renderErrorResponse(route, assets, request.method);

  try {
    if (!config.apiOrigin) throw new PublicSiteApiError();
    const api = createPublicSiteApi(config.apiOrigin, fetchImpl);
    const data = await loadPublicSitePageData(api, route);
    const missingDetail = (route.kind === 'service' && !data.service) ||
      (route.kind === 'doctor' && !data.doctor);
    const status = missingDetail ? 404 : 200;
    const html = renderPublicDocument(route, data, origin, assets.pageStyles, assets.pageStyleText);
    return htmlResponse(html, status, route.locale, noIndex || status === 404, request.method);
  } catch {
    // Error details can contain upstream response data; keep the public response generic.
    return renderErrorResponse(route, assets, request.method);
  }
}

export default {
  async fetch(request: Request): Promise<Response | undefined> {
    const url = new URL(request.url);
    if (url.pathname === '/api' || url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws')) {
      return new Response(null, { status: 404, headers: { 'Cache-Control': 'no-store' } });
    }
    if (!resolvePublicSiteRoute(url.pathname) && url.pathname !== '/robots.txt' && url.pathname !== '/sitemap.xml') {
      return undefined;
    }

    const [runtimeConfigModule, pageStylesModule] = await Promise.all([
      import('nitro/runtime-config'),
      import('./publicSiteStyles.css?raw'),
    ]);
    const config = runtimeConfigModule.useRuntimeConfig() as PublicSiteRuntimeConfig;
    return handlePublicSiteRequest(
      request,
      config,
      {
        pageStyles: [],
        appEntry: '',
        appStyles: [],
        pageStyleText: pageStylesModule.default,
      },
    );
  },
};

function renderPageStyles(styles: string[], pageStyleText?: string): string {
  if (pageStyleText) return `<style>${pageStyleText}</style>`;
  return pageStyleText || styles.map((href) => `<link rel="stylesheet" href="${escapeHtml(href)}">`).join('');
}

function renderErrorResponse(route: PublicSiteRouteMatch, assets: PublicSiteAssets, method: string): Response {
  const { locale } = route;
  const title = PUBLIC_SITE_ERROR_TITLES[locale];
  const css = renderPageStyles(assets.pageStyles, assets.pageStyleText);
  const body = renderToString(<PublicSiteRequestState route={route} status="error" />);
  const html = `<!doctype html><html lang="${escapeHtml(locale)}"><head>` +
    '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' +
    '<meta name="robots" content="noindex,nofollow">' +
    `<title>${escapeHtml(title)}</title>${css}</head>` +
    `<body>${body}</body></html>`;
  return htmlResponse(html, 503, locale, true, method);
}
