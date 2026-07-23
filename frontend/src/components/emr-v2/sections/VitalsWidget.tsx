
import PropTypes from 'prop-types';
import './VitalsWidget.css';
import { Input } from '../../ui/macos';
import { useTranslation } from '../../../i18n/useTranslation';

/**
 * VitalsWidget (Кардиология)
 * 
 * Logic:
 * - BMI Calculation
 * - BP Warning/Critical thresholds
 */
const VitalsWidget = ({ vitals: vitalsRaw = {}, onChange, onFieldTouch, disabled }: { vitals?: Record<string, unknown>; onChange?: (v: Record<string, any>) => void; onFieldTouch?: (field: string) => void; disabled?: boolean }) => {
  const vitals = vitalsRaw as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
    const handleChange = (field, value) => {
        onChange?.({ ...vitals, [field]: value });
        onFieldTouch?.(`vitals.${field}`);
    };

    // BP Warning (subtle, non-blocking)
    const systolic = parseInt(vitals?.systolic) || 0;
    const diastolic = parseInt(vitals?.diastolic) || 0;
    const isBPHigh = systolic > 140 || diastolic > 90;
    const isBPCritical = systolic > 180 || diastolic > 120;

    // BMI calculation
    const bmi = vitals?.height && vitals?.weight
        ? (vitals.weight / Math.pow(vitals.height / 100, 2)).toFixed(1)
        : null;

    return (
        <div className="emr-vitals">
            <div className="emr-vitals__row">
                <div className={`emr-vitals__field ${isBPCritical ? 'emr-vitals__field--critical' : isBPHigh ? 'emr-vitals__field--warning' : ''}`}>
                    <label>{t('misc.vw_ad_sist')}</label>
                    <Input
                        type="number"
                        aria-label="Systolic blood pressure"
                        value={vitals?.systolic || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleChange('systolic', e.target.value)}
                        placeholder="120"
                        disabled={disabled}
                    />
                </div>
                <span className="emr-vitals__separator">/</span>
                <div className={`emr-vitals__field ${isBPCritical ? 'emr-vitals__field--critical' : isBPHigh ? 'emr-vitals__field--warning' : ''}`}>
                    <label>{t('misc.vw_ad_diast')}</label>
                    <Input
                        type="number"
                        aria-label="Diastolic blood pressure"
                        value={vitals?.diastolic || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleChange('diastolic', e.target.value)}
                        placeholder="80"
                        disabled={disabled}
                    />
                </div>
                <div className="emr-vitals__field">
                    <label>{t('misc.vw_puls')}</label>
                    <Input
                        type="number"
                        aria-label="Pulse"
                        value={vitals?.pulse || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleChange('pulse', e.target.value)}
                        placeholder="72"
                        disabled={disabled}
                    />
                </div>
                <div className="emr-vitals__field">
                    <label>SpO₂</label>
                    <Input
                        type="number"
                        aria-label="Blood oxygen saturation"
                        value={vitals?.spo2 || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleChange('spo2', e.target.value)}
                        placeholder="98"
                        disabled={disabled}
                    />
                    <span className="emr-vitals__unit">%</span>
                </div>

                {/* BP Warning - subtle, non-blocking */}
                {isBPHigh && (
                    <div className={`emr-vitals__warning ${isBPCritical ? 'emr-vitals__warning--critical' : ''}`}>
                        {isBPCritical ? t('misc.vw_kriz') : t('misc.vw_ad')}
                    </div>
                )}
            </div>
            <div className="emr-vitals__row">
                <div className="emr-vitals__field">
                    <label>Рост {vitals?.heightSource && <small>({vitals.heightSource})</small>}</label>
                    <Input
                        type="number"
                        aria-label="Height in centimeters"
                        value={vitals?.height || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleChange('height', e.target.value)}
                        placeholder="170"
                        disabled={disabled}
                    />
                    <span className="emr-vitals__unit">см</span>
                </div>
                <div className="emr-vitals__field">
                    <label>Вес {vitals?.weightSource && <small>({vitals.weightSource})</small>}</label>
                    <Input
                        type="number"
                        aria-label="Weight in kilograms"
                        value={vitals?.weight || ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleChange('weight', e.target.value)}
                        placeholder="70"
                        disabled={disabled}
                    />
                    <span className="emr-vitals__unit">кг</span>
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

const vitalsShape = PropTypes.shape({
    systolic: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    diastolic: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    pulse: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    spo2: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    height: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    weight: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    heightSource: PropTypes.string,
    weightSource: PropTypes.string,
});

VitalsWidget.propTypes = {
    vitals: vitalsShape,
    onChange: PropTypes.func,
    onFieldTouch: PropTypes.func,
    disabled: PropTypes.bool,
};
