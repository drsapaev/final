import { describe, expect, it } from 'vitest';

import { ROUTE_REGISTRY } from '../routing/routeRegistry';
import { sanitizeSpeedInsightsEvent } from '../utils/speedInsightsPrivacy.ts';

describe('Speed Insights privacy sanitizer', () => {
  it('drops query strings and hashes that can contain patient workflow identifiers', () => {
    const event = sanitizeSpeedInsightsEvent(
      {
        url: 'https://clinic.example/registrar?patientId=42&q=Aliya#payment',
        name: 'TTFB',
      },
      ROUTE_REGISTRY
    );

    expect(event).toEqual({
      url: '/registrar',
      route: '/registrar',
      name: 'TTFB',
    });
  });

  it('uses canonical dynamic route templates instead of concrete ids and tokens', () => {
    expect(
      sanitizeSpeedInsightsEvent(
        {
          url: '/queue/join/public-qr-token-123',
        },
        ROUTE_REGISTRY
      ).url
    ).toBe('/queue/join/:token');

    expect(
      sanitizeSpeedInsightsEvent(
        {
          url: '/clinical/pickup/98765',
        },
        ROUTE_REGISTRY
      ).url
    ).toBe('/clinical/pickup/:patientId');
  });

  it('redacts unmatched numeric, uuid, and high-entropy path segments', () => {
    const event = sanitizeSpeedInsightsEvent(
      {
        url: '/unknown/patient/123/token/550e8400-e29b-41d4-a716-446655440000/raw/abcdef1234567890',
      },
      ROUTE_REGISTRY
    );

    expect(event.url).toBe('/unknown/patient/[redacted]/token/[redacted]/raw/[redacted]');
  });

  it('fully redacts malformed URLs instead of throwing', () => {
    const event = sanitizeSpeedInsightsEvent(
      {
        url: 'not a url',
        name: 'CLS',
      },
      ROUTE_REGISTRY
    );

    expect(event).toEqual({
      url: '[redacted]',
      name: 'CLS',
    });
  });
});
