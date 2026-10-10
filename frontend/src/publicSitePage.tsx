import type { ReactNode } from 'react';
import './publicSiteStyles.css';
import {
  getPublicSitePath,
  type PublicSiteLocale,
  type PublicSitePageKind,
  type PublicSiteRouteMatch,
} from './routing/publicSiteRouteEntries';
import type {
  PublicSiteClinic,
  PublicSiteDoctor,
  PublicSiteService,
} from './publicSiteApi';

interface Copy {
  services: string;
  doctors: string;
  prices: string;
  contacts: string;
  language: string;
  serviceDetails: string;
  doctorDetails: string;
  homeIntro: string;
  homeServices: string;
  homeDoctors: string;
  viewAll: string;
  contactClinic: string;
  callClinic: string;
  emailClinic: string;
  address: string;
  specialty: string;
  priceOnRequest: string;
  serviceMissing: string;
  doctorMissing: string;
  emptyServices: string;
  emptyDoctors: string;
  contactMissing: string;
  openService: string;
  openDoctor: string;
  clinicName: string;
  publicSiteOnly: string;
  reloadPage: string;
}

const COPY: Record<PublicSiteLocale, Copy> = {
  ru: {
    services: 'Услуги',
    doctors: 'Врачи',
    prices: 'Цены',
    contacts: 'Контакты',
    language: 'Язык',
    serviceDetails: 'Информация об услуге',
    doctorDetails: 'Информация о враче',
    homeIntro: 'Информация об услугах клиники и специалистах.',
    homeServices: 'Популярные услуги',
    homeDoctors: 'Наши специалисты',
    viewAll: 'Посмотреть все',
    contactClinic: 'Связаться с клиникой',
    callClinic: 'Позвонить',
    emailClinic: 'Написать по электронной почте',
    address: 'Адрес',
    specialty: 'Специализация',
    priceOnRequest: 'Цена по запросу',
    serviceMissing: 'Услуга не найдена или больше не опубликована.',
    doctorMissing: 'Врач не найден или профиль больше не опубликован.',
    emptyServices: 'Опубликованные услуги пока не добавлены.',
    emptyDoctors: 'Опубликованные профили врачей пока не добавлены.',
    contactMissing: 'Контактные данные пока не опубликованы.',
    openService: 'Подробнее',
    openDoctor: 'Профиль врача',
    clinicName: 'Doktor KosMed Clinic',
    publicSiteOnly: 'Эта страница открывается через публичный веб-сайт клиники.',
    reloadPage: 'Открыть страницу',
  },
  'uz-Latn': {
    services: 'Xizmatlar',
    doctors: 'Shifokorlar',
    prices: 'Narxlar',
    contacts: 'Kontaktlar',
    language: 'Til',
    serviceDetails: 'Xizmat haqida',
    doctorDetails: 'Shifokor haqida',
    homeIntro: 'Klinika xizmatlari va mutaxassislari haqida ma’lumot.',
    homeServices: 'Xizmatlar',
    homeDoctors: 'Mutaxassislar',
    viewAll: 'Barchasini ko‘rish',
    contactClinic: 'Klinika bilan bog‘lanish',
    callClinic: 'Qo‘ng‘iroq qilish',
    emailClinic: 'Elektron pochta yuborish',
    address: 'Manzil',
    specialty: 'Mutaxassisligi',
    priceOnRequest: 'Narx so‘rov bo‘yicha',
    serviceMissing: 'Xizmat topilmadi yoki endi e’lon qilinmagan.',
    doctorMissing: 'Shifokor topilmadi yoki profili endi e’lon qilinmagan.',
    emptyServices: 'Hozircha e’lon qilingan xizmatlar yo‘q.',
    emptyDoctors: 'Hozircha e’lon qilingan shifokor profillari yo‘q.',
    contactMissing: 'Kontakt ma’lumotlari hozircha e’lon qilinmagan.',
    openService: 'Batafsil',
    openDoctor: 'Shifokor profili',
    clinicName: 'Doktor KosMed Clinic',
    publicSiteOnly: 'Bu sahifa klinikaning ommaviy veb-saytida ochiladi.',
    reloadPage: 'Sahifani ochish',
  },
};

export interface PublicSitePageData {
  clinic?: PublicSiteClinic;
  services?: PublicSiteService[];
  doctors?: PublicSiteDoctor[];
  service?: PublicSiteService;
  doctor?: PublicSiteDoctor;
}

interface PublicSitePageProps {
  route: PublicSiteRouteMatch;
  data: PublicSitePageData;
}

function cleanTelHref(phone?: string | null): string | undefined {
  const value = phone?.trim();
  if (!value || !/^[+()\d\s.-]{6,32}$/.test(value)) return undefined;
  const normalized = value.replace(/[()\s.-]/g, '');
  return /^\+?\d{6,20}$/.test(normalized) ? `tel:${normalized}` : undefined;
}

function cleanMailtoHref(email?: string | null): string | undefined {
  const value = email?.trim();
  if (!value || value.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
    return undefined;
  }
  return `mailto:${encodeURIComponent(value)}`;
}

function formatPrice(service: PublicSiteService, locale: PublicSiteLocale, copy: Copy): string {
  if (service.price === null || !service.currency) return copy.priceOnRequest;
  const amount = Number(service.price);
  if (!Number.isFinite(amount) || !/^[A-Z]{3}$/.test(service.currency)) {
    return `${service.price} ${service.currency}`;
  }
  try {
    const language = locale === 'ru' ? 'ru-RU' : 'uz-UZ';
    return new Intl.NumberFormat(language, {
      style: 'currency',
      currency: service.currency,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${service.price} ${service.currency}`;
  }
}

function localizePath(kind: PublicSitePageKind, locale: PublicSiteLocale, slug?: string): string {
  return getPublicSitePath(kind, locale, slug);
}

function SiteHeader({ locale, route, copy }: {
  locale: PublicSiteLocale;
  route: PublicSiteRouteMatch;
  copy: Copy;
}) {
  const otherLocale = locale === 'ru' ? 'uz-Latn' : 'ru';
  const homePath = localizePath('home', locale);
  const switchPath = localizePath(route.kind, otherLocale, route.slug);
  return (
    <header className="public-site__header">
      <a className="public-site__brand" href={homePath}>
        <span className="public-site__brand-mark" aria-hidden="true">K</span>
        <span>{copy.clinicName}</span>
      </a>
      <nav className="public-site__nav" aria-label={copy.clinicName}>
        <a href={localizePath('services', locale)}>{copy.services}</a>
        <a href={localizePath('doctors', locale)}>{copy.doctors}</a>
        <a href={localizePath('prices', locale)}>{copy.prices}</a>
        <a href={localizePath('contacts', locale)}>{copy.contacts}</a>
      </nav>
      <a className="public-site__language" href={switchPath} aria-label={copy.language}>
        {otherLocale === 'ru' ? 'RU' : 'O‘Z'}
      </a>
    </header>
  );
}

function ContactLinks({ clinic, copy }: { clinic?: PublicSiteClinic; copy: Copy }) {
  const telHref = cleanTelHref(clinic?.phone);
  const mailtoHref = cleanMailtoHref(clinic?.email);
  const hasContact = Boolean(telHref || mailtoHref || clinic?.address);
  if (!hasContact) return <p className="public-site__muted">{copy.contactMissing}</p>;

  return (
    <address className="public-site__contact-list">
      {clinic?.address && <p><span>{copy.address}</span>{clinic.address}</p>}
      {telHref && <p><span>{copy.callClinic}</span><a href={telHref}>{clinic?.phone}</a></p>}
      {mailtoHref && <p><span>{copy.emailClinic}</span><a href={mailtoHref}>{clinic?.email}</a></p>}
    </address>
  );
}

function ServiceList({ services, locale, copy, showPrices = false }: {
  services: PublicSiteService[];
  locale: PublicSiteLocale;
  copy: Copy;
  showPrices?: boolean;
}) {
  if (services.length === 0) return <p className="public-site__empty">{copy.emptyServices}</p>;
  return (
    <ul className="public-site__list">
      {services.map((service) => (
        <li className="public-site__list-item" key={service.slug}>
          <div>
            <a className="public-site__list-title" href={localizePath('service', locale, service.slug)}>{service.name}</a>
            {service.category && <p className="public-site__muted">{service.category}</p>}
            {!showPrices && <p>{service.description}</p>}
          </div>
          <div className="public-site__list-meta">
            {showPrices && <strong>{formatPrice(service, locale, copy)}</strong>}
            <a href={localizePath('service', locale, service.slug)}>{copy.openService}</a>
          </div>
        </li>
      ))}
    </ul>
  );
}

function DoctorList({ doctors, locale, copy }: {
  doctors: PublicSiteDoctor[];
  locale: PublicSiteLocale;
  copy: Copy;
}) {
  if (doctors.length === 0) return <p className="public-site__empty">{copy.emptyDoctors}</p>;
  return (
    <ul className="public-site__list public-site__list--doctors">
      {doctors.map((doctor) => (
        <li className="public-site__list-item" key={doctor.slug}>
          <div>
            <a className="public-site__list-title" href={localizePath('doctor', locale, doctor.slug)}>{doctor.name}</a>
            {doctor.specialty && <p className="public-site__muted">{copy.specialty}: {doctor.specialty}</p>}
            <p>{doctor.bio}</p>
          </div>
          <a href={localizePath('doctor', locale, doctor.slug)}>{copy.openDoctor}</a>
        </li>
      ))}
    </ul>
  );
}

function SectionHeading({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="public-site__section-heading">
      <h2>{title}</h2>
      {action}
    </div>
  );
}

function PageContent({ route, data, copy }: PublicSitePageProps & { copy: Copy }) {
  const locale = route.locale;
  switch (route.kind) {
    case 'home': {
      const services = data.services ?? [];
      const doctors = data.doctors ?? [];
      return (
        <>
          <section className="public-site__hero">
            <p className="public-site__eyebrow">{copy.clinicName}</p>
            <h1>{data.clinic?.name || copy.clinicName}</h1>
            <p className="public-site__lead">{copy.homeIntro}</p>
            <div className="public-site__actions">
              <a className="public-site__button public-site__button--primary" href={localizePath('services', locale)}>{copy.services}</a>
              <a className="public-site__button" href={localizePath('contacts', locale)}>{copy.contactClinic}</a>
            </div>
          </section>
          <section className="public-site__section">
            <SectionHeading title={copy.homeServices} action={<a href={localizePath('services', locale)}>{copy.viewAll}</a>} />
            <ServiceList services={services.slice(0, 4)} locale={locale} copy={copy} />
          </section>
          <section className="public-site__section">
            <SectionHeading title={copy.homeDoctors} action={<a href={localizePath('doctors', locale)}>{copy.viewAll}</a>} />
            <DoctorList doctors={doctors.slice(0, 3)} locale={locale} copy={copy} />
          </section>
        </>
      );
    }
    case 'services':
      return <section className="public-site__section"><h1>{copy.services}</h1><ServiceList services={data.services ?? []} locale={locale} copy={copy} /></section>;
    case 'prices':
      return <section className="public-site__section"><h1>{copy.prices}</h1><ServiceList services={data.services ?? []} locale={locale} copy={copy} showPrices /></section>;
    case 'doctors':
      return <section className="public-site__section"><h1>{copy.doctors}</h1><DoctorList doctors={data.doctors ?? []} locale={locale} copy={copy} /></section>;
    case 'contacts':
      return <section className="public-site__section"><h1>{copy.contacts}</h1><ContactLinks clinic={data.clinic} copy={copy} /></section>;
    case 'service':
      if (!data.service) return <section className="public-site__section"><h1>{copy.serviceDetails}</h1><p className="public-site__empty">{copy.serviceMissing}</p></section>;
      return (
        <article className="public-site__section public-site__detail">
          {data.service.category && <p className="public-site__eyebrow">{data.service.category}</p>}
          <h1>{data.service.name}</h1>
          <p className="public-site__lead">{data.service.description}</p>
          <p className="public-site__price">{formatPrice(data.service, locale, copy)}</p>
          <a className="public-site__button public-site__button--primary" href={localizePath('contacts', locale)}>{copy.contactClinic}</a>
        </article>
      );
    case 'doctor':
      if (!data.doctor) return <section className="public-site__section"><h1>{copy.doctorDetails}</h1><p className="public-site__empty">{copy.doctorMissing}</p></section>;
      return (
        <article className="public-site__section public-site__detail">
          <p className="public-site__eyebrow">{copy.doctorDetails}</p>
          <h1>{data.doctor.name}</h1>
          {data.doctor.specialty && <p className="public-site__lead">{copy.specialty}: {data.doctor.specialty}</p>}
          <p>{data.doctor.bio}</p>
          <a className="public-site__button public-site__button--primary" href={localizePath('contacts', locale)}>{copy.contactClinic}</a>
        </article>
      );
    default:
      return null;
  }
}

export function PublicSitePage({ route, data }: PublicSitePageProps) {
  const copy = COPY[route.locale];
  return (
    <div className="public-site">
      <SiteHeader locale={route.locale} route={route} copy={copy} />
      <main className="public-site__main" id="main-content">
        <PageContent route={route} data={data} copy={copy} />
      </main>
      <footer className="public-site__footer">
        <span>{data.clinic?.name || copy.clinicName}</span>
        <a href={localizePath('contacts', route.locale)}>{copy.contacts}</a>
      </footer>
    </div>
  );
}

export function PublicSiteFallback() {
  const locale: PublicSiteLocale = typeof window !== 'undefined' && window.location.pathname.startsWith('/ru')
    ? 'ru'
    : 'uz-Latn';
  const copy = COPY[locale];
  const currentUrl = typeof window === 'undefined' ? '/' : window.location.href;
  return (
    <main className="public-site__runtime-message">
      <h1>{copy.publicSiteOnly}</h1>
      <a href={currentUrl}>{copy.reloadPage}</a>
    </main>
  );
}
