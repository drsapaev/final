
import PropTypes from 'prop-types';
import { Button, Icon } from '../../ui/macos';
import { useTranslation } from '../../../i18n/useTranslation';

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
  { value: 'patient.sex', labelKey: 'misc.rre_src_sex' },
  { value: 'patient.age', labelKey: 'misc.rre_src_age' },
  { value: 'patient.age_months', labelKey: 'misc.rre_src_age_months' },
];

const RULE_OP_OPTIONS = [
  { value: 'eq', label: '=' },
  { value: 'ne', label: '≠' },
  { value: 'lt', label: '<' },
  { value: 'gt', label: '>' },
  { value: 'le', label: '≤' },
  { value: 'ge', label: '≥' },
  { value: 'between', labelKey: 'misc.rre_op_between' },
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
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const rule = parseRuleText(field.reference_rule_text);
  const isStructured = rule === null || (rule && Array.isArray(rule.cases));

  if (!isStructured) {
    return (
      <div className="ltw-grid-6">
        <span>{t('misc.rre_raw_json')}</span>
        <textarea
          className="macos-input"
          aria-label={t('misc.rre_raw_json_aria')}
          rows={6}
          value={field.reference_rule_text || ''}
          onChange={(event) => updateField(sectionIndex, fieldIndex, 'reference_rule_text', event.target.value)}
        />
        <span className="ltw-text-12 ltw-text-secondary">
          {t('misc.rre_struct_unavailable')}
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
        <span className="ltw-fw-600 ltw-text-14">{t('misc.rre_norm_rules')}</span>
        <Button variant="outline" size="small" onClick={addCase}>
          <Icon name="plus" size={12 as unknown as "small" | "default" | "large" | "xlarge"} />
          {t('misc.rre_add_condition')}
        </Button>
      </div>

      {cases.length === 0 && (
        <span className="ltw-text-13 ltw-text-secondary">
          {t('misc.rre_no_conditions')}
        </span>
      )}

      {cases.map((caseItem, caseIndex) => {
        const isBetween = caseItem.when?.op === 'between';
        return (
          <div key={caseIndex} className="ltw-case-card">
            <div className="ltw-flex-between">
              <span className="ltw-text-13 ltw-fw-500">{t('misc.rre_condition_n', { n: caseIndex + 1 })}</span>
              <Button variant="ghost" size="small" onClick={() => removeCase(caseIndex)} aria-label={t('misc.rre_remove_condition')}>
                <Icon name="trash" size={12 as unknown as "small" | "default" | "large" | "xlarge"} />
              </Button>
            </div>

            <div className="ltw-grid-3">
              <label className="ltw-label-grid">
                <span className="ltw-text-12">{t('misc.rre_source')}</span>
                <select
                  className="macos-input"
                  aria-label={t('misc.rre_source_aria')}
                  value={caseItem.when?.source || 'patient.sex'}
                  onChange={(e) => updateCaseWhen(caseIndex, 'source', e.target.value)}
                >
                  {RULE_SOURCE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{t(o.labelKey)}</option>)}
                </select>
              </label>
              <label className="ltw-label-grid">
                <span className="ltw-text-12">{t('misc.rre_operator')}</span>
                <select
                  className="macos-input"
                  aria-label={t('misc.rre_operator_aria')}
                  value={caseItem.when?.op || 'eq'}
                  onChange={(e) => updateCaseWhen(caseIndex, 'op', e.target.value)}
                >
                  {RULE_OP_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.labelKey ? t(o.labelKey) : o.label}</option>)}
                </select>
              </label>
              {isBetween ? (
                <div className="ltw-grid-2-50-50">
                  <label className="ltw-label-grid">
                    <span className="ltw-text-12">{t('misc.rre_min')}</span>
                    <input
                      className="macos-input"
                      aria-label={t('misc.rre_min_aria')}
                      type="number"
                      value={caseItem.when?.min ?? ''}
                      onChange={(e) => updateCaseWhen(caseIndex, 'min', parseFloat(e.target.value) || 0)}
                    />
                  </label>
                  <label className="ltw-label-grid">
                    <span className="ltw-text-12">{t('misc.rre_max')}</span>
                    <input
                      className="macos-input"
                      aria-label={t('misc.rre_max_aria')}
                      type="number"
                      value={caseItem.when?.max ?? ''}
                      onChange={(e) => updateCaseWhen(caseIndex, 'max', parseFloat(e.target.value) || 0)}
                    />
                  </label>
                </div>
              ) : (
                <label className="ltw-label-grid">
                  <span className="ltw-text-12">{t('misc.rre_value')}</span>
                  {caseItem.when?.source === 'patient.sex' ? (
                    <select
                      className="macos-input"
                      aria-label={t('misc.rre_value_aria')}
                      value={caseItem.when?.value ?? ''}
                      onChange={(e) => updateCaseWhen(caseIndex, 'value', e.target.value)}
                    >
                      <option value="">{t('misc.rre_select')}</option>
                      <option value="M">{t('misc.rre_male_m')}</option>
                      <option value="F">{t('misc.rre_female_f')}</option>
                    </select>
                  ) : (
                    <input
                      className="macos-input"
                      aria-label={t('misc.rre_value_aria')}
                      value={caseItem.when?.value ?? ''}
                      onChange={(e) => updateCaseWhen(caseIndex, 'value', e.target.value)}
                    />
                  )}
                </label>
              )}
            </div>

            <div className="ltw-grid-3-ranges">
              <label className="ltw-label-grid">
                <span className="ltw-text-12">{t('misc.rre_norm_text')}</span>
                <input
                  className="macos-input"
                  aria-label={t('misc.rre_norm_text_aria')}
                  value={caseItem.text || ''}
                  onChange={(e) => updateCase(caseIndex, 'text', e.target.value)}
                  placeholder="3.5-5.0"
                />
              </label>
              <label className="ltw-label-grid">
                <span className="ltw-text-12">{t('misc.rre_lower_bound')}</span>
                <input
                  className="macos-input"
                  aria-label={t('misc.rre_lower_bound_aria')}
                  type="number"
                  value={caseItem.low ?? ''}
                  onChange={(e) => updateCase(caseIndex, 'low', parseFloat(e.target.value) || null)}
                />
              </label>
              <label className="ltw-label-grid">
                <span className="ltw-text-12">{t('misc.rre_upper_bound')}</span>
                <input
                  className="macos-input"
                  aria-label={t('misc.rre_upper_bound_aria')}
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
        <span className="ltw-text-13 ltw-fw-500">{t('misc.rre_default_label')}</span>
        <div className="ltw-grid-3-ranges">
          <label className="ltw-label-grid">
            <span className="ltw-text-12">{t('misc.rre_norm_text')}</span>
            <input
              className="macos-input"
              aria-label={t('misc.rre_norm_text_default_aria')}
              value={defaultRule.text || ''}
              onChange={(e) => updateDefault('text', e.target.value)}
              placeholder="3.5-5.0"
            />
          </label>
          <label className="ltw-label-grid">
            <span className="ltw-text-12">{t('misc.rre_lower_bound')}</span>
            <input
              className="macos-input"
              aria-label={t('misc.rre_lower_bound_default_aria')}
              type="number"
              value={defaultRule.low ?? ''}
              onChange={(e) => updateDefault('low', parseFloat(e.target.value) || null)}
            />
          </label>
          <label className="ltw-label-grid">
            <span className="ltw-text-12">{t('misc.rre_upper_bound')}</span>
            <input
              className="macos-input"
              aria-label={t('misc.rre_upper_bound_default_aria')}
              type="number"
              value={defaultRule.high ?? ''}
              onChange={(e) => updateDefault('high', parseFloat(e.target.value) || null)}
            />
          </label>
        </div>
      </div>

      <details>
        <summary className="ltw-summary-12">
          {t('misc.rre_raw_json_advanced')}
        </summary>
        <textarea
          className="macos-input ltw-raw-json-textarea"
          aria-label={t('misc.rre_raw_json_aria')}
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
