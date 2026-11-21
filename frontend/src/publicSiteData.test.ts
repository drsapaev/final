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

  it('uses the doctor links from service detail without fetching a separate directory or profile', async () => {
    const api = makeApi();
    const detail = {
      ...service,
      related_doctors: [{ slug: doctor.slug, name: doctor.name }],
    };
    vi.mocked(api.getService).mockResolvedValue(detail);

    await expect(loadPublicSitePageData(api, route('/ru/services/synthetic-service')))
      .resolves.toEqual({ service: detail });

    expect(api.getService).toHaveBeenCalledExactlyOnceWith('synthetic-service', 'ru');
    expect(api.getClinic).toHaveBeenCalledOnce();
    expect(api.listDoctors).not.toHaveBeenCalled();
    expect(api.getDoctor).not.toHaveBeenCalled();
  });

  it('starts the header logo and catalog reads together', async () => {
    const api = makeApi();
    const logoUrl = `https://api.kosmed.test/api/v1/public-site/media/${'b'.repeat(64)}`;
    vi.mocked(api.getClinic).mockResolvedValue({ ...clinic, logo_url: logoUrl });

    const data = loadPublicSitePageData(api, route('/ru/prices'));

    expect(api.listServices).toHaveBeenCalledWith('ru');
    expect(api.getClinic).toHaveBeenCalledOnce();
    await expect(data).resolves.toEqual({ services: [service], logoUrl });
  });

  it('keeps the catalog available when loading the optional logo fails', async () => {
    const api = makeApi();
    vi.mocked(api.getClinic).mockRejectedValue(new Error('Synthetic clinic API failure'));

    await expect(loadPublicSitePageData(api, route('/doctors'))).resolves.toEqual({
      doctors: [doctor],
    });
    expect(api.getClinic).toHaveBeenCalledOnce();
  });
});
