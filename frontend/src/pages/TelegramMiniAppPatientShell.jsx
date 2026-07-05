import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Alert, Badge, Button, Card, CardContent, Input, Textarea,
} from '../components/ui/macos';
import { api } from '../api/client.js';

const MINI_APP_LANGUAGE_RU = 'ru';
const MINI_APP_LANGUAGE_UZ = 'uz-Latn';

const MINI_APP_I18N = {
  [MINI_APP_LANGUAGE_RU]: {
    title: 'Mini App пациента',
    sessionReady: 'Сессия подтверждена',
    sessionWaiting: 'Ожидание сессии',
    statusLoading: 'Загрузка статуса...',
    sessionUnavailable: 'Сессия Telegram недоступна. Данные пациента не загружаются.',
    sessionUnavailableBadge: 'Сессия недоступна',
    openFromTelegram: 'Откройте из Telegram',
    openSection: 'Открытый раздел',
    available: 'Сервис доступен',
    statusOnly: 'Только статус',
    patient: 'Пациент',
    patientFallback: 'Пациент',
    accessConfirmed: 'Доступ подтверждён',
    visits: 'Визиты',
    queue: 'Очередь',
    debt: 'Долг',
    results: 'Результаты',
    cabinetLoading: 'Кабинет пациента загружается...',
    cabinetLoadFailed: 'Кабинет пациента не загрузился. Откройте ссылку заново из Telegram.',
    formsLoadFailed: 'Анкеты пациента не загрузились. Откройте ссылку заново из Telegram.',
    documentsLoadFailed: 'Документы пациента не загрузились. Откройте ссылку заново из Telegram.',
    visitsLoading: 'Визиты и записи загружаются...',
    visitsLoadFailed: 'Визиты пациента не загрузились. Откройте ссылку заново из Telegram.',
    queueLoading: 'Очередь пациента загружается...',
    queueLoadFailed: 'Очередь пациента не загрузилась. Откройте ссылку заново из Telegram.',
    sessionNotConfirmed: 'Сессия Mini App не подтверждена',
    sessionExpired: 'Ссылка устарела. Откройте Mini App заново из Telegram',
    appointmentDateRequired: 'Укажите дату и откройте Mini App из Telegram.',
    appointmentPreviewFailed: 'Черновик записи не подтвержден: {reason}',
    appointmentCreateFailed: 'Заявка на запись не создана: {reason}',
    appointmentPrecheck: 'Предварительная проверка',
    appointmentDraft: 'Черновик записи',
    appointmentRequest: 'Заявка',
    appointmentRequestNote: 'После отправки создается только заявка на запись. Визит, очередь и оплата не создаются автоматически.',
    confirmAppointmentRequest: 'Отправить заявку',
    appointmentCreating: 'Заявка отправляется...',
    appointmentRequestCreated: 'Заявка на запись создана. Номер записи: #{appointmentId}. Регистратура подтвердит детали.',
    appointmentRequestCreatedNoId: 'Заявка на запись создана. Регистратура подтвердит детали.',
    onboardingKicker: 'REQUEST REVIEW',
    onboardingTitle: 'Заявка на запись',
    onboardingIntro: 'Если карты пациента ещё нет или Telegram не привязан, отправьте безопасную заявку. Регистратура проверит данные и вручную свяжет её с картой пациента.',
    onboardingPrivacy: 'Не отправляйте диагнозы, результаты анализов и медицинские документы. Здесь нужны только контакт и желаемые детали записи.',
    onboardingBlockedTitle: 'Нужна проверка регистратуры',
    onboardingBlockedText: 'Этот раздел откроется после того, как регистратура свяжет Telegram с картой пациента. Сейчас можно оставить заявку на запись.',
    onboardingOpenAppointments: 'Перейти к заявке',
    contactName: 'Имя',
    contactPhone: 'Телефон',
    desiredService: 'Услуга или направление',
    desiredBranch: 'Филиал',
    onboardingSubmit: 'Отправить заявку',
    onboardingSubmitting: 'Заявка отправляется...',
    onboardingSubmitted: 'Заявка отправлена. Регистратура проверит её и свяжет Telegram с картой пациента.',
    onboardingRequestFailed: 'Заявка не отправлена. Проверьте ссылку из Telegram и попробуйте ещё раз.',
    onboardingSummaryTitle: 'Данные заявки',
    onboardingReviewMessageTitle: 'Сообщение регистратуры',
    onboardingNextStepTitle: 'Что будет дальше',
    onboardingRetry: 'Проверить снова',
    onboardingSupport: 'Связаться с клиникой',
    onboardingUpdateRequest: 'Обновить заявку',
    onboardingReopenFromTelegram: 'Вернуться в Telegram',
    onboardingStatusTitle: 'Статус заявки',
    onboardingStatus: {
      not_found: 'Заявка ещё не отправлена.',
      pending_review: 'Заявка ожидает проверки регистратурой.',
      needs_more_info: 'Регистратуре нужны дополнительные сведения. Обновите заявку или свяжитесь с клиникой.',
      linked_existing: 'Заявка связана с существующей картой пациента. Откройте защищённый кабинет из Telegram.',
      created_patient: 'Карта пациента создана сотрудником. Откройте защищённый кабинет из Telegram.',
      rejected: 'Заявка отклонена. Свяжитесь с регистратурой для уточнения.',
      cancelled: 'Заявка отменена.',
      expired: 'Срок заявки истёк. Отправьте новую заявку или свяжитесь с регистратурой.',
    },
    onboardingNextStep: {
      not_found: 'Заполните безопасные контактные данные и отправьте заявку на запись.',
      pending_review: 'Регистратура проверит контакт и вручную свяжет Telegram с картой пациента.',
      needs_more_info: 'Обновите безопасные данные в заявке ниже или свяжитесь с клиникой.',
      linked_existing: 'Откройте защищённый кабинет заново из Telegram после подтверждения регистратуры.',
      created_patient: 'Откройте защищённый кабинет заново из Telegram после создания карты пациента.',
      rejected: 'Исправьте данные в новой заявке ниже или свяжитесь с клиникой для уточнения.',
      cancelled: 'Когда будете готовы, отправьте новую заявку или свяжитесь с клиникой.',
      expired: 'Отправьте новую заявку ниже или свяжитесь с регистратурой, если нужна помощь.',
    },
    date: 'Дата',
    time: 'Время',
    department: 'Отделение',
    departmentMissing: 'Отделение не указано',
    dateMissing: 'Дата не указана',
    cabinet: 'Кабинет',
    cabinetMissing: 'Кабинет не указан',
    optional: 'Опционально',
    registrarNote: 'Заметка для регистратуры',
    noMedicalData: 'Без медицинских данных',
    checkDraft: 'Проверить черновик',
    dateTime: 'Дата и время',
    timeMissing: 'время не указано',
    status: 'Статус',
    payment: 'Оплата',
    previewOnly: 'Только предпросмотр',
    needsCheck: 'Требует проверки',
    formsLoading: 'Анкеты пациента загружаются...',
    formsEmpty: 'Сейчас нет доступных анкет для заполнения.',
    patientForm: 'Анкета пациента',
    saved: 'Сохранена',
    new: 'Новая',
    formOpenAgain: 'Откройте анкету заново из Telegram.',
    formNotSaved: 'Анкета не сохранена: {reason}',
    formSaved: 'Анкета сохранена.',
    saveForm: 'Сохранить анкету',
    documentsLoading: 'Документы пациента загружаются...',
    documentsEmpty: 'Готовые PDF-результаты пока не найдены.',
    documents: 'Документы',
    readyPdfResults: 'Готовые PDF-результаты',
    readyDateMissing: 'Дата готовности не указана',
    getPdf: 'Получить PDF',
    documentsOpenAgain: 'Откройте документы заново из Telegram.',
    documentFailed: 'Документ не получен: {reason}',
    paymentsLoading: 'Оплаты и долг загружаются...',
    paymentsLoadFailed: 'Оплаты пациента не загрузились. Откройте ссылку заново из Telegram.',
    paymentsTitle: 'Оплаты и долг',
    billed: 'Начислено',
    paid: 'Оплачено',
    pending: 'Ожидает подтверждения',
    linkedVisits: 'Связанные визиты',
    activeQueue: 'Активная очередь',
    queueTitle: 'Моя очередь',
    queueNumber: 'Номер очереди',
    queueStatus: 'Статус очереди',
    queueInactive: 'Нет активной очереди',
    queueEmpty: 'На сегодня активной очереди нет.',
    queueEmptyRecovery: 'Если вы записаны или ожидаете очередь, обратитесь в регистратуру или откройте ссылку заново из Telegram.',
    queueEntries: 'Записи очереди',
    queuePrivacyNote: 'В Telegram показываются только номер очереди, кабинет и статус. Очередь не меняется из Mini App.',
    visitsTitle: 'Мои визиты',
    appointmentRequests: 'Заявки на запись',
    recentVisits: 'Последние визиты',
    appointmentsEmpty: 'Активных заявок на запись пока нет.',
    visitsEmpty: 'Последних визитов пока нет.',
    visitNumber: 'Визит #{id}',
    appointmentNumber: 'Запись #{id}',
    visitsPrivacyNote: 'В Telegram показываются только номер, дата, отделение и статус. Медицинские детали остаются в защищенной системе клиники.',
    currencySuffix: 'сум',
    onlinePaymentUnavailable: 'Онлайн-оплата пока не подключена. Для оплаты обратитесь в кассу клиники.',
    protectedPaymentNote: 'В Telegram не показываются номера счетов и платежей. Подробности доступны только в защищённом кабинете клиники.',
    capabilityStatus: {
      manifest_only: 'Статус из manifest',
      preview_enabled: 'Доступен предпросмотр',
      request_review_enabled: 'Заявка через регистратуру',
      staff_approval_required: 'Нужна проверка регистратуры',
      summary_enabled: 'Доступна сводка',
      ready_pdf_list_enabled: 'Доступны готовые PDF',
    },
    capabilities: {
      appointments: 'Запись',
      visits: 'Визиты',
      queue: 'Очередь',
      forms: 'Анкеты',
      cabinet: 'Кабинет',
      payments: 'Оплаты',
      results: 'Результаты',
    },
    forms: {
      patient_intake: {
        title: 'Анкета перед визитом',
        description: 'Короткие данные для подготовки регистратуры и врача.',
        fields: {
          chief_complaint: 'Причина визита',
          allergies: 'Аллергии',
          current_medications: 'Текущие лекарства',
          medical_history: 'Важная медицинская история',
          consent_to_contact: 'Разрешаю клинике связаться со мной',
        },
      },
    },
  },
  [MINI_APP_LANGUAGE_UZ]: {
    title: 'Bemor Mini App',
    sessionReady: 'Sessiya tasdiqlandi',
    sessionWaiting: 'Sessiya kutilmoqda',
    statusLoading: 'Holat yuklanmoqda...',
    sessionUnavailable: 'Telegram sessiyasi mavjud emas. Bemor maʼlumotlari yuklanmaydi.',
    sessionUnavailableBadge: 'Sessiya mavjud emas',
    openFromTelegram: 'Telegramdan oching',
    openSection: 'Ochiq bo\'lim',
    available: 'Xizmat mavjud',
    statusOnly: 'Faqat holat',
    patient: 'Bemor',
    patientFallback: 'Bemor',
    accessConfirmed: 'Kirish tasdiqlandi',
    visits: 'Tashriflar',
    queue: 'Navbat',
    debt: 'Qarz',
    results: 'Natijalar',
    cabinetLoading: 'Bemor kabineti yuklanmoqda...',
    cabinetLoadFailed: 'Bemor kabineti yuklanmadi. Havolani Telegramdan qayta oching.',
    formsLoadFailed: 'Bemor anketalari yuklanmadi. Havolani Telegramdan qayta oching.',
    documentsLoadFailed: 'Bemor hujjatlari yuklanmadi. Havolani Telegramdan qayta oching.',
    visitsLoading: 'Tashriflar va yozilishlar yuklanmoqda...',
    visitsLoadFailed: 'Bemor tashriflari yuklanmadi. Havolani Telegramdan qayta oching.',
    queueLoading: 'Bemor navbati yuklanmoqda...',
    queueLoadFailed: 'Bemor navbati yuklanmadi. Havolani Telegramdan qayta oching.',
    sessionNotConfirmed: 'Mini App sessiyasi tasdiqlanmadi',
    sessionExpired: 'Havola eskirgan. Mini Appni Telegramdan qayta oching',
    appointmentDateRequired: 'Sanani kiriting va Mini Appni Telegramdan oching.',
    appointmentPreviewFailed: 'Yozilish qoralamasi tasdiqlanmadi: {reason}',
    appointmentCreateFailed: 'Yozilish so\'rovi yaratilmadi: {reason}',
    appointmentPrecheck: 'Oldindan tekshirish',
    appointmentDraft: 'Yozilish qoralamasi',
    appointmentRequest: 'So\'rov',
    appointmentRequestNote: 'Yuborilganda faqat yozilish so\'rovi yaratiladi. Tashrif, navbat va to\'lov avtomatik yaratilmaydi.',
    confirmAppointmentRequest: 'Yozilish so\'rovini yuborish',
    appointmentCreating: 'So\'rov yuborilmoqda...',
    appointmentRequestCreated: 'Yozilish so\'rovi yaratildi. Yozuv raqami: #{appointmentId}. Registratura ma\'lumotlarni tasdiqlaydi.',
    appointmentRequestCreatedNoId: 'Yozilish so\'rovi yaratildi. Registratura ma\'lumotlarni tasdiqlaydi.',
    onboardingKicker: 'REQUEST REVIEW',
    onboardingTitle: 'Qabul uchun so\'rov',
    onboardingIntro: 'Agar bemor kartasi hali yo\'q yoki Telegram bog\'lanmagan bo\'lsa, xavfsiz so\'rov yuboring. Registratura ma\'lumotlarni tekshiradi va uni bemor kartasiga qo\'lda bog\'laydi.',
    onboardingPrivacy: 'Diagnoz, tahlil natijalari va tibbiy hujjatlarni yubormang. Bu yerda faqat aloqa va qabul uchun kerakli tafsilotlar so\'raladi.',
    onboardingBlockedTitle: 'Registratura tekshiruvi kerak',
    onboardingBlockedText: 'Bu bo\'lim Telegram bemor kartasiga bog\'langandan keyin ochiladi. Hozir qabul uchun so\'rov qoldirishingiz mumkin.',
    onboardingOpenAppointments: 'So\'rovga o\'tish',
    contactName: 'Ism',
    contactPhone: 'Telefon',
    desiredService: 'Xizmat yoki yo\'nalish',
    desiredBranch: 'Filial',
    onboardingSubmit: 'So\'rov yuborish',
    onboardingSubmitting: 'So\'rov yuborilmoqda...',
    onboardingSubmitted: 'So\'rov yuborildi. Registratura uni tekshiradi va Telegramni bemor kartasiga bog\'laydi.',
    onboardingRequestFailed: 'So\'rov yuborilmadi. Telegram havolasini tekshiring va qayta urinib ko\'ring.',
    onboardingSummaryTitle: 'So\'rov ma\'lumotlari',
    onboardingReviewMessageTitle: 'Registratura xabari',
    onboardingNextStepTitle: 'Keyingi qadam',
    onboardingRetry: 'Qayta tekshirish',
    onboardingSupport: 'Klinika bilan bog\'lanish',
    onboardingUpdateRequest: 'So\'rovni yangilash',
    onboardingReopenFromTelegram: 'Telegramga qaytish',
    onboardingStatusTitle: 'So\'rov holati',
    onboardingStatus: {
      not_found: 'So\'rov hali yuborilmagan.',
      pending_review: 'So\'rov registratura tekshiruvini kutmoqda.',
      needs_more_info: 'Registraturaga qo\'shimcha ma\'lumot kerak. So\'rovni yangilang yoki klinika bilan bog\'laning.',
      linked_existing: 'So\'rov mavjud bemor kartasiga bog\'landi. Himoyalangan kabinetni Telegramdan oching.',
      created_patient: 'Bemor kartasi xodim tomonidan yaratildi. Himoyalangan kabinetni Telegramdan oching.',
      rejected: 'So\'rov rad etildi. Aniqlashtirish uchun registraturaga murojaat qiling.',
      cancelled: 'So\'rov bekor qilindi.',
      expired: 'So\'rov muddati tugadi. Yangi so\'rov yuboring yoki registraturaga murojaat qiling.',
    },
    onboardingNextStep: {
      not_found: 'Xavfsiz aloqa ma\'lumotlarini to\'ldirib, qabul uchun so\'rov yuboring.',
      pending_review: 'Registratura aloqani tekshiradi va Telegramni bemor kartasiga qo\'lda bog\'laydi.',
      needs_more_info: 'Quyidagi xavfsiz ma\'lumotlarni yangilang yoki klinika bilan bog\'laning.',
      linked_existing: 'Registratura tasdiqlagandan keyin himoyalangan kabinetni Telegramdan qayta oching.',
      created_patient: 'Bemor kartasi yaratilgach, himoyalangan kabinetni Telegramdan qayta oching.',
      rejected: 'Quyidagi yangi so\'rovda ma\'lumotlarni tuzating yoki aniqlik uchun klinika bilan bog\'laning.',
      cancelled: 'Tayyor bo\'lsangiz, yangi so\'rov yuboring yoki klinika bilan bog\'laning.',
      expired: 'Quyida yangi so\'rov yuboring yoki yordam kerak bo\'lsa registraturaga murojaat qiling.',
    },
    date: 'Sana',
    time: 'Vaqt',
    department: 'Bo\'lim',
    departmentMissing: 'Bo\'lim ko\'rsatilmagan',
    dateMissing: 'Sana ko\'rsatilmagan',
    cabinet: 'Kabinet',
    cabinetMissing: 'Kabinet ko\'rsatilmagan',
    optional: 'Ixtiyoriy',
    registrarNote: 'Registratura uchun izoh',
    noMedicalData: 'Tibbiy maʼlumotlarsiz',
    checkDraft: 'Qoralamani tekshirish',
    dateTime: 'Sana va vaqt',
    timeMissing: 'vaqt ko\'rsatilmagan',
    status: 'Holat',
    payment: 'To\'lov',
    previewOnly: 'Faqat ko\'rish',
    needsCheck: 'Tekshiruv kerak',
    formsLoading: 'Bemor anketalari yuklanmoqda...',
    formsEmpty: 'Hozircha to\'ldirish uchun anketa yo\'q.',
    patientForm: 'Bemor anketasi',
    saved: 'Saqlangan',
    new: 'Yangi',
    formOpenAgain: 'Anketani Telegramdan qayta oching.',
    formNotSaved: 'Anketa saqlanmadi: {reason}',
    formSaved: 'Anketa saqlandi.',
    saveForm: 'Anketani saqlash',
    documentsLoading: 'Bemor hujjatlari yuklanmoqda...',
    documentsEmpty: 'Tayyor PDF-natijalar hozircha topilmadi.',
    documents: 'Hujjatlar',
    readyPdfResults: 'Tayyor PDF-natijalar',
    readyDateMissing: 'Tayyor bo\'lgan sana ko\'rsatilmagan',
    getPdf: 'PDF olish',
    documentsOpenAgain: 'Hujjatlarni Telegramdan qayta oching.',
    documentFailed: 'Hujjat olinmadi: {reason}',
    paymentsLoading: 'To\'lovlar va qarz yuklanmoqda...',
    paymentsLoadFailed: 'Bemor to\'lovlari yuklanmadi. Havolani Telegramdan qayta oching.',
    paymentsTitle: 'To\'lovlar va qarz',
    billed: 'Hisoblangan',
    paid: 'To\'langan',
    pending: 'Tasdiqlanishi kutilmoqda',
    linkedVisits: 'Bog\'langan tashriflar',
    activeQueue: 'Faol navbat',
    queueTitle: 'Mening navbatim',
    queueNumber: 'Navbat raqami',
    queueStatus: 'Navbat holati',
    queueInactive: 'Faol navbat yo\'q',
    queueEmpty: 'Bugun faol navbat yo\'q.',
    queueEmptyRecovery: 'Agar siz yozilgan bo\'lsangiz yoki navbat kutayotgan bo\'lsangiz, registraturaga murojaat qiling yoki havolani Telegramdan qayta oching.',
    queueEntries: 'Navbat yozuvlari',
    queuePrivacyNote: 'Telegramda faqat navbat raqami, kabinet va holat ko\'rsatiladi. Mini App navbatni o\'zgartirmaydi.',
    visitsTitle: 'Mening tashriflarim',
    appointmentRequests: 'Yozilish so\'rovlari',
    recentVisits: 'So\'nggi tashriflar',
    appointmentsEmpty: 'Faol yozilish so\'rovlari hozircha yo\'q.',
    visitsEmpty: 'So\'nggi tashriflar hozircha yo\'q.',
    visitNumber: 'Tashrif #{id}',
    appointmentNumber: 'Yozuv #{id}',
    visitsPrivacyNote: 'Telegramda faqat raqam, sana, bo\'lim va holat ko\'rsatiladi. Tibbiy tafsilotlar klinikaning himoyalangan tizimida qoladi.',
    currencySuffix: 'so\'m',
    onlinePaymentUnavailable: 'Onlayn to\'lov hozircha ulanmagan. To\'lov uchun klinika kassasiga murojaat qiling.',
    protectedPaymentNote: 'Telegramda hisob va to\'lov raqamlari ko\'rsatilmaydi. Tafsilotlar faqat klinikaning himoyalangan kabinetida ochiladi.',
    capabilityStatus: {
      manifest_only: 'Manifest holati',
      preview_enabled: 'Oldindan ko\'rish mavjud',
      request_review_enabled: 'Registratura orqali so\'rov',
      staff_approval_required: 'Registratura tekshiruvi kerak',
      summary_enabled: 'Qisqa maʼlumot mavjud',
      ready_pdf_list_enabled: 'Tayyor PDFlar mavjud',
    },
    capabilities: {
      appointments: 'Yozilish',
      visits: 'Tashriflar',
      queue: 'Navbat',
      forms: 'Anketalar',
      cabinet: 'Kabinet',
      payments: 'To\'lovlar',
      results: 'Natijalar',
    },
    forms: {
      patient_intake: {
        title: 'Tashrifdan oldingi anketa',
        description: 'Registratura va shifokor tayyorlanishi uchun qisqa maʼlumotlar.',
        fields: {
          chief_complaint: 'Tashrif sababi',
          allergies: 'Allergiyalar',
          current_medications: 'Hozir qabul qilayotgan dorilar',
          medical_history: 'Muhim tibbiy tarix',
          consent_to_contact: 'Klinika men bilan bog\'lanishiga roziman',
        },
      },
    },
  },
};

const MINI_APP_SECTION_ALIASES = {
  appointments: 'appointments',
  doctors: 'appointments',
  visits: 'visits',
  queue: 'queue',
  navbat: 'queue',
  forms: 'forms',
  cabinet: 'cabinet',
  payments: 'payments',
  results: 'results',
  documents: 'results',
};

const MINI_APP_EXPIRED_ENTRY_TOKEN_REASONS = new Set(['entry_token_invalid', 'entry_token_expired']);
const MINI_APP_HANDLED_ERROR_REQUEST_CONFIG = {
  silent: true,
  expectedErrorStatuses: [400, 403, 503],
};
const MINI_APP_TELEMETRY_REQUEST_CONFIG = {
  silent: true,
  expectedErrorStatuses: [400, 404, 422, 503],
};
const MINI_APP_ONBOARDING_STATUS_EVENTS = {
  pending_review: 'patient_onboarding_pending_review',
  needs_more_info: 'patient_onboarding_needs_more_info',
  linked_existing: 'patient_onboarding_linked_existing',
  created_patient: 'patient_onboarding_created_patient',
  rejected: 'patient_onboarding_rejected',
  expired: 'patient_onboarding_expired',
};
const MINI_APP_ERROR_ALERT_PROPS = {
  role: 'alert',
  'aria-live': 'assertive',
};
const MINI_APP_STATUS_ALERT_PROPS = {
  role: 'status',
  'aria-live': 'polite',
};
const MINI_APP_SUPPORT_TG_URL = 'https://t.me/clinic_support';

function getMiniAppOnboardingValue(request, camelKey, snakeKey, fallback = '') {
  if (!request || typeof request !== 'object') {
    return fallback;
  }
  if (request[camelKey] != null && request[camelKey] !== '') {
    return request[camelKey];
  }
  if (request[snakeKey] != null && request[snakeKey] !== '') {
    return request[snakeKey];
  }
  return fallback;
}

function canEditMiniAppOnboardingRequest(status) {
  return ['not_found', 'needs_more_info', 'rejected', 'cancelled', 'expired'].includes(status);
}

function shouldShowMiniAppOnboardingSummary(status) {
  return status !== 'not_found';
}

function getTelegramMiniAppInitData() {
  if (typeof window === 'undefined') {
    return '';
  }

  return window.Telegram?.WebApp?.initData || '';
}

function getTelegramMiniAppEntryToken(search) {
  const token = new URLSearchParams(search || '').get('entryToken') || '';
  return token.trim();
}

function getTelegramMiniAppEntryTokenSection(search) {
  const token = getTelegramMiniAppEntryToken(search);
  const tokenSection = token.split('_')[1] || '';
  return MINI_APP_SECTION_ALIASES[tokenSection.trim().toLowerCase()] || '';
}

function getTelegramMiniAppAuthPayload(search, section) {
  const initData = getTelegramMiniAppInitData();
  const selectedSection = section || getTelegramMiniAppSelectedSection(search);
  if (initData) {
    return {
      initData,
      section: selectedSection || undefined,
    };
  }

  const entryToken = getTelegramMiniAppEntryToken(search);
  if (entryToken) {
    const tokenSection = getTelegramMiniAppEntryTokenSection(search);
    return {
      entryToken,
      // Local HTTP fallback tokens are signed for the entry section. Keep auth
      // pinned to that section while the Mini App UI switches panels.
      section: tokenSection || selectedSection || undefined,
    };
  }

  return null;
}

function getTelegramMiniAppSelectedSection(search) {
  const section = new URLSearchParams(search || '').get('section') || '';
  return MINI_APP_SECTION_ALIASES[section.trim().toLowerCase()] || '';
}

function normalizeMiniAppLanguage(languageCode) {
  const value = String(languageCode || '').trim().toLowerCase().replace('_', '-');
  return value.startsWith('uz') ? MINI_APP_LANGUAGE_UZ : MINI_APP_LANGUAGE_RU;
}

function getTelegramMiniAppClientLanguage() {
  if (typeof window === 'undefined') {
    return MINI_APP_LANGUAGE_RU;
  }
  return window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code || MINI_APP_LANGUAGE_RU;
}

function getNestedMiniAppTranslation(dictionary, key) {
  return key.split('.').reduce((value, segment) => (
    value && Object.prototype.hasOwnProperty.call(value, segment)
      ? value[segment]
      : undefined
  ), dictionary);
}

function translateMiniAppText(languageCode, key, params = {}) {
  const language = normalizeMiniAppLanguage(languageCode);
  const dictionary = MINI_APP_I18N[language] || MINI_APP_I18N[MINI_APP_LANGUAGE_RU];
  const fallbackDictionary = MINI_APP_I18N[MINI_APP_LANGUAGE_RU];
  const template = getNestedMiniAppTranslation(dictionary, key)
    ?? getNestedMiniAppTranslation(fallbackDictionary, key)
    ?? key;
  return String(template).replace(/\{(\w+)\}/g, (_, paramKey) => (
    params[paramKey] == null ? '' : String(params[paramKey])
  ));
}

function localizeMiniAppCapabilityStatus(languageCode, status) {
  const key = status || 'manifest_only';
  const translated = translateMiniAppText(languageCode, `capabilityStatus.${key}`);
  return translated === `capabilityStatus.${key}` ? key : translated;
}

function localizeMiniAppPatientForm(languageCode, form) {
  const formTranslations = MINI_APP_I18N[normalizeMiniAppLanguage(languageCode)]?.forms?.[form.id]
    || MINI_APP_I18N[MINI_APP_LANGUAGE_RU].forms?.[form.id]
    || {};
  return {
    ...form,
    title: formTranslations.title || form.title,
    description: formTranslations.description || form.description,
    fields: (form.fields || []).map((field) => ({
      ...field,
      label: formTranslations.fields?.[field.key] || field.label,
    })),
  };
}

function formatMiniAppMoney(languageCode, value) {
  const amount = String(value == null || value === '' ? '0' : value).trim();
  const suffix = translateMiniAppText(languageCode, 'currencySuffix');
  return /\b(сум|so'?m)\b/i.test(amount) ? amount : `${amount} ${suffix}`;
}

function getDefaultMiniAppAppointmentDate() {
  const nextDay = new Date();
  nextDay.setDate(nextDay.getDate() + 1);
  const year = nextDay.getFullYear();
  const month = String(nextDay.getMonth() + 1).padStart(2, '0');
  const day = String(nextDay.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function createMiniAppAppointmentPreviewForm() {
  return {
    contactName: '',
    contactPhone: '',
    desiredService: '',
    desiredBranch: '',
    appointmentDate: getDefaultMiniAppAppointmentDate(),
    appointmentTime: '09:30',
    department: '',
    notes: '',
  };
}

function buildMiniAppAppointmentRequestBody(authPayload, form) {
  return {
    ...authPayload,
    appointmentDate: form.appointmentDate,
    appointmentTime: form.appointmentTime || undefined,
    department: form.department.trim() || undefined,
    notes: form.notes.trim() || undefined,
  };
}

function buildMiniAppOnboardingRequestBody(authPayload, form, languageCode) {
  return {
    ...authPayload,
    languageCode,
    contactName: form.contactName.trim() || undefined,
    contactPhone: form.contactPhone.trim() || undefined,
    desiredService: form.desiredService.trim() || form.department.trim() || undefined,
    desiredBranch: form.desiredBranch.trim() || undefined,
    desiredDate: form.appointmentDate || undefined,
    desiredTime: form.appointmentTime || undefined,
    note: form.notes.trim() || undefined,
  };
}

function hydrateMiniAppAppointmentFormFromOnboardingRequest(form, request) {
  if (!request) {
    return form;
  }

  return {
    ...form,
    contactName: form.contactName || getMiniAppOnboardingValue(request, 'contactName', 'contact_name', ''),
    contactPhone: form.contactPhone || getMiniAppOnboardingValue(request, 'contactPhone', 'contact_phone', ''),
    desiredService: form.desiredService || getMiniAppOnboardingValue(request, 'desiredService', 'desired_service', ''),
    desiredBranch: form.desiredBranch || getMiniAppOnboardingValue(request, 'desiredBranch', 'desired_branch', ''),
    appointmentDate: form.appointmentDate || getMiniAppOnboardingValue(request, 'desiredDate', 'desired_date', ''),
    appointmentTime: form.appointmentTime || getMiniAppOnboardingValue(request, 'desiredTime', 'desired_time', ''),
    notes: form.notes || getMiniAppOnboardingValue(request, 'note', 'note', ''),
  };
}

function getMiniAppTelemetryReasonCode(reasonCode) {
  const value = String(reasonCode || '').trim().toLowerCase();
  if (!/^[a-z0-9_:-]{1,64}$/.test(value)) {
    return null;
  }
  return value;
}

function emitMiniAppOnboardingTelemetry(event, meta = {}) {
  const section = MINI_APP_SECTION_ALIASES[String(meta.section || '').trim().toLowerCase()]
    || 'appointments';
  const payloadMeta = {
    role: 'patient',
    scope: 'onboarding',
    section,
    language: normalizeMiniAppLanguage(meta.language),
    success: meta.success !== false,
    reason_code: getMiniAppTelemetryReasonCode(meta.reason_code),
    timestamp: new Date().toISOString(),
  };

  api.post('/telemetry', {
    events: [
      {
        event,
        entity: 'telegram_mini_app',
        timestamp: Date.now(),
        meta: payloadMeta,
      },
    ],
  }, MINI_APP_TELEMETRY_REQUEST_CONFIG).catch(() => {});
}

function emitMiniAppOnboardingStatusTelemetry(status, meta = {}) {
  const event = MINI_APP_ONBOARDING_STATUS_EVENTS[status];
  if (!event) {
    return;
  }
  emitMiniAppOnboardingTelemetry(event, {
    ...meta,
    reason_code: status,
  });
}

function getMiniAppApiErrorReason(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') {
    return detail;
  }
  if (detail && typeof detail.reason === 'string') {
    return detail.reason;
  }
  const reason = error?.response?.data?.reason;
  return typeof reason === 'string' ? reason : fallback;
}

function getMiniAppPatientSessionErrorMessage(error, languageCode) {
  const reason = getMiniAppApiErrorReason(error, 'session_not_confirmed');
  if (MINI_APP_EXPIRED_ENTRY_TOKEN_REASONS.has(reason)) {
    return translateMiniAppText(languageCode, 'sessionExpired');
  }
  return translateMiniAppText(languageCode, 'sessionNotConfirmed');
}

function getMiniAppStatusBadge(status, languageCode) {
  switch (status) {
    case 'ready':
      return { variant: 'success', label: translateMiniAppText(languageCode, 'sessionReady') };
    case 'error':
      return { variant: 'danger', label: translateMiniAppText(languageCode, 'sessionUnavailableBadge') };
    case 'unavailable':
      return { variant: 'secondary', label: translateMiniAppText(languageCode, 'openFromTelegram') };
    case 'checking':
    default:
      return { variant: 'secondary', label: translateMiniAppText(languageCode, 'sessionWaiting') };
  }
}

function isMiniAppCapabilityEnabled(capability) {
  return Boolean(
    capability?.create_enabled ||
    capability?.preview_enabled ||
    capability?.onboarding_request_enabled ||
    capability?.read_enabled ||
    capability?.view_enabled ||
    capability?.capture_enabled ||
    capability?.payment_capture_enabled
  );
}

function notifyTelegramMiniAppReady() {
  if (typeof window === 'undefined') {
    return;
  }

  const webApp = window.Telegram?.WebApp;
  if (!webApp) {
    return;
  }

  try {
    webApp.ready?.();
    webApp.expand?.();
  } catch {
    // Telegram WebApp helpers are best-effort browser hints.
  }
}

function getMiniAppFormsInitialAnswers(forms = []) {
  return forms.reduce((acc, form) => {
    acc[form.id] = form.submission?.answers || {};
    return acc;
  }, {});
}

function getMiniAppFormFieldValue(answers, formId, field) {
  const value = answers?.[formId]?.[field.key];
  if (field.type === 'boolean') {
    return Boolean(value);
  }
  return value == null ? '' : String(value);
}

function getMiniAppReportFileName(report) {
  const safeName = String(report?.name || `report-${report?.id || 'result'}`)
    .trim()
    .replace(/[\\/:*?"<>|]+/g, '-')
    .slice(0, 80);
  return `${safeName || 'report'}.pdf`;
}

function TelegramMiniAppPatientShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const selectedSection = getTelegramMiniAppSelectedSection(location.search);
  const [state, setState] = useState({
    status: 'checking',
    manifest: null,
    error: null,
  });
  const [appointmentPreviewForm, setAppointmentPreviewForm] = useState(createMiniAppAppointmentPreviewForm);
  const [appointmentPreview, setAppointmentPreview] = useState({
    status: 'idle',
    payload: null,
    error: null,
  });
  const [appointmentCreate, setAppointmentCreate] = useState({
    status: 'idle',
    payload: null,
    error: null,
  });
  const [onboardingSubmit, setOnboardingSubmit] = useState({
    status: 'idle',
    payload: null,
    error: null,
  });
  const [cabinetSummary, setCabinetSummary] = useState({
    status: 'idle',
    payload: null,
    error: null,
  });
  const [formsPreview, setFormsPreview] = useState({
    status: 'idle',
    payload: null,
    error: null,
  });
  const [formAnswers, setFormAnswers] = useState({});
  const [formSubmit, setFormSubmit] = useState({
    status: 'idle',
    formId: null,
    error: null,
  });
  const [resultsSummary, setResultsSummary] = useState({
    status: 'idle',
    payload: null,
    error: null,
  });
  const [reportDownload, setReportDownload] = useState({
    status: 'idle',
    reportId: null,
    error: null,
  });
  const languageCode = normalizeMiniAppLanguage(
    state.manifest?.language?.code || getTelegramMiniAppClientLanguage()
  );
  const t = (key, params) => translateMiniAppText(languageCode, key, params);
  const manifestOnboardingRequest = state.manifest?.onboarding?.request || null;
  const onboardingRequest = onboardingSubmit.payload?.request || manifestOnboardingRequest || null;
  const onboardingStatus = onboardingRequest?.status || 'not_found';
  const isOnboardingScope = state.manifest?.scope?.type === 'onboarding';
  const onboardingCapability = state.manifest?.capabilities?.appointments || {};
  const canEditOnboardingRequest = Boolean(
    isOnboardingScope && canEditMiniAppOnboardingRequest(onboardingStatus)
  );

  useEffect(() => {
    if (!isOnboardingScope || !onboardingRequest) {
      return;
    }

    setAppointmentPreviewForm((current) => (
      hydrateMiniAppAppointmentFormFromOnboardingRequest(current, onboardingRequest)
    ));
  }, [isOnboardingScope, onboardingRequest]);

  useEffect(() => {
    let isMounted = true;
    const effectLanguageCode = getTelegramMiniAppClientLanguage();
    notifyTelegramMiniAppReady();

    const authPayload = getTelegramMiniAppAuthPayload(location.search, selectedSection);
    const usesCabinetSummary = selectedSection === 'cabinet'
      || selectedSection === 'payments'
      || selectedSection === 'visits'
      || selectedSection === 'queue';
    setCabinetSummary({
      status: usesCabinetSummary && authPayload ? 'loading' : 'idle',
      payload: null,
      error: null,
    });
    setFormsPreview({
      status: selectedSection === 'forms' && authPayload ? 'loading' : 'idle',
      payload: null,
      error: null,
    });
    setFormSubmit({
      status: 'idle',
      formId: null,
      error: null,
    });
    setResultsSummary({
      status: selectedSection === 'results' && authPayload ? 'loading' : 'idle',
      payload: null,
      error: null,
    });
    setAppointmentPreview({
      status: 'idle',
      payload: null,
      error: null,
    });
    setAppointmentCreate({
      status: 'idle',
      payload: null,
      error: null,
    });
    setOnboardingSubmit({
      status: 'idle',
      payload: null,
      error: null,
    });
    setReportDownload({
      status: 'idle',
      reportId: null,
      error: null,
    });

    if (!authPayload) {
      setState({
        status: 'unavailable',
        manifest: null,
        error: null,
      });
      return () => {
        isMounted = false;
      };
    }

    api.post('/telegram/mini-app/patient/manifest', authPayload, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)
      .then((response) => {
        if (!isMounted) return;
        const manifest = response.data;
        const isOnboardingManifest = manifest?.scope?.type === 'onboarding';
        setState({
          status: 'ready',
          manifest,
          error: null,
        });
        if (isOnboardingManifest) {
          const telemetryMeta = {
            section: selectedSection || 'appointments',
            language: manifest?.language?.code || effectLanguageCode,
            success: true,
          };
          const onboardingStatus = manifest?.onboarding?.request?.status || 'not_found';
          emitMiniAppOnboardingTelemetry('patient_onboarding_opened', telemetryMeta);
          if (onboardingStatus === 'not_found') {
            emitMiniAppOnboardingTelemetry('patient_onboarding_started', telemetryMeta);
          } else {
            emitMiniAppOnboardingStatusTelemetry(onboardingStatus, telemetryMeta);
          }
          setCabinetSummary({
            status: 'idle',
            payload: null,
            error: null,
          });
          setFormsPreview({
            status: 'idle',
            payload: null,
            error: null,
          });
          setResultsSummary({
            status: 'idle',
            payload: null,
            error: null,
          });
          return null;
        }
        if (usesCabinetSummary) {
          return api.post('/telegram/mini-app/cabinet/summary', authPayload, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)
            .then((summaryResponse) => {
              if (!isMounted) return;
              setCabinetSummary({
                status: 'ready',
                payload: summaryResponse.data,
                error: null,
              });
            });
        }
        if (selectedSection === 'forms') {
          return api.post('/telegram/mini-app/forms/preview', authPayload, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)
            .then((formsResponse) => {
              if (!isMounted) return;
              setFormsPreview({
                status: 'ready',
                payload: formsResponse.data,
                error: null,
              });
              setFormAnswers(getMiniAppFormsInitialAnswers(formsResponse.data?.forms || []));
            });
        }
        if (selectedSection === 'results') {
          return api.post('/telegram/mini-app/cabinet/summary', authPayload, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)
            .then((summaryResponse) => {
              if (!isMounted) return;
              setResultsSummary({
                status: 'ready',
                payload: summaryResponse.data,
                error: null,
              });
            });
        }
        return null;
      })
      .catch((error) => {
        if (!isMounted) return;
        setCabinetSummary({
          status: usesCabinetSummary ? 'error' : 'idle',
          payload: null,
          error: translateMiniAppText(
            effectLanguageCode,
            selectedSection === 'payments'
              ? 'paymentsLoadFailed'
              : selectedSection === 'queue'
                ? 'queueLoadFailed'
              : selectedSection === 'visits'
                ? 'visitsLoadFailed'
                : 'cabinetLoadFailed'
          ),
        });
        setFormsPreview({
          status: selectedSection === 'forms' ? 'error' : 'idle',
          payload: null,
          error: translateMiniAppText(effectLanguageCode, 'formsLoadFailed'),
        });
        setResultsSummary({
          status: selectedSection === 'results' ? 'error' : 'idle',
          payload: null,
          error: translateMiniAppText(effectLanguageCode, 'documentsLoadFailed'),
        });
        setState({
          status: 'error',
          manifest: null,
          error: getMiniAppPatientSessionErrorMessage(error, effectLanguageCode),
        });
      });

    return () => {
      isMounted = false;
    };
  }, [location.search, selectedSection]);

  const capabilities = state.manifest?.capabilities || {};
  const capabilityLabels = MINI_APP_I18N[languageCode]?.capabilities
    || MINI_APP_I18N[MINI_APP_LANGUAGE_RU].capabilities;
  const capabilityEntries = Object.entries(capabilityLabels);
  const selectedCapability = selectedSection ? capabilities[selectedSection] || {} : null;
  const selectedCapabilityEnabled = isMiniAppCapabilityEnabled(selectedCapability);
  const canPreviewAppointments = Boolean(
    selectedSection === 'appointments' &&
    selectedCapability?.preview_enabled
  );
  const canCreateAppointments = Boolean(
    canPreviewAppointments &&
    selectedCapability?.create_enabled
  );
  const canSubmitOnboardingRequest = Boolean(
    isOnboardingScope &&
    (selectedSection === 'appointments' || !selectedSection) &&
    onboardingCapability.onboarding_request_enabled &&
    canEditOnboardingRequest
  );

  const handleMiniAppCapabilitySelect = (section) => {
    if (!section || section === selectedSection) {
      return;
    }
    const params = new URLSearchParams(location.search || '');
    params.set('section', section);
    navigate({
      pathname: location.pathname,
      search: `?${params.toString()}`,
    });
  };

  const handleMiniAppRetry = () => {
    if (typeof window !== 'undefined') {
      window.location.reload();
    }
  };

  const handleMiniAppSupportClick = () => {
    if (typeof window !== 'undefined') {
      window.open(MINI_APP_SUPPORT_TG_URL, '_blank', 'noopener,noreferrer');
    }
  };

  const handleMiniAppReturnToTelegram = () => {
    if (typeof window === 'undefined') {
      return;
    }

    const webApp = window.Telegram?.WebApp;
    try {
      if (typeof webApp?.close === 'function') {
        webApp.close();
        return;
      }
    } catch {
      // Best-effort fallback for browser previews outside Telegram.
    }

    window.location.reload();
  };

  const handleMiniAppScrollToOnboardingForm = () => {
    if (typeof document === 'undefined') {
      return;
    }
    document.getElementById('miniapp-onboarding-form')?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    });
  };

  const handleAppointmentPreviewFieldChange = (field) => (event) => {
    setAppointmentPreviewForm((current) => ({
      ...current,
      [field]: event.target.value,
    }));
    setAppointmentPreview({
      status: 'idle',
      payload: null,
      error: null,
    });
    setAppointmentCreate({
      status: 'idle',
      payload: null,
      error: null,
    });
    setOnboardingSubmit({
      status: 'idle',
      payload: null,
      error: null,
    });
  };

  const handleAppointmentPreviewSubmit = (event) => {
    event.preventDefault();

    const authPayload = getTelegramMiniAppAuthPayload(location.search, 'appointments');
    if (!authPayload || !appointmentPreviewForm.appointmentDate) {
      setAppointmentPreview({
        status: 'error',
        payload: null,
        error: t('appointmentDateRequired'),
      });
      return;
    }

    const requestBody = buildMiniAppAppointmentRequestBody(authPayload, appointmentPreviewForm);

    setAppointmentPreview({
      status: 'loading',
      payload: null,
      error: null,
    });
    setAppointmentCreate({
      status: 'idle',
      payload: null,
      error: null,
    });

    api.post('/telegram/mini-app/appointments/preview', requestBody, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)
      .then((response) => {
        setAppointmentPreview({
          status: 'ready',
          payload: response.data,
          error: null,
        });
      })
      .catch((error) => {
        const reason = getMiniAppApiErrorReason(error, 'preview_failed');
        setAppointmentPreview({
          status: 'error',
          payload: null,
          error: t('appointmentPreviewFailed', { reason }),
        });
      });
  };

  const handleAppointmentCreateSubmit = () => {
    const authPayload = getTelegramMiniAppAuthPayload(location.search, 'appointments');
    if (!authPayload || !appointmentPreviewForm.appointmentDate) {
      setAppointmentCreate({
        status: 'error',
        payload: null,
        error: t('appointmentDateRequired'),
      });
      return;
    }

    const requestBody = buildMiniAppAppointmentRequestBody(authPayload, appointmentPreviewForm);

    setAppointmentCreate({
      status: 'loading',
      payload: null,
      error: null,
    });

    api.post('/telegram/mini-app/appointments', requestBody, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)
      .then((response) => {
        setAppointmentCreate({
          status: 'ready',
          payload: response.data,
          error: null,
        });
        if (response.data?.preview) {
          setAppointmentPreview({
            status: 'ready',
            payload: response.data.preview,
            error: null,
          });
        }
      })
      .catch((error) => {
        const reason = getMiniAppApiErrorReason(error, 'appointment_create_failed');
        setAppointmentCreate({
          status: 'error',
          payload: null,
          error: t('appointmentCreateFailed', { reason }),
        });
      });
  };

  const handleOnboardingRequestSubmit = (event) => {
    event.preventDefault();

    const authPayload = getTelegramMiniAppAuthPayload(location.search, 'appointments');
    if (!authPayload || !appointmentPreviewForm.appointmentDate) {
      setOnboardingSubmit({
        status: 'error',
        payload: null,
        error: t('appointmentDateRequired'),
      });
      return;
    }

    const requestBody = buildMiniAppOnboardingRequestBody(
      authPayload,
      appointmentPreviewForm,
      languageCode
    );

    setOnboardingSubmit({
      status: 'loading',
      payload: null,
      error: null,
    });

    api.post('/telegram/mini-app/onboarding/requests', requestBody, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)
      .then((response) => {
        setOnboardingSubmit({
          status: 'ready',
          payload: response.data,
          error: null,
        });
        emitMiniAppOnboardingTelemetry('patient_onboarding_submitted', {
          section: 'appointments',
          language: languageCode,
          success: true,
        });
        emitMiniAppOnboardingStatusTelemetry(response.data?.request?.status, {
          section: 'appointments',
          language: languageCode,
          success: true,
        });
      })
      .catch((error) => {
        const reason = getMiniAppApiErrorReason(error, 'onboarding_submit_failed');
        emitMiniAppOnboardingTelemetry('patient_onboarding_submitted', {
          section: 'appointments',
          language: languageCode,
          success: false,
          reason_code: reason,
        });
        setOnboardingSubmit({
          status: 'error',
          payload: null,
          error: t('onboardingRequestFailed'),
        });
      });
  };

  const handlePatientFormFieldChange = (formId, field) => (event) => {
    const value = field.type === 'boolean' ? event.target.checked : event.target.value;
    setFormAnswers((current) => ({
      ...current,
      [formId]: {
        ...(current[formId] || {}),
        [field.key]: value,
      },
    }));
  };

  const handlePatientFormSubmit = (form) => (event) => {
    event.preventDefault();

    const authPayload = getTelegramMiniAppAuthPayload(location.search, 'forms');
    if (!authPayload) {
      setFormSubmit({
        status: 'error',
        formId: form.id,
        error: t('formOpenAgain'),
      });
      return;
    }

    setFormSubmit({
      status: 'loading',
      formId: form.id,
      error: null,
    });

    api.post('/telegram/mini-app/forms/submissions', {
      ...authPayload,
      formId: form.id,
      answers: formAnswers[form.id] || {},
      status: 'submitted',
    }, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)
      .then((response) => {
        const submission = response.data?.submission;
        setFormsPreview((current) => ({
          ...current,
          payload: {
            ...(current.payload || {}),
            forms: (current.payload?.forms || []).map((item) => (
              item.id === form.id ? { ...item, submission } : item
            )),
          },
        }));
        setFormSubmit({
          status: 'ready',
          formId: form.id,
          error: null,
        });
      })
      .catch((error) => {
        const reason = error?.response?.data?.detail?.reason || 'form_save_failed';
        setFormSubmit({
          status: 'error',
          formId: form.id,
          error: t('formNotSaved', { reason }),
        });
      });
  };

  const handleReportDownload = (report) => () => {
    const authPayload = getTelegramMiniAppAuthPayload(location.search, 'results');
    if (!authPayload) {
      setReportDownload({
        status: 'error',
        reportId: report.id,
        error: t('documentsOpenAgain'),
      });
      return;
    }

    setReportDownload({
      status: 'loading',
      reportId: report.id,
      error: null,
    });

    api.post(
      '/telegram/mini-app/reports/download',
      {
        ...authPayload,
        reportId: report.id,
      },
      {
        ...MINI_APP_HANDLED_ERROR_REQUEST_CONFIG,
        responseType: 'blob',
      }
    )
      .then((response) => {
        const blob = new Blob([response.data], { type: 'application/pdf' });
        const objectUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download = getMiniAppReportFileName(report);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
        setReportDownload({
          status: 'ready',
          reportId: report.id,
          error: null,
        });
      })
      .catch((error) => {
        const reason = error?.response?.data?.detail?.reason || 'report_download_failed';
        setReportDownload({
          status: 'error',
          reportId: report.id,
          error: t('documentFailed', { reason }),
        });
      });
  };

  const previewAppointment = appointmentPreview.payload?.appointment || null;
  const createdAppointmentId = appointmentCreate.payload?.appointment_id || null;
  const patientForms = (formsPreview.payload?.forms || []).map((form) => (
    localizeMiniAppPatientForm(languageCode, form)
  ));
  const patientReports = resultsSummary.payload?.reports || [];
  const paymentsSummary = cabinetSummary.payload?.payments || {};
  const patientAppointments = cabinetSummary.payload?.appointments || [];
  const patientVisits = cabinetSummary.payload?.visits || [];
  const patientQueueEntries = cabinetSummary.payload?.queue || [];
  const currentQueueEntry = patientQueueEntries[0] || null;
  const paymentsDebtValue = Number(String(paymentsSummary.debt || '0').replace(/\s/g, ''));
  const onboardingStatusMessage = t(`onboardingStatus.${onboardingStatus}`);
  const onboardingNextStepMessage = t(`onboardingNextStep.${onboardingStatus}`);
  const onboardingSummaryItems = [
    { label: t('contactName'), value: getMiniAppOnboardingValue(onboardingRequest, 'contactName', 'contact_name', appointmentPreviewForm.contactName) },
    { label: t('contactPhone'), value: getMiniAppOnboardingValue(onboardingRequest, 'contactPhone', 'contact_phone', appointmentPreviewForm.contactPhone) },
    { label: t('desiredService'), value: getMiniAppOnboardingValue(onboardingRequest, 'desiredService', 'desired_service', appointmentPreviewForm.desiredService) },
    { label: t('desiredBranch'), value: getMiniAppOnboardingValue(onboardingRequest, 'desiredBranch', 'desired_branch', appointmentPreviewForm.desiredBranch) },
    { label: t('date'), value: getMiniAppOnboardingValue(onboardingRequest, 'desiredDate', 'desired_date', appointmentPreviewForm.appointmentDate) },
    { label: t('time'), value: getMiniAppOnboardingValue(onboardingRequest, 'desiredTime', 'desired_time', appointmentPreviewForm.appointmentTime) },
  ].filter((item) => item.value);
  const statusBadge = getMiniAppStatusBadge(state.status, languageCode);

  return (
    <div style={miniAppPageStyle}>
      <main style={miniAppMainStyle}>
        <section style={miniAppHeroStyle}>
          <div style={miniAppHeroTitleGroupStyle}>
            <p style={miniAppKickerStyle}>Kosmed Clinic</p>
            <h1 style={miniAppTitleStyle}>{t('title')}</h1>
          </div>
          <Badge
            variant={statusBadge.variant}
            size="small"
            style={miniAppStatusBadgeStyle}
            aria-live={state.status === 'error' ? 'assertive' : 'polite'}
          >
            {statusBadge.label}
          </Badge>
        </section>

        {state.status === 'checking' && (
          <Alert severity="info" style={miniAppNoticeStyle} {...MINI_APP_STATUS_ALERT_PROPS}>
            {t('statusLoading')}
          </Alert>
        )}

        {state.status === 'unavailable' && (
          <>
            <Alert severity="info" style={miniAppNoticeStyle} {...MINI_APP_STATUS_ALERT_PROPS}>
              {t('sessionUnavailable')}
            </Alert>
            <div style={miniAppActionRowStyle}>
              <Button
                type="button"
                variant="outlined"
                size="small"
                aria-label={t('onboardingRetry')}
                onClick={handleMiniAppRetry}
              >
                {t('onboardingRetry')}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="small"
                aria-label={t('onboardingSupport')}
                onClick={handleMiniAppSupportClick}
              >
                {t('onboardingSupport')}
              </Button>
            </div>
          </>
        )}

        {state.status === 'error' && (
          <>
            <Alert severity="error" style={miniAppNoticeStyle} {...MINI_APP_ERROR_ALERT_PROPS}>
              {state.error}
            </Alert>
            <div style={miniAppActionRowStyle}>
              <Button
                type="button"
                variant="outlined"
                size="small"
                aria-label={t('onboardingRetry')}
                onClick={handleMiniAppRetry}
              >
                {t('onboardingRetry')}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="small"
                aria-label={t('onboardingSupport')}
                onClick={handleMiniAppSupportClick}
              >
                {t('onboardingSupport')}
              </Button>
            </div>
          </>
        )}

        {state.status === 'ready' && (
          <>
            {selectedSection && (
              <Card padding="small" shadow="none" style={miniAppSelectedSectionStyle}>
                <CardContent style={miniAppSelectedSectionContentStyle}>
                  <div>
                    <p style={miniAppKickerStyle}>{t('openSection')}</p>
                    <h2 style={miniAppSelectedSectionTitleStyle}>
                      {capabilityLabels[selectedSection]}
                    </h2>
                  </div>
                  <div style={miniAppSelectedSectionStatusStyle}>
                    <Badge
                      variant={selectedCapabilityEnabled ? 'primary' : 'secondary'}
                      size="small"
                    >
                      {selectedCapabilityEnabled ? t('available') : t('statusOnly')}
                    </Badge>
                    <p style={miniAppCapabilityTextStyle}>
                      {localizeMiniAppCapabilityStatus(languageCode, selectedCapability?.status)}
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}

            {isOnboardingScope && selectedSection && selectedSection !== 'appointments' && (
              <Card padding="small" shadow="none" style={miniAppOnboardingBlockedStyle}>
                <CardContent style={miniAppAppointmentPreviewContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>{t('onboardingKicker')}</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>{t('onboardingBlockedTitle')}</h2>
                    </div>
                    <Badge variant="warning" size="small">{t('statusOnly')}</Badge>
                  </div>
                  <Alert severity="info" style={miniAppNoticeStyle}>
                    {t('onboardingBlockedText')}
                  </Alert>
                  <Button
                    type="button"
                    variant="primary"
                    size="small"
                    onClick={() => handleMiniAppCapabilitySelect('appointments')}
                    aria-label={t('onboardingOpenAppointments')}
                  >
                    {t('onboardingOpenAppointments')}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="small"
                    onClick={handleMiniAppSupportClick}
                    aria-label={t('onboardingSupport')}
                  >
                    {t('onboardingSupport')}
                  </Button>
                </CardContent>
              </Card>
            )}

            {isOnboardingScope && (selectedSection === 'appointments' || !selectedSection) && (
              <Card padding="small" shadow="none" style={miniAppAppointmentPreviewStyle}>
                <CardContent style={miniAppAppointmentPreviewContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>{t('onboardingKicker')}</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>{t('onboardingTitle')}</h2>
                      <p style={miniAppCapabilityTextStyle}>{t('onboardingIntro')}</p>
                    </div>
                    <Badge variant="secondary" size="small">{t('appointmentRequest')}</Badge>
                  </div>

                  <Alert severity="info" style={miniAppNoticeStyle}>
                    <span style={miniAppQueueEmptyContentStyle}>
                      <strong>{t('onboardingStatusTitle')}</strong>
                      <span>{onboardingStatusMessage}</span>
                    </span>
                  </Alert>

                  {shouldShowMiniAppOnboardingSummary(onboardingStatus) && (
                    <div style={miniAppOnboardingSummaryStyle}>
                      <div style={miniAppOnboardingSummaryHeaderStyle}>
                        <div>
                          <p style={miniAppKickerStyle}>{t('onboardingSummaryTitle')}</p>
                          <h3 style={miniAppSubsectionTitleStyle}>{t('onboardingNextStepTitle')}</h3>
                        </div>
                        <Badge variant="secondary" size="small">
                          {t('appointmentRequest')}
                        </Badge>
                      </div>
                      {onboardingSummaryItems.length > 0 && (
                        <div style={miniAppOnboardingSummaryGridStyle}>
                          {onboardingSummaryItems.map((item) => (
                            <div key={`${item.label}-${item.value}`} style={miniAppOnboardingSummaryItemStyle}>
                              <p style={miniAppCapabilityTextStyle}>{item.label}</p>
                              <strong>{item.value}</strong>
                            </div>
                          ))}
                        </div>
                      )}
                      <p style={miniAppCapabilityTextStyle}>{onboardingNextStepMessage}</p>
                      {onboardingRequest?.reviewMessage && (
                        <Alert severity="info" style={miniAppNoticeStyle}>
                          <span style={miniAppQueueEmptyContentStyle}>
                            <strong>{t('onboardingReviewMessageTitle')}</strong>
                            <span>{onboardingRequest.reviewMessage}</span>
                          </span>
                        </Alert>
                      )}
                      <div style={miniAppActionRowStyle}>
                        {['linked_existing', 'created_patient'].includes(onboardingStatus) ? (
                          <Button
                            type="button"
                            variant="primary"
                            size="small"
                            aria-label={t('onboardingReopenFromTelegram')}
                            onClick={handleMiniAppReturnToTelegram}
                          >
                            {t('onboardingReopenFromTelegram')}
                          </Button>
                        ) : (
                          <Button
                            type="button"
                            variant="primary"
                            size="small"
                            aria-label={canEditOnboardingRequest ? t('onboardingUpdateRequest') : t('onboardingRetry')}
                            onClick={canEditOnboardingRequest ? handleMiniAppScrollToOnboardingForm : handleMiniAppRetry}
                          >
                            {canEditOnboardingRequest ? t('onboardingUpdateRequest') : t('onboardingRetry')}
                          </Button>
                        )}
                        <Button
                          type="button"
                          variant="ghost"
                          size="small"
                          aria-label={t('onboardingSupport')}
                          onClick={handleMiniAppSupportClick}
                        >
                          {t('onboardingSupport')}
                        </Button>
                      </div>
                    </div>
                  )}

                  {canSubmitOnboardingRequest && (
                    <form
                      id="miniapp-onboarding-form"
                      style={miniAppAppointmentFormStyle}
                      onSubmit={handleOnboardingRequestSubmit}
                    >
                      <div style={miniAppAppointmentFormGridStyle}>
                        <Input
                          label={t('contactName')}
                          value={appointmentPreviewForm.contactName}
                          onChange={handleAppointmentPreviewFieldChange('contactName')}
                          maxLength={256}
                          style={miniAppAppointmentInputStyle}
                        />
                        <Input
                          label={t('contactPhone')}
                          value={appointmentPreviewForm.contactPhone}
                          onChange={handleAppointmentPreviewFieldChange('contactPhone')}
                          maxLength={32}
                          required
                          style={miniAppAppointmentInputStyle}
                        />
                        <Input
                          label={t('desiredService')}
                          value={appointmentPreviewForm.desiredService}
                          onChange={handleAppointmentPreviewFieldChange('desiredService')}
                          maxLength={128}
                          style={miniAppAppointmentInputStyle}
                        />
                        <Input
                          label={t('desiredBranch')}
                          value={appointmentPreviewForm.desiredBranch}
                          onChange={handleAppointmentPreviewFieldChange('desiredBranch')}
                          maxLength={128}
                          style={miniAppAppointmentInputStyle}
                        />
                        <Input
                          type="date"
                          label={t('date')}
                          value={appointmentPreviewForm.appointmentDate}
                          onChange={handleAppointmentPreviewFieldChange('appointmentDate')}
                          required
                          style={miniAppAppointmentInputStyle}
                        />
                        <Input
                          type="time"
                          label={t('time')}
                          value={appointmentPreviewForm.appointmentTime}
                          onChange={handleAppointmentPreviewFieldChange('appointmentTime')}
                          style={miniAppAppointmentInputStyle}
                        />
                      </div>
                      <Textarea
                        label={t('registrarNote')}
                        value={appointmentPreviewForm.notes}
                        onChange={handleAppointmentPreviewFieldChange('notes')}
                        placeholder={t('noMedicalData')}
                        maxLength={1000}
                        minRows={2}
                      />
                      <Alert severity="warning" style={miniAppNoticeStyle}>
                        {t('onboardingPrivacy')}
                      </Alert>

                      {onboardingSubmit.status === 'error' && (
                        <Alert severity="error" style={miniAppNoticeStyle}>
                          {onboardingSubmit.error}
                        </Alert>
                      )}

                      {onboardingSubmit.status === 'ready' && (
                        <Alert severity="success" style={miniAppNoticeStyle}>
                          {t('onboardingSubmitted')}
                        </Alert>
                      )}

                      <div style={miniAppActionRowStyle}>
                        <Button
                          type="submit"
                          variant="primary"
                          size="small"
                          loading={onboardingSubmit.status === 'loading'}
                          disabled={onboardingSubmit.status === 'loading'}
                          aria-label={onboardingSubmit.status === 'loading'
                            ? t('onboardingSubmitting')
                            : t('onboardingSubmit')}
                        >
                          {onboardingSubmit.status === 'loading'
                            ? t('onboardingSubmitting')
                            : t('onboardingSubmit')}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="small"
                          aria-label={t('onboardingSupport')}
                          onClick={handleMiniAppSupportClick}
                        >
                          {t('onboardingSupport')}
                        </Button>
                      </div>
                    </form>
                  )}
                </CardContent>
              </Card>
            )}

            {selectedSection === 'cabinet' && cabinetSummary.status === 'loading' && (
              <Alert severity="info" style={miniAppNoticeStyle}>
                {t('cabinetLoading')}
              </Alert>
            )}

            {selectedSection === 'cabinet' && cabinetSummary.status === 'error' && (
              <Alert severity="error" style={miniAppNoticeStyle}>
                {cabinetSummary.error}
              </Alert>
            )}

            {selectedSection === 'cabinet' && cabinetSummary.status === 'ready' && (
              <Card padding="small" shadow="none" style={miniAppAppointmentPreviewStyle}>
                <CardContent style={miniAppAppointmentPreviewContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>{t('patient')}</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>
                        {cabinetSummary.payload?.patient?.name || t('patientFallback')}
                      </h2>
                    </div>
                    <Badge variant="success" size="small">{t('accessConfirmed')}</Badge>
                  </div>
                  <div style={miniAppAppointmentPreviewResultStyle}>
                    <div>
                      <p style={miniAppCapabilityTextStyle}>{t('visits')}</p>
                      <strong>{cabinetSummary.payload?.visits?.length || 0}</strong>
                    </div>
                    <div>
                      <p style={miniAppCapabilityTextStyle}>{t('queue')}</p>
                      <strong>{cabinetSummary.payload?.queue?.length || 0}</strong>
                    </div>
                    <div>
                      <p style={miniAppCapabilityTextStyle}>{t('debt')}</p>
                      <strong>{cabinetSummary.payload?.payments?.debt || '0'}</strong>
                    </div>
                    <div>
                      <p style={miniAppCapabilityTextStyle}>{t('results')}</p>
                      <strong>{cabinetSummary.payload?.reports?.length || 0}</strong>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {selectedSection === 'queue' && cabinetSummary.status === 'loading' && (
              <Alert severity="info" style={miniAppNoticeStyle}>
                {t('queueLoading')}
              </Alert>
            )}

            {selectedSection === 'queue' && cabinetSummary.status === 'error' && (
              <Alert severity="error" style={miniAppNoticeStyle}>
                {cabinetSummary.error}
              </Alert>
            )}

            {selectedSection === 'queue' && cabinetSummary.status === 'ready' && (
              <Card padding="small" shadow="none" style={miniAppAppointmentPreviewStyle}>
                <CardContent style={miniAppAppointmentPreviewContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>{t('patient')}</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>{t('queueTitle')}</h2>
                      <p style={miniAppCapabilityTextStyle}>
                        {cabinetSummary.payload?.patient?.name || t('patientFallback')}
                      </p>
                    </div>
                    <Badge
                      variant={currentQueueEntry ? 'success' : 'secondary'}
                      size="small"
                    >
                      {currentQueueEntry ? t('activeQueue') : t('queueInactive')}
                    </Badge>
                  </div>

                  {currentQueueEntry ? (
                    <>
                      <div style={miniAppAppointmentPreviewResultStyle}>
                        <div>
                          <p style={miniAppCapabilityTextStyle}>{t('queueNumber')}</p>
                          <strong>№{currentQueueEntry.number}</strong>
                        </div>
                        <div>
                          <p style={miniAppCapabilityTextStyle}>{t('cabinet')}</p>
                          <strong>{currentQueueEntry.cabinet || t('cabinetMissing')}</strong>
                        </div>
                        <div>
                          <p style={miniAppCapabilityTextStyle}>{t('queueStatus')}</p>
                          <strong>{currentQueueEntry.status || t('status')}</strong>
                        </div>
                      </div>

                      {patientQueueEntries.length > 1 && (
                        <section style={miniAppVisitsSectionStyle}>
                          <h3 style={miniAppSubsectionTitleStyle}>{t('queueEntries')}</h3>
                          <div style={miniAppVisitsListStyle}>
                            {patientQueueEntries.map((entry) => (
                              <div key={`queue-${entry.number}-${entry.status}`} style={miniAppVisitItemStyle}>
                                <div style={miniAppVisitItemHeaderStyle}>
                                  <strong>№{entry.number}</strong>
                                  <Badge variant="secondary" size="small">
                                    {entry.status || t('status')}
                                  </Badge>
                                </div>
                                <div style={miniAppAppointmentPreviewResultStyle}>
                                  <div>
                                    <p style={miniAppCapabilityTextStyle}>{t('cabinet')}</p>
                                    <strong>{entry.cabinet || t('cabinetMissing')}</strong>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </section>
                      )}
                    </>
                  ) : (
                    <Alert severity="info" style={miniAppNoticeStyle}>
                      <span style={miniAppQueueEmptyContentStyle}>
                        <strong>{t('queueInactive')}</strong>
                        <span>{t('queueEmpty')}</span>
                        <span>{t('queueEmptyRecovery')}</span>
                      </span>
                    </Alert>
                  )}

                  <Alert severity="warning" style={miniAppNoticeStyle}>
                    {t('queuePrivacyNote')}
                  </Alert>
                </CardContent>
              </Card>
            )}

            {selectedSection === 'visits' && cabinetSummary.status === 'loading' && (
              <Alert severity="info" style={miniAppNoticeStyle}>
                {t('visitsLoading')}
              </Alert>
            )}

            {selectedSection === 'visits' && cabinetSummary.status === 'error' && (
              <Alert severity="error" style={miniAppNoticeStyle}>
                {cabinetSummary.error}
              </Alert>
            )}

            {selectedSection === 'visits' && cabinetSummary.status === 'ready' && (
              <Card padding="small" shadow="none" style={miniAppAppointmentPreviewStyle}>
                <CardContent style={miniAppAppointmentPreviewContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>{t('patient')}</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>{t('visitsTitle')}</h2>
                      <p style={miniAppCapabilityTextStyle}>
                        {cabinetSummary.payload?.patient?.name || t('patientFallback')}
                      </p>
                    </div>
                    <Badge variant="success" size="small">{t('accessConfirmed')}</Badge>
                  </div>

                  <div style={miniAppAppointmentPreviewResultStyle}>
                    <div>
                      <p style={miniAppCapabilityTextStyle}>{t('appointmentRequests')}</p>
                      <strong>{patientAppointments.length}</strong>
                    </div>
                    <div>
                      <p style={miniAppCapabilityTextStyle}>{t('recentVisits')}</p>
                      <strong>{patientVisits.length}</strong>
                    </div>
                  </div>

                  <section style={miniAppVisitsSectionStyle}>
                    <h3 style={miniAppSubsectionTitleStyle}>{t('appointmentRequests')}</h3>
                    {patientAppointments.length === 0 ? (
                      <Alert severity="info" style={miniAppNoticeStyle}>
                        {t('appointmentsEmpty')}
                      </Alert>
                    ) : (
                      <div style={miniAppVisitsListStyle}>
                        {patientAppointments.map((appointment) => (
                          <div key={`appointment-${appointment.id}`} style={miniAppVisitItemStyle}>
                            <div style={miniAppVisitItemHeaderStyle}>
                              <strong>{t('appointmentNumber', { id: appointment.id })}</strong>
                              <Badge variant="secondary" size="small">
                                {appointment.status || t('status')}
                              </Badge>
                            </div>
                            <div style={miniAppAppointmentPreviewResultStyle}>
                              <div>
                                <p style={miniAppCapabilityTextStyle}>{t('dateTime')}</p>
                                <strong>
                                  {appointment.date || t('dateMissing')} {appointment.time || t('timeMissing')}
                                </strong>
                              </div>
                              <div>
                                <p style={miniAppCapabilityTextStyle}>{t('department')}</p>
                                <strong>{appointment.department || t('departmentMissing')}</strong>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>

                  <section style={miniAppVisitsSectionStyle}>
                    <h3 style={miniAppSubsectionTitleStyle}>{t('recentVisits')}</h3>
                    {patientVisits.length === 0 ? (
                      <Alert severity="info" style={miniAppNoticeStyle}>
                        {t('visitsEmpty')}
                      </Alert>
                    ) : (
                      <div style={miniAppVisitsListStyle}>
                        {patientVisits.map((visit) => (
                          <div key={`visit-${visit.id}`} style={miniAppVisitItemStyle}>
                            <div style={miniAppVisitItemHeaderStyle}>
                              <strong>{t('visitNumber', { id: visit.id })}</strong>
                              <Badge variant="secondary" size="small">
                                {visit.status || t('status')}
                              </Badge>
                            </div>
                            <div style={miniAppAppointmentPreviewResultStyle}>
                              <div>
                                <p style={miniAppCapabilityTextStyle}>{t('date')}</p>
                                <strong>{visit.date || t('dateMissing')}</strong>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>

                  <Alert severity="warning" style={miniAppNoticeStyle}>
                    {t('visitsPrivacyNote')}
                  </Alert>
                </CardContent>
              </Card>
            )}

            {selectedSection === 'payments' && cabinetSummary.status === 'loading' && (
              <Alert severity="info" style={miniAppNoticeStyle}>
                {t('paymentsLoading')}
              </Alert>
            )}

            {selectedSection === 'payments' && cabinetSummary.status === 'error' && (
              <Alert severity="error" style={miniAppNoticeStyle}>
                {cabinetSummary.error}
              </Alert>
            )}

            {selectedSection === 'payments' && cabinetSummary.status === 'ready' && (
              <Card padding="small" shadow="none" style={miniAppAppointmentPreviewStyle}>
                <CardContent style={miniAppAppointmentPreviewContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>{t('patient')}</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>{t('paymentsTitle')}</h2>
                      <p style={miniAppCapabilityTextStyle}>
                        {cabinetSummary.payload?.patient?.name || t('patientFallback')}
                      </p>
                    </div>
                    <Badge
                      variant={paymentsDebtValue > 0 ? 'warning' : 'success'}
                      size="small"
                    >
                      {t('debt')}: {formatMiniAppMoney(languageCode, paymentsSummary.debt)}
                    </Badge>
                  </div>

                  <div style={miniAppAppointmentPreviewResultStyle}>
                    <div>
                      <p style={miniAppCapabilityTextStyle}>{t('billed')}</p>
                      <strong>{formatMiniAppMoney(languageCode, paymentsSummary.billed)}</strong>
                    </div>
                    <div>
                      <p style={miniAppCapabilityTextStyle}>{t('paid')}</p>
                      <strong>{formatMiniAppMoney(languageCode, paymentsSummary.paid)}</strong>
                    </div>
                    <div>
                      <p style={miniAppCapabilityTextStyle}>{t('pending')}</p>
                      <strong>{formatMiniAppMoney(languageCode, paymentsSummary.pending)}</strong>
                    </div>
                    <div>
                      <p style={miniAppCapabilityTextStyle}>{t('linkedVisits')}</p>
                      <strong>{paymentsSummary.linked_visit_count || 0}</strong>
                    </div>
                    <div>
                      <p style={miniAppCapabilityTextStyle}>{t('activeQueue')}</p>
                      <strong>{paymentsSummary.active_queue_count || 0}</strong>
                    </div>
                  </div>

                  <Alert severity="info" style={miniAppNoticeStyle}>
                    {t('onlinePaymentUnavailable')}
                  </Alert>
                  <Alert severity="warning" style={miniAppNoticeStyle}>
                    {t('protectedPaymentNote')}
                  </Alert>
                </CardContent>
              </Card>
            )}

            {canPreviewAppointments && (
              <Card padding="small" shadow="none" style={miniAppAppointmentPreviewStyle}>
                <CardContent style={miniAppAppointmentPreviewContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>{t('appointmentPrecheck')}</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>{t('appointmentDraft')}</h2>
                    </div>
                    <Badge variant="secondary" size="small">{t('appointmentRequest')}</Badge>
                  </div>

                  <form style={miniAppAppointmentFormStyle} onSubmit={handleAppointmentPreviewSubmit}>
                    <div style={miniAppAppointmentFormGridStyle}>
                      <Input
                        type="date"
                        label={t('date')}
                        value={appointmentPreviewForm.appointmentDate}
                        onChange={handleAppointmentPreviewFieldChange('appointmentDate')}
                        required
                        style={miniAppAppointmentInputStyle}
                      />
                      <Input
                        type="time"
                        label={t('time')}
                        value={appointmentPreviewForm.appointmentTime}
                        onChange={handleAppointmentPreviewFieldChange('appointmentTime')}
                        style={miniAppAppointmentInputStyle}
                      />
                      <Input
                        label={t('department')}
                        value={appointmentPreviewForm.department}
                        onChange={handleAppointmentPreviewFieldChange('department')}
                        placeholder={t('optional')}
                        maxLength={64}
                        style={miniAppAppointmentInputStyle}
                      />
                    </div>
                    <Textarea
                      label={t('registrarNote')}
                      value={appointmentPreviewForm.notes}
                      onChange={handleAppointmentPreviewFieldChange('notes')}
                      placeholder={t('noMedicalData')}
                      maxLength={1000}
                      minRows={2}
                    />
                    <Button
                      type="submit"
                      variant="primary"
                      size="small"
                      loading={appointmentPreview.status === 'loading'}
                      disabled={appointmentPreview.status === 'loading'}
                    >
                      {t('checkDraft')}
                    </Button>
                  </form>

                  {appointmentPreview.status === 'error' && (
                    <Alert severity="error" style={miniAppNoticeStyle}>
                      {appointmentPreview.error}
                    </Alert>
                  )}

                  {appointmentPreview.status === 'ready' && previewAppointment && (
                    <>
                      <div style={miniAppAppointmentPreviewResultStyle}>
                        <div>
                          <p style={miniAppCapabilityTextStyle}>{t('dateTime')}</p>
                          <strong>{previewAppointment.appointment_date} {previewAppointment.appointment_time || t('timeMissing')}</strong>
                        </div>
                        <div>
                          <p style={miniAppCapabilityTextStyle}>{t('status')}</p>
                          <strong>{previewAppointment.status}</strong>
                        </div>
                        <div>
                          <p style={miniAppCapabilityTextStyle}>{t('payment')}</p>
                          <strong>{previewAppointment.payment_type} / {previewAppointment.payment_currency}</strong>
                        </div>
                        <Badge variant={appointmentPreview.payload?.mutation_allowed ? 'warning' : 'success'} size="small">
                          {appointmentPreview.payload?.preview_only ? t('previewOnly') : t('needsCheck')}
                        </Badge>
                      </div>

                      <Alert severity="info" style={miniAppNoticeStyle}>
                        {t('appointmentRequestNote')}
                      </Alert>

                      {appointmentCreate.status === 'error' && (
                        <Alert severity="error" style={miniAppNoticeStyle}>
                          {appointmentCreate.error}
                        </Alert>
                      )}

                      {appointmentCreate.status === 'ready' && (
                        <Alert severity="success" style={miniAppNoticeStyle}>
                          {createdAppointmentId
                            ? t('appointmentRequestCreated', { appointmentId: createdAppointmentId })
                            : t('appointmentRequestCreatedNoId')}
                        </Alert>
                      )}

                      {canCreateAppointments && (
                        <Button
                          type="button"
                          variant="primary"
                          size="small"
                          loading={appointmentCreate.status === 'loading'}
                          disabled={appointmentCreate.status === 'loading' || appointmentCreate.status === 'ready'}
                          onClick={handleAppointmentCreateSubmit}
                        >
                          {appointmentCreate.status === 'loading'
                            ? t('appointmentCreating')
                            : t('confirmAppointmentRequest')}
                        </Button>
                      )}
                    </>
                  )}
                </CardContent>
              </Card>
            )}

            {selectedSection === 'forms' && formsPreview.status === 'loading' && (
              <Alert severity="info" style={miniAppNoticeStyle}>
                {t('formsLoading')}
              </Alert>
            )}

            {selectedSection === 'forms' && formsPreview.status === 'error' && (
              <Alert severity="error" style={miniAppNoticeStyle}>
                {formsPreview.error}
              </Alert>
            )}

            {selectedSection === 'forms' && formsPreview.status === 'ready' && patientForms.length === 0 && (
              <Alert severity="info" style={miniAppNoticeStyle}>
                {t('formsEmpty')}
              </Alert>
            )}

            {selectedSection === 'forms' && formsPreview.status === 'ready' && patientForms.map((form) => (
              <Card key={form.id} padding="small" shadow="none" style={miniAppAppointmentPreviewStyle}>
                <CardContent style={miniAppAppointmentPreviewContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>{t('patientForm')}</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>{form.title}</h2>
                      <p style={miniAppCapabilityTextStyle}>{form.description}</p>
                    </div>
                    <Badge variant={form.submission ? 'success' : 'secondary'} size="small">
                      {form.submission ? t('saved') : t('new')}
                    </Badge>
                  </div>

                  <form style={miniAppAppointmentFormStyle} onSubmit={handlePatientFormSubmit(form)}>
                    {(form.fields || []).map((field) => (
                      field.type === 'boolean' ? (
                        <label key={field.key} style={miniAppCheckboxRowStyle}>
                          <input
                            type="checkbox"
                            aria-label={field.label || field.key}
                            checked={getMiniAppFormFieldValue(formAnswers, form.id, field)}
                            onChange={handlePatientFormFieldChange(form.id, field)}
                            style={miniAppCheckboxStyle}
                          />
                          <span>{field.label}</span>
                        </label>
                      ) : (
                        <Textarea
                          key={field.key}
                          label={field.label}
                          value={getMiniAppFormFieldValue(formAnswers, form.id, field)}
                          onChange={handlePatientFormFieldChange(form.id, field)}
                          maxLength={field.max_length || undefined}
                          minRows={2}
                        />
                      )
                    ))}

                    {formSubmit.status === 'error' && formSubmit.formId === form.id && (
                      <Alert severity="error" style={miniAppNoticeStyle}>
                        {formSubmit.error}
                      </Alert>
                    )}

                    {formSubmit.status === 'ready' && formSubmit.formId === form.id && (
                      <Alert severity="success" style={miniAppNoticeStyle}>
                        {t('formSaved')}
                      </Alert>
                    )}

                    <Button
                      type="submit"
                      variant="primary"
                      size="small"
                      loading={formSubmit.status === 'loading' && formSubmit.formId === form.id}
                      disabled={formSubmit.status === 'loading'}
                    >
                      {t('saveForm')}
                    </Button>
                  </form>
                </CardContent>
              </Card>
            ))}

            {selectedSection === 'results' && resultsSummary.status === 'loading' && (
              <Alert severity="info" style={miniAppNoticeStyle}>
                {t('documentsLoading')}
              </Alert>
            )}

            {selectedSection === 'results' && resultsSummary.status === 'error' && (
              <Alert severity="error" style={miniAppNoticeStyle}>
                {resultsSummary.error}
              </Alert>
            )}

            {selectedSection === 'results' && resultsSummary.status === 'ready' && patientReports.length === 0 && (
              <Alert severity="info" style={miniAppNoticeStyle}>
                {t('documentsEmpty')}
              </Alert>
            )}

            {selectedSection === 'results' && resultsSummary.status === 'ready' && patientReports.length > 0 && (
              <Card padding="small" shadow="none" style={miniAppAppointmentPreviewStyle}>
                <CardContent style={miniAppAppointmentPreviewContentStyle}>
                  <div style={miniAppAppointmentPreviewHeaderStyle}>
                    <div>
                      <p style={miniAppKickerStyle}>{t('documents')}</p>
                      <h2 style={miniAppSelectedSectionTitleStyle}>{t('readyPdfResults')}</h2>
                    </div>
                    <Badge variant="success" size="small">{patientReports.length}</Badge>
                  </div>

                  <div style={miniAppListStyle}>
                    {patientReports.map((report) => (
                      <div key={report.id} style={miniAppListItemStyle}>
                        <div>
                          <strong>{report.name}</strong>
                          <p style={miniAppCapabilityTextStyle}>
                            {report.ready_at || t('readyDateMissing')} · {report.status}
                          </p>
                        </div>
                        <Button
                          type="button"
                          variant="secondary"
                          size="small"
                          loading={reportDownload.status === 'loading' && reportDownload.reportId === report.id}
                          disabled={reportDownload.status === 'loading'}
                          onClick={handleReportDownload(report)}
                        >
                          {t('getPdf')}
                        </Button>
                      </div>
                    ))}
                  </div>

                  {reportDownload.status === 'error' && (
                    <Alert severity="error" style={miniAppNoticeStyle}>
                      {reportDownload.error}
                    </Alert>
                  )}
                </CardContent>
              </Card>
            )}

            <section style={miniAppGridStyle}>
              {capabilityEntries.map(([key, label]) => {
                const capability = capabilities[key] || {};
                const enabled = isMiniAppCapabilityEnabled(capability);
                const isSelected = key === selectedSection;
                return (
                  <Card
                    key={key}
                    interactive
                    onClick={() => handleMiniAppCapabilitySelect(key)}
                    aria-label={`${t('openSection')}: ${label}`}
                    aria-pressed={isSelected}
                    padding="small"
                    shadow="none"
                    style={{
                      ...miniAppCapabilityStyle,
                      ...(isSelected ? miniAppCapabilitySelectedStyle : {}),
                    }}
                  >
                    <CardContent style={miniAppCapabilityContentStyle}>
                      <div style={miniAppCapabilityHeaderStyle}>
                        <h2 style={miniAppCapabilityTitleStyle}>{label}</h2>
                        <Badge variant={enabled ? 'primary' : 'secondary'} size="small">
                          {enabled ? t('available') : t('statusOnly')}
                        </Badge>
                      </div>
                      <p style={miniAppCapabilityTextStyle}>
                        {localizeMiniAppCapabilityStatus(languageCode, capability.status)}
                      </p>
                    </CardContent>
                  </Card>
                );
              })}
            </section>
          </>
        )}
      </main>
    </div>
  );
}

const miniAppPageStyle = {
  minHeight: '100vh',
  background: 'var(--mac-bg-page, #f5f7fb)',
  color: 'var(--mac-text-primary, #111827)',
  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
};

const miniAppMainStyle = {
  width: '100%',
  maxWidth: '720px',
  margin: '0 auto',
  padding: '20px 16px 28px',
  boxSizing: 'border-box',
};

const miniAppHeroStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  columnGap: '16px',
  rowGap: '10px',
  flexWrap: 'wrap',
  padding: '8px 0 18px',
};

const miniAppHeroTitleGroupStyle = {
  flex: '1 1 220px',
  minWidth: 0,
};

const miniAppKickerStyle = {
  margin: '0 0 6px',
  fontSize: '13px',
  fontWeight: 700,
  color: 'var(--mac-text-secondary, #5f6b7a)',
};

const miniAppTitleStyle = {
  margin: 0,
  fontSize: '28px',
  lineHeight: 1.15,
  fontWeight: 800,
  color: 'var(--mac-text-primary, #111827)',
};

const miniAppStatusBadgeStyle = {
  flexShrink: 0,
  fontWeight: 700,
  maxWidth: 'min(100%, 220px)',
  whiteSpace: 'normal',
  textAlign: 'center',
};

const miniAppNoticeStyle = {
  fontSize: '14px',
  lineHeight: 1.5,
};

const miniAppQueueEmptyContentStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
};

const miniAppActionRowStyle = {
  display: 'flex',
  gap: '10px',
  flexWrap: 'wrap',
  alignItems: 'center',
};

const miniAppOnboardingSummaryStyle = {
  border: '1px solid var(--mac-border, #d8dde8)',
  borderRadius: '12px',
  padding: '14px',
  background: 'var(--mac-bg-secondary, rgba(255, 255, 255, 0.72))',
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
};

const miniAppOnboardingSummaryHeaderStyle = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: '12px',
  flexWrap: 'wrap',
};

const miniAppOnboardingSummaryGridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
  gap: '10px',
};

const miniAppOnboardingSummaryItemStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
  minWidth: 0,
};

const miniAppGridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(156px, 1fr))',
  gap: '12px',
};

const miniAppSelectedSectionStyle = {
  marginBottom: '12px',
  borderColor: 'var(--mac-accent-border)',
};

const miniAppSelectedSectionContentStyle = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: '14px',
  flexWrap: 'wrap',
};

const miniAppSelectedSectionTitleStyle = {
  margin: 0,
  fontSize: '20px',
  lineHeight: 1.25,
  fontWeight: 800,
  color: 'var(--mac-text-primary, #111827)',
};

const miniAppSelectedSectionStatusStyle = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'flex-end',
  gap: '8px',
  minWidth: '128px',
};

const miniAppAppointmentPreviewStyle = {
  marginBottom: '12px',
  borderColor: 'var(--mac-success-border, color-mix(in srgb, var(--mac-success), transparent 74%))',
};

const miniAppOnboardingBlockedStyle = {
  marginBottom: '12px',
  borderColor: 'var(--mac-warning-border, color-mix(in srgb, var(--mac-warning), transparent 72%))',
};

const miniAppAppointmentPreviewContentStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '14px',
};

const miniAppAppointmentPreviewHeaderStyle = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: '14px',
  flexWrap: 'wrap',
};

const miniAppAppointmentFormStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
};

const miniAppAppointmentFormGridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
  gap: '12px',
};

const miniAppAppointmentInputStyle = {
  width: '100%',
  boxSizing: 'border-box',
};

const miniAppAppointmentPreviewResultStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(132px, 1fr))',
  alignItems: 'center',
  gap: '12px',
  padding: '12px',
  border: '1px solid var(--mac-success-border, color-mix(in srgb, var(--mac-success), transparent 76%))',
  borderRadius: '8px',
  background: 'var(--mac-success-bg)',
  fontSize: '13px',
  color: 'var(--mac-text-primary, #111827)',
};

const miniAppVisitsSectionStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
};

const miniAppSubsectionTitleStyle = {
  margin: 0,
  fontSize: '15px',
  lineHeight: 1.3,
  fontWeight: 800,
  color: 'var(--mac-text-primary, #111827)',
};

const miniAppVisitsListStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
};

const miniAppVisitItemStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
  padding: '12px',
  border: '1px solid var(--mac-border, rgba(15, 23, 42, 0.12))',
  borderRadius: '8px',
  background: 'var(--mac-bg-secondary, #ffffff)',
};

const miniAppVisitItemHeaderStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  gap: '10px',
  flexWrap: 'wrap',
  fontSize: '14px',
};

const miniAppCheckboxRowStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  minHeight: '40px',
  padding: '10px 12px',
  border: '1px solid var(--mac-border, rgba(15, 23, 42, 0.12))',
  borderRadius: '8px',
  background: 'var(--mac-bg-secondary, rgba(255, 255, 255, 0.72))',
  fontSize: '14px',
  fontWeight: 650,
  color: 'var(--mac-text-primary, #111827)',
};

const miniAppCheckboxStyle = {
  width: '18px',
  height: '18px',
  flexShrink: 0,
};

const miniAppListStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
};

const miniAppListItemStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '12px',
  padding: '12px',
  border: '1px solid var(--mac-border, rgba(15, 23, 42, 0.12))',
  borderRadius: '8px',
  background: 'var(--mac-bg-secondary, rgba(255, 255, 255, 0.72))',
  flexWrap: 'wrap',
};

const miniAppCapabilityStyle = {
  minHeight: '128px',
};

const miniAppCapabilitySelectedStyle = {
  outline: '2px solid var(--mac-accent-border)',
  outlineOffset: '-2px',
};

const miniAppCapabilityContentStyle = {
  minHeight: '104px',
  boxSizing: 'border-box',
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'space-between',
  gap: '12px',
};

const miniAppCapabilityHeaderStyle = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: '10px',
};

const miniAppCapabilityTitleStyle = {
  margin: 0,
  fontSize: '16px',
  lineHeight: 1.25,
  fontWeight: 750,
};

const miniAppCapabilityTextStyle = {
  margin: 0,
  fontSize: '13px',
  lineHeight: 1.4,
  color: 'var(--mac-text-secondary, #5f6b7a)',
  overflowWrap: 'anywhere',
};

export default TelegramMiniAppPatientShell;
