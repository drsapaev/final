import type { components } from './types/generated/api';
import type { PublicSiteLocale } from './routing/publicSiteRouteEntries';

export type PublicSiteClinic = components['schemas']['PublicSiteClinicOut'];
export type PublicSiteService = components['schemas']['PublicSiteServiceOut'];
export type PublicSiteDoctor = components['schemas']['PublicSiteDoctorOut'];

export class PublicSiteApiError extends Error {
  constructor() {
    super('Public site data is unavailable');
    this.name = 'PublicSiteApiError';
  }
}

export type PublicSiteFetch = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

export interface PublicSiteApi {
  getClinic(): Promise<PublicSiteClinic>;
  listServices(locale: PublicSiteLocale): Promise<PublicSiteService[]>;
  getService(slug: string, locale: PublicSiteLocale): Promise<PublicSiteService | null>;
  listDoctors(locale: PublicSiteLocale): Promise<PublicSiteDoctor[]>;
  getDoctor(slug: string, locale: PublicSiteLocale): Promise<PublicSiteDoctor | null>;
}

const REQUEST_TIMEOUT_MS = 8_000;

function normalizeApiOrigin(value: string): string {
  const url = new URL(value);
  const localHost = url.hostname === 'localhost' || url.hostname === '127.0.0.1';
  if ((url.protocol !== 'https:' && !(localHost && url.protocol === 'http:')) ||
      url.username || url.password || url.search || url.hash) {
    throw new PublicSiteApiError();
  }
  return url.origin;
}

export function createPublicSiteApi(
  apiOrigin: string,
  fetchImpl: PublicSiteFetch = fetch,
): PublicSiteApi {
  const origin = normalizeApiOrigin(apiOrigin);

  async function request<T>(path: string, missingIsNull = false): Promise<T | null> {
    let response: Response;
    try {
      response = await fetchImpl(new URL(`/api/v1/public-site/${path}`, origin), {
        method: 'GET',
        headers: { Accept: 'application/json' },
        cache: 'no-store',
        credentials: 'omit',
        redirect: 'error',
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
    } catch {
      throw new PublicSiteApiError();
    }

    if (missingIsNull && response.status === 404) return null;
    if (!response.ok) throw new PublicSiteApiError();

    try {
      return await response.json() as T;
    } catch {
      throw new PublicSiteApiError();
    }
  }

  async function requestList<T>(path: string): Promise<T[]> {
    const result = await request<unknown>(path);
    if (!Array.isArray(result)) throw new PublicSiteApiError();
    return result as T[];
  }

  const localized = (path: string, locale: PublicSiteLocale) =>
    `${path}?locale=${encodeURIComponent(locale)}`;

  return {
    async getClinic() {
      const result = await request<PublicSiteClinic>('clinic');
      if (!result || typeof result !== 'object') throw new PublicSiteApiError();
      return result;
    },
    listServices(locale) {
      return requestList<PublicSiteService>(localized('services', locale));
    },
    async getService(slug, locale) {
      return request<PublicSiteService>(
        localized(`services/${encodeURIComponent(slug)}`, locale),
        true,
      );
    },
    listDoctors(locale) {
      return requestList<PublicSiteDoctor>(localized('doctors', locale));
    },
    async getDoctor(slug, locale) {
      return request<PublicSiteDoctor>(
        localized(`doctors/${encodeURIComponent(slug)}`, locale),
        true,
      );
    },
  };
}
