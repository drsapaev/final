/**
 * BloodTestsTab — R-15 (UX audit): extracted from CardiologistPanelUnified.
 *
 * This component renders the "Анализы крови" tab content:
 *   1. Header with "Новый анализ" button
 *   2. Stats cards (average cholesterol, LDL, glucose)
 *   3. Blood test history list
 *   4. Blood test entry form (when showForm.open)
 *
 * All state and business logic stays in the parent (CardiologistPanelUnified).
 * This is a presentational component — it receives data and callbacks via props.
 *
 * Extraction rationale: CardiologistPanelUnified.jsx was 2500+ lines.
 * The blood tests tab accounted for ~350 lines of JSX. Moving it here
 * reduces the parent by ~14% and makes both files easier to maintain.
 */

import PropTypes from 'prop-types';
import { TestTube, Plus, Save } from 'lucide-react';
import { Button, Textarea, Badge, MacOSCard } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

/**
 * @param {Object} props
 * @param {Array} props.bloodTests - Array of blood test records
 * @param {Object} props.bloodTestForm - Current form state
 * @param {Function} props.setBloodTestForm - Update form state
 * @param {boolean} props.showFormOpen - Whether the form is visible
 * @param {Function} props.onNewTest - Open the form
 * @param {Function} props.onCancelForm - Close the form
 * @param {Function} props.onSubmit - Submit handler (form onSubmit)
 * @param {Function} props.getEmptyBloodTestForm - Reset form to empty
 * @param {Function} props.getFieldRangeWarning - Range validation helper
 * @param {Function} props.isLdlCritical - LDL critical check
 * @param {Object} props.settings - User settings (ldlThreshold, etc.)
 * @param {Function} props.getColor - Theme color getter
 * @param {Function} props.getFontSize - Theme font size getter
 * @param {Function} props.getSpacing - Theme spacing getter
 */
export function BloodTestsTab({
  bloodTests = [],
  bloodTestForm,
  setBloodTestForm,
  showFormOpen = false,
  onNewTest,
  onCancelForm,
  onSubmit,
  getEmptyBloodTestForm,
  getFieldRangeWarning,
  isLdlCritical,
  settings,
  getColor,
  getFontSize,
  getSpacing,
}) {
  const { t } = useTranslation();
  // Helper: compute average of a field across all blood tests
  const avg = (key) => {
    const nums = bloodTests
      .map((t) => Number(t[key]))
      .filter((v) => !Number.isNaN(v));
    if (nums.length === 0) return '—';
    const sum = nums.reduce((a, b) => a + b, 0);
    return Math.round((sum / nums.length) * 10) / 10;
  };

  // Stats items
  const statItems = [
    { label: t('cardio.cardio_blood_stat_avg_cholesterol'), value: avg('cholesterol_total'), unit: t('cardio.cardio_blood_unit_mgdl') },
    { label: t('cardio.cardio_blood_stat_avg_ldl'), value: avg('cholesterol_ldl'), unit: t('cardio.cardio_blood_unit_mgdl'), critical: isLdlCritical(avg('cholesterol_ldl')) },
    { label: t('cardio.cardio_blood_stat_avg_glucose'), value: avg('glucose'), unit: t('cardio.cardio_blood_unit_mgdl') },
  ];

  // Helper: render a form input with range validation
  const renderField = (fieldName, label, placeholder, ariaLabel) => {
    const warning = getFieldRangeWarning(fieldName, bloodTestForm[fieldName]);
    const isError = warning?.valid === false;
    return (
      <div>
        <label className="cardio-form-label">{label}</label>
        <input
          type="number"
          aria-label={ariaLabel}
          value={bloodTestForm[fieldName]}
          onChange={(e) => setBloodTestForm({ ...bloodTestForm, [fieldName]: e.target.value })}
          className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white cardio-input-themed"
          style={{
            border: `1px solid ${isError ? 'var(--mac-error)' : getColor('border')}`,
            backgroundColor: isError ? 'var(--mac-error-bg)' : getColor('surface'),
            color: isError ? 'var(--mac-error)' : getColor('text'),
          }}
          placeholder={placeholder}
        />
        {isError && (
          <div role="alert" style={{ marginTop: '4px', fontSize: getFontSize('xs'), color: 'var(--mac-error)', fontWeight: '500' }}>
            {warning.message}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="cardio-flex-col-visible" style={{ gap: '24px' }}>
      {/* Legacy notice — CardioBloodTest is deprecated in favor of LabResultsSection */}
      <div style={{
        padding: '12px 16px',
        background: 'rgba(255, 149, 0, 0.08)',
        border: '1px solid rgba(255, 149, 0, 0.3)',
        borderRadius: '10px',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '10px',
      }}>
        <TestTube size={18} style={{ color: 'var(--mac-warning)', flexShrink: 0, marginTop: '2px' }} />
        <div>
          <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--mac-warning)' }}>
            {t('cardio.cardio_blood_notice_title')}
          </div>
          <div style={{ fontSize: '13px', color: 'var(--mac-text-secondary)', marginTop: '4px' }}>
            {t('cardio.cardio_blood_notice_desc')}
          </div>
        </div>
      </div>

      {/* Header */}
      <MacOSCard className="cardio-card-padded">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: getSpacing('lg') }}>
          <h3 style={{ display: 'flex', alignItems: 'center', fontSize: getFontSize('lg'), fontWeight: '500', color: getColor('text') }}>
            <TestTube size={20} style={{ marginRight: getSpacing('sm'), color: getColor('secondary', 600) }} />
            {t('cardio.cardio_blood_history_title')}
          </h3>
          <Button onClick={onNewTest} title={t('cardio.cardio_blood_manual_input_title')}>
            <Plus size={16} className="cardio-icon-mr" />
            {t('cardio.cardio_blood_manual_input')}
          </Button>
        </div>

        {/* Stats cards */}
        {bloodTests.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: getSpacing('lg'), marginBottom: getSpacing('xl') }}>
            {statItems.map((it, idx) => (
              <div key={idx} style={{
                padding: getSpacing('md'),
                border: `1px solid ${it.critical ? 'var(--mac-danger)' : getColor('border')}`,
                backgroundColor: it.critical ? 'var(--mac-error-bg)' : getColor('surface'),
                color: getColor('text'),
                borderRadius: '8px',
              }}>
                <div style={{ fontSize: getFontSize('sm'), color: it.critical ? 'var(--mac-danger)' : getColor('textSecondary'), marginBottom: getSpacing('xs') }}>
                  {it.label}
                </div>
                <div className="cardio-stat-value" style={{ color: it.critical ? 'var(--mac-danger)' : getColor('text') }}>
                  {it.value} {typeof it.value === 'number' ? it.unit : ''}
                  {it.critical && (
                    <span className="cardio-critical-warn">{it.value} &gt; {settings?.ldlThreshold ?? 100}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Blood test list */}
        {bloodTests.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('lg') }}>
            {bloodTests.map((test) => (
              <div key={test.id} style={{ padding: getSpacing('lg'), border: `1px solid ${getColor('border')}`, backgroundColor: getColor('surface'), borderRadius: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: getSpacing('sm') }}>
                  <h4 style={{ fontSize: getFontSize('base'), fontWeight: '500', color: getColor('text') }}>{t('cardio.cardio_blood_test_title', { id: test.id })}</h4>
                  <Badge variant="info">{test.test_date}</Badge>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: getSpacing('lg'), fontSize: getFontSize('sm'), color: getColor('textSecondary'), marginBottom: getSpacing('sm') }}>
                  <div>{t('cardio.cardio_blood_cholesterol', { value: test.cholesterol_total })}</div>
                  <div>HDL: {test.cholesterol_hdl}</div>
                  <div style={isLdlCritical(test.cholesterol_ldl) ? { color: 'var(--mac-error)', fontWeight: '600' } : undefined}>
                    LDL: {test.cholesterol_ldl}
                    {isLdlCritical(test.cholesterol_ldl) && <span style={{ marginLeft: '4px', fontSize: getFontSize('xs') }}>{t('cardio.cardio_blood_critical')}</span>}
                  </div>
                  <div>{t('cardio.cardio_blood_triglycerides', { value: test.triglycerides })}</div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: getSpacing('lg'), fontSize: getFontSize('sm'), color: getColor('textSecondary') }}>
                  <div>{t('cardio.cardio_blood_glucose', { value: test.glucose })}</div>
                  <div>{t('cardio.cardio_blood_crp', { value: test.crp })}</div>
                  <div>{t('cardio.cardio_blood_troponin', { value: test.troponin })}</div>
                </div>
                {test.interpretation && (
                  <div style={{ marginTop: getSpacing('sm'), padding: getSpacing('sm'), background: getColor('surfaceSecondary'), borderRadius: '4px', fontSize: getFontSize('sm'), color: getColor('textSecondary') }}>
                    {test.interpretation}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: getSpacing('xl'), color: getColor('textSecondary') }}>
            <TestTube size={48} style={{ opacity: 0.3, marginBottom: getSpacing('md') }} />
            <div style={{ fontSize: getFontSize('base') }}>{t('cardio.cardio_blood_empty_title')}</div>
            <div style={{ fontSize: getFontSize('sm'), marginTop: getSpacing('xs') }}>
              {t('cardio.cardio_blood_empty_desc')}
            </div>
          </div>
        )}
      </MacOSCard>

      {/* Blood test form */}
      {showFormOpen && (
        <MacOSCard className="cardio-card-padded">
          <h3 style={{ fontSize: getFontSize('lg'), fontWeight: '500', marginBottom: getSpacing('lg'), color: getColor('text') }}>
            {t('cardio.cardio_blood_form_title')}
          </h3>
          <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('lg') }}>
            <div className="grid grid-cols-1 md:grid-cols-3" style={{ gap: getSpacing('lg') }}>
              <div>
                <label className="cardio-form-label">{t('cardio.cardio_blood_date_label')}</label>
                <input
                  type="date"
                  required
                  aria-label={t('cardio.cardio_blood_date_aria')}
                  value={bloodTestForm.test_date}
                  onChange={(e) => setBloodTestForm({ ...bloodTestForm, test_date: e.target.value })}
                  className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white cardio-input-themed"
                  style={{ border: `1px solid ${getColor('border')}`, backgroundColor: getColor('surface'), color: getColor('text') }}
                />
              </div>
              {renderField('cholesterol_total', t('cardio.cardio_blood_total_ch_label'), t('cardio.cardio_blood_ph_total_ch'), t('cardio.cardio_blood_total_ch_label'))}
              {renderField('cholesterol_hdl', t('cardio.cardio_blood_hdl_label'), t('cardio.cardio_blood_ph_hdl'), t('cardio.cardio_blood_hdl_label'))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3" style={{ gap: getSpacing('lg') }}>
              <div>
                <label className="cardio-form-label">{t('cardio.cardio_blood_ldl_label')}</label>
                <input
                  type="number"
                  aria-label="LDL cholesterol"
                  value={bloodTestForm.cholesterol_ldl}
                  onChange={(e) => setBloodTestForm({ ...bloodTestForm, cholesterol_ldl: e.target.value })}
                  className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white cardio-input-themed"
                  style={{
                    border: `1px solid ${isLdlCritical(bloodTestForm.cholesterol_ldl) ? 'var(--mac-error)' : getColor('border')}`,
                    backgroundColor: isLdlCritical(bloodTestForm.cholesterol_ldl) ? 'var(--mac-error-bg)' : getColor('surface'),
                    color: isLdlCritical(bloodTestForm.cholesterol_ldl) ? 'var(--mac-error)' : getColor('text'),
                  }}
                  placeholder={t('cardio.cardio_blood_ph_ldl')}
                />
                {isLdlCritical(bloodTestForm.cholesterol_ldl) && (
                  <div role="alert" style={{ marginTop: '4px', fontSize: getFontSize('xs'), color: 'var(--mac-error)', fontWeight: '500' }}>
                    {t('cardio.cardio_blood_ldl_warning', { threshold: settings?.ldlThreshold ?? 100 })}
                  </div>
                )}
              </div>
              {renderField('triglycerides', t('cardio.cardio_blood_triglycerides_label'), t('cardio.cardio_blood_ph_triglycerides'), t('cardio.cardio_blood_triglycerides_label'))}
              {renderField('glucose', t('cardio.cardio_blood_glucose_label'), t('cardio.cardio_blood_ph_glucose'), t('cardio.cardio_blood_glucose_label'))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: getSpacing('lg') }}>
              {renderField('crp', t('cardio.cardio_blood_crp_label'), t('cardio.cardio_blood_ph_crp'), 'CRP')}
              {renderField('troponin', t('cardio.cardio_blood_troponin_label'), t('cardio.cardio_blood_ph_troponin'), t('cardio.cardio_blood_troponin_label'))}
            </div>

            <div>
              <label className="cardio-form-label">{t('cardio.cardio_blood_interpretation_label')}</label>
              <Textarea
                value={bloodTestForm.interpretation}
                onChange={(e) => setBloodTestForm({ ...bloodTestForm, interpretation: e.target.value })}
                placeholder={t('cardio.cardio_blood_ph_interpretation')}
                rows={4}
              />
            </div>

            <div className="flex justify-end" style={{ gap: getSpacing('md') }}>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  onCancelForm();
                  setBloodTestForm(getEmptyBloodTestForm());
                }}
              >
                {t('cardio.cardio_blood_cancel')}
              </Button>
              <Button type="submit">
                <Save size={16} className="cardio-icon-mr" />
                {t('cardio.cardio_blood_save')}
              </Button>
            </div>
          </form>
        </MacOSCard>
      )}
    </div>
  );
}

BloodTestsTab.propTypes = {
  bloodTests: PropTypes.array,
  bloodTestForm: PropTypes.object.isRequired,
  setBloodTestForm: PropTypes.func.isRequired,
  showFormOpen: PropTypes.bool,
  onNewTest: PropTypes.func.isRequired,
  onCancelForm: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
  getEmptyBloodTestForm: PropTypes.func.isRequired,
  getFieldRangeWarning: PropTypes.func.isRequired,
  isLdlCritical: PropTypes.func.isRequired,
  settings: PropTypes.object,
  getColor: PropTypes.func.isRequired,
  getFontSize: PropTypes.func.isRequired,
  getSpacing: PropTypes.func.isRequired,
};

export default BloodTestsTab;
