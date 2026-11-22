import type { PublicSitePageData } from './publicSiteData';
import type { PublicSiteLocale, PublicSitePageKind, PublicSiteRouteMatch } from './routing/publicSiteRouteEntries';

interface PageMeta {
  title: string;
  description: string;
}

const BRAND = 'Doktor KosMed Clinic';

const META_COPY: Record<PublicSiteLocale, Record<PublicSitePageKind, PageMeta>> = {
  ru: {
    home: { title: `${BRAND} — услуги и врачи`, description: 'Информация об опубликованных услугах, врачах и контактах клиники.' },
    services: { title: `Услуги — ${BRAND}`, description: 'Опубликованные услуги клиники и информация о них.' },
    service: { title: `Услуга — ${BRAND}`, description: 'Описание опубликованной услуги клиники.' },
    doctors: { title: `Врачи — ${BRAND}`, description: 'Профили врачей, опубликованные клиникой.' },
    doctor: { title: `Врач — ${BRAND}`, description: 'Информация о профиле врача клиники.' },
    prices: { title: `Цены — ${BRAND}`, description: 'Опубликованные цены на услуги клиники.' },
    contacts: { title: `Контакты — ${BRAND}`, description: 'Контактные данные клиники.' },
  },
  'uz-Latn': {
    home: { title: `${BRAND} — xizmatlar va shifokorlar`, description: 'Klinikaning e’lon qilingan xizmatlari, shifokorlari va kontaktlari haqida ma’lumot.' },
    services: { title: `Xizmatlar — ${BRAND}`, description: 'Klinikaning e’lon qilingan xizmatlari va ular haqida ma’lumot.' },
    service: { title: `Xizmat — ${BRAND}`, description: 'Klinikaning e’lon qilingan xizmati tavsifi.' },
    doctors: { title: `Shifokorlar — ${BRAND}`, description: 'Klinika tomonidan e’lon qilingan shifokor profillari.' },
    doctor: { title: `Shifokor — ${BRAND}`, description: 'Klinika shifokorining profili haqida ma’lumot.' },
    prices: { title: `Narxlar — ${BRAND}`, description: 'Klinika xizmatlari uchun e’lon qilingan narxlar.' },
    contacts: { title: `Kontaktlar — ${BRAND}`, description: 'Klinikaning kontakt ma’lumotlari.' },
  },
};

export const PUBLIC_SITE_ERROR_TITLES: Record<PublicSiteLocale, string> = {
  ru: `Страница временно недоступна — ${BRAND}`,
  'uz-Latn': `Sahifa vaqtincha ochilmayapti — ${BRAND}`,
};

function truncateDescription(value: string): string {
  const compact = value.replace(/\s+/g, ' ').trim();
  if (compact.length <= 160) return compact;
  return `${compact.slice(0, 157).trimEnd()}…`;
}

export function getPublicSitePageMetadata(route: PublicSiteRouteMatch, data: PublicSitePageData = {}): PageMeta {
  const base = META_COPY[route.locale][route.kind];
  if (route.kind === 'service' && data.service) {
    return {
      title: `${data.service.name} — ${BRAND}`,
      description: truncateDescription(data.service.description),
    };
  }
  if (route.kind === 'doctor' && data.doctor) {
    return {
      title: `${data.doctor.name} — ${BRAND}`,
      description: truncateDescription(data.doctor.bio),
    };
  }
  return base;
}
