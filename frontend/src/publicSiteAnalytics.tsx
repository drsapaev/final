import { createElement } from 'react';
import { getApiOrigin } from './api/runtime';

const ANALYTICS_PATH = '/api/v1/public-site/analytics/events';

export function getPublicSiteAnalyticsEndpoint(configuredOrigin?: string): string | undefined {
  if (!configuredOrigin) return undefined;

  try {
    const url = new URL(configuredOrigin);
    const isLocalHttp = url.protocol === 'http:'
      && (url.hostname === 'localhost' || url.hostname === '127.0.0.1');
    if ((url.protocol !== 'https:' && !isLocalHttp) || url.href !== url.origin + '/') return undefined;
    return url.origin + ANALYTICS_PATH;
  } catch {
    return undefined;
  }
}

export function getVitePublicSiteAnalyticsEndpoint(): string | undefined {
  if (import.meta.env.VITE_PUBLIC_SITE_ANALYTICS_ENABLED !== 'true') return undefined;
  return getPublicSiteAnalyticsEndpoint(getApiOrigin());
}

interface PublicSiteAnalyticsProps {
  endpoint?: string;
  event?: 'site_view' | 'booking_form_open';
  trackPhone?: boolean;
}

export function PublicSiteAnalytics({ endpoint, event, trackPhone = false }: PublicSiteAnalyticsProps) {
  if (!endpoint) return null;

  return (
    <>
      <script async src="/public-site-analytics.js" />
      {createElement('kosmed-public-site-analytics', {
        hidden: true,
        'data-endpoint': endpoint,
        'data-event': event,
        'data-track-phone': trackPhone ? '' : undefined,
      })}
    </>
  );
}
