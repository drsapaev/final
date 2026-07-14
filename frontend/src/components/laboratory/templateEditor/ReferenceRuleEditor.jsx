import PropTypes from 'prop-types';
import { Button, Icon } from '../../ui/macos';

/**
 * L-H-6 fix: ReferenceRuleEditor выделен в отдельный файл (~290 строк).
 *
 * Phase 3: structured editor for reference_rule JSON.
 * Replaces raw JSON textarea with a visual cases editor.
 *
 * Rule format (from backend _sex_reference_rule / _ige_reference_rule):
 * {
 *   "cases": [
 *     { "when": {"source":"patient.sex","op":"eq","value":"M"},
 *       "text":"3.5-5.0", "low":3.5, "high":5.0 }
 *   ],
 *   "default": { "text":"3.5-5.0", "low":3.5, "high":5.0 }
 * }
 *
 * Supports:
 *   - source: patient.sex | patient.age | patient.age_months
 *   - op: eq | ne | lt | gt | le | ge | between
 *   - value: string or number (for eq/ne/lt/gt/le/ge)
 *   - min/max: numbers (for between)
 *   - text/low/high: reference range for this case
 */

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

  if (!isStructured) {
    return (
      <div className="ltw-grid-6">
        <span>Правила нормы (raw JSON)</span>
        <textarea
          className="macos-input"
          aria-label="JSON правил нормы"
          rows={6}
          value={field.reference_rule_text || ''}
          onChange={(event) => updateField(sectionIndex, fieldIndex, 'reference_rule_text', event.target.value)}
        />
        <span className="ltw-text-12 ltw-text-secondary">
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
    <div className="ltw-rule-editor">
      <div className="ltw-flex-between">
        <span className="ltw-fw-600 ltw-text-14">Правила нормы</span>
        <Button variant="outline" size="small" onClick={addCase}>
          <Icon name="plus" size={12} />
          Добавить условие
        </Button>
      </div>

      {cases.length === 0 && (
        <span className="ltw-text-13 ltw-text-secondary">
          Нет условий. Будет использоваться значение по умолчанию.
        </span>
      )}

      {cases.map((caseItem, caseIndex) => {
        const isBetween = caseItem.when?.op === 'between';
        return (
          <div key={caseIndex} className="ltw-case-card">
            <div className="ltw-flex-between">
              <span className="ltw-text-13 ltw-fw-500">Условие {caseIndex + 1}</span>
              <Button variant="ghost" size="small" onClick={() => removeCase(caseIndex)} aria-label="Удалить условие">
                <Icon name="trash" size={12} />
              </Button>
            </div>

            <div className="ltw-grid-3">
              <label className="ltw-label-grid">
                <span className="ltw-text-12">Источник</span>
                <select
                  className="macos-input"
                  aria-label="Источник условия"
                  value={caseItem.when?.source || 'patient.sex'}
                  onChange={(e) => updateCaseWhen(caseIndex, 'source', e.target.value)}
                >
                  {RULE_SOURCE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </label>
              <label className="ltw-label-grid">
                <span className="ltw-text-12">Оператор</span>
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
                <div className="ltw-grid-2-50-50">
                  <label className="ltw-label-grid">
                    <span className="ltw-text-12">Минимум</span>
                    <input
                      className="macos-input"
                      aria-label="Минимум условия"
                      type="number"
                      value={caseItem.when?.min ?? ''}
                      onChange={(e) => updateCaseWhen(caseIndex, 'min', parseFloat(e.target.value) || 0)}
                    />
                  </label>
                  <label className="ltw-label-grid">
                    <span className="ltw-text-12">Максимум</span>
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
                <label className="ltw-label-grid">
                  <span className="ltw-text-12">Значение</span>
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

            <div className="ltw-grid-3-ranges">
              <label className="ltw-label-grid">
                <span className="ltw-text-12">Текст нормы</span>
                <input
                  className="macos-input"
                  aria-label="Текст нормы для условия"
                  value={caseItem.text || ''}
                  onChange={(e) => updateCase(caseIndex, 'text', e.target.value)}
                  placeholder="3.5-5.0"
                />
              </label>
              <label className="ltw-label-grid">
                <span className="ltw-text-12">Нижняя граница</span>
                <input
                  className="macos-input"
                  aria-label="Нижняя граница нормы"
                  type="number"
                  value={caseItem.low ?? ''}
                  onChange={(e) => updateCase(caseIndex, 'low', parseFloat(e.target.value) || null)}
                />
              </label>
              <label className="ltw-label-grid">
                <span className="ltw-text-12">Верхняя граница</span>
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

      <div className="ltw-default-card">
        <span className="ltw-text-13 ltw-fw-500">По умолчанию (если ни одно условие не сработало)</span>
        <div className="ltw-grid-3-ranges">
          <label className="ltw-label-grid">
            <span className="ltw-text-12">Текст нормы</span>
            <input
              className="macos-input"
              aria-label="Текст нормы по умолчанию"
              value={defaultRule.text || ''}
              onChange={(e) => updateDefault('text', e.target.value)}
              placeholder="3.5-5.0"
            />
          </label>
          <label className="ltw-label-grid">
            <span className="ltw-text-12">Нижняя граница</span>
            <input
              className="macos-input"
              aria-label="Нижняя граница по умолчанию"
              type="number"
              value={defaultRule.low ?? ''}
              onChange={(e) => updateDefault('low', parseFloat(e.target.value) || null)}
            />
          </label>
          <label className="ltw-label-grid">
            <span className="ltw-text-12">Верхняя граница</span>
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

      <details>
        <summary className="ltw-summary-12">
          Raw JSON (для продвинутых)
        </summary>
        <textarea
          className="macos-input ltw-raw-json-textarea"
          aria-label="Raw JSON правил нормы"
          rows={6}
          value={field.reference_rule_text || ''}
          onChange={(event) => updateField(sectionIndex, fieldIndex, 'reference_rule_text', event.target.value)}
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

export default ReferenceRuleEditor;
