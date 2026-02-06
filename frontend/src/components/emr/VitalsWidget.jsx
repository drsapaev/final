import React from 'react';
import './VitalsWidget.css';

/**
 * VitalsWidget (Кардиология)
 * 
 * Logic:
 * - BMI Calculation
 * - BP Warning/Critical thresholds
 */
const VitalsWidget = ({ vitals = {}, onChange, onFieldTouch, disabled }) => {
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
                    <label>АД сист.</label>
                    <input
                        type="number"
                        value={vitals?.systolic || ''}
                        onChange={(e) => handleChange('systolic', e.target.value)}
                        placeholder="120"
                        disabled={disabled}
                    />
                </div>
                <span className="emr-vitals__separator">/</span>
                <div className={`emr-vitals__field ${isBPCritical ? 'emr-vitals__field--critical' : isBPHigh ? 'emr-vitals__field--warning' : ''}`}>
                    <label>АД диаст.</label>
                    <input
                        type="number"
                        value={vitals?.diastolic || ''}
                        onChange={(e) => handleChange('diastolic', e.target.value)}
                        placeholder="80"
                        disabled={disabled}
                    />
                </div>
                <div className="emr-vitals__field">
                    <label>Пульс</label>
                    <input
                        type="number"
                        value={vitals?.pulse || ''}
                        onChange={(e) => handleChange('pulse', e.target.value)}
                        placeholder="72"
                        disabled={disabled}
                    />
                </div>
                <div className="emr-vitals__field">
                    <label>SpO₂</label>
                    <input
                        type="number"
                        value={vitals?.spo2 || ''}
                        onChange={(e) => handleChange('spo2', e.target.value)}
                        placeholder="98"
                        disabled={disabled}
                    />
                    <span className="emr-vitals__unit">%</span>
                </div>

                {/* BP Warning - subtle, non-blocking */}
                {isBPHigh && (
                    <div className={`emr-vitals__warning ${isBPCritical ? 'emr-vitals__warning--critical' : ''}`}>
                        {isBPCritical ? '⚠️ Криз' : '↑ АД'}
                    </div>
                )}
            </div>
            <div className="emr-vitals__row">
                <div className="emr-vitals__field">
                    <label>Рост {vitals?.heightSource && <small>({vitals.heightSource})</small>}</label>
                    <input
                        type="number"
                        value={vitals?.height || ''}
                        onChange={(e) => handleChange('height', e.target.value)}
                        placeholder="170"
                        disabled={disabled}
                    />
                    <span className="emr-vitals__unit">см</span>
                </div>
                <div className="emr-vitals__field">
                    <label>Вес {vitals?.weightSource && <small>({vitals.weightSource})</small>}</label>
                    <input
                        type="number"
                        value={vitals?.weight || ''}
                        onChange={(e) => handleChange('weight', e.target.value)}
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
