/**
 * Locales Index
 * Centralized export of all translation files
 */

import ru from './ru';
import uz from './uz';
import en from './en';

// Доступные языки
export const availableLanguages = [
    { code: 'ru', name: 'Русский', flag: '🇷🇺', nativeName: 'Русский' },
    { code: 'uz', name: 'O\'zbek', flag: '🇺🇿', nativeName: 'O\'zbekcha' },
    { code: 'en', name: 'English', flag: '🇺🇸', nativeName: 'English' },
];

// Все переводы
export const translations = {
    ru,
    uz,
    en,
};

// Получить перевод по ключу с поддержкой вложенных ключей
// Например: t('patient.myAppointments') или t('common.save')
export function getTranslation(lang, key, fallback) {
    const keys = key.split('.');
    let result = translations[lang] || translations.ru;

    for (const k of keys) {
        if (result && typeof result === 'object' && k in result) {
            result = result[k];
        } else {
            return fallback || key;
        }
    }

    return result || fallback || key;
}

// Функция для интерполяции значений в строку
// Например: interpolate('Минимум {min} символов', { min: 8 }) => 'Минимум 8 символов'
export function interpolate(str, values) {
    if (!values || typeof str !== 'string') return str;

    return str.replace(/\{(\w+)\}/g, (match, key) => {
        return values[key] !== undefined ? values[key] : match;
    });
}

export default translations;
