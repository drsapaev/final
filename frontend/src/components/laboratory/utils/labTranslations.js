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
    select_patient_short: 'Выберите пациента из очереди или откройте уже существующий лабораторный отчёт.',
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
    // Editor content (STRAT#19)
    patient_label: 'Пациент',
    visit_services: 'Услуги визита',
    resolving_templates: 'Подбираю доступные отчёты для выбранного визита...',
    recommended_report: 'Рекомендуемый отчёт',
    unmapped_services: 'Ненастроенные услуги визита',
    no_template_found: 'Для выбранного визита не найдено ни одного допустимого отчёта.',
    no_template_hint: 'Настройте mapping услуги к шаблону (требуется роль Admin)',
    no_template_escape: 'или создайте отчёт без привязки к услугам.',
    show_all_templates: 'Показать все шаблоны (без привязки к услугам)',
    single_template_found: 'Единственный допустимый отчёт найден:',
    click_create_to_open: 'Нажмите «Создать отчёт», чтобы открыть его для заполнения.',
    creating_report: 'Создаю...',
    create_report: 'Создать отчёт',
    select_template: 'Выберите шаблон отчёта',
    // Print feedback (STRAT#19)
    print_sending: 'Отправляю лабораторный отчёт на печать...',
    print_sent: 'Лабораторный отчёт отправлен на печать',
    print_pdf_failed: 'Не удалось сформировать PDF. Проверьте соединение и попробуйте снова.',
    print_pdf_invalid: 'PDF сформирован некорректно. Обратитесь к администратору.',
    print_pdf_opened: 'PDF открыт в новой вкладке. Статус печати обновлён.',
    print_pdf_blocked: 'PDF сформирован, но новая вкладка заблокирована. Разрешите pop-up для этого сайта и нажмите «Печать» снова, чтобы обновить статус отчёта.',
    // Critical findings (STRAT#19)
    critical_findings: 'Критические показатели',
    critical_findings_hint: 'Проверьте правильность ввода. Критические значения требуют внимания врача.',
    // ReportEditor field-level (STRAT#24)
    norm_label: 'Норма',
    norm_not_set: 'не задана',
    threshold_label: 'Порог',
    select_value: 'Выберите значение',
    result_label: 'Результат',
    comment_placeholder: 'комментарий…',
    comment_label: 'Комментарий к полю',
    critical_value: 'Критическое значение',
    check_input: 'Проверьте правильность ввода',
    value: 'Значение',
    out_of_range: 'вне референсного диапазона',
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
    delete_section_message: '«{name}» будет удалена со всеми полями и правилами нормы.',
    delete_section_description: 'Действие нельзя отменить после сохранения черновика. Если нужно сохранить структуру — нажмите «Отмена» и сохраните текущий черновик перед удалением.',
    delete_field_title: 'Удалить показатель?',
    delete_field_message: '«{name}» будет удалён со всеми правилами нормы.',
    delete_field_description: 'Действие нельзя отменить после сохранения черновика. Если нужно сохранить поле — нажмите «Отмена».',
    // Order dialog
    order_title: 'Заказать анализы?',
    order_message: 'Будет создан заказ «{name}» для этого пациента.',
    order_description: 'Лаборатория увидит заказ в очереди и приступит к выполнению. Если заказ ошибочный — его придётся отменять через лабораторию.',
    // Archive version dialog (STRAT#10)
    archive_title: 'Архивирование версии шаблона',
    archive_message: 'Версия станет недоступна для создания новых отчётов.',
    archive_description: 'Существующие отчёты, созданные по этой версии, сохранят доступ к данным. Восстановить архивированную версию нельзя — потребуется создать новый черновик на основе существующей.',
    archive_confirm: 'Архивировать',
  },

  // ─── Template editor ─────────────────────────────────────────────────────
  template: {
    title: 'Шаблоны',
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
    loading: 'Загрузка…',
    load_more_aria: 'Загрузить ещё записи с сервера',
    no_entries: 'На сегодня не найдено лабораторных записей.',
    no_matches: 'Ничего не найдено. Измените поисковый запрос или фильтр.',
    filter_all: 'Все',
    filter_active: 'В работе',
    filter_completed: 'Завершены',
    sort_default: 'По умолчанию',
    sort_name: 'По имени',
    sort_time: 'По времени',
    sort_label: 'Сортировать:',
    sort_aria: 'Сортировка очереди',
    search_placeholder: 'Поиск по ФИО, телефону, ID…',
    search_aria: 'Поиск по очереди лаборатории',
    search_clear: 'Очистить поиск',
    filter_group_aria: 'Фильтр по статусу',
    filter_count: 'Показано',
    filter_count_search: 'поиск',
    filter_count_filter: 'фильтр',
    // Card strings (STRAT#18)
    patient_no_name: 'Пациент без имени',
    visit: 'Визит',
    visit_not_linked: 'не привязан',
    phone: 'Телефон',
    services: 'Услуги',
    payment: 'Оплата',
    patient_id_aria: 'Показать внутренний ID пациента',
    patient_id_label: 'ID пациента',
    report_exists: 'Отчёт существует',
    report_new: 'Новый отчёт',
    // History panel (STRAT#18)
    history_title: 'История отчётов пациента',
    history_empty: 'Для выбранного пациента ещё нет лабораторных отчётов.',
    history_report_number: 'Отчёт',
    history_created: 'Создан',
    history_status: 'Статус',
    history_flags: 'флагов',
    history_critical: 'критич.',
    // History panel — LabReportHistoryPanel (STRAT#21)
    history_recent_title: 'Недавние лабораторные отчёты',
    history_patient_title: 'Доступные отчёты пациента',
    history_no_saved: 'В лаборатории пока нет сохранённых отчётов для повторного открытия.',
    history_no_matches: 'Для выбранного фильтра нет лабораторных отчётов.',
    history_visit: 'Визит',
    history_no_visit: 'без визита',
    history_patient_number: 'Пациент',
    history_severity_all: 'Все',
    history_severity_clean: 'Без флагов',
    history_severity_flagged: 'С флагами',
    history_severity_critical: 'Критические',
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
    // Template-specific (STRAT#17)
    catalog_load_failed: 'Не удалось загрузить лабораторный каталог.',
    template_code_name_required: 'Укажите код и название шаблона.',
    select_template_first: 'Выберите шаблон для редактирования.',
    select_template: 'Выберите шаблон.',
    select_version_for_archive: 'Выберите версию для архивирования.',
    select_template_for_copy: 'Выберите шаблон для копирования.',
    validation_errors: 'Ошибки валидации',
    no_norm_in_catalog: 'В каталоге нет норм для этого аналита.',
    catalog_load_error: 'Ошибка загрузки из каталога',
  },

  // ─── Success messages ────────────────────────────────────────────────────
  success: {
    draft_saved: 'Черновик сохранён.',
    draft_saved_in_progress: 'Черновик сохранён. Статус изменён на «Заполняется» — отчёт теперь в работе.',
    finalized: 'Отчёт утверждён.',
    revised: 'Создана исправленная версия отчёта.',
    notified: 'Результаты отправлены пациенту через Telegram.',
    order_created: 'Заказ создан. Лаборатория увидит его в очереди.',
    template_created: 'Шаблон создан.',
    draft_restored: 'Черновик восстановлен из серверной версии.',
    report_created: 'Новый лабораторный отчёт создан.',
    // Template-specific (STRAT#17)
    template_draft_saved: 'Черновик шаблона сохранён.',
    template_published: 'Версия шаблона опубликована.',
    template_archived: 'Версия шаблона архивирована.',
    template_cloned: 'Копия шаблона создана.',
    norm_loaded_from_catalog: 'Норма загружена из каталога',
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
    show_phone_aria: 'Показать номер телефона',
    hide_phone_aria: 'Скрыть номер телефона',
    phone_restricted: 'Доступ к номеру ограничен ролью',
    phone_not_set: 'не указан',
    no_services: 'Нет данных об услугах',
  },

  // ─── AI analysis (STRAT#22) ──────────────────────────────────────────────
  ai: {
    button_label: 'AI Интерпретация',
    button_tooltip: 'AI интерпретация результатов с учётом возраста и пола пациента',
    button_disabled: 'Заполните показатели в отчёте для активации AI',
    dialog_title: 'AI Интерпретация результатов отчёта',
    dialog_close: 'Закрыть',
    dialog_close_aria: 'Закрыть AI-анализ',
    patient_label: 'Пациент',
    age_label: 'Возраст',
    age_years: 'лет',
    age_unknown: 'неизвестен',
    gender_label: 'Пол',
    gender_male: 'мужской',
    gender_female: 'женский',
    gender_other: 'другой',
    gender_not_set: 'не указан',
    fields_count: 'Показателей',
    blocked_no_results: 'AI-анализ недоступен: нет заполненных показателей в отчёте.',
    blocked_no_age: 'AI-анализ недоступен: в snapshot пациента не указан возраст. Проверьте, что у пациента заполнена дата рождения.',
    blocked_no_gender: 'AI-анализ недоступен: в snapshot пациента не указан пол. Референсные интервалы зависят от пола — интерпретация невозможна.',
    blocked_generic: 'AI-анализ недоступен: проверьте данные пациента',
    fill_fields_first: 'Сначала заполните хотя бы один показатель в отчёте.',
    missing_age_gender: 'AI-интерпретация невозможна без возраста и пола пациента.',
  },

  // ─── ContentTab field labels (STRAT#23) ──────────────────────────────────
  content: {
    header: 'Секции и показатели',
    header_fields: 'показателей в',
    header_sections: 'секц.',
    developer_mode: 'Режим разработчика',
    developer_mode_title: 'Показать raw JSON правил видимости и подсветки для каждого поля. Только для продвинутых пользователей.',
    developer_mode_aria: 'Режим разработчика (raw JSON правил)',
    add_section: 'Добавить секцию',
    add_field: 'Добавить показатель',
    load_all_norms: 'Загрузить все нормы',
    load_all_norms_title: 'Загрузить референсные интервалы из каталога для всех полей, у которых указан код аналита',
    section_aria: 'Секция',
    section_fields_count: 'полей',
    move_section_up: 'Переместить секцию вверх',
    move_section_down: 'Переместить секцию вниз',
    delete_section: 'Удалить секцию',
    section_key: 'Ключ секции',
    section_title: 'Заголовок секции',
    field_aria: 'Поле',
    field_no_title: '(без названия)',
    field_required: 'обязательное',
    move_field_up: 'Переместить поле вверх',
    move_field_down: 'Переместить поле вниз',
    duplicate_field: 'Дублировать поле',
    delete_field: 'Удалить поле',
    field_key: 'Ключ поля',
    field_label: 'Название поля',
    value_type: 'Тип значения',
    unit: 'Единица измерения',
    analyte_code: 'Код анализируемого показателя',
    unit_code: 'Код единицы измерения',
    reference_mode: 'Источник нормы',
    load_from_catalog: 'Загрузить из каталога',
    catalog_hint: 'Укажите код аналита для загрузки нормы из каталога',
    reference_text: 'Текст нормы',
    required_label: 'Обязательное',
    required_aria: 'Обязательное поле',
    advanced_rules: 'Расширенные правила (видимость / подсветка) — raw JSON',
    visibility_rules_json: 'JSON правил видимости',
    highlight_rules_json: 'JSON правил подсветки',
    section_fallback: 'Секция',
    field_fallback: 'Поле',
  },

  // ─── Session (STRAT#26 — for future migration when guardrail allows) ─────
  session: {
    expired: 'Сессия истекла. Пожалуйста, войдите снова.',
    extending: 'Продлеваем сессию...',
    warning_title: 'Сессия скоро истечёт',
    warning_body: 'Ваша сессия истекает. Продлите, чтобы не потерять несохранённые данные.',
    btn_later: 'Позже',
    btn_extend: 'Продлить сессию',
  },

  // ─── Registrar (STRAT#30) ────────────────────────────────────────────────
  registrar: {
    // Confirm dialogs
    send_to_cabinet_title: 'Отправить в кабинет',
    send_to_cabinet_message: 'Отправить пациента «{name}» в кабинет?',
    send_to_cabinet_confirm: 'Отправить',
    complete_visit_title: 'Завершение приёма',
    complete_visit_message: 'Завершить приём пациента «{name}»?',
    complete_visit_confirm: 'Завершить',
    postpone_tomorrow_title: 'Перенос на завтра',
    postpone_tomorrow_message: 'Перенести запись пациента на завтра?',
    postpone_tomorrow_description: 'Запись будет перемещена на завтрашний день. Пациенту потребуется новая запись на сегодня, если он придёт.',
    postpone_tomorrow_confirm: 'Перенести',
    postpone_date_title: 'Перенос на другую дату',
    postpone_date_confirm: 'Перенести',
    cancel: 'Отмена',
    // Notify messages
    sent_to_cabinet: 'Пациент отправлен в кабинет',
    visit_completed: 'Приём завершён',
    appointment_created: 'Запись создана! Обновите страницу для отображения изменений.',
    visit_postponed: 'Визит успешно перенесён на завтра',
    visit_postponed_date: 'Визит успешно перенесён',
    no_visit_for_postpone: 'Не удалось определить визит для переноса',
    select_postpone_date: 'Выберите дату переноса',
    invalid_date_format: 'Неверный формат даты. Используйте YYYY-MM-DD',
    invalid_time_format: 'Неверный формат времени. Используйте HH:MM',
    cannot_postpone_past: 'Нельзя перенести запись на прошедшую дату',
    backend_unavailable: 'Backend недоступен. Проверьте подключение и повторите попытку.',
    unknown_patient: 'Неизвестный пациент',
    incorrect_server_data: 'Некорректные данные от сервера',
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
