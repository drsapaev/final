// Translation Context and Hook
import React, { createContext, useContext, useState, useEffect } from 'react';

const TranslationContext = createContext();

export const useTranslation = () => {
  const context = useContext(TranslationContext);
  if (!context) {
    throw new Error('useTranslation must be used within a TranslationProvider');
  }
  return context;
};

// Translation Provider Component
export const TranslationProvider = ({ children }) => {
  const [language, setLanguageState] = useState(() => {
    // Проверяем сохраненный язык
    const saved = localStorage.getItem('language') || localStorage.getItem('app_language');
    if (saved && ['ru', 'uz', 'en', 'kk'].includes(saved)) {
      return saved;
    }
    // По умолчанию русский
    return 'ru';
  });

  const setLanguage = (newLanguage) => {
    if (['ru', 'uz', 'en', 'kk'].includes(newLanguage)) {
      setLanguageState(newLanguage);
      localStorage.setItem('language', newLanguage);
      localStorage.setItem('app_language', newLanguage); // Для совместимости
    }
  };

  // Переводы для приложения
  const translations = {
    ru: {
      // Общие
      language: 'Язык',
      theme: 'Тема',
      login: 'Войти',
      logout: 'Выйти',
      save: 'Сохранить',
      cancel: 'Отмена',
      close: 'Закрыть',
      back: 'Назад',
      next: 'Далее',
      loading: 'Загрузка...',
      error: 'Ошибка',
      success: 'Успешно',

      // Landing page
      title: 'MediClinic Pro',
      subtitle: 'Система управления медицинской клиникой',
      loginButton: 'Войти в систему',
      activateButton: 'Активировать лицензию',
      contacts: 'Контактная информация',
      address: 'г. Ташкент, ул. Беруний',
      phone: '+998 (95) 104-34-34',
      schedule: 'Пн–Сб: 9:00–17:00',
      telegram: '@clinic_support',
      footer: 'v2.1.0 · 2025 · MediClinic Pro',

      // Темы
      lightTheme: 'Светлая тема',
      darkTheme: 'Темная тема',
      systemTheme: 'Системная тема',

      // Кнопки действий
      emergency: 'Экстренный вызов',
      diagnose: 'Диагностировать',
      treat: 'Лечение',
      approve: 'Одобрить',
      reject: 'Отклонить',
      cardiolgy: 'Кардиология',
      laboratory: 'Анализы'
    },

    uz: {
      // Общие
      language: 'Til',
      theme: 'Mavzu',
      login: 'Kirish',
      logout: 'Chiqish',
      save: 'Saqlash',
      cancel: 'Bekor qilish',
      close: 'Yopish',
      back: 'Orqaga',
      next: 'Keyingisi',
      loading: 'Yuklanmo...',
      error: 'Xatolik',
      success: 'Muvaffaqiyat',

      // Landing page
      title: 'MediClinic Pro',
      subtitle: 'Tibbiy klinikani boshqarish tizimi',
      loginButton: 'Tizimga kirish',
      activateButton: 'Litsenziyani faollashtirish',
      contacts: 'Aloqa ma\'lumotlari',
      address: 'Toshkent sh., Beruniy ko\'chasi',
      phone: '+998 (95) 104-34-34',
      schedule: 'Du–Sha: 9:00–17:00',
      telegram: '@clinic_support',
      footer: 'v2.1.0 · 2025 · MediClinic Pro',

      // Темы
      lightTheme: 'Yorqin mavzu',
      darkTheme: 'Qora mavzu',
      systemTheme: 'Tizim mavzusi',

      // Кнопки действий
      emergency: 'Favqulodda chaqiruv',
      diagnose: 'Tashxis qo\'yish',
      treat: 'Davolash',
      approve: 'Tasdiqlash',
      reject: 'Rad etish',
      cardiolgy: 'Kardiologiya',
      laboratory: 'Tahlillar'
    },

    en: {
      // Общие
      language: 'Language',
      theme: 'Theme',
      login: 'Login',
      logout: 'Logout',
      save: 'Save',
      cancel: 'Cancel',
      close: 'Close',
      back: 'Back',
      next: 'Next',
      loading: 'Loading...',
      error: 'Error',
      success: 'Success',

      // Landing page
      title: 'MediClinic Pro',
      subtitle: 'Medical Clinic Management System',
      loginButton: 'Sign In',
      activateButton: 'Activate License',
      contacts: 'Contact Information',
      address: 'Tashkent, Beruniy Street',
      phone: '+998 (95) 104-34-34',
      schedule: 'Mon–Sat: 9:00–17:00',
      telegram: '@clinic_support',
      footer: 'v2.1.0 · 2025 · MediClinic Pro',

      // Темы
      lightTheme: 'Light Theme',
      darkTheme: 'Dark Theme',
      systemTheme: 'System Theme',

      // Кнопки действий
      emergency: 'Emergency Call',
      diagnose: 'Diagnose',
      treat: 'Treat',
      approve: 'Approve',
      reject: 'Reject',
      cardiolgy: 'Cardiology',
      laboratory: 'Laboratory'
    },

    kk: {
      // Общие
      language: 'Тіл',
      theme: 'Тақырып',
      login: 'Кіру',
      logout: 'Шығу',
      save: 'Сақтау',
      cancel: 'Болдырмау',
      close: 'Жабу',
      back: 'Артқа',
      next: 'Келесі',
      loading: 'Жүктелуде...',
      error: 'Қате',
      success: 'Сәтті',

      // Landing page
      title: 'MediClinic Pro',
      subtitle: 'Медициналық клиниканы басқару жүйесі',
      loginButton: 'Жүйеге кіру',
      activateButton: 'Лицензияны белсендіру',
      contacts: 'Байланыс ақпараты',
      address: 'Ташкент қ., Беруний көшесі',
      phone: '+998 (95) 104-34-34',
      schedule: 'Дс–Сб: 9:00–17:00',
      telegram: '@clinic_support',
      footer: 'v2.1.0 · 2025 · MediClinic Pro',

      // Темы
      lightTheme: 'Жарық тақырып',
      darkTheme: 'Қараңғы тақырып',
      systemTheme: 'Жүйе тақырыбы',

      // Кнопки действий
      emergency: 'Төтенше шақыру',
      diagnose: 'Диагноз қою',
      treat: 'Емдеу',
      approve: 'Мақұлдау',
      reject: 'Бас тарту',
      cardiolgy: 'Кардиология',
      laboratory: 'Зертханалық талдаулар'
    }
  };

  const t = (key, fallback = key) => {
    return translations[language]?.[key] || fallback;
  };

  // Сохраняем язык в localStorage при изменении
  useEffect(() => {
    localStorage.setItem('language', language);
    localStorage.setItem('app_language', language);
  }, [language]);

  const value = {
    language,
    setLanguage,
    t,
    translations: translations[language] || translations.ru,
    availableLanguages: [
      { code: 'ru', name: 'Русский', flag: '🇷🇺' },
      { code: 'uz', name: 'O\'zbek', flag: '🇺🇿' },
      { code: 'en', name: 'English', flag: '🇺🇸' },
      { code: 'kk', name: 'Қазақ', flag: '🇰🇿' }
    ]
  };

  return (
    <TranslationContext.Provider value={value}>
      {children}
    </TranslationContext.Provider>
  );
};
