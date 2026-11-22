import type {
  PublicSiteApi, PublicSiteClinic, PublicSiteDoctor, PublicSiteService, PublicSiteServiceDetail,
} from './publicSiteApi';
import type { PublicSiteRouteMatch } from './routing/publicSiteRouteEntries';

export interface PublicSitePageData {
  clinic?: PublicSiteClinic;
  logoUrl?: PublicSiteClinic['logo_url'];
  services?: PublicSiteService[];
  doctors?: PublicSiteDoctor[];
  service?: PublicSiteServiceDetail;
  doctor?: PublicSiteDoctor;
}

const HEADER_LOGO_TIMEOUT_MS = 1_500;

async function withHeaderLogo(
  api: PublicSiteApi,
  page: Promise<PublicSitePageData>,
): Promise<PublicSitePageData> {
  const [data, logoUrl] = await Promise.all([
    page,
    api.getClinic(AbortSignal.timeout(HEADER_LOGO_TIMEOUT_MS))
      .then((clinic) => clinic.logo_url, () => null),
  ]);
  return logoUrl ? { ...data, logoUrl } : data;
}

/** Load the public projection needed by a route for both Nitro and Vite. */
export function loadPublicSitePageData(
  api: PublicSiteApi,
  route: PublicSiteRouteMatch,
): Promise<PublicSitePageData> {
  switch (route.kind) {
    case 'home':
      return Promise.all([
        api.getClinic(),
        api.listServices(route.locale),
        api.listDoctors(route.locale),
      ]).then(([clinic, services, doctors]) => ({ clinic, services, doctors }));
    case 'services':
    case 'prices':
      return withHeaderLogo(api, api.listServices(route.locale).then((services) => ({ services })));
    case 'service':
      return withHeaderLogo(
        api,
        api.getService(route.slug ?? '', route.locale)
          .then((service) => ({ service: service ?? undefined })),
      );
    case 'doctors':
      return withHeaderLogo(api, api.listDoctors(route.locale).then((doctors) => ({ doctors })));
    case 'doctor':
      return withHeaderLogo(
        api,
        api.getDoctor(route.slug ?? '', route.locale)
          .then((doctor) => ({ doctor: doctor ?? undefined })),
      );
    case 'contacts':
      return api.getClinic().then((clinic) => ({ clinic }));
    default:
      return Promise.resolve({});
  }
}
