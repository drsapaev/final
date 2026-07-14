/**
 * L-H-6 fix: shared constants для templateEditor.
 * Раньше жили в LabTemplateWorkbench.jsx как module-level consts.
 * Теперь переиспользуются всеми tab-renderer'ами.
 */

export const layoutOptions = [
  { value: 'lab_table_classic_v1', label: 'Классический' },
  { value: 'lab_table_compact_v1', label: 'Компактный' }
];

export const versionStatusLabels = {
  PUBLISHED: 'Опубликован',
  DRAFT: 'Черновик',
  ARCHIVED: 'Архив'
};

export const brandingFieldLabels = {
  document_title: 'Заголовок документа',
  document_subtitle: 'Подзоловок документа',
  clinic_name: 'Название клиники',
  address: 'Адрес',
  phone: 'Телефон',
  logo_url: 'Логотип (URL)'
};

export const signerFieldLabels = {
  lab_technician_label: 'Подпись лаборанта',
  lab_technician_name: 'ФИО лаборанта',
  approver_label: 'Подпись утверждающего',
  approver_name: 'ФИО утверждающего'
};

export const fieldTypeOptions = [
  { value: 'numeric', label: 'Число' },
  { value: 'text', label: 'Текст' },
  { value: 'choice', label: 'Выбор из списка' },
  { value: 'multiline', label: 'Многострочный текст' }
];

export const referenceModeOptions = [
  { value: 'static_text', label: 'Текстовая норма' },
  { value: 'rule_based', label: 'Норма по правилам' },
  { value: 'catalog', label: 'Из каталога' }
];

export const EDITOR_TABS = [
  { id: 'content',  label: 'Содержимое' },
  { id: 'design',   label: 'Оформление' },
  { id: 'signers',  label: 'Подписи' },
  { id: 'preview',  label: 'Предпросмотр' },
];

export function formatVersionStatus(status) {
  return versionStatusLabels[status] || status;
}
