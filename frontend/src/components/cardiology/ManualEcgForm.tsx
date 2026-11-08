/**
 * ManualEcgForm — CARDIO-FE-001 (audit 3886 round 20).
 *
 * A dedicated controlled form for entering ECG parameters by hand (from a
 * printout or another system). Previously the "Добавить ЭКГ" flow reused
 * `<BloodTestsTab showFormOpen />`, which rendered cholesterol/HDL/LDL/
 * triglycerides/glucose/CRP/troponin inputs, required the blood-test
 * `test_date` field, and POSTed `heart_rate`/`pr_interval`/`qrs_duration`/
 * `qt_interval`/`rhythm`/`axis` read from that blood-test form state —
 * i.e. every ECG measurement was serialized as null.
 *
 * Contract (fail-first, ManualEcgForm.test.tsx):
 *  - renders ECG inputs (date, HR, PR, QRS, QT, rhythm, axis,
 *    interpretation) and NO blood-test inputs;
 *  - the POST /cardio/ecg payload carries the entered measurements under
 *    the backend `CardioECGRecordCreate` DTO keys with `source: 'manual'`;
 *  - a missing date or a fully empty clinical set never fires the POST
 *    (no silent empty ECG records);
 *  - the submit button is disabled while the request is in flight
 *    (no duplicate submissions).
 *
 * The backend stays authoritative for authorization and validation; this
 * form only stops mislabeling blood-test input as ECG measurements.
 */
import React, { useMemo, useState } from 'react';
import { HeartPulse, Save } from 'lucide-react';
import { Button, Card } from '../ui/macos';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import notify from '../../services/notify';
import { useTranslation } from '../../i18n/useTranslation';
import { useTheme } from '../../contexts/ThemeContext';

export interface ManualEcgFormProps {
  /** Canonical patient id (required for the POST payload). */
  patientId?: string | number | null;
  /** Visit id, when the ECG belongs to an active encounter. */
  visitId?: string | number | null;
  /** Close the form without saving. */
  onCancel: () => void;
  /** Called after a confirmed 2xx save so the panel can reload data. */
  onSaved?: () => void;
}

interface EcgManualFormState {
  ecg_date: string;
  heart_rate: string;
  pr_interval: string;
  qrs_duration: string;
  qt_interval: string;
  rhythm: string;
  axis: string;
  interpretation: string;
}

const EMPTY_ECG_FORM: EcgManualFormState = {
  ecg_date: '',
  heart_rate: '',
  pr_interval: '',
  qrs_duration: '',
  qt_interval: '',
  rhythm: '',
  axis: '',
  interpretation: '',
};

/** Physiological ranges for manual ECG entry (mirrors the FIELD_RANGES
 * style of the blood-test form; the backend schema stays the authority). */
const ECG_FIELD_RANGES: Record<string, { min: number; max: number; unit: string; labelKey: string }> = {
  heart_rate: { min: 20, max: 250, unit: 'bpm', labelKey: 'cardio.cardio_ecg_hr_short' },
  pr_interval: { min: 40, max: 500, unit: 'ms', labelKey: 'cardio.cardio_ecg_pr_interval' },
  qrs_duration: { min: 20, max: 300, unit: 'ms', labelKey: 'cardio.cardio_ecg_qrs_interval' },
  qt_interval: { min: 200, max: 600, unit: 'ms', labelKey: 'cardio.cardio_ecg_qt_interval' },
};

const ECG_NUMERIC_FIELDS = Object.keys(ECG_FIELD_RANGES);
const ECG_TEXT_FIELDS = ['rhythm', 'axis', 'interpretation'] as const;

function toNumberOrNull(raw: string): number | null {
  const trimmed = String(raw ?? '').trim();
  if (trimmed === '') return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

/** Style factories (UI_AUDIT_PLAN Phase 0 ratchet: no inline `style={{…}}`
 * literals and no raw `var(--mac-*)` without fallback in JSX — theme
 * values flow through the useTheme getters). */
interface ThemeGetters {
  getColor: (key: string, shade?: number) => string;
  getFontSize: (key: string) => string;
  getSpacing: (key: string) => string;
}

const sectionHeaderStyle = (g: ThemeGetters): React.CSSProperties => ({
  display: 'flex',
  alignItems: 'center',
  gap: g.getSpacing('sm'),
  margin: 0,
  fontSize: g.getFontSize('lg'),
  fontWeight: '500',
  color: g.getColor('text'),
});

const hintStyle = (g: ThemeGetters): React.CSSProperties => ({
  margin: `0 0 ${g.getSpacing('lg')}`,
  fontSize: g.getFontSize('sm'),
  color: g.getColor('textSecondary'),
});

const columnFormStyle = (g: ThemeGetters): React.CSSProperties => ({
  display: 'flex',
  flexDirection: 'column',
  gap: g.getSpacing('lg'),
});

const gridGapStyle = (g: ThemeGetters): React.CSSProperties => ({ gap: g.getSpacing('lg') });

const alertStyle = (g: ThemeGetters): React.CSSProperties => ({
  fontSize: g.getFontSize('xs'),
  color: g.getColor('danger'),
  fontWeight: '500',
});

const textareaStyle = (g: ThemeGetters, base: React.CSSProperties): React.CSSProperties => ({
  ...base,
  minHeight: 80,
  padding: g.getSpacing('sm'),
});

const iconStyle = (color: string): React.CSSProperties => ({ color });

const actionsRowStyle = (g: ThemeGetters): React.CSSProperties => ({
  display: 'flex',
  gap: g.getSpacing('sm'),
  justifyContent: 'flex-end',
});

export function ManualEcgForm({
  patientId,
  visitId,
  onCancel,
  onSaved,
}: ManualEcgFormProps): React.JSX.Element {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const { getColor, getFontSize, getSpacing } = useTheme();
  const [form, setForm] = useState<EcgManualFormState>({
    ...EMPTY_ECG_FORM,
    ecg_date: new Date().toISOString().slice(0, 10),
  });
  const [submitting, setSubmitting] = useState(false);
  const [validationMessage, setValidationMessage] = useState('');

  const fieldWarning = useMemo(() => {
    for (const field of ECG_NUMERIC_FIELDS) {
      const parsed = toNumberOrNull(form[field as keyof EcgManualFormState]);
      if (parsed === null) continue;
      const range = ECG_FIELD_RANGES[field];
      const options = {
        label: t(range.labelKey),
        value: parsed,
        unit: range.unit,
      };
      if (parsed < range.min) {
        return t('cardio.cardio_panel_range_below_min', { ...options, min: range.min });
      }
      if (parsed > range.max) {
        return t('cardio.cardio_panel_range_above_max', { ...options, max: range.max });
      }
    }
    return '';
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form, rawT]);

  const hasClinicalInput = useMemo(
    () =>
      ECG_NUMERIC_FIELDS.concat(ECG_TEXT_FIELDS)
        .some((field) => String(form[field as keyof EcgManualFormState] ?? '').trim() !== ''),
    [form],
  );

  const setField = (field: keyof EcgManualFormState, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setValidationMessage('');
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;

    const { ecg_date } = form;
    if (!ecg_date) {
      setValidationMessage(t('cardio.cardio_manual_ecg_date_required'));
      return;
    }
    if (!patientId) {
      setValidationMessage(t('cardio.cardio_manual_ecg_no_patient'));
      return;
    }
    if (!hasClinicalInput) {
      // CARDIO-FE-001: never persist a manual ECG record that carries no
      // ECG content at all — the old flow did exactly that (null
      // measurements behind an unrelated blood-test date).
      setValidationMessage(t('cardio.cardio_manual_ecg_empty_clinical'));
      return;
    }

    const payload = {
      patient_id: Number(patientId),
      visit_id: visitId != null && visitId !== '' ? Number(visitId) : null,
      file_id: null,
      ecg_date,
      heart_rate: toNumberOrNull(form.heart_rate),
      pr_interval: toNumberOrNull(form.pr_interval),
      qrs_duration: toNumberOrNull(form.qrs_duration),
      qt_interval: toNumberOrNull(form.qt_interval),
      rhythm: form.rhythm.trim() || null,
      axis: form.axis.trim() || null,
      interpretation: form.interpretation.trim() || null,
      source: 'manual',
      parameters: {
        heart_rate: toNumberOrNull(form.heart_rate),
        pr_interval: toNumberOrNull(form.pr_interval),
        qrs_duration: toNumberOrNull(form.qrs_duration),
        qt_interval: toNumberOrNull(form.qt_interval),
        rhythm: form.rhythm.trim() || null,
        axis: form.axis.trim() || null,
        interpretation: form.interpretation.trim() || null,
        entered_manually: true,
      },
    };

    setSubmitting(true);
    try {
      await api.post('/cardio/ecg', payload);
      notify.success(t('cardio.ecg_added'));
      onSaved?.();
    } catch (error) {
      logger.error('[ManualEcgForm] Ошибка сохранения ЭКГ:', error);
      notify.error(t('cardio.ecg_save_failed'));
    } finally {
      setSubmitting(false);
    }
  };

  const inputStyle = (invalid: boolean): React.CSSProperties => ({
    border: `1px solid ${invalid ? getColor('danger') : getColor('border')}`,
    backgroundColor: invalid ? getColor('surfaceSecondary') : getColor('surface'),
    color: invalid ? getColor('danger') : getColor('text'),
  });

  const renderNumericField = (field: keyof EcgManualFormState, label: string, placeholder: string) => {
    const parsed = toNumberOrNull(form[field]);
    const range = ECG_FIELD_RANGES[field as string];
    const invalid = parsed !== null && (parsed < range.min || parsed > range.max);
    return (
      <div>
        <label className="cardio-form-label" htmlFor={`manual-ecg-${field}`}>{label}</label>
        <input
          id={`manual-ecg-${field}`}
          type="number"
          inputMode="decimal"
          aria-label={label}
          value={form[field]}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setField(field, e.target.value)}
          className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white cardio-input-themed"
          style={inputStyle(invalid)}
          placeholder={placeholder}
        />
      </div>
    );
  };

  const themeGetters = { getColor, getFontSize, getSpacing };

  return (
    <Card className="cardio-card-padded">
      <div className="cardio-flex-between" style={gridGapStyle(themeGetters)}>
        <h3 style={sectionHeaderStyle(themeGetters)}>
          <HeartPulse size={20} style={iconStyle(getColor('secondary', 600))} />
          {t('cardio.cardio_panel_add_ecg_title')}
        </h3>
        <Button variant="outline" size="small" onClick={onCancel}>
          {t('cardio.cardio_panel_close')}
        </Button>
      </div>

      <p style={hintStyle(themeGetters)}>
        {t('cardio.cardio_manual_ecg_hint')}
      </p>

      <form onSubmit={handleSubmit} style={columnFormStyle(themeGetters)} noValidate>
        <div className="grid grid-cols-1 md:grid-cols-3" style={gridGapStyle(themeGetters)}>
          <div>
            <label className="cardio-form-label" htmlFor="manual-ecg-date">{t('cardio.cardio_manual_ecg_date_label')}</label>
            <input
              id="manual-ecg-date"
              type="date"
              required
              aria-label={t('cardio.cardio_manual_ecg_date_aria')}
              value={form.ecg_date}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setField('ecg_date', e.target.value)}
              className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white cardio-input-themed"
              style={inputStyle(false)}
            />
          </div>
          {renderNumericField('heart_rate', t('cardio.cardio_ecg_hr_short'), t('cardio.cardio_manual_ecg_hr_ph'))}
          {renderNumericField('pr_interval', t('cardio.cardio_ecg_pr_interval'), t('cardio.cardio_manual_ecg_ms_ph'))}
          {renderNumericField('qrs_duration', t('cardio.cardio_ecg_qrs_interval'), t('cardio.cardio_manual_ecg_ms_ph'))}
          {renderNumericField('qt_interval', t('cardio.cardio_ecg_qt_interval'), t('cardio.cardio_manual_ecg_ms_ph'))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2" style={gridGapStyle(themeGetters)}>
          <div>
            <label className="cardio-form-label" htmlFor="manual-ecg-rhythm">{t('cardio.cardio_manual_ecg_rhythm_label')}</label>
            <input
              id="manual-ecg-rhythm"
              type="text"
              aria-label={t('cardio.cardio_manual_ecg_rhythm_label')}
              value={form.rhythm}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setField('rhythm', e.target.value)}
              className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white cardio-input-themed"
              style={inputStyle(false)}
              placeholder={t('cardio.cardio_manual_ecg_rhythm_ph')}
            />
          </div>
          <div>
            <label className="cardio-form-label" htmlFor="manual-ecg-axis">{t('cardio.cardio_ecg_heart_axis')}</label>
            <input
              id="manual-ecg-axis"
              type="text"
              aria-label={t('cardio.cardio_ecg_heart_axis')}
              value={form.axis}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setField('axis', e.target.value)}
              className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white cardio-input-themed"
              style={inputStyle(false)}
              placeholder={t('cardio.cardio_manual_ecg_axis_ph')}
            />
          </div>
        </div>

        <div>
          <label className="cardio-form-label" htmlFor="manual-ecg-interpretation">{t('cardio.cardio_manual_ecg_interpretation_label')}</label>
          <textarea
            id="manual-ecg-interpretation"
            aria-label={t('cardio.cardio_manual_ecg_interpretation_label')}
            value={form.interpretation}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setField('interpretation', e.target.value)}
            className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white cardio-input-themed"
            style={textareaStyle(themeGetters, inputStyle(false))}
            placeholder={t('cardio.cardio_manual_ecg_interpretation_ph')}
            rows={4}
          />
        </div>

        {(validationMessage || fieldWarning) && (
          <div role="alert" style={alertStyle(themeGetters)}>
            {validationMessage || fieldWarning}
          </div>
        )}

        <div style={actionsRowStyle(themeGetters)}>
          <Button type="button" variant="outline" onClick={onCancel} disabled={submitting}>
            {t('cardio.cardio_panel_close')}
          </Button>
          <Button type="submit" variant="primary" disabled={submitting}>
            <Save size={16} className="cardio-icon-mr" />
            {submitting ? t('cardio.cardio_manual_ecg_submitting') : t('cardio.cardio_manual_ecg_submit')}
          </Button>
        </div>
      </form>
    </Card>
  );
}

export default ManualEcgForm;
