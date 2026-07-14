/**
 * Registrar Panel translations.
 *
 * QW-06 fix: extracted from RegistrarPanel.jsx (was 50+ inline keys).
 * Added EN translations (previously missing — EN users saw RU fallback).
 *
 * Usage:
 *   import { getRegistrarTranslator } from './registrarTranslations';
 *   const t = getRegistrarTranslator(language);
 *   t('welcome'); // → 'Добро пожаловать' (ru) | 'Xush kelibsiz' (uz) | 'Welcome' (en)
 *
 * Future: merge into locales/{ru,uz,en}.js registrar section once
 * useTranslation.jsx is refactored to use the centralized locale files
 * (currently useTranslation.jsx has its own inline dict — see audit
 * §5.6 Consistency and §8 Strategic Changes, Direction 3).
 */

const translations = {
  ru: {
    // Основные
    welcome: 'Добро пожаловать',
    start_work: 'Начать работу',
    quick_start: 'Быстрый старт',
    loading: 'Загрузка',
    error: 'Ошибка',
    success: 'Успешно',
    warning: 'Предупреждение',
    // Вкладки
    tabs_welcome: 'Главная',
    tabs_appointments: 'Все записи',
    tabs_cardio: 'Кардиолог',
    tabs_echokg: 'ЭКГ',
    tabs_derma: 'Дерматолог',
    tabs_dental: 'Стоматолог',
    tabs_lab: 'Лаборатория',
    tabs_procedures: 'Процедуры',
    tabs_queue: 'Онлайн-очередь',
    // UX Audit R-3.8: subtitle для QueueView
    queue_subtitle: 'Управление онлайн-записью и QR кодами для очереди',
    // Действия
    new_appointment: 'Новая запись',
    export_csv: 'Экспорт CSV',
    today: 'Сегодня',
    reset: 'Сбросить',
    confirm: 'Подтвердить',
    cancel: 'Отменить',
    no_show: 'Неявка',
    reason: 'Причина',
    search: 'Поиск',
    filter: 'Фильтр',
    clear_filter: 'Очистить фильтр',
    // Мастер
    patient: 'Пациент',
    details: 'Детали',
    payment: 'Оплата',
    next: 'Далее',
    back: 'Назад',
    save: 'Сохранить',
    close: 'Закрыть',
    add_to_queue: 'Добавить в очередь',
    priority: 'Приоритет',
    available_slots: 'Доступные слоты',
    tomorrow: 'Завтра',
    select_date: 'Выбрать дату',
    online_payment: 'Онлайн оплата',
    // Поля формы
    full_name: 'ФИО',
    birth_date: 'Дата рождения',
    phone: 'Телефон',
    address: 'Адрес',
    services: 'Услуги',
    doctor: 'Врач',
    appointment_type: 'Тип обращения',
    payment_method: 'Способ оплаты',
    amount: 'Сумма',
    // Статусы
    status_scheduled: 'Запланирован',
    status_confirmed: 'Подтвержден',
    status_queued: 'В очереди',
    status_in_cabinet: 'В кабинете',
    status_done: 'Завершен',
    status_cancelled: 'Отменен',
    status_no_show: 'Неявка',
    status_paid_pending: 'Ожидает оплаты',
    status_paid: 'Оплачен',
    // Статистика
    total_patients: 'Всего пациентов',
    today_appointments: 'Записей сегодня',
    pending_payments: 'Ожидают оплаты',
    active_queues: 'Активные очереди',
    empty_table: 'Нет данных для отображения',
    // Сообщения
    appointment_created: 'Запись создана успешно',
    appointment_cancelled: 'Запись отменена',
    payment_successful: 'Оплата прошла успешно',
    print_ticket: 'Печать талона',
    auto_refresh: 'Автообновление',
    data_source_demo: 'Показаны демо-данные',
    data_source_api: 'Данные загружены с сервера',
  },
  uz: {
    // Asosiy
    welcome: 'Xush kelibsiz',
    start_work: 'Ishni boshlash',
    quick_start: 'Tezkor start',
    loading: 'Yuklanmoqda',
    error: 'Xatolik',
    success: 'Muvaffaqiyatli',
    warning: 'Ogohlantirish',
    // Vkladkalar
    tabs_welcome: 'Asosiy',
    tabs_appointments: 'Yozilganlar',
    tabs_cardio: 'Kardiolog',
    tabs_echokg: 'EKG',
    tabs_derma: 'Dermatolog',
    tabs_dental: 'Stomatolog',
    tabs_lab: 'Laboratoriya',
    tabs_procedures: 'Muolajalar',
    tabs_queue: 'Navbat',
    // UX Audit R-3.8: subtitle для QueueView
    queue_subtitle: 'Onlayn yozilish va navbat uchun QR kodlarni boshqarish',
    // Amallar
    new_appointment: 'Yangi yozuv',
    export_csv: 'CSV eksport',
    today: 'Bugun',
    reset: 'Tozalash',
    confirm: 'Tasdiqlash',
    cancel: 'Bekor qilish',
    no_show: 'Kelmaslik',
    reason: 'Sabab',
    search: 'Qidirish',
    filter: 'Filter',
    clear_filter: 'Filterni tozalash',
    // Master
    patient: 'Bemor',
    details: 'Tafsilotlar',
    payment: 'To\'lov',
    next: 'Keyingi',
    back: 'Orqaga',
    save: 'Saqlash',
    close: 'Yopish',
    add_to_queue: 'Navbatga qo\'shish',
    priority: 'Ustuvorlik',
    available_slots: 'Mavjud vaqtlar',
    tomorrow: 'Ertaga',
    select_date: 'Sanani tanlash',
    online_payment: 'Onlayn to\'lov',
    // Forma maydonlari
    full_name: 'F.I.Sh',
    birth_date: 'Tug\'ilgan sana',
    phone: 'Telefon',
    address: 'Manzil',
    services: 'Xizmatlar',
    doctor: 'Shifokor',
    appointment_type: 'Murojaat turi',
    payment_method: 'To\'lov usuli',
    amount: 'Summa',
    // Holatlar
    status_scheduled: 'Rejalashtirilgan',
    status_confirmed: 'Tasdiqlangan',
    status_queued: 'Navbatda',
    status_in_cabinet: 'Kabinetda',
    status_done: 'Tugallangan',
    status_cancelled: 'Bekor qilingan',
    status_no_show: 'Kelmagan',
    status_paid_pending: 'To\'lovni kutmoqda',
    status_paid: 'To\'langan',
    // Statistika
    total_patients: 'Jami bemorlar',
    today_appointments: 'Bugungi yozuvlar',
    pending_payments: 'To\'lovni kutmoqda',
    active_queues: 'Faol navbatlar',
    empty_table: 'Ma\'lumot yo\'q',
    // Xabarlar
    appointment_created: 'Yozuv muvaffaqiyatli yaratildi',
    appointment_cancelled: 'Yozuv bekor qilindi',
    payment_successful: 'To\'lov muvaffaqiyatli o\'tdi',
    print_ticket: 'Talon chop etish',
    auto_refresh: 'Avtomatik yangilash',
    data_source_demo: 'Demo ma\'lumotlar ko\'rsatilgan',
    data_source_api: 'Ma\'lumotlar serverdan yuklandi',
  },
  en: {
    // Main
    welcome: 'Welcome',
    start_work: 'Start work',
    quick_start: 'Quick start',
    loading: 'Loading',
    error: 'Error',
    success: 'Success',
    warning: 'Warning',
    // Tabs
    tabs_welcome: 'Home',
    tabs_appointments: 'All appointments',
    tabs_cardio: 'Cardiologist',
    tabs_echokg: 'ECG',
    tabs_derma: 'Dermatologist',
    tabs_dental: 'Dentist',
    tabs_lab: 'Laboratory',
    tabs_procedures: 'Procedures',
    tabs_queue: 'Online queue',
    // UX Audit R-3.8: subtitle для QueueView
    queue_subtitle: 'Manage online booking and QR codes for the queue',
    // Actions
    new_appointment: 'New appointment',
    export_csv: 'Export CSV',
    today: 'Today',
    reset: 'Reset',
    confirm: 'Confirm',
    cancel: 'Cancel',
    no_show: 'No-show',
    reason: 'Reason',
    search: 'Search',
    filter: 'Filter',
    clear_filter: 'Clear filter',
    // Wizard
    patient: 'Patient',
    details: 'Details',
    payment: 'Payment',
    next: 'Next',
    back: 'Back',
    save: 'Save',
    close: 'Close',
    add_to_queue: 'Add to queue',
    priority: 'Priority',
    available_slots: 'Available slots',
    tomorrow: 'Tomorrow',
    select_date: 'Select date',
    online_payment: 'Online payment',
    // Form fields
    full_name: 'Full name',
    birth_date: 'Date of birth',
    phone: 'Phone',
    address: 'Address',
    services: 'Services',
    doctor: 'Doctor',
    appointment_type: 'Appointment type',
    payment_method: 'Payment method',
    amount: 'Amount',
    // Statuses
    status_scheduled: 'Scheduled',
    status_confirmed: 'Confirmed',
    status_queued: 'In queue',
    status_in_cabinet: 'In cabinet',
    status_done: 'Completed',
    status_cancelled: 'Cancelled',
    status_no_show: 'No-show',
    status_paid_pending: 'Awaiting payment',
    status_paid: 'Paid',
    // Statistics
    total_patients: 'Total patients',
    today_appointments: 'Today\'s appointments',
    pending_payments: 'Pending payments',
    active_queues: 'Active queues',
    empty_table: 'No data to display',
    // Messages
    appointment_created: 'Appointment created successfully',
    appointment_cancelled: 'Appointment cancelled',
    payment_successful: 'Payment successful',
    print_ticket: 'Print ticket',
    auto_refresh: 'Auto-refresh',
    data_source_demo: 'Showing demo data',
    data_source_api: 'Data loaded from server',
  },
};

/**
 * Returns a translator function for the given language.
 * Falls back to Russian, then to the key itself if neither is found.
 *
 * @param {'ru'|'uz'|'en'} language - UI language code
 * @returns {(key: string) => string} translator function
 */
export const getRegistrarTranslator = (language) => (key) =>
  (translations[language] && translations[language][key]) ||
  translations.ru[key] ||
  key;

export default translations;
