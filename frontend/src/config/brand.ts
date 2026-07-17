/**
 * Единый brand config для всего приложения.
 *
 * До этого рефакторинга в проекте использовались 3 разных имени продукта:
 *   - "Система управления клиникой" (README, t('title'))
 *   - "MediClinic Pro" (Landing hero description)
 *   - "Clinic OS" (Landing liveStatus badge)
 *
 * UX Audit (cross-cutting issue 10.5) выявил, что это путает пользователя.
 * Теперь все экраны должны импортировать BRAND из этого файла.
 *
 * Usage:
 *   import { BRAND } from '../config/brand';
 *   <h1>{BRAND.name}</h1>
 *   <p>{BRAND.tagline}</p>
 *
 * Migration:
 *   - Заменить хардкоженные строки в Landing.jsx, LoginFormStyled.jsx,
 *     EMRContainerV2.jsx, footer и т.д. на BRAND.name / BRAND.shortName.
 *   - LANDING_COPY в landingContent.js может использовать BRAND как fallback.
 *
 * @type {object}
 */
export const BRAND = {
  /** Полное имя продукта для заголовков, hero, документации. */
  name: 'MediClinic Pro',
  /** Короткое имя для шапки, таб-названия, mobile-header. */
  shortName: 'Clinic OS',
  /** Подзаголовок / elevator pitch. */
  tagline: 'EMR, очередь и платежи в одном контуре',
  /** Юридическое / формальное имя. */
  legalName: 'Система управления клиникой',
  /** Категория продукта — для SEO-метатегов и schema.org. */
  category: 'Clinic management system',
  /** Путь к SVG-логотипу (должен лежать в /public/brand/). */
  logo: '/brand/logo.svg',
  /** Путь к монограмме (32×32) — для favicon и шапки. */
  logoMark: '/brand/logo-mark.svg',
  /** Email поддержки. */
  supportEmail: 'support@mediclinic.pro',
  /** Текущая версия продукта — показывается в footer и help-диалогах. */
  version: '1.0.0',
};

/**
 * Список ролей в системе (использовался в Landing hero.quickStats как метрика
 * "4 ключевые роли", но реально ролей 5 — UX Audit нашёл расхождение).
 *
 * Единственный источник истины — README перечисляет:
 * Admin, Doctor, Registrar, Lab, Cashier.
 */
export const SYSTEM_ROLES = [
  { key: 'admin', label: 'Администратор', shortLabel: 'Админ' },
  { key: 'doctor', label: 'Врач', shortLabel: 'Врач' },
  { key: 'registrar', label: 'Регистратура', shortLabel: 'Ресепшн' },
  { key: 'lab', label: 'Лаборатория', shortLabel: 'Лаба' },
  { key: 'cashier', label: 'Касса', shortLabel: 'Касса' },
];

export const SYSTEM_ROLES_COUNT = SYSTEM_ROLES.length;

export default BRAND;
