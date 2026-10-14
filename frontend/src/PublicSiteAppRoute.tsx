import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { getApiOrigin } from './api/runtime';
import { createPublicSiteApi } from './publicSiteApi';
import { loadPublicSitePageData, type PublicSitePageData } from './publicSiteData';
import {
  PublicSiteFallback,
  PublicSitePage,
  PublicSiteRequestState,
} from './publicSitePage';
import { resolvePublicSiteRoute } from './routing/publicSiteRouteEntries';

type PageState =
  | { pathname: string; status: 'loading' | 'error' }
  | { pathname: string; status: 'ready'; data: PublicSitePageData };

export default function PublicSiteAppRoute() {
  const { pathname } = useLocation();
  const route = resolvePublicSiteRoute(pathname);
  const [pageState, setPageState] = useState<PageState>({ pathname, status: 'loading' });

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
  const state = pageState.pathname === pathname ? pageState : { pathname, status: 'loading' as const };
  if (state.status === 'ready') return <PublicSitePage route={route} data={state.data} />;
  return <PublicSiteRequestState route={route} status={state.status} />;
}
