/**
 * STRAT#3: labTranslations — centralized Russian strings for the lab module.
 *
 * Раньше все русские строки были размазаны по JSX-у lab-компонентов:
 *   <Button>Сохранить черновик</Button>
 *   notify('success', 'Черновик сохранён.')
 *   <Alert>Выберите пациента из очереди...</Alert>
 *
 * Это затрудняло:
 *   1. Перевод на другие языки (каждую строку пришлось бы искать в JSX)
 *   2. Согласованность терминов (в одном месте "черновик", в другом "драфт")
 *   3. A/B тестирование текстов (нельзя подсунуть варианты)
 *
 * Этот модуль — первый шаг к i18n. Пока t() возвращает русскую строку
 * из словаря. Когда будет внедряться react-i18next на уровне проекта,
 * достаточно будет заменить t() на useTranslation().t — сигнатура та же.
 *
 * Namespace организация:
 *   - common: общие кнопки и действия (Сохранить, Отмена, Удалить)
 *   - status: статусы бланка и очереди
 *   - workbench: редактор отчёта
 *   - template: редактор шаблонов
 *   - queue: очередь лаборатории
 *   - errors: сообщения об ошибках
 *   - success: сообщения об успехе
 *
 * Usage:
 *   import { t } from './utils/labTranslations';
 *   <Button>{t('common.save')}</Button>
 *   notify('success', t('success.draft_saved'));
 */

const TRANSLATIONS = {
  // ─── Common actions ──────────────────────────────────────────────────────
  common: {
    save: 'Сохранить',
    save_draft: 'Сохранить черновик',
    cancel: 'Отмена',
    delete: 'Удалить',
    confirm: 'Подтвердить',
    close: 'Закрыть',
    refresh: 'Обновить',
    search: 'Поиск',
    reset: 'Сбросить',
    back: 'Назад',
    next: 'Далее',
    yes: 'Да',
    no: 'Нет',
  },

  // ─── Lab report statuses (single source of truth) ────────────────────────
  // Дублирует labStatusConfig.js labels — но это намеренно: когда i18n
  // будет подключён, labStatusConfig будет читать отсюда.
  status: {
    draft: 'Черновик',
    in_progress: 'Заполняется',
    ready: 'Готов к проверке',
    finalized: 'Утверждён',
    printed: 'Напечатан',
    archived: 'Архив',
    unknown: 'Неизвестно',
  },

  // ─── Queue statuses ──────────────────────────────────────────────────────
  queue_status: {
    waiting: 'Ожидает',
    confirmed: 'Подтверждён',
    pending: 'Ожидает',
    called: 'Вызван',
    in_progress: 'В работе',
    completed: 'Завершён',
    done: 'Завершён',
  },

  // ─── Workbench (report editor) ───────────────────────────────────────────
  workbench: {
    title: 'Редактор лабораторного отчёта',
    select_patient_prompt: 'Выберите пациента из очереди или откройте уже существующий лабораторный отчёт из списка ниже.',
    new_revision: 'исправленная версия отчёта',
    required_fields_missing: 'Не заполнено',
    unsaved_changes: 'несохранённые изменения',
    saving: 'сохраняется…',
    saved_at: 'сохранено',
    signatures: 'Подписи',
    signatures_readonly_hint: 'только для чтения — отчёт утверждён',
    progress_aria_label: 'Прогресс бланка',
    step_completed: 'пройден',
    step_current: 'текущий шаг',
    step_upcoming: 'предстоит',
  },

  // ─── Actions bar ─────────────────────────────────────────────────────────
  actions: {
    save_draft: 'Сохранить черновик',
    saving: 'Сохраняю…',
    finalize: 'Утвердить',
    finalizing: 'Утверждаю…',
    revise: 'Исправленная версия',
    revising: 'Создаю…',
    revise_title: 'Создать исправленную версию отчёта',
    print: 'Печать результата',
    printing: 'Отправляю…',
    notify_patient: 'Отправить пациенту',
    notifying: 'Отправляю…',
  },

  // ─── Confirm dialogs ─────────────────────────────────────────────────────
  confirm: {
    // Common labels
    finalize_confirm: 'Утвердить',
    revise_confirm: 'Создать версию',
    notify_confirm: 'Отправить',
    reset_confirm: 'Сбросить',
    delete_section_confirm: 'Удалить секцию',
    delete_field_confirm: 'Удалить поле',
    order_confirm: 'Заказать',
    cancel: 'Отмена',
    // Finalize dialog
    finalize_title: 'Утверждение отчёта',
    finalize_message: 'После утверждения отчёт становится неизменяемым.',
    finalize_description: 'Редактирование полей и подписей будет заблокировано. Для исправления потребуется создать исправленную версию. Действие нельзя отменить.',
    // Revise dialog
    revise_title: 'Создание исправленной версии',
    revise_message: 'Будет создана новая версия отчёта на основе утверждённой.',
    revise_description: 'Старая версия останется в истории как утверждённая. Новая версия станет активной и доступной для редактирования. Это действие создаёт запись в аудите.',
    // Notify dialog
    notify_title: 'Отправка результатов пациенту',
    notify_message: 'Результаты будут отправлены в Telegram.',
    notify_description: 'Сообщение нельзя отозвать. Пациент получит PDF с результатами лабораторных анализов. Перед отправкой убедитесь, что отчёт утверждён и не содержит ошибок.',
    // Reset draft dialog
    reset_draft_title: 'Сброс черновика',
    reset_draft_message: 'Все несохранённые изменения будут потеряны.',
    reset_draft_description: 'Восстановится последняя версия с сервера. Действие нельзя отменить. Если нужно сохранить текущее состояние — нажмите «Отмена» и «Сохранить черновик».',
    // Delete section/field dialogs
    delete_section_title: 'Удалить секцию?',
    delete_field_title: 'Удалить показатель?',
    // Order dialog
    order_title: 'Заказать анализы?',
    order_message: 'Будет создан заказ для этого пациента.',
    order_description: 'Лаборатория увидит заказ в очереди и приступит к выполнению. Если заказ ошибочный — его придётся отменять через лабораторию.',
    // Archive version dialog (STRAT#10)
    archive_title: 'Архивирование версии шаблона',
    archive_message: 'Версия станет недоступна для создания новых отчётов.',
    archive_description: 'Существующие отчёты, созданные по этой версии, сохранят доступ к данным. Восстановить архивированную версию нельзя — потребуется создать новый черновик на основе существующей.',
    archive_confirm: 'Архивировать',
  },

  // ─── Template editor ─────────────────────────────────────────────────────
  template: {
    content_tab: 'Содержимое',
    design_tab: 'Оформление',
    signers_tab: 'Подписи',
    preview_tab: 'Предпросмотр',
    add_section: 'Добавить секцию',
    add_field: 'Добавить показатель',
    load_all_references: 'Загрузить все нормы',
    load_from_catalog: 'Загрузить из каталога',
    developer_mode: 'Режим разработчика',
    new_template: 'Новый',
    clone: 'Клонировать',
    publish: 'Опубликовать',
    archive: 'Архивировать',
  },

  // ─── Queue ───────────────────────────────────────────────────────────────
  queue: {
    title: 'Очередь лаборатории',
    total: 'Всего',
    in_progress: 'В работе',
    show_more: 'Показать ещё',
    remaining: 'осталось',
    no_entries: 'На сегодня не найдено лабораторных записей.',
    no_matches: 'Ничего не найдено. Измените поисковый запрос или фильтр.',
    filter_all: 'Все',
    filter_active: 'В работе',
    filter_completed: 'Завершены',
    sort_default: 'По умолчанию',
    sort_name: 'По имени',
    sort_time: 'По времени',
  },

  // ─── Error messages ──────────────────────────────────────────────────────
  errors: {
    select_patient_template: 'Выберите запись и шаблон.',
    no_template_for_services: 'Для выбранных услуг нет настроенного лабораторного отчёта. Добавьте mapping service_code -> template.',
    open_or_create_first: 'Сначала создайте или откройте отчёт.',
    save_failed: 'Не удалось сохранить.',
    finalize_failed: 'Не удалось утвердить отчёт.',
    print_failed: 'Не удалось сформировать PDF.',
    notify_failed: 'Не удалось отправить результаты пациенту.',
    order_failed: 'Не удалось создать заказ.',
    invalid_numeric: 'Некорректное числовое значение',
    field_restored: 'Поле возвращено к предыдущему значению.',
  },

  // ─── Success messages ────────────────────────────────────────────────────
  success: {
    draft_saved: 'Черновик сохранён.',
    draft_saved_in_progress: 'Черновик сохранён. Статус изменён на «Заполняется» — отчёт теперь в работе.',
    finalized: 'Отчёт утверждён.',
    revised: 'Создана исправленная версия отчёта.',
    notified: 'Результаты отправлены пациенту через Telegram.',
    order_created: 'Заказ создан. Лаборатория увидит его в очереди.',
    template_created: 'Новый шаблон создан.',
    draft_restored: 'Черновик восстановлен из серверной версии.',
  },

  // ─── Empty states ────────────────────────────────────────────────────────
  empty: {
    no_lab_results: 'Нет готовых результатов анализов для этого пациента.',
    no_templates: 'Нет опубликованных шаблонов анализов.',
    loading_results: 'Загрузка результатов анализов…',
    loading_templates: 'Загрузка шаблонов…',
  },

  // ─── PII / privacy ───────────────────────────────────────────────────────
  pii: {
    show_patient_id: 'ID пациента',
    show_phone: 'Показать номер (доступ ограничен)',
    hide_phone: 'Скрыть номер',
    phone_restricted: 'Доступ к номеру ограничен ролью',
    phone_not_set: 'не указан',
  },
};

/**
 * t(key) — возвращает перевод по dotted-ключу.
 *
 * @example t('common.save') → 'Сохранить'
 * @example t('errors.save_failed') → 'Не удалось сохранить.'
 *
 * Если ключ не найден — возвращает сам ключ (полезно для отладки).
 * Когда будет подключён react-i18next, t() будет заменён на
 * useTranslation().t с тем же синтаксисом.
 */
export function t(key) {
  if (!key || typeof key !== 'string') return key;
  const parts = key.split('.');
  let current = TRANSLATIONS;
  for (const part of parts) {
    if (current && typeof current === 'object' && part in current) {
      current = current[part];
    } else {
      // Key not found — return the key itself for debugging
      return key;
    }
  }
  return typeof current === 'string' ? current : key;
}

/**
 * tInterpolate(key, params) — перевод с подстановкой параметров.
 *
 * @example tInterpolate('errors.invalid_numeric', { value: 'abc' })
 *   → 'Некорректное числовое значение: "abc"'
 *
 * Шаблон: строки вида "Текст {paramName}" — {paramName} заменяется на params[paramName].
 */
export function tInterpolate(key, params = {}) {
  const template = t(key);
  if (!params || typeof params !== 'object') return template;
  return template.replace(/\{(\w+)\}/g, (match, paramName) => {
    return params[paramName] !== undefined ? String(params[paramName]) : match;
  });
}

// Export the raw dictionary for migration tools and tests.
export { TRANSLATIONS };
