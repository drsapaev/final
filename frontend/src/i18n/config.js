/**
 * STRAT#49: i18n config for react-i18next.
 *
 * Инициализирует i18next с TRANSLATIONS из labTranslations.js.
 * Подключается в main.jsx / App.jsx через: import './i18n/config';
 *
 * Когда все компоненты используют useTranslation() из react-i18next,
 * i18n/adapter.js можно заменить на: export { useTranslation } from 'react-i18next';
 */

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { TRANSLATIONS } from '../components/laboratory/utils/labTranslations';

i18n
  .use(initReactI18next)
  .init({
    resources: {
      ru: {
        translation: TRANSLATIONS,
      },
    },
    lng: 'ru',
    fallbackLng: 'ru',
    interpolation: {
      escapeValue: false,
    },
    react: {
      useSuspense: false,
    },
  });

export default i18n;
