import { readFileSync } from 'node:fs';
import { URL as NodeURL } from 'node:url';
import { runInNewContext } from 'node:vm';
import { render } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getPublicSiteAnalyticsEndpoint,
  getVitePublicSiteAnalyticsEndpoint,
  PublicSiteAnalytics,
} from './publicSiteAnalytics';

const origin = 'https://api.kosmed.test';
const endpoint = origin + '/api/v1/public-site/analytics/events';
const tagName = 'kosmed-public-site-analytics';
const fetchEvent = vi.fn();
const script = readFileSync(new NodeURL('../public/public-site-analytics.js', import.meta.url), 'utf8');

vi.mock('./api/runtime', () => ({ getApiOrigin: () => 'https://api.kosmed.test' }));

function installCollector() {
  runInNewContext(script, {
    document,
    customElements,
    HTMLElement,
    Element,
    AbortController,
    URL,
    fetch: fetchEvent,
  });
  document.dispatchEvent(new Event('DOMContentLoaded'));
}

function request(event: 'site_view' | 'phone_click' | 'booking_form_open') {
  return [endpoint, {
    method: 'POST',
    body: event,
    headers: { 'Content-Type': 'text/plain' },
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
    redirect: 'error',
    keepalive: true,
    cache: 'no-store',
  }];
}

beforeEach(() => {
  fetchEvent.mockReset();
  fetchEvent.mockResolvedValue(new Response(null, { status: 204 }));
});

afterEach(() => vi.unstubAllEnvs());

describe('public-site analytics configuration', () => {
  it('requires an explicit Vite flag', () => {
    vi.stubEnv('VITE_PUBLIC_SITE_ANALYTICS_ENABLED', undefined);
    expect(getVitePublicSiteAnalyticsEndpoint()).toBeUndefined();
    vi.stubEnv('VITE_PUBLIC_SITE_ANALYTICS_ENABLED', 'false');
    expect(getVitePublicSiteAnalyticsEndpoint()).toBeUndefined();
    vi.stubEnv('VITE_PUBLIC_SITE_ANALYTICS_ENABLED', 'true');
    expect(getVitePublicSiteAnalyticsEndpoint()).toBe(endpoint);
  });

  it('derives a fixed collector from a configured HTTPS or local development origin', () => {
    expect(getPublicSiteAnalyticsEndpoint(origin)).toBe(endpoint);
    expect(getPublicSiteAnalyticsEndpoint('http://127.0.0.1:18000'))
      .toBe('http://127.0.0.1:18000/api/v1/public-site/analytics/events');
    for (const input of [
      undefined,
      '/relative',
      'http://untrusted.test',
      'https://operator@api.kosmed.test',
      origin + '/patient-portal',
      origin + '?q=synthetic',
      origin + '#synthetic',
    ]) {
      expect(getPublicSiteAnalyticsEndpoint(input)).toBeUndefined();
    }
  });

  it('renders neither a marker nor a script when disabled', () => {
    const { container } = render(<PublicSiteAnalytics event="site_view" trackPhone />);
    expect(container).toBeEmptyDOMElement();
    expect(fetchEvent).not.toHaveBeenCalled();
  });
});

describe('public-site analytics browser collector', () => {
  it('sends one fixed page view and counts only clicks on telephone links in the page', () => {
    const { container } = render(
      <>
        <div className="public-site">
          <a href="tel:000000"><span>Call</span></a>
          <a href="#main-content">Read more</a>
          <PublicSiteAnalytics endpoint={endpoint} event="site_view" trackPhone />
        </div>
        <a href="tel:000001">Outside the public site</a>
      </>,
    );
    installCollector();
    installCollector();
    expect(fetchEvent.mock.calls).toEqual([request('site_view')]);

    for (const link of container.querySelectorAll('a')) {
      link.addEventListener('click', (event) => event.preventDefault());
      (link.firstElementChild ?? link).dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    }
    expect(fetchEvent.mock.calls).toEqual([request('site_view'), request('phone_click')]);
  });

  it('sends one form opening after the form becomes usable, including after lifecycle replays', () => {
    const analytics = (usable: boolean) => (
      <StrictMode>
        <div className="public-site">
          <PublicSiteAnalytics endpoint={endpoint} event={usable ? 'booking_form_open' : undefined} />
          {usable ? <form aria-label="Synthetic booking" /> : null}
        </div>
      </StrictMode>
    );
    const { container, rerender } = render(analytics(false));
    installCollector();
    expect(fetchEvent).not.toHaveBeenCalled();

    rerender(analytics(true));
    rerender(analytics(false));
    rerender(analytics(true));
    const marker = container.querySelector(tagName);
    const scope = marker?.parentElement;
    if (!marker || !scope) throw new Error('Expected the booking analytics marker');
    marker.remove();
    scope.append(marker);

    expect(fetchEvent.mock.calls).toEqual([request('booking_form_open')]);
  });

  it('ignores an invalid event or a tampered collector URL', () => {
    const { container } = render(
      <div className="public-site">
        <PublicSiteAnalytics endpoint={endpoint + '?unexpected'} event="site_view" trackPhone />
        <PublicSiteAnalytics endpoint={endpoint} />
      </div>,
    );
    container.querySelectorAll(tagName)[1].setAttribute('data-event', 'unexpected');
    installCollector();
    expect(fetchEvent).not.toHaveBeenCalled();
  });
});
