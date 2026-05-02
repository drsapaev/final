import { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Icon } from '../ui/macos';
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
  selectedTemplate,
  onSelectTemplate,
  onTemplatesChanged,
  notify
}) {
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
    if (activeVersion?.status === 'DRAFT') {
      return activeVersion.id;
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
    <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '16px', alignItems: 'start' }}>
      <Card variant="filled" padding="none">
        <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: '16px' }}>
          <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Icon name="rectangle.stack.badge.plus" size={20} />
            Шаблоны
          </CardTitle>
        </CardHeader>
        <CardContent style={{ padding: '16px', background: 'var(--mac-bg-secondary)', display: 'grid', gap: '16px' }}>
          <div style={{ display: 'grid', gap: '8px' }}>
            <input className="macos-input" placeholder="Код шаблона" value={newTemplate.code} onChange={(event) => setNewTemplate((prev) => ({ ...prev, code: event.target.value }))} />
            <input className="macos-input" placeholder="Название" value={newTemplate.name} onChange={(event) => setNewTemplate((prev) => ({ ...prev, name: event.target.value }))} />
            <input className="macos-input" placeholder="Семейство" value={newTemplate.family} onChange={(event) => setNewTemplate((prev) => ({ ...prev, family: event.target.value }))} />
            <textarea className="macos-input" rows={3} placeholder="Описание" value={newTemplate.description} onChange={(event) => setNewTemplate((prev) => ({ ...prev, description: event.target.value }))} />
            <Button variant="primary" onClick={handleCreateTemplate} disabled={saving}>
              <Icon name="plus" size={16} />
              Создать шаблон
            </Button>
          </div>

          <div style={{ display: 'grid', gap: '8px' }}>
            {templates.map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() => onSelectTemplate(template.id)}
                style={{
                  border: '1px solid var(--mac-border)',
                  borderRadius: '14px',
                  padding: '12px',
                  textAlign: 'left',
                  background: selectedTemplate?.id === template.id ? 'color-mix(in oklab, var(--mac-accent) 10%, var(--mac-bg-primary))' : 'var(--mac-bg-primary)',
                  cursor: 'pointer',
                  display: 'grid',
                  gap: '6px'
                }}
              >
                <div style={{ fontWeight: 600, color: 'var(--mac-text-primary)' }}>{template.name}</div>
                <div style={{ fontSize: '13px', color: 'var(--mac-text-secondary)' }}>{template.code} • {template.family}</div>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  {template.published_version_id && <Badge variant="success">Опубликован</Badge>}
                  {template.draft_version_id && <Badge variant="warning">Черновик</Badge>}
                </div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card variant="filled" padding="none">
        <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: '16px' }}>
          <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Icon name="slider.horizontal.3" size={20} />
              Редактор бланка
            </span>
            {selectedTemplate && (
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
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
        <CardContent style={{ padding: '16px', background: 'var(--mac-bg-secondary)' }}>
          {!selectedTemplate ? (
            <Alert severity="info">Выберите шаблон слева, чтобы редактировать оформление, секции и строки анализов.</Alert>
          ) : (
            <div style={{ display: 'grid', gap: '18px' }}>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                <Badge variant="info">{selectedTemplate.code}</Badge>
                <Badge variant="primary">{selectedTemplate.family}</Badge>
                {activeVersion?.status && <Badge variant={activeVersion.status === 'PUBLISHED' ? 'success' : 'warning'}>{formatVersionStatus(activeVersion.status)}</Badge>}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '12px' }}>
                <label style={{ display: 'grid', gap: '6px' }}>
                  <span>Макет печати</span>
                  <select className="macos-input" value={draftVersion.layout_preset} onChange={(event) => setDraftVersion((prev) => ({ ...prev, layout_preset: event.target.value }))}>
                    {layoutOptions.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <label style={{ display: 'grid', gap: '6px' }}>
                  <span>Подвал</span>
                  <textarea className="macos-input" rows={3} value={draftVersion.footer_notes} onChange={(event) => setDraftVersion((prev) => ({ ...prev, footer_notes: event.target.value }))} />
                </label>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '12px' }}>
                {['document_title', 'document_subtitle', 'clinic_name', 'address', 'phone', 'logo_url'].map((key) => (
                  <label key={key} style={{ display: 'grid', gap: '6px' }}>
                    <span>{brandingFieldLabels[key] || key}</span>
                    <input className="macos-input" value={draftVersion.branding_overrides?.[key] || ''} onChange={(event) => updateBranding(key, event.target.value)} />
                  </label>
                ))}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: '12px' }}>
                {['lab_technician_label', 'lab_technician_name', 'approver_label', 'approver_name'].map((key) => (
                  <label key={key} style={{ display: 'grid', gap: '6px' }}>
                    <span>{signerFieldLabels[key] || key}</span>
                    <input className="macos-input" value={draftVersion.signer_defaults?.[key] || ''} onChange={(event) => updateSigner(key, event.target.value)} />
                  </label>
                ))}
              </div>

              <div style={{ display: 'grid', gap: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontWeight: 600 }}>Секции и показатели</div>
                  <Button variant="outline" onClick={addSection}>
                    <Icon name="plus" size={16} />
                    Добавить секцию
                  </Button>
                </div>

                {draftVersion.sections.map((section, sectionIndex) => (
                  <div key={`${section.key}-${sectionIndex}`} style={{ border: '1px solid var(--mac-border)', borderRadius: '16px', padding: '14px', background: 'var(--mac-bg-primary)', display: 'grid', gap: '12px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '8px', alignItems: 'end' }}>
                      <label style={{ display: 'grid', gap: '6px' }}>
                        <span>Ключ секции</span>
                        <input className="macos-input" value={section.key} onChange={(event) => updateSection(sectionIndex, 'key', event.target.value)} />
                      </label>
                      <label style={{ display: 'grid', gap: '6px' }}>
                        <span>Заголовок секции</span>
                        <input className="macos-input" value={section.title || ''} onChange={(event) => updateSection(sectionIndex, 'title', event.target.value)} />
                      </label>
                      <Button variant="outline" onClick={() => removeSection(sectionIndex)}>
                        <Icon name="trash" size={16} />
                        Удалить
                      </Button>
                    </div>

                    <div style={{ display: 'grid', gap: '12px' }}>
                      {section.fields.map((field, fieldIndex) => (
                        <div key={`${field.field_key}-${fieldIndex}`} style={{ border: '1px solid color-mix(in oklab, var(--mac-border) 80%, transparent)', borderRadius: '14px', padding: '12px', display: 'grid', gap: '10px' }}>
                          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.2fr 0.8fr 0.8fr auto', gap: '8px', alignItems: 'end' }}>
                            <label style={{ display: 'grid', gap: '6px' }}>
                              <span>Ключ поля</span>
                              <input className="macos-input" value={field.field_key} onChange={(event) => updateField(sectionIndex, fieldIndex, 'field_key', event.target.value)} />
                            </label>
                            <label style={{ display: 'grid', gap: '6px' }}>
                              <span>Название поля</span>
                              <input className="macos-input" value={field.label} onChange={(event) => updateField(sectionIndex, fieldIndex, 'label', event.target.value)} />
                            </label>
                            <label style={{ display: 'grid', gap: '6px' }}>
                              <span>Тип значения</span>
                              <select className="macos-input" value={field.value_type} onChange={(event) => updateField(sectionIndex, fieldIndex, 'value_type', event.target.value)}>
                                {fieldTypeOptions.map((option) => (
                                  <option key={option.value} value={option.value}>{option.label}</option>
                                ))}
                              </select>
                            </label>
                            <label style={{ display: 'grid', gap: '6px' }}>
                              <span>Единица измерения</span>
                              <input className="macos-input" value={field.unit || ''} onChange={(event) => updateField(sectionIndex, fieldIndex, 'unit', event.target.value)} />
                            </label>
                            <Button variant="outline" onClick={() => removeField(sectionIndex, fieldIndex)}>
                              <Icon name="minus" size={16} />
                              Удалить
                            </Button>
                          </div>

                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 0.8fr 1.2fr auto', gap: '8px', alignItems: 'end' }}>
                            <label style={{ display: 'grid', gap: '6px' }}>
                              <span>Код анализируемого показателя</span>
                              <input
                                className="macos-input"
                                list="lab-analyte-catalog"
                                value={field.analyte_code || ''}
                                onChange={(event) => updateFieldCatalog(sectionIndex, fieldIndex, 'analyte_code', event.target.value)}
                              />
                            </label>
                            <label style={{ display: 'grid', gap: '6px' }}>
                              <span>Код единицы измерения</span>
                              <input
                                className="macos-input"
                                list="lab-unit-catalog"
                                value={field.unit_code || ''}
                                onChange={(event) => updateField(sectionIndex, fieldIndex, 'unit_code', event.target.value)}
                              />
                            </label>
                            <label style={{ display: 'grid', gap: '6px' }}>
                              <span>Источник нормы</span>
                              <select className="macos-input" value={field.reference_mode} onChange={(event) => updateField(sectionIndex, fieldIndex, 'reference_mode', event.target.value)}>
                                {referenceModeOptions.map((option) => (
                                  <option key={option.value} value={option.value}>{option.label}</option>
                                ))}
                              </select>
                            </label>
                            <label style={{ display: 'grid', gap: '6px' }}>
                              <span>Текст нормы</span>
                              <input className="macos-input" value={field.reference_text || ''} onChange={(event) => updateField(sectionIndex, fieldIndex, 'reference_text', event.target.value)} />
                            </label>
                            <label style={{ display: 'flex', gap: '8px', alignItems: 'center', paddingBottom: '8px' }}>
                              <input type="checkbox" checked={Boolean(field.required)} onChange={(event) => updateField(sectionIndex, fieldIndex, 'required', event.target.checked)} />
                              Обязательное поле
                            </label>
                          </div>

                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '8px' }}>
                            <label style={{ display: 'grid', gap: '6px' }}>
                              <span>JSON правил нормы</span>
                              <textarea className="macos-input" rows={4} value={field.reference_rule_text || ''} onChange={(event) => updateField(sectionIndex, fieldIndex, 'reference_rule_text', event.target.value)} />
                            </label>
                            <label style={{ display: 'grid', gap: '6px' }}>
                              <span>JSON правил видимости</span>
                              <textarea className="macos-input" rows={4} value={field.visibility_rule_text || ''} onChange={(event) => updateField(sectionIndex, fieldIndex, 'visibility_rule_text', event.target.value)} />
                            </label>
                            <label style={{ display: 'grid', gap: '6px' }}>
                              <span>JSON правил подсветки</span>
                              <textarea className="macos-input" rows={4} value={field.highlight_rule_text || ''} onChange={(event) => updateField(sectionIndex, fieldIndex, 'highlight_rule_text', event.target.value)} />
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

LabTemplateWorkbench.defaultProps = {
  selectedTemplate: null
};
