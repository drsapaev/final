import { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Icon,
  Dialog, DialogTitle, DialogContent, DialogActions, Input, Label, Textarea,
} from '../ui/macos';
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
  document_subtitle: 'Подзоловок документа',
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

// Phase 4+ refactor: editor tabs — Content / Design / Signers / Preview.
const EDITOR_TABS = [
  { id: 'content',  label: 'Содержимое' },
  { id: 'design',   label: 'Оформление' },
  { id: 'signers',  label: 'Подписи' },
  { id: 'preview',  label: 'Предпросмотр' },
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

// ============================================================
// Phase 4+: New Template Dialog (was always-visible form)
// ============================================================
function NewTemplateDialog({ open, onClose, onCreate, saving }) {
  const [form, setForm] = useState({
    code: '',
    name: '',
    family: 'hematology',
    description: ''
  });

  useEffect(() => {
    if (open) {
      setForm({ code: '', name: '', family: 'hematology', description: '' });
    }
  }, [open]);

  const handleSubmit = (e) => {
    e.preventDefault();
    onCreate(form);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Новый шаблон</DialogTitle>
      <DialogContent>
        <form onSubmit={handleSubmit} id="new-template-form" style={{ display: 'grid', gap: '12px', paddingTop: '8px' }}>
          <div>
            <Label htmlFor="new-template-code" style={{ display: 'block', marginBottom: 4 }}>Код шаблона</Label>
            <Input
              id="new-template-code"
              aria-label="Код шаблона"
              value={form.code}
              onChange={(e) => setForm((prev) => ({ ...prev, code: e.target.value }))}
              placeholder="Напр. hematology_basic"
              style={{ width: '100%', boxSizing: 'border-box' }}
              required
            />
          </div>
          <div>
            <Label htmlFor="new-template-name" style={{ display: 'block', marginBottom: 4 }}>Название</Label>
            <Input
              id="new-template-name"
              aria-label="Название шаблона"
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
              placeholder="Напр. Общий анализ крови"
              style={{ width: '100%', boxSizing: 'border-box' }}
              required
            />
          </div>
          <div>
            <Label htmlFor="new-template-family" style={{ display: 'block', marginBottom: 4 }}>Семейство</Label>
            {/* PR-59: replaced free-text Input with <select> to prevent typo-induced fragmentation */}
            <select
              id="new-template-family"
              aria-label="Семейство шаблона"
              value={form.family}
              onChange={(e) => setForm((prev) => ({ ...prev, family: e.target.value }))}
              className="macos-input"
              style={{ width: '100%', boxSizing: 'border-box' }}
            >
              <option value="hematology">Гематология</option>
              <option value="biochemistry">Биохимия</option>
              <option value="coagulation">Коагулология</option>
              <option value="urinalysis">Общий анализ мочи</option>
              <option value="immunology">Иммунология</option>
              <option value="microbiology">Микробиология</option>
              <option value="endocrinology">Эндокринология</option>
              <option value="other">Прочее</option>
            </select>
          </div>
          <div>
            <Label htmlFor="new-template-description" style={{ display: 'block', marginBottom: 4 }}>Описание</Label>
            <Textarea
              id="new-template-description"
              aria-label="Описание шаблона"
              value={form.description}
              onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
              placeholder="Краткое описание шаблона"
              minRows={3}
              style={{ width: '100%', boxSizing: 'border-box' }}
            />
          </div>
        </form>
      </DialogContent>
      <DialogActions>
        <Button variant="outline" onClick={onClose}>Отмена</Button>
        <Button variant="primary" type="submit" form="new-template-form" disabled={saving}>
          <Icon name="plus" size={16} />
          Создать
        </Button>
      </DialogActions>
    </Dialog>
  );
}

NewTemplateDialog.propTypes = {
  open: PropTypes.bool,
  onClose: PropTypes.func.isRequired,
  onCreate: PropTypes.func.isRequired,
  saving: PropTypes.bool,
};

// ============================================================
// Phase 3: ReferenceRuleEditor — structured editor for reference_rule JSON.
// Replaces raw JSON textarea with a visual cases editor.
//
// Rule format (from backend _sex_reference_rule / _ige_reference_rule):
// {
//   "cases": [
//     { "when": {"source":"patient.sex","op":"eq","value":"M"},
//       "text":"3.5-5.0", "low":3.5, "high":5.0 }
//   ],
//   "default": { "text":"3.5-5.0", "low":3.5, "high":5.0 }
// }
//
// Supports:
//   - source: patient.sex | patient.age | patient.age_months
//   - op: eq | ne | lt | gt | le | ge | between
//   - value: string or number (for eq/ne/lt/gt/le/ge)
//   - min/max: numbers (for between)
//   - text/low/high: reference range for this case
// ============================================================

const RULE_SOURCE_OPTIONS = [
  { value: 'patient.sex', label: 'Пол пациента' },
  { value: 'patient.age', label: 'Возраст (лет)' },
  { value: 'patient.age_months', label: 'Возраст (мес.)' },
];

const RULE_OP_OPTIONS = [
  { value: 'eq', label: '=' },
  { value: 'ne', label: '≠' },
  { value: 'lt', label: '<' },
  { value: 'gt', label: '>' },
  { value: 'le', label: '≤' },
  { value: 'ge', label: '≥' },
  { value: 'between', label: 'между' },
];

function parseRuleText(text) {
  if (!text?.trim()) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function serializeRule(rule) {
  if (!rule) return '';
  return JSON.stringify(rule, null, 2);
}

function ReferenceRuleEditor({ sectionIndex, fieldIndex, field, updateField }) {
  const rule = parseRuleText(field.reference_rule_text);
  const isStructured = rule === null || (rule && Array.isArray(rule.cases));

  // If the rule doesn't match our expected format, show raw JSON fallback.
  if (!isStructured) {
    return (
      <div style={{ display: 'grid', gap: '6px' }}>
        <span>Правила нормы (raw JSON)</span>
        <textarea
          className="macos-input"
          aria-label="JSON правил нормы"
          rows={6}
          value={field.reference_rule_text || ''}
          onChange={(event) => updateField(sectionIndex, fieldIndex, 'reference_rule_text', event.target.value)}
        />
        <span style={{ fontSize: '12px', color: 'var(--mac-text-secondary)' }}>
          Структурированный редактор недоступен — формат не распознан.
        </span>
      </div>
    );
  }

  const cases = rule?.cases || [];
  const defaultRule = rule?.default || { text: '', low: '', high: '' };

  const updateRule = (nextRule) => {
    updateField(sectionIndex, fieldIndex, 'reference_rule_text', serializeRule(nextRule));
  };

  const addCase = () => {
    const newCase = {
      when: { source: 'patient.sex', op: 'eq', value: 'M' },
      text: '',
      low: '',
      high: '',
    };
    updateRule({ ...rule, cases: [...cases, newCase] });
  };

  const updateCase = (caseIndex, key, value) => {
    const nextCases = cases.map((c, i) => i === caseIndex ? { ...c, [key]: value } : c);
    updateRule({ ...rule, cases: nextCases });
  };

  const updateCaseWhen = (caseIndex, whenKey, value) => {
    const nextCases = cases.map((c, i) => {
      if (i !== caseIndex) return c;
      return { ...c, when: { ...c.when, [whenKey]: value } };
    });
    updateRule({ ...rule, cases: nextCases });
  };

  const removeCase = (caseIndex) => {
    updateRule({ ...rule, cases: cases.filter((_, i) => i !== caseIndex) });
  };

  const updateDefault = (key, value) => {
    updateRule({ ...rule, default: { ...defaultRule, [key]: value } });
  };

  return (
    <div style={{ border: '1px solid var(--mac-border)', borderRadius: '10px', padding: '12px', display: 'grid', gap: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 600, fontSize: '14px' }}>Правила нормы</span>
        <Button variant="outline" size="small" onClick={addCase}>
          <Icon name="plus" size={12} />
          Добавить условие
        </Button>
      </div>

      {cases.length === 0 && (
        <span style={{ fontSize: '13px', color: 'var(--mac-text-secondary)' }}>
          Нет условий. Будет использоваться значение по умолчанию.
        </span>
      )}

      {cases.map((caseItem, caseIndex) => {
        const isBetween = caseItem.when?.op === 'between';
        return (
          <div key={caseIndex} style={{ border: '1px solid color-mix(in oklab, var(--mac-border) 70%, transparent)', borderRadius: '8px', padding: '10px', display: 'grid', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '13px', fontWeight: 500 }}>Условие {caseIndex + 1}</span>
              <Button variant="ghost" size="small" onClick={() => removeCase(caseIndex)} aria-label="Удалить условие">
                <Icon name="trash" size={12} />
              </Button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 0.5fr 1fr', gap: '8px', alignItems: 'end' }}>
              <label style={{ display: 'grid', gap: '4px' }}>
                <span style={{ fontSize: '12px' }}>Источник</span>
                <select
                  className="macos-input"
                  aria-label="Источник условия"
                  value={caseItem.when?.source || 'patient.sex'}
                  onChange={(e) => updateCaseWhen(caseIndex, 'source', e.target.value)}
                >
                  {RULE_SOURCE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </label>
              <label style={{ display: 'grid', gap: '4px' }}>
                <span style={{ fontSize: '12px' }}>Оператор</span>
                <select
                  className="macos-input"
                  aria-label="Оператор условия"
                  value={caseItem.when?.op || 'eq'}
                  onChange={(e) => updateCaseWhen(caseIndex, 'op', e.target.value)}
                >
                  {RULE_OP_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </label>
              {isBetween ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                  <label style={{ display: 'grid', gap: '4px' }}>
                    <span style={{ fontSize: '12px' }}>Минимум</span>
                    <input
                      className="macos-input"
                      aria-label="Минимум условия"
                      type="number"
                      value={caseItem.when?.min ?? ''}
                      onChange={(e) => updateCaseWhen(caseIndex, 'min', parseFloat(e.target.value) || 0)}
                    />
                  </label>
                  <label style={{ display: 'grid', gap: '4px' }}>
                    <span style={{ fontSize: '12px' }}>Максимум</span>
                    <input
                      className="macos-input"
                      aria-label="Максимум условия"
                      type="number"
                      value={caseItem.when?.max ?? ''}
                      onChange={(e) => updateCaseWhen(caseIndex, 'max', parseFloat(e.target.value) || 0)}
                    />
                  </label>
                </div>
              ) : (
                <label style={{ display: 'grid', gap: '4px' }}>
                  <span style={{ fontSize: '12px' }}>Значение</span>
                  {/* PR-61 / Medium-18: sex enum when source is patient.sex */}
                  {caseItem.when?.source === 'patient.sex' ? (
                    <select
                      className="macos-input"
                      aria-label="Значение условия"
                      value={caseItem.when?.value ?? ''}
                      onChange={(e) => updateCaseWhen(caseIndex, 'value', e.target.value)}
                    >
                      <option value="">Выберите...</option>
                      <option value="M">Мужской (M)</option>
                      <option value="F">Женский (F)</option>
                    </select>
                  ) : (
                    <input
                      className="macos-input"
                      aria-label="Значение условия"
                      value={caseItem.when?.value ?? ''}
                      onChange={(e) => updateCaseWhen(caseIndex, 'value', e.target.value)}
                    />
                  )}
                </label>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 0.5fr 0.5fr', gap: '8px', alignItems: 'end' }}>
              <label style={{ display: 'grid', gap: '4px' }}>
                <span style={{ fontSize: '12px' }}>Текст нормы</span>
                <input
                  className="macos-input"
                  aria-label="Текст нормы для условия"
                  value={caseItem.text || ''}
                  onChange={(e) => updateCase(caseIndex, 'text', e.target.value)}
                  placeholder="3.5-5.0"
                />
              </label>
              <label style={{ display: 'grid', gap: '4px' }}>
                <span style={{ fontSize: '12px' }}>Нижняя граница</span>
                <input
                  className="macos-input"
                  aria-label="Нижняя граница нормы"
                  type="number"
                  value={caseItem.low ?? ''}
                  onChange={(e) => updateCase(caseIndex, 'low', parseFloat(e.target.value) || null)}
                />
              </label>
              <label style={{ display: 'grid', gap: '4px' }}>
                <span style={{ fontSize: '12px' }}>Верхняя граница</span>
                <input
                  className="macos-input"
                  aria-label="Верхняя граница нормы"
                  type="number"
                  value={caseItem.high ?? ''}
                  onChange={(e) => updateCase(caseIndex, 'high', parseFloat(e.target.value) || null)}
                />
              </label>
            </div>
          </div>
        );
      })}

      {/* Default case */}
      <div style={{ border: '1px dashed var(--mac-border)', borderRadius: '8px', padding: '10px', display: 'grid', gap: '8px' }}>
        <span style={{ fontSize: '13px', fontWeight: 500 }}>По умолчанию (если ни одно условие не сработало)</span>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 0.5fr 0.5fr', gap: '8px', alignItems: 'end' }}>
          <label style={{ display: 'grid', gap: '4px' }}>
            <span style={{ fontSize: '12px' }}>Текст нормы</span>
            <input
              className="macos-input"
              aria-label="Текст нормы по умолчанию"
              value={defaultRule.text || ''}
              onChange={(e) => updateDefault('text', e.target.value)}
              placeholder="3.5-5.0"
            />
          </label>
          <label style={{ display: 'grid', gap: '4px' }}>
            <span style={{ fontSize: '12px' }}>Нижняя граница</span>
            <input
              className="macos-input"
              aria-label="Нижняя граница по умолчанию"
              type="number"
              value={defaultRule.low ?? ''}
              onChange={(e) => updateDefault('low', parseFloat(e.target.value) || null)}
            />
          </label>
          <label style={{ display: 'grid', gap: '4px' }}>
            <span style={{ fontSize: '12px' }}>Верхняя граница</span>
            <input
              className="macos-input"
              aria-label="Верхняя граница по умолчанию"
              type="number"
              value={defaultRule.high ?? ''}
              onChange={(e) => updateDefault('high', parseFloat(e.target.value) || null)}
            />
          </label>
        </div>
      </div>

      {/* Raw JSON toggle for advanced users */}
      <details>
        <summary style={{ cursor: 'pointer', fontSize: '12px', color: 'var(--mac-text-secondary)' }}>
          Raw JSON (для продвинутых)
        </summary>
        <textarea
          className="macos-input"
          aria-label="Raw JSON правил нормы"
          rows={6}
          value={field.reference_rule_text || ''}
          onChange={(event) => updateField(sectionIndex, fieldIndex, 'reference_rule_text', event.target.value)}
          style={{ marginTop: '6px' }}
        />
      </details>
    </div>
  );
}

ReferenceRuleEditor.propTypes = {
  sectionIndex: PropTypes.number.isRequired,
  fieldIndex: PropTypes.number.isRequired,
  field: PropTypes.object.isRequired,
  updateField: PropTypes.func.isRequired,
};

export default function LabTemplateWorkbench({
  templates,
  selectedTemplate = null,
  onSelectTemplate,
  onTemplatesChanged,
  notify
}) {
  // Phase 4+: New Template dialog state (was always-visible form).
  const [showNewTemplateDialog, setShowNewTemplateDialog] = useState(false);

  // Phase 4+: editor tabs — Content / Design / Signers / Preview.
  const [editorTab, setEditorTab] = useState('content');

  // WF-21 fix: search в списке шаблонов.
  const [templateSearch, setTemplateSearch] = useState('');
  const [draftVersion, setDraftVersion] = useState(hydrateVersion(null));
  const [saving, setSaving] = useState(false);
  const [catalogUnits, setCatalogUnits] = useState([]);
  const [catalogAnalytes, setCatalogAnalytes] = useState([]);

  // Phase 4+ Phase 2: collapsible sections + field cards + duplicate + reorder.
  const [expandedSections, setExpandedSections] = useState(new Set([0])); // first section open
  const [expandedFields, setExpandedFields] = useState(new Set()); // all fields collapsed by default

  const toggleSection = (sectionIndex) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(sectionIndex)) {
        next.delete(sectionIndex);
      } else {
        next.add(sectionIndex);
      }
      return next;
    });
  };

  const toggleField = (sectionIndex, fieldIndex) => {
    const key = `${sectionIndex}-${fieldIndex}`;
    setExpandedFields((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

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

  async function handleCreateTemplate(formData) {
    if (!formData.code || !formData.name) {
      notify('error', 'Укажите код и название шаблона.');
      return;
    }
    setSaving(true);
    try {
      await labReportingApi.createTemplate({
        ...formData,
        initial_version: blankVersion
      });
      notify('success', 'Шаблон создан.');
      setShowNewTemplateDialog(false);
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

  // PR-57: validate reference ranges (low < high) before save/publish
  function validateReferenceRanges() {
    if (!draftVersion?.sections) return [];
    const errors = [];
    draftVersion.sections.forEach((section, sIdx) => {
      (section.fields || []).forEach((field, fIdx) => {
        const rule = field.reference_rule;
        if (!rule) return;
        // Check default case
        const def = rule.default;
        if (def && def.low != null && def.high != null && def.low !== '' && def.high !== '') {
          if (parseFloat(def.low) >= parseFloat(def.high)) {
            errors.push(`Секция "${section.title || sIdx + 1}", поле "${field.label || field.field_key}": default low (${def.low}) ≥ high (${def.high})`);
          }
        }
        // Check each case
        (rule.cases || []).forEach((c, cIdx) => {
          if (c.low != null && c.high != null && c.low !== '' && c.high !== '') {
            if (parseFloat(c.low) >= parseFloat(c.high)) {
              errors.push(`Секция "${section.title || sIdx + 1}", поле "${field.label || field.field_key}", условие ${cIdx + 1}: low (${c.low}) ≥ high (${c.high})`);
            }
          }
        });
      });
    });
    return errors;
  }

  // PR-57: validate field_key uniqueness before save/publish
  function validateFieldKeyUniqueness() {
    if (!draftVersion?.sections) return [];
    const errors = [];
    const seenKeys = new Set();
    draftVersion.sections.forEach((section, sIdx) => {
      (section.fields || []).forEach((field, fIdx) => {
        const key = field.field_key;
        if (!key) return;
        if (seenKeys.has(key)) {
          errors.push(`Дубликат field_key "${key}" в секции "${section.title || sIdx + 1}"`);
        }
        seenKeys.add(key);
      });
    });
    return errors;
  }

  async function handleSaveTemplate() {
    if (!selectedTemplate) {
      notify('error', 'Выберите шаблон для редактирования.');
      return;
    }
    // PR-57: validate before saving
    const rangeErrors = validateReferenceRanges();
    const keyErrors = validateFieldKeyUniqueness();
    if (rangeErrors.length > 0 || keyErrors.length > 0) {
      const allErrors = [...rangeErrors, ...keyErrors];
      notify('error', `Ошибки валидации (${allErrors.length}):\n${allErrors.slice(0, 5).join('\n')}${allErrors.length > 5 ? '\n...' : ''}`);
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
    // PR-57: validate before publishing
    const rangeErrors = validateReferenceRanges();
    const keyErrors = validateFieldKeyUniqueness();
    if (rangeErrors.length > 0 || keyErrors.length > 0) {
      const allErrors = [...rangeErrors, ...keyErrors];
      notify('error', `Ошибки валидации (${allErrors.length}):\n${allErrors.slice(0, 5).join('\n')}${allErrors.length > 5 ? '\n...' : ''}`);
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

  // PR-65 / Medium-19: archive template version (soft-delete)
  async function handleArchiveTemplate() {
    if (!selectedTemplate || !activeVersion) {
      notify('error', 'Выберите версию для архивирования.');
      return;
    }
    if (!confirm('Архивировать эту версию шаблона? Она станет недоступна для новых отчётов.')) {
      return;
    }
    setSaving(true);
    try {
      await labReportingApi.archiveTemplateVersion(activeVersion.id);
      notify('success', 'Версия шаблона архивирована.');
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

  // Phase 4+ Phase 2: duplicate + reorder helpers.
  function duplicateField(sectionIndex, fieldIndex) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section, index) => {
        if (index !== sectionIndex) return section;
        const fieldToClone = section.fields[fieldIndex];
        if (!fieldToClone) return section;
        const cloned = {
          ...fieldToClone,
          field_key: `${fieldToClone.field_key || 'field'}_copy_${Date.now()}`,
          label: `${fieldToClone.label || 'Поле'} (копия)`,
        };
        const newFields = [...section.fields];
        newFields.splice(fieldIndex + 1, 0, cloned);
        return { ...section, fields: newFields };
      })
    }));
  }

  function moveField(sectionIndex, fieldIndex, direction) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section, index) => {
        if (index !== sectionIndex) return section;
        const newFields = [...section.fields];
        const targetIndex = direction === 'up' ? fieldIndex - 1 : fieldIndex + 1;
        if (targetIndex < 0 || targetIndex >= newFields.length) return section;
        [newFields[fieldIndex], newFields[targetIndex]] = [newFields[targetIndex], newFields[fieldIndex]];
        return { ...section, fields: newFields };
      })
    }));
  }

  function moveSection(sectionIndex, direction) {
    setDraftVersion((prev) => {
      const newSections = [...prev.sections];
      const targetIndex = direction === 'up' ? sectionIndex - 1 : sectionIndex + 1;
      if (targetIndex < 0 || targetIndex >= newSections.length) return prev;
      [newSections[sectionIndex], newSections[targetIndex]] = [newSections[targetIndex], newSections[sectionIndex]];
      return { ...prev, sections: newSections };
    });
  }

  // ============================================================
  // Editor tab renderers
  // ============================================================
  const renderContentTab = () => (
    <div style={{ display: 'grid', gap: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        {/* PR-61 / Low-29: count fields not just sections (was misleading) */}
        <div style={{ fontWeight: 600 }}>Секции и показатели ({draftVersion?.sections?.reduce((acc, s) => acc + (s.fields?.length || 0), 0) || 0} показателей в {draftVersion?.sections?.length || 0} секц.)</div>
        <Button variant="outline" onClick={addSection}>
          <Icon name="plus" size={16} />
          Добавить секцию
        </Button>
      </div>

      {draftVersion.sections.map((section, sectionIndex) => {
        const isSectionExpanded = expandedSections.has(sectionIndex);
        return (
          <div key={`${section.key}-${sectionIndex}`} style={{ border: '1px solid var(--mac-border)', borderRadius: '16px', background: 'var(--mac-bg-primary)', overflow: 'hidden' }}>
            {/* Section header — collapsible */}
            <button
              type="button"
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', padding: '12px 14px', cursor: 'pointer', borderBottom: isSectionExpanded ? '1px solid var(--mac-border)' : 'none', background: 'transparent', border: 'none', width: '100%', textAlign: 'left' }}
              onClick={() => toggleSection(sectionIndex)}
              aria-expanded={isSectionExpanded}
              aria-label={`Секция: ${section.title || section.key}`}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
                <Icon name={isSectionExpanded ? 'chevron.down' : 'chevron.right'} size={16} />
                <span style={{ fontWeight: 600, fontSize: '15px' }}>{section.title || section.key}</span>
                <Badge variant="default">{section.fields.length} полей</Badge>
              </div>
              <span style={{ display: 'flex', gap: '4px' }}>
                <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); moveSection(sectionIndex, 'up'); }} disabled={sectionIndex === 0} aria-label="Переместить секцию вверх">
                  <Icon name="arrow.up" size={14} />
                </Button>
                <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); moveSection(sectionIndex, 'down'); }} disabled={sectionIndex === draftVersion.sections.length - 1} aria-label="Переместить секцию вниз">
                  <Icon name="arrow.down" size={14} />
                </Button>
                <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); removeSection(sectionIndex); }} aria-label="Удалить секцию">
                  <Icon name="trash" size={14} />
                </Button>
              </span>
            </button>

            {/* Section content — only when expanded */}
            {isSectionExpanded && (
              <div style={{ padding: '14px', display: 'grid', gap: '12px' }}>
                {/* Section key + title editors */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', alignItems: 'end' }}>
                  <label style={{ display: 'grid', gap: '6px' }}>
                    <span>Ключ секции</span>
                    <input className="macos-input" aria-label="Ключ секции" value={section.key} onChange={(event) => updateSection(sectionIndex, 'key', event.target.value)} />
                  </label>
                  <label style={{ display: 'grid', gap: '6px' }}>
                    <span>Заголовок секции</span>
                    <input className="macos-input" aria-label="Заголовок секции" value={section.title || ''} onChange={(event) => updateSection(sectionIndex, 'title', event.target.value)} />
                  </label>
                </div>

                {/* Fields */}
                <div style={{ display: 'grid', gap: '8px' }}>
                  {section.fields.map((field, fieldIndex) => {
                    const fieldKey = `${sectionIndex}-${fieldIndex}`;
                    const isFieldExpanded = expandedFields.has(fieldKey);
                    return (
                      <div key={`${field.field_key}-${fieldIndex}`} style={{ border: '1px solid color-mix(in oklab, var(--mac-border) 80%, transparent)', borderRadius: '12px', overflow: 'hidden' }}>
                        {/* Field header — collapsible */}
                        <button
                          type="button"
                          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', padding: '10px 12px', cursor: 'pointer', background: isFieldExpanded ? 'var(--mac-bg-secondary)' : 'transparent', border: 'none', width: '100%', textAlign: 'left' }}
                          onClick={() => toggleField(sectionIndex, fieldIndex)}
                          aria-expanded={isFieldExpanded}
                          aria-label={`Поле: ${field.label || field.field_key}`}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
                            <Icon name={isFieldExpanded ? 'chevron.down' : 'chevron.right'} size={14} />
                            <span style={{ fontWeight: 500, fontSize: '14px' }}>{field.label || field.field_key || '(без названия)'}</span>
                            <Badge variant="info">{fieldTypeOptions.find((o) => o.value === field.value_type)?.label || field.value_type}</Badge>
                            {field.required && <Badge variant="warning">обязательное</Badge>}
                          </div>
                          <span style={{ display: 'flex', gap: '4px' }}>
                            <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); moveField(sectionIndex, fieldIndex, 'up'); }} disabled={fieldIndex === 0} aria-label="Переместить поле вверх">
                              <Icon name="arrow.up" size={12} />
                            </Button>
                            <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); moveField(sectionIndex, fieldIndex, 'down'); }} disabled={fieldIndex === section.fields.length - 1} aria-label="Переместить поле вниз">
                              <Icon name="arrow.down" size={12} />
                            </Button>
                            <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); duplicateField(sectionIndex, fieldIndex); }} aria-label="Дублировать поле">
                              <Icon name="doc.on.doc" size={12} />
                            </Button>
                            <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); removeField(sectionIndex, fieldIndex); }} aria-label="Удалить поле">
                              <Icon name="trash" size={12} />
                            </Button>
                          </span>
                        </button>

                        {/* Field content — only when expanded */}
                        {isFieldExpanded && (
                          <div style={{ padding: '12px', display: 'grid', gap: '10px' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.2fr 0.8fr 0.8fr', gap: '8px', alignItems: 'end' }}>
                              <label style={{ display: 'grid', gap: '6px' }}>
                                <span>Ключ поля</span>
                                <input className="macos-input" aria-label="Ключ поля" value={field.field_key} onChange={(event) => updateField(sectionIndex, fieldIndex, 'field_key', event.target.value)} />
                              </label>
                              <label style={{ display: 'grid', gap: '6px' }}>
                                <span>Название поля</span>
                                <input className="macos-input" aria-label="Название поля" value={field.label} onChange={(event) => updateField(sectionIndex, fieldIndex, 'label', event.target.value)} />
                              </label>
                              <label style={{ display: 'grid', gap: '6px' }}>
                                <span>Тип значения</span>
                                <select className="macos-input" aria-label="Тип значения" value={field.value_type} onChange={(event) => updateField(sectionIndex, fieldIndex, 'value_type', event.target.value)}>
                                  {fieldTypeOptions.map((option) => (
                                    <option key={option.value} value={option.value}>{option.label}</option>
                                  ))}
                                </select>
                              </label>
                              <label style={{ display: 'grid', gap: '6px' }}>
                                <span>Единица измерения</span>
                                <input className="macos-input" aria-label="Единица измерения" value={field.unit || ''} onChange={(event) => updateField(sectionIndex, fieldIndex, 'unit', event.target.value)} />
                              </label>
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 0.8fr 1.2fr auto', gap: '8px', alignItems: 'end' }}>
                              <label style={{ display: 'grid', gap: '6px' }}>
                                <span>Код анализируемого показателя</span>
                                <input
                                  className="macos-input"
                                  aria-label="Код анализируемого показателя"
                                  list="lab-analyte-catalog"
                                  value={field.analyte_code || ''}
                                  onChange={(event) => updateFieldCatalog(sectionIndex, fieldIndex, 'analyte_code', event.target.value)}
                                />
                              </label>
                              <label style={{ display: 'grid', gap: '6px' }}>
                                <span>Код единицы измерения</span>
                                <input
                                  className="macos-input"
                                  aria-label="Код единицы измерения"
                                  list="lab-unit-catalog"
                                  value={field.unit_code || ''}
                                  onChange={(event) => updateField(sectionIndex, fieldIndex, 'unit_code', event.target.value)}
                                />
                              </label>
                              <label style={{ display: 'grid', gap: '6px' }}>
                                <span>Источник нормы</span>
                                <select className="macos-input" aria-label="Источник нормы" value={field.reference_mode} onChange={(event) => updateField(sectionIndex, fieldIndex, 'reference_mode', event.target.value)}>
                                  {referenceModeOptions.map((option) => (
                                    <option key={option.value} value={option.value}>{option.label}</option>
                                  ))}
                                </select>
                              </label>
                              <label style={{ display: 'grid', gap: '6px' }}>
                                <span>Текст нормы</span>
                                <input className="macos-input" aria-label="Текст нормы" value={field.reference_text || ''} onChange={(event) => updateField(sectionIndex, fieldIndex, 'reference_text', event.target.value)} />
                              </label>
                              <label style={{ display: 'flex', gap: '8px', alignItems: 'center', paddingBottom: '8px' }}>
                                <input type="checkbox" aria-label="Обязательное поле" checked={Boolean(field.required)} onChange={(event) => updateField(sectionIndex, fieldIndex, 'required', event.target.checked)} />
                                Обязательное
                              </label>
                            </div>

                            {/* Phase 3: structured editor for reference rules.
                                Replaces raw JSON textarea with a visual cases editor.
                                Rule format (from backend _sex_reference_rule):
                                {
                                  "cases": [
                                    { "when": {"source":"patient.sex","op":"eq","value":"M"},
                                      "text":"3.5-5.0", "low":3.5, "high":5.0 }
                                  ],
                                  "default": { "text":"3.5-5.0", "low":3.5, "high":5.0 }
                                }
                                Visibility + highlight rules stay as raw JSON (rarely used,
                                advanced-only) — they're collapsed by default. */}
                            <ReferenceRuleEditor
                              sectionIndex={sectionIndex}
                              fieldIndex={fieldIndex}
                              field={field}
                              updateField={updateField}
                            />

                            <details style={{ marginTop: '8px' }}>
                              <summary style={{ cursor: 'pointer', fontSize: '13px', color: 'var(--mac-text-secondary)' }}>
                                Расширенные правила (видимость / подсветка) — raw JSON
                              </summary>
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '8px' }}>
                                <label style={{ display: 'grid', gap: '6px' }}>
                                  <span>JSON правил видимости</span>
                                  <textarea className="macos-input" aria-label="JSON правил видимости" rows={3} value={field.visibility_rule_text || ''} onChange={(event) => updateField(sectionIndex, fieldIndex, 'visibility_rule_text', event.target.value)} />
                                </label>
                                <label style={{ display: 'grid', gap: '6px' }}>
                                  <span>JSON правил подсветки</span>
                                  <textarea className="macos-input" aria-label="JSON правил подсветки" rows={3} value={field.highlight_rule_text || ''} onChange={(event) => updateField(sectionIndex, fieldIndex, 'highlight_rule_text', event.target.value)} />
                                </label>
                              </div>
                            </details>
                          </div>
                        )}
                      </div>
                    );
                  })}
                  <Button variant="outline" onClick={() => addField(sectionIndex)}>
                    <Icon name="plus" size={16} />
                    Добавить показатель
                  </Button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );

  const renderDesignTab = () => (
    <div style={{ display: 'grid', gap: '18px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '12px' }}>
        <label style={{ display: 'grid', gap: '6px' }}>
          <span>Макет печати</span>
          <select className="macos-input" aria-label="Макет печати" value={draftVersion.layout_preset} onChange={(event) => setDraftVersion((prev) => ({ ...prev, layout_preset: event.target.value }))}>
            {layoutOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label style={{ display: 'grid', gap: '6px' }}>
          <span>Подвал</span>
          <textarea className="macos-input" aria-label="Подвал шаблона" rows={3} value={draftVersion.footer_notes} onChange={(event) => setDraftVersion((prev) => ({ ...prev, footer_notes: event.target.value }))} />
        </label>
      </div>

      <div>
        <div style={{ fontWeight: 600, marginBottom: '10px' }}>Брендирование документа</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '12px' }}>
          {['document_title', 'document_subtitle', 'clinic_name', 'address', 'phone', 'logo_url'].map((key) => (
            <label key={key} style={{ display: 'grid', gap: '6px' }}>
              <span>{brandingFieldLabels[key] || key}</span>
              <input className="macos-input" aria-label={brandingFieldLabels[key] || key} value={draftVersion.branding_overrides?.[key] || ''} onChange={(event) => updateBranding(key, event.target.value)} />
            </label>
          ))}
        </div>
      </div>
    </div>
  );

  const renderSignersTab = () => (
    <div>
      <div style={{ fontWeight: 600, marginBottom: '10px' }}>Подписи по умолчанию</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: '12px' }}>
        {['lab_technician_label', 'lab_technician_name', 'approver_label', 'approver_name'].map((key) => (
          <label key={key} style={{ display: 'grid', gap: '6px' }}>
            <span>{signerFieldLabels[key] || key}</span>
            <input className="macos-input" aria-label={signerFieldLabels[key] || key} value={draftVersion.signer_defaults?.[key] || ''} onChange={(event) => updateSigner(key, event.target.value)} />
          </label>
        ))}
      </div>
    </div>
  );

  const renderPreviewTab = () => {
    // Phase 4+ tab 4: read-only sample render of the template.
    // Shows branding + sections + fields as they'll appear in the PDF.
    const branding = draftVersion.branding_overrides || {};
    const signers = draftVersion.signer_defaults || {};

    return (
      <div style={{ display: 'grid', gap: '16px' }}>
        <Alert severity="info">
          Предпросмотр показывает структуру бланка. Финальный PDF рендерится на backend.
        </Alert>

        <Card variant="filled" padding="default">
          <div style={{ textAlign: 'center', marginBottom: '16px', borderBottom: '1px solid var(--mac-border)', paddingBottom: '12px' }}>
            {branding.clinic_name && <div style={{ fontWeight: 600, fontSize: '15px' }}>{branding.clinic_name}</div>}
            {branding.document_title && <div style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px' }}>{branding.document_title}</div>}
            {branding.document_subtitle && <div style={{ fontSize: '13px', color: 'var(--mac-text-secondary)', marginTop: '2px' }}>{branding.document_subtitle}</div>}
            {branding.address && <div style={{ fontSize: '12px', color: 'var(--mac-text-secondary)', marginTop: '4px' }}>{branding.address}</div>}
            {branding.phone && <div style={{ fontSize: '12px', color: 'var(--mac-text-secondary)' }}>{branding.phone}</div>}
          </div>

          {draftVersion.sections.map((section, sectionIndex) => (
            <div key={sectionIndex} style={{ marginBottom: '16px' }}>
              <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: '8px', borderBottom: '1px solid var(--mac-border)', paddingBottom: '4px' }}>
                {section.title || section.key}
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--mac-border)' }}>
                    <th style={{ textAlign: 'left', padding: '4px 8px' }}>Показатель</th>
                    <th style={{ textAlign: 'left', padding: '4px 8px' }}>Значение</th>
                    <th style={{ textAlign: 'left', padding: '4px 8px' }}>Единица</th>
                    <th style={{ textAlign: 'left', padding: '4px 8px' }}>Норма</th>
                  </tr>
                </thead>
                <tbody>
                  {section.fields.map((field, fieldIndex) => (
                    <tr key={fieldIndex} style={{ borderBottom: '1px solid var(--mac-border)' }}>
                      <td style={{ padding: '4px 8px' }}>
                        {field.label || field.field_key}
                        {field.required && <span style={{ color: 'var(--mac-error)', marginLeft: '2px' }}>*</span>}
                      </td>
                      <td style={{ padding: '4px 8px', color: 'var(--mac-text-secondary)' }}>—</td>
                      <td style={{ padding: '4px 8px', color: 'var(--mac-text-secondary)' }}>{field.unit || ''}</td>
                      <td style={{ padding: '4px 8px', color: 'var(--mac-text-secondary)' }}>{field.reference_text || (field.reference_mode === 'rule_based' ? '(по правилам)' : '')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}

          {draftVersion.footer_notes && (
            <div style={{ borderTop: '1px solid var(--mac-border)', paddingTop: '8px', fontSize: '12px', color: 'var(--mac-text-secondary)' }}>
              {draftVersion.footer_notes}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginTop: '24px', fontSize: '12px' }}>
            <div>
              <div style={{ color: 'var(--mac-text-secondary)' }}>{signers.lab_technician_label || 'Лаборант'}:</div>
              <div style={{ marginTop: '16px', borderTop: '1px solid var(--mac-border)', paddingTop: '2px' }}>
                {signers.lab_technician_name || '_______________'}
              </div>
            </div>
            <div>
              <div style={{ color: 'var(--mac-text-secondary)' }}>{signers.approver_label || 'Подпись'}:</div>
              <div style={{ marginTop: '16px', borderTop: '1px solid var(--mac-border)', paddingTop: '2px' }}>
                {signers.approver_name || '_______________'}
              </div>
            </div>
          </div>
        </Card>
      </div>
    );
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '16px', alignItems: 'start' }}>
      <Card variant="filled" padding="none">
        <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: '16px' }}>
          <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Icon name="rectangle.stack.badge.plus" size={20} />
              Шаблоны
            </span>
            <Button variant="primary" size="small" onClick={() => setShowNewTemplateDialog(true)} disabled={saving}>
              <Icon name="plus" size={14} />
              Новый
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent style={{ padding: '16px', background: 'var(--mac-bg-secondary)', display: 'grid', gap: '16px' }}>
          {/* WF-21 fix: search для консистентности с LabQueueWorkbench */}
          <div style={{ position: 'relative', marginBottom: '8px' }}>
            <input
              type="search"
              value={templateSearch}
              onChange={(e) => setTemplateSearch(e.target.value)}
              placeholder="Поиск по названию, коду, семейству…"
              aria-label="Поиск шаблонов"
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: '10px',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: '14px',
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
                  color: 'var(--mac-text-muted)', fontSize: '16px',
                }}
              >
                ×
              </button>
            )}
          </div>

          <div style={{ display: 'grid', gap: '8px' }}>
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
                {/* PR-60 / High-7: Cancel changes — reverts draft to server version */}
                <Button
                  variant="outline"
                  onClick={() => {
                    if (activeVersion) {
                      setDraftVersion(hydrateVersion(activeVersion));
                      notify('info', 'Изменения отменены. Восстановлена версия с сервера.');
                    }
                  }}
                  disabled={saving || !activeVersion}
                  title="Отменить изменения и восстановить версию с сервера"
                >
                  <Icon name="arrow.counterclockwise" size={16} />
                  Отменить
                </Button>
                <Button variant="outline" onClick={handleSaveTemplate} disabled={saving}>
                  <Icon name="square.and.arrow.down" size={16} />
                  Сохранить черновик
                </Button>
                <Button variant="primary" onClick={handlePublishVersion} disabled={saving}>
                  <Icon name="checkmark.seal" size={16} />
                  Опубликовать
                </Button>
                {/* PR-65 / Medium-19: archive template version (soft-delete) */}
                <Button variant="outline" onClick={handleArchiveTemplate} disabled={saving || !activeVersion} title="Архивировать версию">
                  <Icon name="archivebox" size={16} />
                  Архивировать
                </Button>
              </div>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent style={{ padding: '16px', background: 'var(--mac-bg-secondary)' }}>
          {!selectedTemplate ? (
            <Alert severity="info">Выберите шаблон слева, чтобы редактировать оформление, секции и строки анализов.</Alert>
          ) : (
            <div style={{ display: 'grid', gap: '16px' }}>
              {/* Template metadata badges */}
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                <Badge variant="info">{selectedTemplate.code}</Badge>
                <Badge variant="primary">{selectedTemplate.family}</Badge>
                {activeVersion?.status && <Badge variant={activeVersion.status === 'PUBLISHED' ? 'success' : 'warning'}>{formatVersionStatus(activeVersion.status)}</Badge>}
              </div>

              {/* Phase 4+: editor tabs — Content / Design / Signers / Preview */}
              <div style={{ display: 'flex', gap: '4px', borderBottom: '1px solid var(--mac-border)', paddingBottom: '8px' }}>
                {EDITOR_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setEditorTab(tab.id)}
                    aria-pressed={editorTab === tab.id}
                    style={{
                      padding: '8px 16px',
                      border: 'none',
                      background: editorTab === tab.id ? 'var(--mac-accent)' : 'transparent',
                      color: editorTab === tab.id ? 'white' : 'var(--mac-text-primary)',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      fontSize: '14px',
                      fontWeight: editorTab === tab.id ? 600 : 400,
                    }}>
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Tab content */}
              {editorTab === 'content' && renderContentTab()}
              {editorTab === 'design' && renderDesignTab()}
              {editorTab === 'signers' && renderSignersTab()}
              {editorTab === 'preview' && renderPreviewTab()}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Phase 4+: New Template dialog (was always-visible form) */}
      <NewTemplateDialog
        open={showNewTemplateDialog}
        onClose={() => setShowNewTemplateDialog(false)}
        onCreate={handleCreateTemplate}
        saving={saving}
      />

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
