import { describe, expect, it, vi } from 'vitest';
import type { PublicSiteApi } from './publicSiteApi';
import { loadPublicSitePageData } from './publicSiteData';
import { resolvePublicSiteRoute } from './routing/publicSiteRouteEntries';

const clinic = { name: 'SYNTHETIC QA CLINIC', address: null, phone: null, email: null };
const service = {
  slug: 'synthetic-service',
  name: 'SYNTHETIC TEST SERVICE',
  description: 'Synthetic test content only.',
  price: null,
  currency: null,
  category: null,
};
const doctor = {
  slug: 'synthetic-profile',
  name: 'SYNTHETIC TEST PROFILE',
  bio: 'Synthetic test content only.',
  specialty: null,
};

function makeApi(): PublicSiteApi {
  return {
    getClinic: vi.fn(async () => clinic),
    listServices: vi.fn(async () => [service]),
    getService: vi.fn(async () => service),
    listDoctors: vi.fn(async () => [doctor]),
    getDoctor: vi.fn(async () => doctor),
  };
}

function route(path: string) {
  const match = resolvePublicSiteRoute(path);
  if (!match) throw new Error(`No public-site route for ${path}`);
  return match;
}

describe('loadPublicSitePageData', () => {
  it('loads the home page from clinic, services, and doctors public projections', async () => {
    const api = makeApi();

    await expect(loadPublicSitePageData(api, route('/'))).resolves.toEqual({
      clinic,
      services: [service],
      doctors: [doctor],
    });
    expect(api.getClinic).toHaveBeenCalledOnce();
    expect(api.listServices).toHaveBeenCalledWith('uz-Latn');
    expect(api.listDoctors).toHaveBeenCalledWith('uz-Latn');
  });

  it.each([
    ['/services', { services: [service] }],
    ['/prices', { services: [service] }],
    ['/services/synthetic-service', { service }],
    ['/doctors', { doctors: [doctor] }],
    ['/doctors/synthetic-profile', { doctor }],
    ['/contacts', { clinic }],
  ])('loads %s from the same public API adapter used by SSR', async (path, expected) => {
    await expect(loadPublicSitePageData(makeApi(), route(path))).resolves.toEqual(expected);
  });

  it('uses the requested locale for localized content', async () => {
    const api = makeApi();

    await loadPublicSitePageData(api, route('/ru/services'));

    expect(api.listServices).toHaveBeenCalledWith('ru');
  });
});
