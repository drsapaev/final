import { useEffect, useLayoutEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { getApiOrigin } from './api/runtime';
import { getVitePublicSiteAnalyticsEndpoint } from './publicSiteAnalytics';
import { createPublicSiteApi } from './publicSiteApi';
import { loadPublicSitePageData, type PublicSitePageData } from './publicSiteData';
import { getPublicSitePageMetadata, PUBLIC_SITE_ERROR_TITLES } from './publicSiteMetadata';
import { PublicSiteFallback, PublicSitePage } from './publicSitePage';
import { resolvePublicSiteRoute } from './routing/publicSiteRouteEntries';

type PageState =
  | { pathname: string; status: 'loading' | 'error' }
  | { pathname: string; status: 'ready'; data: PublicSitePageData };

export default function PublicSiteAppRoute() {
  const { pathname } = useLocation();
  const route = resolvePublicSiteRoute(pathname);
  const locale = route?.locale;
  const [pageState, setPageState] = useState<PageState>({ pathname, status: 'loading' });
  const state = pageState.pathname === pathname ? pageState : { pathname, status: 'loading' as const };
  const title = route && (state.status === 'error'
    ? PUBLIC_SITE_ERROR_TITLES[route.locale]
    : getPublicSitePageMetadata(route, state.status === 'ready' ? state.data : undefined).title);

  useLayoutEffect(() => {
    if (!locale) return undefined;

    const root = document.documentElement;
    const previousLanguage = root.getAttribute('lang');
    root.lang = locale;
    root.classList.add('public-site-document');

    return () => {
      root.classList.remove('public-site-document');
      if (root.lang !== locale) return;
      if (previousLanguage === null) root.removeAttribute('lang');
      else root.lang = previousLanguage;
    };
  }, [locale]);

  useLayoutEffect(() => {
    if (!title) return undefined;

    const previousTitle = document.title;
    document.title = title;
    const appliedTitle = document.title;

    return () => {
      if (document.title === appliedTitle) document.title = previousTitle;
    };
  }, [title]);

  useEffect(() => {
    const route = resolvePublicSiteRoute(pathname);
    if (!route) return undefined;

    let active = true;

    try {
      const api = createPublicSiteApi(getApiOrigin());
      void loadPublicSitePageData(api, route).then(
        (data) => {
          if (active) setPageState({ pathname, status: 'ready', data });
        },
        () => {
          if (active) setPageState({ pathname, status: 'error' });
        },
      );
    } catch {
      setPageState({ pathname, status: 'error' });
    }

    return () => {
      active = false;
    };
  }, [pathname]);

  if (!route) return <PublicSiteFallback />;
  // Keep the native skip link's target mounted as this pathname's content loads.
  return state.status === 'ready'
    ? <PublicSitePage key={pathname} route={route} data={state.data} analyticsEndpoint={getVitePublicSiteAnalyticsEndpoint()} />
    : <PublicSitePage key={pathname} route={route} status={state.status} />;
}
