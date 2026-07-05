import { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Icon,
  Input,
  Checkbox } from '../ui/macos';
import { labReportingApi } from '../../api/labReporting';

const blankField = () => ({
  analyte_code: '',
  unit_code: '',
  field_key: '',
  label: '',
  value_type: 'numeric',
  unit: '',
  reference_mode: 'static_text',
  reference_text: '',
  reference_rule: null,
  visibility_rule: null,
  highlight_rule: null,
  choice_options: null,
  sort_order: 0,
  required: false
});

const blankSection = (index) => ({
  key: `section_${index}`,
  title: `Раздел ${index}`,
  sort_order: index * 10,
  section_style: {},
  fields: [blankField()]
});

const blankVersion = {
  layout_preset: 'lab_table_classic_v1',
  page_settings: { paper_size: 'A4', orientation: 'portrait' },
  branding_overrides: {
    document_title: '',
    document_subtitle: '',
    clinic_name: '',
    address: '',
    phone: '',
    logo_url: ''
  },
  signer_defaults: {
    lab_technician_label: 'Лаборант',
    lab_technician_name: '',
    approver_label: 'Подпись',
    approver_name: ''
  },
  footer_notes: '',
  sections: [blankSection(1)]
};

const layoutOptions = [
  { value: 'lab_table_classic_v1', label: 'Классический' },
  { value: 'lab_table_compact_v1', label: 'Компактный' }
];

const versionStatusLabels = {
  PUBLISHED: 'Опубликован',
  DRAFT: 'Черновик',
  ARCHIVED: 'Архив'
};

const brandingFieldLabels = {
  document_title: 'Заголовок документа',
  document_subtitle: 'Подзаголовок документа',
  clinic_name: 'Название клиники',
  address: 'Адрес',
  phone: 'Телефон',
  logo_url: 'Логотип (URL)'
};

const signerFieldLabels = {
  lab_technician_label: 'Подпись лаборанта',
  lab_technician_name: 'ФИО лаборанта',
  approver_label: 'Подпись утверждающего',
  approver_name: 'ФИО утверждающего'
};

const fieldTypeOptions = [
  { value: 'numeric', label: 'Число' },
  { value: 'text', label: 'Текст' },
  { value: 'choice', label: 'Выбор из списка' },
  { value: 'multiline', label: 'Многострочный текст' }
];

const referenceModeOptions = [
  { value: 'static_text', label: 'Текстовая норма' },
  { value: 'rule_based', label: 'Норма по правилам' },
  { value: 'catalog', label: 'Из каталога' }
];

function formatVersionStatus(status) {
  return versionStatusLabels[status] || status;
}

const TEMPLATE_VERSION_ACTION_CAN_FIELD = {
  update: 'can_update',
  publish: 'can_publish',
  create_draft: 'can_create_draft'
};

function hasTemplateVersionAction(version, action) {
  const normalizedAction = String(action || '').trim().toLowerCase();
  if (!normalizedAction) {
    return false;
  }

  if (Array.isArray(version?.available_actions)) {
    return version.available_actions.some(
      (availableAction) => String(availableAction || '').trim().toLowerCase() === normalizedAction
    );
  }

  const flagName = TEMPLATE_VERSION_ACTION_CAN_FIELD[normalizedAction];
  if (flagName && Object.prototype.hasOwnProperty.call(version || {}, flagName)) {
    return Boolean(version[flagName]);
  }

  return false;
}

function parseJsonInput(value) {
  if (!value?.trim()) {
    return null;
  }
  try {
    return JSON.parse(value);
  } catch {
    return Symbol.for('invalid-json');
  }
}

function stringifyJson(value) {
  if (!value) {
    return '';
  }
  return JSON.stringify(value, null, 2);
}

function buildVersionPayload(draftVersion) {
  const sections = draftVersion.sections.map((section, sectionIndex) => ({
    ...section,
    sort_order: section.sort_order ?? (sectionIndex + 1) * 10,
    section_style: section.section_style || {},
    fields: section.fields.map((field, fieldIndex) => {
      const referenceRule = parseJsonInput(field.reference_rule_text || '');
      const visibilityRule = parseJsonInput(field.visibility_rule_text || '');
      const highlightRule = parseJsonInput(field.highlight_rule_text || '');
      if ([referenceRule, visibilityRule, highlightRule].includes(Symbol.for('invalid-json'))) {
        throw new Error('Один из JSON-блоков правил заполнен некорректно');
      }
      return {
        ...field,
        sort_order: field.sort_order ?? (fieldIndex + 1) * 10,
        reference_rule: referenceRule,
        visibility_rule: visibilityRule,
        highlight_rule: highlightRule,
        reference_rule_text: undefined,
        visibility_rule_text: undefined,
        highlight_rule_text: undefined
      };
    })
  }));

  return {
    layout_preset: draftVersion.layout_preset,
    page_settings: draftVersion.page_settings || { paper_size: 'A4', orientation: 'portrait' },
    branding_overrides: draftVersion.branding_overrides || {},
    signer_defaults: draftVersion.signer_defaults || {},
    footer_notes: draftVersion.footer_notes || '',
    sections
  };
}

function hydrateVersion(version) {
  if (!version) {
    return { ...blankVersion, sections: [blankSection(1)] };
  }
  return {
    layout_preset: version.layout_preset,
    page_settings: version.page_settings || { paper_size: 'A4', orientation: 'portrait' },
    branding_overrides: {
      clinic_name: '',
      address: '',
      phone: '',
      logo_url: '',
      document_title: '',
      document_subtitle: '',
      ...(version.branding_overrides || {})
    },
    signer_defaults: {
      lab_technician_label: 'Лаборант',
      lab_technician_name: '',
      approver_label: 'Подпись',
      approver_name: '',
      ...(version.signer_defaults || {})
    },
    footer_notes: version.footer_notes || '',
    sections: (version.sections || []).map((section) => ({
      ...section,
      fields: (section.fields || []).map((field) => ({
        ...field,
        reference_rule_text: stringifyJson(field.reference_rule),
        visibility_rule_text: stringifyJson(field.visibility_rule),
        highlight_rule_text: stringifyJson(field.highlight_rule)
      }))
    }))
  };
}

export default function LabTemplateWorkbench({
  templates,
  selectedTemplate = null,
  onSelectTemplate,
  onTemplatesChanged,
  notify
}) {
  // WF-21 fix: search в списке шаблонов для консистентности с LabQueueWorkbench.
  const [templateSearch, setTemplateSearch] = useState('');
  const [draftVersion, setDraftVersion] = useState(hydrateVersion(null));
  const [newTemplate, setNewTemplate] = useState({
    code: '',
    name: '',
    family: 'hematology',
    description: ''
  });
  const [saving, setSaving] = useState(false);
  const [catalogUnits, setCatalogUnits] = useState([]);
  const [catalogAnalytes, setCatalogAnalytes] = useState([]);

  const activeVersion = useMemo(() => {
    if (!selectedTemplate) {
      return null;
    }
    return selectedTemplate.versions.find((version) => version.id === selectedTemplate.draft_version_id)
      || selectedTemplate.versions.find((version) => version.id === selectedTemplate.published_version_id)
      || selectedTemplate.versions[selectedTemplate.versions.length - 1]
      || null;
  }, [selectedTemplate]);

  useEffect(() => {
    setDraftVersion(hydrateVersion(activeVersion));
  }, [activeVersion]);

  useEffect(() => {
    let cancelled = false;

    async function loadCatalog() {
      try {
        const [units, analytes] = await Promise.all([
          labReportingApi.listCatalogUnits(),
          labReportingApi.listCatalogAnalytes()
        ]);
        if (cancelled) {
          return;
        }
        setCatalogUnits(units);
        setCatalogAnalytes(analytes);
      } catch (error) {
        if (!cancelled) {
          notify('error', error.message || 'Не удалось загрузить лабораторный каталог.');
        }
      }
    }

    loadCatalog();
    return () => {
      cancelled = true;
    };
  }, [notify]);

  async function handleCreateTemplate() {
    if (!newTemplate.code || !newTemplate.name) {
      notify('error', 'Укажите код и название шаблона.');
      return;
    }
    setSaving(true);
    try {
      await labReportingApi.createTemplate({
        ...newTemplate,
        initial_version: blankVersion
      });
      notify('success', 'Шаблон создан.');
      setNewTemplate({ code: '', name: '', family: 'hematology', description: '' });
      await onTemplatesChanged();
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
    }
  }

  async function ensureDraftVersion() {
    if (!selectedTemplate) {
      throw new Error('Сначала выберите шаблон');
    }
    if (hasTemplateVersionAction(activeVersion, 'update')) {
      return activeVersion.id;
    }
    if (!hasTemplateVersionAction(activeVersion, 'create_draft')) {
      throw new Error('Сервер не разрешил создать черновик для этой версии шаблона');
    }
    const version = await labReportingApi.createTemplateVersion(selectedTemplate.id, activeVersion?.id || null);
    await onTemplatesChanged(selectedTemplate.id);
    return version.id;
  }

  async function handleSaveTemplate() {
    if (!selectedTemplate) {
      notify('error', 'Выберите шаблон для редактирования.');
      return;
    }
    setSaving(true);
    try {
      const versionId = await ensureDraftVersion();
      const payload = buildVersionPayload(draftVersion);
      await labReportingApi.updateTemplateVersion(versionId, payload);
      notify('success', 'Черновик шаблона сохранён.');
      await onTemplatesChanged(selectedTemplate.id);
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
    }
  }

  async function handlePublishVersion() {
    if (!selectedTemplate) {
      notify('error', 'Выберите шаблон.');
      return;
    }
    setSaving(true);
    try {
      const versionId = await ensureDraftVersion();
      await labReportingApi.updateTemplateVersion(versionId, buildVersionPayload(draftVersion));
      await labReportingApi.publishTemplateVersion(versionId);
      notify('success', 'Версия шаблона опубликована.');
      await onTemplatesChanged(selectedTemplate.id);
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleCloneTemplate() {
    if (!selectedTemplate) {
      notify('error', 'Выберите шаблон для копирования.');
      return;
    }
    setSaving(true);
    try {
      const cloned = await labReportingApi.cloneTemplate(selectedTemplate.id);
      notify('success', 'Копия шаблона создана.');
      await onTemplatesChanged(cloned.id);
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
    }
  }

  function updateBranding(key, value) {
    setDraftVersion((prev) => ({
      ...prev,
      branding_overrides: {
        ...prev.branding_overrides,
        [key]: value
      }
    }));
  }

  function updateSigner(key, value) {
    setDraftVersion((prev) => ({
      ...prev,
      signer_defaults: {
        ...prev.signer_defaults,
        [key]: value
      }
    }));
  }

  function updateSection(sectionIndex, key, value) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section, index) => (
        index === sectionIndex ? { ...section, [key]: value } : section
      ))
    }));
  }

  function updateField(sectionIndex, fieldIndex, key, value) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section, index) => {
        if (index !== sectionIndex) {
          return section;
        }
        return {
          ...section,
          fields: section.fields.map((field, nestedIndex) => (
            nestedIndex === fieldIndex ? { ...field, [key]: value } : field
          ))
        };
      })
    }));
  }

  function updateFieldCatalog(sectionIndex, fieldIndex, key, value) {
    if (key !== 'analyte_code') {
      updateField(sectionIndex, fieldIndex, key, value);
      return;
    }
    const analyte = catalogAnalytes.find((item) => item.code === value);
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section, index) => {
        if (index !== sectionIndex) {
          return section;
        }
        return {
          ...section,
          fields: section.fields.map((field, nestedIndex) => {
            if (nestedIndex !== fieldIndex) {
              return field;
            }
            return {
              ...field,
              analyte_code: value,
              unit_code: analyte?.default_unit_code || field.unit_code || ''
            };
          })
        };
      })
    }));
  }

  function addSection() {
    setDraftVersion((prev) => ({
      ...prev,
      sections: [...prev.sections, blankSection(prev.sections.length + 1)]
    }));
  }

  function addField(sectionIndex) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section, index) => (
        index === sectionIndex
          ? { ...section, fields: [...section.fields, blankField()] }
          : section
      ))
    }));
  }

  function removeField(sectionIndex, fieldIndex) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section, index) => (
        index === sectionIndex
          ? { ...section, fields: section.fields.filter((_, nestedIndex) => nestedIndex !== fieldIndex) }
          : section
      ))
    }));
  }

  function removeSection(sectionIndex) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.filter((_, index) => index !== sectionIndex)
    }));
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 'var(--mac-spacing-4)', alignItems: 'start' }}>
      <Card variant="filled" padding="none">
        <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: 'var(--mac-spacing-4)' }}>
          <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
            <Icon name="rectangle.stack.badge.plus" size={20} />
            Шаблоны
          </CardTitle>
        </CardHeader>
        <CardContent style={{ padding: 'var(--mac-spacing-4)', background: 'var(--mac-bg-secondary)', display: 'grid', gap: 'var(--mac-spacing-4)' }}>
          <div style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
            <Input className="macos-input" aria-label="Код шаблона" placeholder="Код шаблона" value={newTemplate.code} onChange={(event) => setNewTemplate((prev) => ({ ...prev, code: event.target.value }))} />
            <Input className="macos-input" aria-label="Название шаблона" placeholder="Название" value={newTemplate.name} onChange={(event) => setNewTemplate((prev) => ({ ...prev, name: event.target.value }))} />
            <Input className="macos-input" aria-label="Семейство шаблона" placeholder="Семейство" value={newTemplate.family} onChange={(event) => setNewTemplate((prev) => ({ ...prev, family: event.target.value }))} />
            <textarea className="macos-input" aria-label="Описание шаблона" rows={3} placeholder="Описание" value={newTemplate.description} onChange={(event) => setNewTemplate((prev) => ({ ...prev, description: event.target.value }))} />
            <Button variant="primary" onClick={handleCreateTemplate} disabled={saving}>
              <Icon name="plus" size={16} />
              Создать шаблон
            </Button>
          </div>

          {/* WF-21 fix: search для консистентности с LabQueueWorkbench */}
          <div style={{ position: 'relative', marginBottom: 'var(--mac-spacing-2)' }}>
            <Input
              type="search"
              value={templateSearch}
              onChange={(e) => setTemplateSearch(e.target.value)}
              placeholder="Поиск по названию, коду, семейству…"
              aria-label="Поиск шаблонов"
              style={{
                width: '100%',
                padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                borderRadius: 'var(--mac-radius-lg)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                outline: 'none',
              }}
            />
            {templateSearch && (
              <button
                type="button"
                onClick={() => setTemplateSearch('')}
                aria-label="Очистить поиск"
                style={{
                  position: 'absolute', right: '8px', top: '50%',
                  transform: 'translateY(-50%)', background: 'none',
                  border: 'none', cursor: 'pointer',
                  color: 'var(--mac-text-muted)', fontSize: 'var(--mac-font-size-lg)',
                }}
              >
                ×
              </button>
            )}
          </div>

          <div style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
            {templates
              .filter((t) => {
                if (!templateSearch.trim()) return true;
                const q = templateSearch.trim().toLowerCase();
                return [t.name, t.code, t.family].some((f) => (f || '').toLowerCase().includes(q));
              })
              .map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() => onSelectTemplate(template.id)}
                style={{
                  border: '1px solid var(--mac-border)',
                  borderRadius: '14px',
                  padding: 'var(--mac-spacing-3)',
                  textAlign: 'left',
                  background: selectedTemplate?.id === template.id ? 'color-mix(in oklab, var(--mac-accent) 10%, var(--mac-bg-primary))' : 'var(--mac-bg-primary)',
                  cursor: 'pointer',
                  display: 'grid',
                  gap: 'var(--mac-spacing-2)'
                }}
              >
                <div style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>{template.name}</div>
                <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>{template.code} • {template.family}</div>
                <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap' }}>
                  {template.published_version_id && <Badge variant="success">Опубликован</Badge>}
                  {template.draft_version_id && <Badge variant="warning">Черновик</Badge>}
                </div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card variant="filled" padding="none">
        <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: 'var(--mac-spacing-4)' }}>
          <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--mac-spacing-3)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
              <Icon name="slider.horizontal.3" size={20} />
              Редактор бланка
            </span>
            {selectedTemplate && (
              <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap' }}>
                <Button variant="outline" onClick={handleCloneTemplate} disabled={saving}>
                  <Icon name="doc.on.doc" size={16} />
                  Клонировать
                </Button>
                <Button variant="outline" onClick={handleSaveTemplate} disabled={saving}>
                  <Icon name="square.and.arrow.down" size={16} />
                  Сохранить черновик
                </Button>
                <Button variant="primary" onClick={handlePublishVersion} disabled={saving}>
                  <Icon name="checkmark.seal" size={16} />
                  Опубликовать
                </Button>
              </div>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent style={{ padding: 'var(--mac-spacing-4)', background: 'var(--mac-bg-secondary)' }}>
          {!selectedTemplate ? (
            <Alert severity="info">Выберите шаблон слева, чтобы редактировать оформление, секции и строки анализов.</Alert>
          ) : (
            <div style={{ display: 'grid', gap: '18px' }}>
              <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap', alignItems: 'center' }}>
                <Badge variant="info">{selectedTemplate.code}</Badge>
                <Badge variant="primary">{selectedTemplate.family}</Badge>
                {activeVersion?.status && <Badge variant={activeVersion.status === 'PUBLISHED' ? 'success' : 'warning'}>{formatVersionStatus(activeVersion.status)}</Badge>}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 'var(--mac-spacing-3)' }}>
                <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                  <span>Макет печати</span>
                  <select className="macos-input" aria-label="Макет печати" value={draftVersion.layout_preset} onChange={(event) => setDraftVersion((prev) => ({ ...prev, layout_preset: event.target.value }))}>
                    {layoutOptions.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                  <span>Подвал</span>
                  <textarea className="macos-input" aria-label="Подвал шаблона" rows={3} value={draftVersion.footer_notes} onChange={(event) => setDraftVersion((prev) => ({ ...prev, footer_notes: event.target.value }))} />
                </label>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 'var(--mac-spacing-3)' }}>
                {['document_title', 'document_subtitle', 'clinic_name', 'address', 'phone', 'logo_url'].map((key) => (
                  <label key={key} style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                    <span>{brandingFieldLabels[key] || key}</span>
                    <Input className="macos-input" aria-label={brandingFieldLabels[key] || key} value={draftVersion.branding_overrides?.[key] || ''} onChange={(event) => updateBranding(key, event.target.value)} />
                  </label>
                ))}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 'var(--mac-spacing-3)' }}>
                {['lab_technician_label', 'lab_technician_name', 'approver_label', 'approver_name'].map((key) => (
                  <label key={key} style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                    <span>{signerFieldLabels[key] || key}</span>
                    <Input className="macos-input" aria-label={signerFieldLabels[key] || key} value={draftVersion.signer_defaults?.[key] || ''} onChange={(event) => updateSigner(key, event.target.value)} />
                  </label>
                ))}
              </div>

              <div style={{ display: 'grid', gap: 'var(--mac-spacing-3)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>Секции и показатели</div>
                  <Button variant="outline" onClick={addSection}>
                    <Icon name="plus" size={16} />
                    Добавить секцию
                  </Button>
                </div>

                {draftVersion.sections.map((section, sectionIndex) => (
                  <div key={`${section.key}-${sectionIndex}`} style={{ border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-xl)', padding: '14px', background: 'var(--mac-bg-primary)', display: 'grid', gap: 'var(--mac-spacing-3)' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 'var(--mac-spacing-2)', alignItems: 'end' }}>
                      <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                        <span>Ключ секции</span>
                        <Input className="macos-input" aria-label="Ключ секции" value={section.key} onChange={(event) => updateSection(sectionIndex, 'key', event.target.value)} />
                      </label>
                      <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                        <span>Заголовок секции</span>
                        <Input className="macos-input" aria-label="Заголовок секции" value={section.title || ''} onChange={(event) => updateSection(sectionIndex, 'title', event.target.value)} />
                      </label>
                      <Button variant="outline" onClick={() => removeSection(sectionIndex)}>
                        <Icon name="trash" size={16} />
                        Удалить
                      </Button>
                    </div>

                    <div style={{ display: 'grid', gap: 'var(--mac-spacing-3)' }}>
                      {section.fields.map((field, fieldIndex) => (
                        <div key={`${field.field_key}-${fieldIndex}`} style={{ border: '1px solid color-mix(in oklab, var(--mac-border) 80%, transparent)', borderRadius: '14px', padding: 'var(--mac-spacing-3)', display: 'grid', gap: '10px' }}>
                          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.2fr 0.8fr 0.8fr auto', gap: 'var(--mac-spacing-2)', alignItems: 'end' }}>
                            <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                              <span>Ключ поля</span>
                              <Input className="macos-input" aria-label="Ключ поля" value={field.field_key} onChange={(event) => updateField(sectionIndex, fieldIndex, 'field_key', event.target.value)} />
                            </label>
                            <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                              <span>Название поля</span>
                              <Input className="macos-input" aria-label="Название поля" value={field.label} onChange={(event) => updateField(sectionIndex, fieldIndex, 'label', event.target.value)} />
                            </label>
                            <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                              <span>Тип значения</span>
                              <select className="macos-input" aria-label="Тип значения" value={field.value_type} onChange={(event) => updateField(sectionIndex, fieldIndex, 'value_type', event.target.value)}>
                                {fieldTypeOptions.map((option) => (
                                  <option key={option.value} value={option.value}>{option.label}</option>
                                ))}
                              </select>
                            </label>
                            <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                              <span>Единица измерения</span>
                              <Input className="macos-input" aria-label="Единица измерения" value={field.unit || ''} onChange={(event) => updateField(sectionIndex, fieldIndex, 'unit', event.target.value)} />
                            </label>
                            <Button variant="outline" onClick={() => removeField(sectionIndex, fieldIndex)}>
                              <Icon name="minus" size={16} />
                              Удалить
                            </Button>
                          </div>

                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 0.8fr 1.2fr auto', gap: 'var(--mac-spacing-2)', alignItems: 'end' }}>
                            <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                              <span>Код анализируемого показателя</span>
                              <Input
                                className="macos-input"
                                aria-label="Код анализируемого показателя"
                                list="lab-analyte-catalog"
                                value={field.analyte_code || ''}
                                onChange={(event) => updateFieldCatalog(sectionIndex, fieldIndex, 'analyte_code', event.target.value)}
                              />
                            </label>
                            <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                              <span>Код единицы измерения</span>
                              <Input
                                className="macos-input"
                                aria-label="Код единицы измерения"
                                list="lab-unit-catalog"
                                value={field.unit_code || ''}
                                onChange={(event) => updateField(sectionIndex, fieldIndex, 'unit_code', event.target.value)}
                              />
                            </label>
                            <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                              <span>Источник нормы</span>
                              <select className="macos-input" aria-label="Источник нормы" value={field.reference_mode} onChange={(event) => updateField(sectionIndex, fieldIndex, 'reference_mode', event.target.value)}>
                                {referenceModeOptions.map((option) => (
                                  <option key={option.value} value={option.value}>{option.label}</option>
                                ))}
                              </select>
                            </label>
                            <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                              <span>Текст нормы</span>
                              <Input className="macos-input" aria-label="Текст нормы" value={field.reference_text || ''} onChange={(event) => updateField(sectionIndex, fieldIndex, 'reference_text', event.target.value)} />
                            </label>
                            <label style={{ display: 'flex', gap: 'var(--mac-spacing-2)', alignItems: 'center', paddingBottom: '8px' }}>
                              <Checkbox aria-label="Обязательное поле" checked={Boolean(field.required)} onChange={(event) => updateField(sectionIndex, fieldIndex, 'required', event.target.checked)} />
                              Обязательное поле
                            </label>
                          </div>

                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 'var(--mac-spacing-2)' }}>
                            <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                              <span>JSON правил нормы</span>
                              <textarea className="macos-input" aria-label="JSON правил нормы" rows={4} value={field.reference_rule_text || ''} onChange={(event) => updateField(sectionIndex, fieldIndex, 'reference_rule_text', event.target.value)} />
                            </label>
                            <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                              <span>JSON правил видимости</span>
                              <textarea className="macos-input" aria-label="JSON правил видимости" rows={4} value={field.visibility_rule_text || ''} onChange={(event) => updateField(sectionIndex, fieldIndex, 'visibility_rule_text', event.target.value)} />
                            </label>
                            <label style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
                              <span>JSON правил подсветки</span>
                              <textarea className="macos-input" aria-label="JSON правил подсветки" rows={4} value={field.highlight_rule_text || ''} onChange={(event) => updateField(sectionIndex, fieldIndex, 'highlight_rule_text', event.target.value)} />
                            </label>
                          </div>
                        </div>
                      ))}
                      <Button variant="outline" onClick={() => addField(sectionIndex)}>
                        <Icon name="plus" size={16} />
                        Добавить показатель
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
      <datalist id="lab-analyte-catalog">
        {catalogAnalytes.map((analyte) => (
          <option key={analyte.code} value={analyte.code}>
            {analyte.name}
          </option>
        ))}
      </datalist>
      <datalist id="lab-unit-catalog">
        {catalogUnits.map((unit) => (
          <option key={unit.code} value={unit.code}>
            {unit.symbol}
          </option>
        ))}
      </datalist>
    </div>
  );
}

LabTemplateWorkbench.propTypes = {
  templates: PropTypes.array.isRequired,
  selectedTemplate: PropTypes.object,
  onSelectTemplate: PropTypes.func.isRequired,
  onTemplatesChanged: PropTypes.func.isRequired,
  notify: PropTypes.func.isRequired
};
