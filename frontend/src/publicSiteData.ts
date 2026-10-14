import type { PublicSiteApi, PublicSiteClinic, PublicSiteDoctor, PublicSiteService } from './publicSiteApi';
import type { PublicSiteRouteMatch } from './routing/publicSiteRouteEntries';

export interface PublicSitePageData {
  clinic?: PublicSiteClinic;
  services?: PublicSiteService[];
  doctors?: PublicSiteDoctor[];
  service?: PublicSiteService;
  doctor?: PublicSiteDoctor;
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
      return api.listServices(route.locale).then((services) => ({ services }));
    case 'service':
      return api.getService(route.slug ?? '', route.locale)
        .then((service) => ({ service: service ?? undefined }));
    case 'doctors':
      return api.listDoctors(route.locale).then((doctors) => ({ doctors }));
    case 'doctor':
      return api.getDoctor(route.slug ?? '', route.locale)
        .then((doctor) => ({ doctor: doctor ?? undefined }));
    case 'contacts':
      return api.getClinic().then((clinic) => ({ clinic }));
    default:
      return Promise.resolve({});
  }
}
