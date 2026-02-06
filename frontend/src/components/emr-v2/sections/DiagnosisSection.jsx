/**
 * DiagnosisSection - Диагноз с МКБ-10
 * 
 * Phase 4.3: Connected to external component (ICD10 autocomplete)
 * 
 * Note: ICD10 autocomplete is passed as prop, not imported
 * to keep section independent from specific implementation
 */

import React, { useMemo } from 'react';
import EMRSection from './EMRSection';
import EMRSmartFieldV2 from './EMRSmartFieldV2';
import EMRTextField from './EMRTextField';
import { useDoctorPhrases } from '../../../hooks/useDoctorPhrases';
import './DiagnosisSection.css';

/**
 * DiagnosisSection Component
 * 
 * @param {Object} props
 * @param {string} props.diagnosis - Main diagnosis text
 * @param {string} props.icd10Code - ICD-10 code
 * @param {Function} props.onDiagnosisChange - Diagnosis change handler
 * @param {Function} props.onIcd10Change - ICD-10 change handler
 * @param {boolean} props.disabled - Read-only mode
 * @param {boolean} props.defaultOpen - Start expanded
 * @param {React.ComponentType} props.ICD10Component - Optional ICD10 autocomplete component
 */
export function DiagnosisSection({
    diagnosis = '',
    icd10Code = '',
    onDiagnosisChange,
    onIcd10Change,
    disabled = false,
    defaultOpen = true,
    ICD10Component = null,
    // AI Props
    suggestions = [],
    aiLoading = false,
    onApplySuggestion,
    onDismissSuggestion,
    onRequestAI,
    doctorId,
    specialty = 'general',
    experimentalGhostMode = false,
    onTelemetry,
}) {
    // 🧠 Connect Doctor History (Personal Learning)
    const { suggestions: doctorSuggestions, loading: historyLoading } = useDoctorPhrases({
        doctorId,
        field: 'diagnosis',
        specialty,
        currentText: diagnosis,
        config: { minQueryLength: 2 }
    });

    // Merge suggestions: Doctor History first, then Generic AI
    const allSuggestions = useMemo(() => {
        const historyItems = doctorSuggestions.map(s => ({
            id: s.id,
            content: s.text,
            source: 'history', // Badge will show "История"
            confidence: 1.0
        }));

        return [...historyItems, ...suggestions];
    }, [doctorSuggestions, suggestions]);

    return (
        <EMRSection
            title="Диагноз"
            icon="🩺"
            required
            disabled={disabled}
            defaultOpen={defaultOpen}
            badge={icd10Code || undefined}
        >
            <div className="diagnosis-section">
                {/* Main diagnosis text */}
                <EMRSmartFieldV2
                    value={diagnosis}
                    onChange={onDiagnosisChange}
                    placeholder="Основной диагноз..."
                    multiline
                    rows={2}
                    disabled={disabled}
                    label="Диагноз"
                    required
                    id="emr-diagnosis"
                    fieldName="diagnosis"
                    suggestions={allSuggestions}
                    aiLoading={aiLoading || historyLoading}
                    onApplySuggestion={onApplySuggestion}
                    onDismissSuggestion={onDismissSuggestion}
                    onRequestAI={onRequestAI}
                    experimentalGhostMode={experimentalGhostMode}
                    onTelemetry={onTelemetry}
                />

                {/* ICD-10 code */}
                <div className="diagnosis-section__icd10">
                    {ICD10Component ? (
                        <ICD10Component
                            value={icd10Code}
                            onChange={onIcd10Change}
                            placeholder="Код МКБ-10"
                            disabled={disabled}
                        />
                    ) : (
                        <EMRTextField
                            value={icd10Code}
                            onChange={onIcd10Change}
                            placeholder="например, J06.9"
                            disabled={disabled}
                            label="Код МКБ-10"
                            id="emr-icd10"
                        />
                    )}
                </div>
            </div>
        </EMRSection>
    );
}

export default DiagnosisSection;
