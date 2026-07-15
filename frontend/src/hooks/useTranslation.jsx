import { t } from '../i18n/adapter';
// Translation Context and Hook
import { createContext, useContext, useState, useEffect } from 'react';
import PropTypes from 'prop-types';
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

      // PR-44 / P0-19: extracted from PhoneVerification.jsx (demonstrates pattern)
      verificationTitle: 'Верификация телефона',
      verificationCode: 'Код подтверждения',
      sendCode: 'Отправить код',
      verifyCode: 'Подтвердить',
      resendCode: 'Отправить снова',
      codeSent: 'Код отправлен',
      verificationSuccess: 'Телефон подтвержден',
      verificationFailed: 'Ошибка верификации',

      // PR-72: Chat translations
      chatMessages: 'Сообщения',
      chatMessagesOffline: 'Сообщения (офлайн)',
      chatOpen: 'Открыть сообщения',
      chatOpenOffline: 'Открыть сообщения, офлайн',
      chatToday: 'Сегодня',
      chatYesterday: 'Вчера',
      chatTitle: 'Чат',
      chatOnline: 'Онлайн',
      chatConnecting: 'Подключение...',
      chatBack: 'Назад',
      chatSend: 'Отправить',
      chatSendError: 'Ошибка отправки сообщения',
      chatVoiceError: 'Ошибка отправки голосового сообщения: ',
      chatCopied: 'Текст скопирован',
      chatDeleteTitle: 'Удаление сообщения',
      chatDeleteConfirm: 'Удалить это сообщение у себя?',
      chatDeleteDesc: 'Сообщение будет удалено только из вашего просмотра. Другие участники увидят его.',
      chatDelete: 'Удалить',
      chatCancel: 'Отмена',
      chatDeleted: 'Сообщение удалено',
      chatDeleteError: 'Не удалось удалить сообщение',
      chatFileSent: 'Файл отправлен',
      chatFileError: 'Ошибка при загрузке файла',
      chatClose: 'Закрыть чат',
      chatNewChat: 'Новый чат',
      chatSearch: 'Поиск в переписке',
      chatSearchPlaceholder: 'Поиск...',
      chatInputPlaceholder: 'Сообщение... (Shift+Enter для новой строки)',
      chatVoiceMessage: 'Голосовое сообщение',
      chatQuickReplies: 'Быстрые ответы',
      chatUrgent: 'Пометить как срочное',
      chatUrgentRemove: 'Снять срочность',
      chatMute: 'Отключить уведомления',
      chatUnmute: 'Включить уведомления',
      chatEmptyConversation: 'Напишите первое сообщение',
      chatCopy: 'Копировать',
      chatReply: 'Ответить',
      chatAll: 'Все',
      chatUnread: 'Непрочитанные',
      chatEmployees: 'Сотрудники',
      chatPhoto: '📷 Фото',
      chatVoice: '🎤 Голосовое сообщение',
      chatFile: '📎 Файл',
      chatUrgentPrefix: '🚨 СРОЧНО: ',

      // PR-73: Lab translations (ru)
      labWaiting: 'Ожидает',
      labConfirmed: 'Подтверждён',
      labCalled: 'Вызван',
      labInProgress: 'В работе',
      labCompleted: 'Завершён',
      labDraft: 'Черновик',
      labFilling: 'Заполняется',
      labReady: 'Готов к проверке',
      labFinalized: 'Утверждён',
      labPrinted: 'Напечатан',
      labUnknown: 'Неизвестно',
      labPaymentPending: 'Не оплачено',
      labPaymentPaid: 'Оплачено',
      labPaymentPartial: 'Частично оплачено',
      labPaymentRefunded: 'Возврат',
      labPaymentCancelled: 'Отменено',
      labSpecialtyLab: 'Лаборатория',
      labSpecialtyGeneral: 'Общая очередь',
      labSeverityCritical: 'Критично',
      labSeverityFlagged: 'Есть отклонения',
      labSeverityWarning: 'Предупреждение',
      labSeverityClean: 'Без отклонений',
      labQueueTab: 'Очередь',
      labTemplatesTab: 'Шаблоны',
      labReportsTab: 'Отчёты',
      labTechnicianLabel: 'Подпись лаборанта',
      labTechnicianName: 'ФИО лаборанта',
      labApproverLabel: 'Подпись утверждающего',
      labApproverName: 'ФИО утверждающего',

      // Landing page
      title: 'MediClinic Pro',
      subtitle: t('final.app_subtitle_ru'),
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

      // PR-44 / P0-19: extracted from PhoneVerification.jsx
      verificationTitle: 'Telefonni tasdiqlash',
      verificationCode: 'Tasdiqlash kodi',
      sendCode: 'Kod yuborish',
      verifyCode: 'Tasdiqlash',
      resendCode: 'Qayta yuborish',
      codeSent: 'Kod yuborildi',
      verificationSuccess: 'Telefon tasdiqlandi',
      verificationFailed: 'Tasdiqlash xatoligi',

      // PR-72: Chat translations (uz)
      chatMessages: 'Xabarlar',
      chatMessagesOffline: 'Xabarlar (oflayn)',
      chatOpen: 'Xabarlarni ochish',
      chatOpenOffline: 'Xabarlarni ochish, oflayn',
      chatToday: 'Bugun',
      chatYesterday: 'Kecha',
      chatTitle: 'Chat',
      chatOnline: 'Onlayn',
      chatConnecting: 'Ulanmoqda...',
      chatBack: 'Orqaga',
      chatSend: 'Yuborish',
      chatSendError: 'Xabar yuborishda xatolik',
      chatVoiceError: 'Ovozli xabar yuborishda xatolik: ',
      chatCopied: 'Matn nusxalandi',
      chatDeleteTitle: 'Xabarni o\'chirish',
      chatDeleteConfirm: 'Bu xabarni o\'chirishni xohlaysizmi?',
      chatDeleteDesc: 'Xabar faqat sizning ko\'rinishingizdan o\'chiriladi.',
      chatDelete: 'O\'chirish',
      chatCancel: 'Bekor qilish',
      chatDeleted: 'Xabar o\'chirildi',
      chatDeleteError: 'Xabarni o\'chirib bo\'lmadi',
      chatFileSent: 'Fayl yuborildi',
      chatFileError: 'Fayl yuklashda xatolik',
      chatClose: 'Chatni yopish',
      chatNewChat: 'Yangi chat',
      chatSearch: 'Yozishmalarda qidirish',
      chatSearchPlaceholder: 'Qidirish...',
      chatInputPlaceholder: 'Xabar... (Shift+Enter — yangi qator)',
      chatVoiceMessage: 'Ovozli xabar',
      chatQuickReplies: 'Tezkor javoblar',
      chatUrgent: 'Shoshilinch deb belgilash',
      chatUrgentRemove: 'Shoshilinchlikni olib tashlash',
      chatMute: 'Bildirishnomalarni o\'chirish',
      chatUnmute: 'Bildirishnomalarni yoqish',
      chatEmptyConversation: 'Birinchi xabarni yozing',
      chatCopy: 'Nusxalash',
      chatReply: 'Javob berish',
      chatAll: 'Barchasi',
      chatUnread: 'O\'qilmagan',
      chatEmployees: 'Xodimlar',
      chatPhoto: '📷 Foto',
      chatVoice: '🎤 Ovozli xabar',
      chatFile: '📎 Fayl',
      chatUrgentPrefix: '🚨 SHOSHILINCH: ',

      // PR-73: Lab translations (uz)
      labWaiting: 'Kutmoqda',
      labConfirmed: 'Tasdiqlangan',
      labCalled: 'Chaqirilgan',
      labInProgress: 'Ishda',
      labCompleted: 'Tugatilgan',
      labDraft: 'Qoralama',
      labFilling: "To'ldirilmoqda",
      labReady: 'Tekshiruvga tayyor',
      labFinalized: 'Tasdiqlangan',
      labPrinted: 'Chop etilgan',
      labUnknown: 'Noma\'lum',
      labPaymentPending: 'To\'lanmagan',
      labPaymentPaid: 'To\'langan',
      labPaymentPartial: 'Qisman to\'langan',
      labPaymentRefunded: 'Qaytarish',
      labPaymentCancelled: 'Bekor qilingan',
      labSpecialtyLab: 'Laboratoriya',
      labSpecialtyGeneral: 'Umumiy navbat',
      labSeverityCritical: 'Kritik',
      labSeverityFlagged: 'Og\'ishlar bor',
      labSeverityWarning: 'Ogohlantirish',
      labSeverityClean: 'Og\'ishlar yo\'q',
      labQueueTab: 'Navbat',
      labTemplatesTab: 'Shablonlar',
      labReportsTab: 'Hisobotlar',
      labTechnicianLabel: 'Laborant imzosi',
      labTechnicianName: 'Laborant F.I.O',
      labApproverLabel: 'Tasdiqlovchi imzosi',
      labApproverName: 'Tasdiqlovchi F.I.O',

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

      // PR-44 / P0-19: extracted from PhoneVerification.jsx
      verificationTitle: 'Phone Verification',
      verificationCode: 'Verification Code',
      sendCode: 'Send Code',
      verifyCode: 'Verify',
      resendCode: 'Resend Code',
      codeSent: 'Code sent',
      verificationSuccess: 'Phone verified',
      verificationFailed: 'Verification failed',

      // PR-72: Chat translations (en)
      chatMessages: 'Messages',
      chatMessagesOffline: 'Messages (offline)',
      chatOpen: 'Open messages',
      chatOpenOffline: 'Open messages, offline',
      chatToday: 'Today',
      chatYesterday: 'Yesterday',
      chatTitle: 'Chat',
      chatOnline: 'Online',
      chatConnecting: 'Connecting...',
      chatBack: 'Back',
      chatSend: 'Send',
      chatSendError: 'Failed to send message',
      chatVoiceError: 'Failed to send voice message: ',
      chatCopied: 'Text copied',
      chatDeleteTitle: 'Delete message',
      chatDeleteConfirm: 'Delete this message for yourself?',
      chatDeleteDesc: 'The message will be deleted only from your view. Others will still see it.',
      chatDelete: 'Delete',
      chatCancel: 'Cancel',
      chatDeleted: 'Message deleted',
      chatDeleteError: 'Failed to delete message',
      chatFileSent: 'File sent',
      chatFileError: 'Error uploading file',
      chatClose: 'Close chat',
      chatNewChat: 'New chat',
      chatSearch: 'Search in conversation',
      chatSearchPlaceholder: 'Search...',
      chatInputPlaceholder: 'Message... (Shift+Enter for new line)',
      chatVoiceMessage: 'Voice message',
      chatQuickReplies: 'Quick replies',
      chatUrgent: 'Mark as urgent',
      chatUrgentRemove: 'Remove urgent',
      chatMute: 'Mute notifications',
      chatUnmute: 'Unmute notifications',
      chatEmptyConversation: 'Write first message',
      chatCopy: 'Copy',
      chatReply: 'Reply',
      chatAll: 'All',
      chatUnread: 'Unread',
      chatEmployees: 'Employees',
      chatPhoto: '📷 Photo',
      chatVoice: '🎤 Voice message',
      chatFile: '📎 File',
      chatUrgentPrefix: '🚨 URGENT: ',

      // PR-73: Lab translations (en)
      labWaiting: 'Waiting',
      labConfirmed: 'Confirmed',
      labCalled: 'Called',
      labInProgress: 'In progress',
      labCompleted: 'Completed',
      labDraft: 'Draft',
      labFilling: 'Filling',
      labReady: 'Ready for review',
      labFinalized: 'Finalized',
      labPrinted: 'Printed',
      labUnknown: 'Unknown',
      labPaymentPending: 'Unpaid',
      labPaymentPaid: 'Paid',
      labPaymentPartial: 'Partially paid',
      labPaymentRefunded: 'Refunded',
      labPaymentCancelled: 'Cancelled',
      labSpecialtyLab: 'Laboratory',
      labSpecialtyGeneral: 'General queue',
      labSeverityCritical: 'Critical',
      labSeverityFlagged: 'Has deviations',
      labSeverityWarning: 'Warning',
      labSeverityClean: 'No deviations',
      labQueueTab: 'Queue',
      labTemplatesTab: 'Templates',
      labReportsTab: 'Reports',
      labTechnicianLabel: 'Lab tech signature',
      labTechnicianName: 'Lab tech full name',
      labApproverLabel: 'Approver signature',
      labApproverName: 'Approver full name',

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


TranslationProvider.propTypes = {
  ...(TranslationProvider.propTypes || {}),
  children: PropTypes.any,
};
