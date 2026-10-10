import { matchPath } from 'react-router-dom';

export const PUBLIC_SITE_ROUTE_DEFINITIONS = [
  { id: 'landing', path: '/', kind: 'home', locale: 'uz-Latn' },
  { id: 'public-site-ru-home', path: '/ru', kind: 'home', locale: 'ru' },
  { id: 'public-site-services', path: '/services', kind: 'services', locale: 'uz-Latn' },
  { id: 'public-site-service-detail', path: '/services/:slug', kind: 'service', locale: 'uz-Latn' },
  { id: 'public-site-doctors', path: '/doctors', kind: 'doctors', locale: 'uz-Latn' },
  { id: 'public-site-doctor-detail', path: '/doctors/:slug', kind: 'doctor', locale: 'uz-Latn' },
  { id: 'public-site-prices', path: '/prices', kind: 'prices', locale: 'uz-Latn' },
  { id: 'public-site-contacts', path: '/contacts', kind: 'contacts', locale: 'uz-Latn' },
  { id: 'public-site-ru-services', path: '/ru/services', kind: 'services', locale: 'ru' },
  { id: 'public-site-ru-service-detail', path: '/ru/services/:slug', kind: 'service', locale: 'ru' },
  { id: 'public-site-ru-doctors', path: '/ru/doctors', kind: 'doctors', locale: 'ru' },
  { id: 'public-site-ru-doctor-detail', path: '/ru/doctors/:slug', kind: 'doctor', locale: 'ru' },
  { id: 'public-site-ru-prices', path: '/ru/prices', kind: 'prices', locale: 'ru' },
  { id: 'public-site-ru-contacts', path: '/ru/contacts', kind: 'contacts', locale: 'ru' },
] as const;

export type PublicSiteLocale = 'uz-Latn' | 'ru';
export type PublicSitePageKind = (typeof PUBLIC_SITE_ROUTE_DEFINITIONS)[number]['kind'];

export interface PublicSiteRouteMatch {
  id: (typeof PUBLIC_SITE_ROUTE_DEFINITIONS)[number]['id'];
  path: string;
  kind: PublicSitePageKind;
  locale: PublicSiteLocale;
  slug?: string;
}

export function resolvePublicSiteRoute(pathname: string): PublicSiteRouteMatch | null {
  for (const route of PUBLIC_SITE_ROUTE_DEFINITIONS) {
    const match = matchPath({ path: route.path, end: true }, pathname);
    if (match) {
      return {
        id: route.id,
        path: route.path,
        kind: route.kind,
        locale: route.locale,
        slug: match.params.slug,
      };
    }
  }
  return null;
}

export function getPublicSitePath(
  kind: PublicSitePageKind,
  locale: PublicSiteLocale,
  slug?: string,
): string {
  const route = PUBLIC_SITE_ROUTE_DEFINITIONS.find(
    (candidate) => candidate.kind === kind && candidate.locale === locale,
  );
  if (!route) return locale === 'ru' ? '/ru' : '/';
  return route.path.includes(':slug')
    ? route.path.replace(':slug', encodeURIComponent(slug ?? ''))
    : route.path;
}

export const PUBLIC_SITE_ROUTE_ENTRIES = PUBLIC_SITE_ROUTE_DEFINITIONS.map((route) => ({
  id: route.id,
  path: route.path,
  group: 'public',
  surface: 'screen',
  lifecycle: 'stable',
  shell: 'landing',
  auth: 'public',
  roles: [],
  entry: 'direct',
  nav: false,
  title: 'Doktor KosMed Clinic',
  owner: `public-site.${route.kind}`,
  component: 'PublicSiteFallback',
  legacyRedirectFrom: [],
  layout: { hideHeader: true, hideSidebar: true, pageTitle: 'Doktor KosMed Clinic' },
}));
