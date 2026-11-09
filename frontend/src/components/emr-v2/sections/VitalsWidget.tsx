
import './VitalsWidget.css';
import { Input } from '../../ui/macos';
import { useTranslation } from '@/i18n/useTranslation';

/**
 * VitalsWidget (Кардиология)
 * 
 * Logic:
 * - BMI Calculation (only from positive, finite height/weight)
 * - BP Warning/Critical thresholds
 * - EMRVITAL-FE-001 (audit 3886, round 21): every field is parsed with
 *   Number() and validated against a physiologically possible range.
 *   Out-of-range / non-finite entries are flagged in place (class +
 *   aria-invalid + explicit hint) instead of being silently accepted;
 *   BMI is computed ONLY from positive finite measurements, so '0'/negative
 *   height can never render Infinity/NaN. Values are never rewritten —
 *   the clinician sees exactly what was entered plus why it is implausible.
 */
const VITALS_BOUNDS: Record<string, { min: number; max: number }> = {
    systolic: { min: 40, max: 300 },
    diastolic: { min: 20, max: 250 },
    pulse: { min: 20, max: 300 },
    spo2: { min: 1, max: 100 },
    height: { min: 20, max: 280 },
    weight: { min: 0.5, max: 500 },
};

const parseVital = (raw: unknown): number | null => {
    if (raw === null || raw === undefined) return null;
    const s = String(raw).trim();
    if (s === '') return null;
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
};

const VitalsWidget = ({ vitals: vitalsRaw = {}, onChange, onFieldTouch, disabled }: { vitals?: Record<string, unknown>; onChange?: (v: Record<string, any>) => void; onFieldTouch?: (field: string) => void; disabled?: boolean }) => {
  const vitals = vitalsRaw as Record<string, any>;
  const { t: rawT } = useTranslation(); const t = rawT;
    const handleChange = (field: string, value: string) => {
        onChange?.({ ...vitals, [field]: value });
        onFieldTouch?.(`vitals.${field}`);
    };

    // EMRVITAL-FE-001: parse through Number() (never parseInt-with-||0 for the
    // validity decision) and flag out-of-range values explicitly.
    const isFieldInvalid = (field: string): boolean => {
        const n = parseVital(vitals?.[field]);
        if (n === null) return false; // empty field is simply not filled yet
        const bounds = VITALS_BOUNDS[field];
        return !!bounds && (n < bounds.min || n > bounds.max);
    };

    // BP Warning (subtle, non-blocking) — computed from parsed numbers so
    // non-numeric garbage never fabricates a "normal" reading either.
    const systolic = parseVital(vitals?.systolic) ?? 0;
    const diastolic = parseVital(vitals?.diastolic) ?? 0;
    const isBPHigh = systolic > 140 || diastolic > 90;
    const isBPCritical = systolic > 180 || diastolic > 120;

    // BMI calculation — EMRVITAL-FE-001: only from positive finite values,
    // so '0' (truthy string!), negatives and non-numics can never produce
    // Infinity/NaN on the clinical form.
    const heightCm = parseVital(vitals?.height);
    const weightKg = parseVital(vitals?.weight);
    const bmiValue =
        heightCm !== null && weightKg !== null && heightCm > 0 && weightKg > 0
            ? weightKg / Math.pow(heightCm / 100, 2)
            : null;
    const bmi = bmiValue !== null && Number.isFinite(bmiValue) ? bmiValue.toFixed(1) : null;
    const fieldHint = (field: string) =>
        isFieldInvalid(field)
            ? t('misc.vw_invalid_range', { min: VITALS_BOUNDS[field].min, max: VITALS_BOUNDS[field].max })
            : null;


    return (
        <div className="emr-vitals">
            <div className="emr-vitals__row">
                <div className={`emr-vitals__field ${isBPCritical ? 'emr-vitals__field--critical' : isBPHigh ? 'emr-vitals__field--warning' : ''} ${isFieldInvalid('systolic') ? 'emr-vitals__field--invalid' : ''}`}>
                    <label>{t('misc.vw_ad_sist')}</label>
                    <Input
                        type="number"
                        aria-label="Systolic blood pressure"
                        error={isFieldInvalid('systolic')}
                        value={vitals?.systolic || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleChange('systolic', e.target.value)}
                        placeholder="120"
                        disabled={disabled}
                    />
                    {fieldHint('systolic') && <span className="emr-vitals__invalid-hint" role="alert">{fieldHint('systolic')}</span>}
                </div>
                <span className="emr-vitals__separator">/</span>
                <div className={`emr-vitals__field ${isBPCritical ? 'emr-vitals__field--critical' : isBPHigh ? 'emr-vitals__field--warning' : ''} ${isFieldInvalid('diastolic') ? 'emr-vitals__field--invalid' : ''}`}>
                    <label>{t('misc.vw_ad_diast')}</label>
                    <Input
                        type="number"
                        aria-label="Diastolic blood pressure"
                        error={isFieldInvalid('diastolic')}
                        value={vitals?.diastolic || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleChange('diastolic', e.target.value)}
                        placeholder="80"
                        disabled={disabled}
                    />
                    {fieldHint('diastolic') && <span className="emr-vitals__invalid-hint" role="alert">{fieldHint('diastolic')}</span>}
                </div>
                <div className={`emr-vitals__field ${isFieldInvalid('pulse') ? 'emr-vitals__field--invalid' : ''}`}>
                    <label>{t('misc.vw_puls')}</label>
                    <Input
                        type="number"
                        aria-label="Pulse"
                        error={isFieldInvalid('pulse')}
                        value={vitals?.pulse || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleChange('pulse', e.target.value)}
                        placeholder="72"
                        disabled={disabled}
                    />
                    {fieldHint('pulse') && <span className="emr-vitals__invalid-hint" role="alert">{fieldHint('pulse')}</span>}
                </div>
                <div className={`emr-vitals__field ${isFieldInvalid('spo2') ? 'emr-vitals__field--invalid' : ''}`}>
                    <label>SpO₂</label>
                    <Input
                        type="number"
                        aria-label="Blood oxygen saturation"
                        error={isFieldInvalid('spo2')}
                        value={vitals?.spo2 || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleChange('spo2', e.target.value)}
                        placeholder="98"
                        disabled={disabled}
                    />
                    <span className="emr-vitals__unit">%</span>
                    {fieldHint('spo2') && <span className="emr-vitals__invalid-hint" role="alert">{fieldHint('spo2')}</span>}
                </div>

                {/* BP Warning - subtle, non-blocking */}
                {isBPHigh && (
                    <div className={`emr-vitals__warning ${isBPCritical ? 'emr-vitals__warning--critical' : ''}`}>
                        {isBPCritical ? t('misc.vw_kriz') : t('misc.vw_ad')}
                    </div>
                )}
            </div>
            <div className="emr-vitals__row">
                <div className={`emr-vitals__field ${isFieldInvalid('height') ? 'emr-vitals__field--invalid' : ''}`}>
                    <label>Рост {vitals?.heightSource && <small>({vitals.heightSource})</small>}</label>
                    <Input
                        type="number"
                        aria-label="Height in centimeters"
                        error={isFieldInvalid('height')}
                        value={vitals?.height || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleChange('height', e.target.value)}
                        placeholder="170"
                        disabled={disabled}
                    />
                    <span className="emr-vitals__unit">см</span>
                    {fieldHint('height') && <span className="emr-vitals__invalid-hint" role="alert">{fieldHint('height')}</span>}
                </div>
                <div className={`emr-vitals__field ${isFieldInvalid('weight') ? 'emr-vitals__field--invalid' : ''}`}>
                    <label>Вес {vitals?.weightSource && <small>({vitals.weightSource})</small>}</label>
                    <Input
                        type="number"
                        aria-label="Weight in kilograms"
                        error={isFieldInvalid('weight')}
                        value={vitals?.weight || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleChange('weight', e.target.value)}
                        placeholder="70"
                        disabled={disabled}
                    />
                    <span className="emr-vitals__unit">кг</span>
                    {fieldHint('weight') && <span className="emr-vitals__invalid-hint" role="alert">{fieldHint('weight')}</span>}
                </div>
                {bmi && (
                    <div className="emr-vitals__bmi">
                        ИМТ: {bmi}
                    </div>
                )}
            </div>
        </div>
    );
};

export default VitalsWidget;


